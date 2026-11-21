from typing import Any
from langchain_core.tools import tool
from acreditai.schemas.tools import ConsultarAssinaturaInput
from acreditai.tools.saas_client import SaasAPIError, SaasClient


@tool(args_schema=ConsultarAssinaturaInput)
def consultar_assinatura(empresa_id: int) -> dict[str, Any]:
    """Consulta o plano, status e saldo de créditos da assinatura de uma empresa."""
    client = SaasClient()
    try:
        dados = client.consultar_assinatura(empresa_id=empresa_id)
        return {"ok": True, "assinatura": dados}
    except SaasAPIError as err:
        return {"ok": False, "status_code": err.status_code, "erro": err.message, "assinatura": None}
