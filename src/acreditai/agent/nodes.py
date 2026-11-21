from datetime import datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from acreditai.agent.prompts import SYSTEM_PROMPT_INTERPRETER
from acreditai.agent.state import AgentState, EtapaAuditoria
from acreditai.config import settings
from acreditai.tools.assinatura_tool import consultar_assinatura
from acreditai.tools.credito_tool import incluir_creditos
from acreditai.tools.empresa_tool import buscar_empresa


class InterpretacaoOutput(BaseModel):
    intencao: Literal["consultar", "incluir_creditos", "fora_escopo"]
    empresa_nome: Optional[str] = Field(default=None)
    creditos_solicitados: Optional[int] = Field(default=None)
    motivo_recusa: Optional[str] = Field(default=None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _auditar(state: AgentState, etapa: str, status: str, detalhe: str) -> list[EtapaAuditoria]:
    trilha = list(state.get("trilha_auditoria", []))
    trilha.append({"etapa": etapa, "status": status, "detalhe": detalhe, "timestamp": _now_iso()})
    return trilha


def _checar_limite_iteracoes(state: AgentState) -> bool:
    return state.get("iteracoes", 0) >= settings.max_iteracoes_grafo


def interpretar_solicitacao(state: AgentState) -> dict:
    if _checar_limite_iteracoes(state):
        return {"status_operacao": "erro", "motivo": "Limite máximo de iterações atingido."}

    iteracoes = state.get("iteracoes", 0) + 1
    ultima_msg = state["messages"][-1].content if state.get("messages") else ""

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    ).with_structured_output(InterpretacaoOutput)

    resultado: InterpretacaoOutput = llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT_INTERPRETER),
            HumanMessage(content=str(ultima_msg)),
        ]
    )

    if resultado.intencao == "fora_escopo":
        motivo = resultado.motivo_recusa or (
            "Solicitação fora do escopo permitido. O agente realiza apenas consultas de assinatura e inclusão de créditos."
        )
        return {
            "iteracoes": iteracoes,
            "intencao": "fora_escopo",
            "status_operacao": "negado",
            "motivo": motivo,
            "trilha_auditoria": _auditar(state, "Interpretar Solicitação", "bloqueado", motivo),
        }

    if not resultado.empresa_nome and not state.get("empresa_id"):
        motivo = "Não foi possível identificar o nome fantasia da empresa na solicitação."
        return {
            "iteracoes": iteracoes,
            "intencao": resultado.intencao,
            "status_operacao": "erro",
            "motivo": motivo,
            "trilha_auditoria": _auditar(state, "Interpretar Solicitação", "erro", motivo),
        }

    detalhe = f"Intenção: {resultado.intencao} | Empresa: {resultado.empresa_nome}"
    if resultado.creditos_solicitados is not None:
        detalhe += f" | Créditos: {resultado.creditos_solicitados}"

    return {
        "iteracoes": iteracoes,
        "intencao": resultado.intencao,
        "empresa_nome": resultado.empresa_nome,
        "creditos_solicitados": resultado.creditos_solicitados,
        "trilha_auditoria": _auditar(state, "Interpretar Solicitação", "sucesso", detalhe),
    }


