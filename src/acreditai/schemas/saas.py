from typing import Annotated

from pydantic import BaseModel, Field


IdSaas = Annotated[int, Field(strict=True, gt=0)]


class EmpresaSaas(BaseModel):
    id: IdSaas
    nome_fantasia: str = Field(min_length=1)


class AssinaturaSaas(BaseModel):
    id: IdSaas
    empresa_id: IdSaas
    plano: str = Field(min_length=1)
    status: str = Field(min_length=1)
    saldo_creditos_api: int = Field(strict=True)
