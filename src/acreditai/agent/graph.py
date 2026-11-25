from langgraph.graph import END, START, StateGraph
from acreditai.agent.nodes import (
    buscar_empresa_node,
    consultar_assinatura_node,
    incluir_creditos_node,
    interpretar_solicitacao,
    montar_resposta,
    validar_regras_node,
)
from acreditai.agent.state import AgentState


def _rotear_pos_interpretacao(state: AgentState) -> str:
    if state.get("status_operacao") in ("negado", "erro"):
        return "montar_resposta"
    return "buscar_empresa"


def _rotear_pos_busca(state: AgentState) -> str:
    if state.get("status_operacao") in ("erro", "aguardando_desambiguacao"):
        return "montar_resposta"
    return "consultar_assinatura"


def _rotear_pos_consulta(state: AgentState) -> str:
    if state.get("status_operacao") in ("erro", "concluido"):
        return "montar_resposta"
    return "validar_regras"


def _rotear_pos_validacao(state: AgentState) -> str:
    if state.get("status_operacao") in ("negado", "erro", "aguardando_aprovacao"):
        return "montar_resposta"
    return "incluir_creditos"


def build_graph(
    *,
    buscar=buscar_empresa_node,
    consultar=consultar_assinatura_node,
    incluir=incluir_creditos_node,
):
    workflow = StateGraph(AgentState)

    workflow.add_node("interpretar", interpretar_solicitacao)
    workflow.add_node("buscar_empresa", buscar)
    workflow.add_node("consultar_assinatura", consultar)
    workflow.add_node("validar_regras", validar_regras_node)
    workflow.add_node("incluir_creditos", incluir)
    workflow.add_node("montar_resposta", montar_resposta)

    workflow.add_edge(START, "interpretar")
    workflow.add_conditional_edges("interpretar", _rotear_pos_interpretacao)
    workflow.add_conditional_edges("buscar_empresa", _rotear_pos_busca)
    workflow.add_conditional_edges("consultar_assinatura", _rotear_pos_consulta)
    workflow.add_conditional_edges("validar_regras", _rotear_pos_validacao)
    workflow.add_edge("incluir_creditos", "montar_resposta")
    workflow.add_edge("montar_resposta", END)

    return workflow.compile()


agent_graph = build_graph()