def buscar_empresa_node(state: AgentState) -> dict:
    if _checar_limite_iteracoes(state):
        return {"status_operacao": "erro", "motivo": "Limite máximo de iterações atingido."}

    iteracoes = state.get("iteracoes", 0) + 1

    # Caso o analista já tenha escolhido explicitamente o empresa_id na desambiguação
    if state.get("empresa_id"):
        return {
            "iteracoes": iteracoes,
            "trilha_auditoria": _auditar(
                state,
                "Buscar Empresa",
                "sucesso",
                f"Empresa pré-selecionada confirmada (ID: {state['empresa_id']}).",
            ),
        }

    nome = state.get("empresa_nome") or ""
    resp = buscar_empresa.invoke({"nome": nome})

    if not resp.get("ok"):
        motivo = resp.get("erro", "Erro ao consultar empresa.")
        return {
            "iteracoes": iteracoes,
            "status_operacao": "erro",
            "motivo": motivo,
            "trilha_auditoria": _auditar(state, "Buscar Empresa", "erro", motivo),
        }

    empresas = resp.get("empresas", [])
    if len(empresas) == 0:
        motivo = f"Nenhuma empresa encontrada com o nome '{nome}'."
        return {
            "iteracoes": iteracoes,
            "status_operacao": "erro",
            "motivo": motivo,
            "trilha_auditoria": _auditar(state, "Buscar Empresa", "erro", motivo),
        }

    if len(empresas) > 1:
        motivo = f"Foram encontradas {len(empresas)} empresas para '{nome}'. Selecione qual deseja utilizar."
        return {
            "iteracoes": iteracoes,
            "empresas_candidatas": empresas,
            "status_operacao": "aguardando_desambiguacao",
            "motivo": motivo,
            "trilha_auditoria": _auditar(state, "Buscar Empresa", "alerta", motivo),
        }

    empresa = empresas[0]
    emp_id = empresa.get("empresa_id") or empresa.get("id")
    emp_nome = empresa.get("nome") or empresa.get("nome_fantasia") or nome

    return {
        "iteracoes": iteracoes,
        "empresa_id": emp_id,
        "empresa_confirmada": emp_nome,
        "empresas_candidatas": empresas,
        "trilha_auditoria": _auditar(
            state, "Buscar Empresa", "sucesso", f"Empresa única localizada: {emp_nome} (ID: {emp_id})."
        ),
    }


def consultar_assinatura_node(state: AgentState) -> dict:
    if _checar_limite_iteracoes(state):
        return {"status_operacao": "erro", "motivo": "Limite máximo de iterações atingido."}

    iteracoes = state.get("iteracoes", 0) + 1
    emp_id = state["empresa_id"]
    resp = consultar_assinatura.invoke({"empresa_id": emp_id})

    if not resp.get("ok") or not resp.get("assinatura"):
        motivo = resp.get("erro", "Assinatura não encontrada para a empresa.")
        return {
            "iteracoes": iteracoes,
            "status_operacao": "erro",
            "motivo": motivo,
            "trilha_auditoria": _auditar(state, "Consultar Assinatura", "erro", motivo),
        }

    ass = resp["assinatura"]
    ass_id = ass.get("assinatura_id") or ass.get("id")
    plano = ass.get("plano", "Padrão")
    status = str(ass.get("status", "")).upper()
    saldo = int(ass.get("saldo_creditos", ass.get("saldo", 0)))

    novo_status_op = "concluido" if state.get("intencao") == "consultar" else state["status_operacao"]

    return {
        "iteracoes": iteracoes,
        "assinatura_id": ass_id,
        "plano": plano,
        "status_assinatura": status,
        "saldo_atual": saldo,
        "status_operacao": novo_status_op,
        "trilha_auditoria": _auditar(
            state,
            "Consultar Assinatura",
            "sucesso",
            f"Assinatura ID {ass_id} | Plano: {plano} | Status: {status} | Saldo: {saldo}",
        ),
    }


