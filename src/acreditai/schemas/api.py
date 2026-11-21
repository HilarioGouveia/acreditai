from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    mensagem: str = Field(..., min_length=3, max_length=1000)
    solicitante: str = Field(default="Analista CS", min_length=2, max_length=80)
    exigir_aprovacao: bool = Field(
        default=False,
        description="Quando True, suspende antes da inclusão de créditos aguardando aprovação humana.",
    )
    empresa_id_selecionada: Optional[int] = Field(
        default=None,
        gt=0,
        description="Opcional: ID explícito escolhido após uma desambiguação.",
    )


class DecisaoAprovacaoRequest(BaseModel):
    decisao: Literal["aprovar", "rejeitar"]
    aprovador: str = Field(default="Supervisor CS", min_length=2, max_length=80)
    empresa_id: Optional[int] = Field(
        default=None,
        gt=0,
        description="Obrigatório quando a pendência for de desambiguação de empresa.",
    )


class EtapaAuditoriaOut(BaseModel):
    etapa: str
    status: str
    detalhe: str
    timestamp: str


class AgentResponse(BaseModel):
    execucao_id: str
    status: str
    motivo: Optional[str] = None
    empresa: Optional[dict[str, Any]] = None
    empresas_candidatas: list[dict[str, Any]] = Field(default_factory=list)
    assinatura: Optional[dict[str, Any]] = None
    creditos: Optional[dict[str, Any]] = None
    auditoria: list[EtapaAuditoriaOut] = Field(default_factory=list)
