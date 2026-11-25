import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from langchain_core.messages import HumanMessage

from acreditai.agent.graph import agent_graph
from acreditai.agent.nodes import (
    consultar_assinatura_node,
    incluir_creditos_node,
    montar_resposta,
    validar_regras_node,
)
from acreditai.config import settings
from acreditai.schemas.api import ChatRequest, DecisaoAprovacaoRequest


def _novo_execucao_id() -> str:
    ano = datetime.now(timezone.utc).year
    sufixo = uuid.uuid4().hex[:6].upper()
    return f"EXEC-{ano}-{sufixo}"


def executar_agente(payload: ChatRequest, repo, graph=agent_graph):
    execucao_id = _novo_execucao_id()
    initial_state = {
        "messages": [HumanMessage(content=payload.mensagem)],
        "execucao_id": execucao_id,
        "solicitante": payload.solicitante,
        "exigir_aprovacao": payload.exigir_aprovacao,
        "iteracoes": 0,
        "intencao": None,
        "empresa_nome": None,
        "creditos_solicitados": None,
        "empresas_candidatas": [],
        "empresa_id": payload.empresa_id_selecionada,
        "empresa_confirmada": None,
        "assinatura_id": None,
        "plano": None,
        "status_assinatura": None,
        "saldo_atual": None,
        "saldo_final": None,
        "status_operacao": "em_andamento",
        "motivo": None,
        "trilha_auditoria": [],
        "resposta_final": None,
    }

    final_state = graph.invoke(
        initial_state,
        config={"recursion_limit": settings.max_iteracoes_grafo},
    )
    resposta = final_state["resposta_final"]
    repo.salvar_execucao(
        execucao_id=execucao_id,
        solicitante=payload.solicitante,
        prompt_original=payload.mensagem,
        state=final_state,
        resposta=resposta,
    )
    return resposta


def decidir_aprovacao(
    execucao_id: str,
    payload: DecisaoAprovacaoRequest,
    aprovador: str,
    repo,
    consultar=consultar_assinatura_node,
    incluir=incluir_creditos_node,
):
    registro = repo.obter_execucao(execucao_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")

    status_atual = registro["status"]
    if status_atual not in ("aguardando_aprovacao", "aguardando_desambiguacao"):
        raise HTTPException(status_code=400, detail=f"Execução já finalizada com status '{status_atual}'.")

    state = registro["state"]
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if payload.decisao == "rejeitar":
        state["status_operacao"] = "rejeitado"
        state["motivo"] = f"Operação rejeitada por {aprovador}."
        state["trilha_auditoria"].append(
            {
                "etapa": "Decisão Humana (HITL)",
                "status": "bloqueado",
                "detalhe": state["motivo"],
                "timestamp": agora,
            }
        )
        resposta = montar_resposta(state)["resposta_final"]
        repo.salvar_execucao(
            execucao_id=execucao_id,
            solicitante=registro["solicitante"],
            prompt_original=registro["prompt_original"],
            state=state,
            resposta=resposta,
            aprovador=aprovador,
        )
        return resposta

    # Fluxo de aprovação ou resolução de ambiguidade
    if status_atual == "aguardando_desambiguacao":
        if not payload.empresa_id:
            raise HTTPException(status_code=422, detail="Informe o empresa_id escolhido para desambiguar.")
        candidata = next(
            (
                c
                for c in state.get("empresas_candidatas", [])
                if (c.get("empresa_id") or c.get("id")) == payload.empresa_id
            ),
            None,
        )
        if candidata is None:
            raise HTTPException(status_code=422, detail="Selecione uma das empresas candidatas.")
        state["empresa_id"] = payload.empresa_id
        state["empresa_confirmada"] = (
            (candidata.get("nome") or candidata.get("nome_fantasia")) if candidata else state.get("empresa_nome")
        )
        state["status_operacao"] = "em_andamento"
        state["trilha_auditoria"].append(
            {
                "etapa": "Desambiguação Humana",
                "status": "sucesso",
                "detalhe": f"Empresa ID {payload.empresa_id} confirmada por {aprovador}.",
                "timestamp": agora,
            }
        )
        state.update(consultar(state))
        if state["status_operacao"] not in ("erro", "concluido"):
            state.update(validar_regras_node(state))
            if state["status_operacao"] == "em_andamento":
                state.update(incluir(state))
    else:
        state["status_operacao"] = "aprovado"
        state["trilha_auditoria"].append(
            {
                "etapa": "Aprovação Humana (HITL)",
                "status": "sucesso",
                "detalhe": f"Aprovado por {aprovador}.",
                "timestamp": agora,
            }
        )
        state.update(incluir(state))

    resposta = montar_resposta(state)["resposta_final"]
    repo.salvar_execucao(
        execucao_id=execucao_id,
        solicitante=registro["solicitante"],
        prompt_original=registro["prompt_original"],
        state=state,
        resposta=resposta,
        aprovador=aprovador,
    )
    return resposta
