from typing import Any
from langchain_core.tools import tool
from acreditai.schemas.tools import BuscarEmpresaInput
from acreditai.tools.saas_client import SaasAPIError, SaasClient


@tool(args_schema=BuscarEmpresaInput)
def buscar_empresa(nome: str) -> dict[str, Any]:
    """Busca empresas cadastradas no SaaS pelo nome fantasia."""
    client = SaasClient()
    try:
        empresas = client.buscar_empresas(nome=nome.strip())
        return {"ok": True, "empresas": empresas}
    except SaasAPIError as err:
        return {"ok": False, "status_code": err.status_code, "erro": err.message, "empresas": []}
