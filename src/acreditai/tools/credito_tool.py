from typing import Any
from langchain_core.tools import tool
from acreditai.schemas.tools import IncluirCreditosInput
from acreditai.tools.saas_client import SaasAPIError, SaasClient


@tool(args_schema=IncluirCreditosInput)
def incluir_creditos(assinatura_id: int, quantidade: int) -> dict[str, Any]:
    """Inclui créditos extras de API (entre 1 e 3000) em uma assinatura ativa."""
    client = SaasClient()
    try:
        resultado = client.incluir_creditos(assinatura_id=assinatura_id, quantidade=quantidade)
        return {"ok": True, "resultado": resultado}
    except SaasAPIError as err:
        return {"ok": False, "status_code": err.status_code, "erro": err.message, "resultado": None}