def validar_regras_node(state: AgentState) -> dict:
    if _checar_limite_iteracoes(state):
        return {"status_operacao": "erro", "motivo": "Limite máximo de iterações atingido."}

    iteracoes = state.get("iteracoes", 0) + 1
    status_ass = (state.get("status_assinatura") or "").upper()
    qtd = state.get("creditos_solicitados")

    if status_ass != "ATIVA":
        motivo = f"Operação negada: a assinatura está com status '{status_ass}'. Apenas assinaturas ATIVAS podem receber créditos."
        return {
            "iteracoes": iteracoes,
            "status_operacao": "negado",
            "motivo": motivo,
            "trilha_auditoria": _auditar(state, "Validar Regras", "bloqueado", motivo),
        }

    if qtd is None or qtd <= 0:
        motivo = "Operação negada: a quantidade de créditos solicitada deve ser maior que zero."
        return {
            "iteracoes": iteracoes,
            "status_operacao": "negado",
            "motivo": motivo,
            "trilha_auditoria": _auditar(state, "Validar Regras", "bloqueado", motivo),
        }

    if qtd > settings.max_creditos_operacao:
        motivo = (
            f"Operação negada: a quantidade solicitada ({qtd}) excede o limite operacional máximo de "
            f"{settings.max_creditos_operacao} créditos por operação."
        )
        return {
            "iteracoes": iteracoes,
            "status_operacao": "negado",
            "motivo": motivo,
            "trilha_auditoria": _auditar(state, "Validar Regras", "bloqueado", motivo),
        }

    if state.get("exigir_aprovacao") and state.get("status_operacao") != "aprovado":
        motivo = "Validações concluídas com sucesso. Aguardando aprovação humana (HITL) para efetivar créditos."
        return {
            "iteracoes": iteracoes,
            "status_operacao": "aguardando_aprovacao",
            "motivo": motivo,
            "trilha_auditoria": _auditar(state, "Validar Regras (HITL)", "pendente", motivo),
        }

    return {
        "iteracoes": iteracoes,
        "trilha_auditoria": _auditar(
            state,
            "Validar Regras",
            "sucesso",
            f"Assinatura ATIVA e quantidade ({qtd} <= {settings.max_creditos_operacao}) aprovadas.",
        ),
    }


def incluir_creditos_node(state: AgentState) -> dict:
    if _checar_limite_iteracoes(state):
        return {"status_operacao": "erro", "motivo": "Limite máximo de iterações atingido."}

    iteracoes = state.get("iteracoes", 0) + 1
    ass_id = state["assinatura_id"]
    qtd = state["creditos_solicitados"]

    resp = incluir_creditos.invoke({"assinatura_id": ass_id, "quantidade": qtd})

    if not resp.get("ok"):
        motivo = resp.get("erro", "Falha ao incluir créditos na API SaaS.")
        return {
            "iteracoes": iteracoes,
            "status_operacao": "erro",
            "motivo": motivo,
            "trilha_auditoria": _auditar(state, "Incluir Créditos", "erro", motivo),
        }

    resultado = resp.get("resultado") or {}
    saldo_anterior = state.get("saldo_atual") or 0
    saldo_final = resultado.get("saldo_creditos") or resultado.get("saldo_final") or (saldo_anterior + qtd)

    return {
        "iteracoes": iteracoes,
        "saldo_final": int(saldo_final),
        "status_operacao": "concluido",
        "motivo": None,
        "trilha_auditoria": _auditar(
            state,
            "Incluir Créditos",
            "sucesso",
            f"Adicionados +{qtd} créditos na assinatura {ass_id}. Novo saldo: {saldo_final}.",
        ),
    }


def montar_resposta(state: AgentState) -> dict:
    empresa_payload = None
    if state.get("empresa_id"):
        empresa_payload = {
            "empresa_id": state["empresa_id"],
            "nome": state.get("empresa_confirmada") or state.get("empresa_nome"),
        }

    assinatura_payload = None
    if state.get("assinatura_id"):
        assinatura_payload = {
            "assinatura_id": state["assinatura_id"],
            "plano": state.get("plano"),
            "status": state.get("status_assinatura"),
        }

    creditos_payload = None
    if state.get("saldo_atual") is not None:
        creditos_payload = {
            "saldo_anterior": state["saldo_atual"],
            "creditos_adicionados": state.get("creditos_solicitados") if state.get("status_operacao") == "concluido" and state.get("intencao") == "incluir_creditos" else 0,
            "creditos_solicitados": state.get("creditos_solicitados") or 0,
            "saldo_final": state.get("saldo_final") if state.get("saldo_final") is not None else state["saldo_atual"],
        }

    resposta = {
        "execucao_id": state["execucao_id"],
        "status": state["status_operacao"],
        "motivo": state.get("motivo"),
        "empresa": empresa_payload,
        "empresas_candidatas": state.get("empresas_candidatas", []),
        "assinatura": assinatura_payload,
        "creditos": creditos_payload,
        "auditoria": state.get("trilha_auditoria", []),
    }
    return {"resposta_final": resposta}
