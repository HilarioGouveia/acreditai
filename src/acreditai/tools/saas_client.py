from typing import Any
import httpx
from acreditai.config import settings


class SaasAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class SaasClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.saas_api_url).rstrip("/")
        self.token = token if token is not None else settings.saas_api_token
        self.timeout = timeout or settings.http_timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _handle_response(self, response: httpx.Response) -> Any:
        if response.status_code == 404:
            raise SaasAPIError(404, "Recurso não encontrado no sistema SaaS.")
        if response.status_code == 422:
            raise SaasAPIError(422, "Parâmetros inválidos rejeitados pela API SaaS.")
        if response.status_code >= 500:
            raise SaasAPIError(response.status_code, "Erro interno no servidor SaaS.")
        response.raise_for_status()
        return response.json()

    def buscar_empresas(self, nome: str) -> list[dict[str, Any]]:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.get("/empresas", params={"nome": nome}, headers=self._headers())
                data = self._handle_response(resp)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get("items") or data.get("empresas") or [data]
                return []
        except SaasAPIError:
            raise
        except httpx.TimeoutException as exc:
            raise SaasAPIError(504, "Timeout ao consultar empresas no SaaS.") from exc
        except httpx.HTTPError as exc:
            raise SaasAPIError(503, f"Falha de comunicação com a API SaaS: {exc}") from exc

    def consultar_assinatura(self, empresa_id: int) -> dict[str, Any]:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.get(f"/assinaturas/{empresa_id}", headers=self._headers())
                return self._handle_response(resp)
        except SaasAPIError:
            raise
        except httpx.TimeoutException as exc:
            raise SaasAPIError(504, "Timeout ao consultar assinatura no SaaS.") from exc
        except httpx.HTTPError as exc:
            raise SaasAPIError(503, f"Falha de comunicação ao consultar assinatura: {exc}") from exc

    def incluir_creditos(self, assinatura_id: int, quantidade: int) -> dict[str, Any]:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.post(
                    f"/assinaturas/{assinatura_id}/creditos",
                    json={"quantidade": quantidade},
                    headers=self._headers(),
                )
                return self._handle_response(resp)
        except SaasAPIError:
            raise
        except httpx.TimeoutException as exc:
            raise SaasAPIError(504, "Timeout ao incluir créditos no SaaS.") from exc
        except httpx.HTTPError as exc:
            raise SaasAPIError(503, f"Falha de comunicação ao incluir créditos: {exc}") from exc
