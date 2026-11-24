from pydantic import BaseModel, Field


class BuscarEmpresaInput(BaseModel):
    nome: str = Field(
        ...,
        min_length=2,
        max_length=120,
        description="Nome fantasia ou termo de busca da empresa cliente.",
    )


class ConsultarAssinaturaInput(BaseModel):
    empresa_id: int = Field(
        ...,
        gt=0,
        description="Identificador numérico único da empresa.",
    )


class IncluirCreditosInput(BaseModel):
    motivo: str = Field(..., min_length=3)
    assinatura_id: int = Field(
        ...,
        gt=0,
        description="Identificador numérico único da assinatura ativa.",
    )
    quantidade: int = Field(
        ...,
        gt=0,
        le=3000,
        description="Quantidade de créditos extras a incluir (mínimo 1, máximo 3000).",
    )
