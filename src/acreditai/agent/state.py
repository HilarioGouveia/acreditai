from typing import Annotated, Any, Literal, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class EtapaAuditoria(TypedDict):
    etapa: str
    status: Literal["sucesso", "alerta", "bloqueado", "erro", "pendente"]
    detalhe: str
    timestamp: str


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

    execucao_id: str
    solicitante: str
    exigir_aprovacao: bool
    iteracoes: int

    intencao: Optional[Literal["consultar", "incluir_creditos", "fora_escopo"]]
    empresa_nome: Optional[str]
    creditos_solicitados: Optional[int]

    empresas_candidatas: list[dict[str, Any]]
    empresa_id: Optional[int]
    empresa_confirmada: Optional[str]
    assinatura_id: Optional[int]
    plano: Optional[str]
    status_assinatura: Optional[str]
    saldo_atual: Optional[int]
    saldo_final: Optional[int]

    status_operacao: Literal[
        "em_andamento",
        "aguardando_desambiguacao",
        "aguardando_aprovacao",
        "aprovado",
        "rejeitado",
        "concluido",
        "negado",
        "erro",
    ]
    motivo: Optional[str]
    trilha_auditoria: list[EtapaAuditoria]
    resposta_final: Optional[dict[str, Any]]
