from datetime import datetime, timezone
import uuid
from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage

from acreditai.agent.graph import agent_graph
from acreditai.agent.nodes import (
    consultar_assinatura_node,
    incluir_creditos_node,
    montar_resposta,
    validar_regras_node,
)
from acreditai.config import settings
from acreditai.schemas.api import AgentResponse, ChatRequest, DecisaoAprovacaoRequest
from acreditai.storage.repository import ExecucaoRepository

app = FastAPI(
    title="AcreditAi - Copiloto Operacional de Créditos B2B",
    version="0.1.0",
    description="API do Agente de IA orquestrado com LangChain e LangGraph para gestão de créditos de API.",
)

repo = ExecucaoRepository()


def _novo_execucao_id() -> str:
    ano = datetime.now(timezone.utc).year
    sufixo = uuid.uuid4().hex[:6].upper()
    return f"EXEC-{ano}-{sufixo}"


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "acreditai", "saas_url": settings.saas_api_url}


@app.post("/agent/chat", response_model=AgentResponse)
def executar_agente(payload: ChatRequest):
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

    final_state = agent_graph.invoke(
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


@app.get("/agent/aprovacoes")
def listar_aprovacoes():
    return {"pendentes": repo.listar_pendentes()}


@app.post("/agent/aprovacoes/{execucao_id}/decidir", response_model=AgentResponse)
def decidir_aprovacao(execucao_id: str, payload: DecisaoAprovacaoRequest):
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
        state["motivo"] = f"Operação rejeitada por {payload.aprovador}."
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
            aprovador=payload.aprovador,
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
        state["empresa_id"] = payload.empresa_id
        state["empresa_confirmada"] = (
            (candidata.get("nome") or candidata.get("nome_fantasia")) if candidata else state.get("empresa_nome")
        )
        state["status_operacao"] = "em_andamento"
        state["trilha_auditoria"].append(
            {
                "etapa": "Desambiguação Humana",
                "status": "sucesso",
                "detalhe": f"Empresa ID {payload.empresa_id} confirmada por {payload.aprovador}.",
                "timestamp": agora,
            }
        )
        state.update(consultar_assinatura_node(state))
        if state["status_operacao"] not in ("erro", "concluido"):
            state["exigir_aprovacao"] = False
            state.update(validar_regras_node(state))
            if state["status_operacao"] not in ("negado", "erro"):
                state.update(incluir_creditos_node(state))
    else:
        state["status_operacao"] = "aprovado"
        state["trilha_auditoria"].append(
            {
                "etapa": "Aprovação Humana (HITL)",
                "status": "sucesso",
                "detalhe": f"Aprovado por {payload.aprovador}.",
                "timestamp": agora,
            }
        )
        state.update(incluir_creditos_node(state))

    resposta = montar_resposta(state)["resposta_final"]
    repo.salvar_execucao(
        execucao_id=execucao_id,
        solicitante=registro["solicitante"],
        prompt_original=registro["prompt_original"],
        state=state,
        resposta=resposta,
        aprovador=payload.aprovador,
    )
    return resposta


@app.get("/agent/historico")
def listar_historico():
    return {"historico": repo.listar_historico()}


@app.get("/agent/auditoria/{execucao_id}")
def detalhar_auditoria(execucao_id: str):
    registro = repo.obter_execucao(execucao_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    return registro
