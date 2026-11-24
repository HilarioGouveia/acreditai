from typing import Any, TypeVar
import httpx
from pydantic import TypeAdapter, ValidationError

from acreditai.config import settings
from acreditai.schemas.saas import AssinaturaSaas, EmpresaSaas


T = TypeVar("T")

empresas_schema = TypeAdapter(list[EmpresaSaas])
assinaturas_schema = TypeAdapter(list[AssinaturaSaas])
assinatura_schema = TypeAdapter(AssinaturaSaas)


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

    def _handle_response(self, response: httpx.Response, schema: TypeAdapter[T]) -> T:
        if response.status_code in (401, 403):
            raise SaasAPIError(response.status_code, "Acesso negado pela API SaaS.")
        if response.status_code == 404:
            raise SaasAPIError(404, "Recurso não encontrado no sistema SaaS.")
        if response.status_code == 422:
            raise SaasAPIError(422, "Parâmetros inválidos rejeitados pela API SaaS.")
        if response.status_code >= 500:
            raise SaasAPIError(response.status_code, "Erro interno no servidor SaaS.")
        response.raise_for_status()
        try:
            return schema.validate_json(response.content)
        except ValidationError as exc:
            raise SaasAPIError(502, "A API SaaS retornou uma resposta inválida.") from exc

    def buscar_empresas(self, nome: str) -> list[dict[str, Any]]:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.get("/empresas", params={"nome": nome}, headers=self._headers())
                empresas = self._handle_response(resp, empresas_schema)
                return [empresa.model_dump() for empresa in empresas]
        except SaasAPIError:
            raise
        except httpx.TimeoutException as exc:
            raise SaasAPIError(504, "Timeout ao consultar empresas no SaaS.") from exc
        except httpx.HTTPError as exc:
            raise SaasAPIError(503, f"Falha de comunicação com a API SaaS: {exc}") from exc

    def consultar_assinatura(self, empresa_id: int) -> list[dict[str, Any]]:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.get(f"/assinaturas/{empresa_id}", headers=self._headers())
                assinaturas = self._handle_response(resp, assinaturas_schema)
                if any(assinatura.empresa_id != empresa_id for assinatura in assinaturas):
                    raise SaasAPIError(502, "A API SaaS retornou uma assinatura de outra empresa.")
                return [assinatura.model_dump() for assinatura in assinaturas]
        except SaasAPIError:
            raise
        except httpx.TimeoutException as exc:
            raise SaasAPIError(504, "Timeout ao consultar assinatura no SaaS.") from exc
        except httpx.HTTPError as exc:
            raise SaasAPIError(503, f"Falha de comunicação ao consultar assinatura: {exc}") from exc

    def incluir_creditos(self, assinatura_id: int, quantidade: int, motivo: str) -> dict[str, Any]:
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                resp = client.post(
                    f"/assinaturas/{assinatura_id}/creditos",
                    json={"quantidade": quantidade, "motivo": motivo},
                    headers=self._headers(),
                )
                assinatura = self._handle_response(resp, assinatura_schema)
                if assinatura.id != assinatura_id:
                    raise SaasAPIError(502, "A API SaaS retornou uma assinatura diferente da solicitada.")
                return assinatura.model_dump()
        except SaasAPIError:
            raise
        except httpx.TimeoutException as exc:
            raise SaasAPIError(504, "Timeout ao incluir créditos no SaaS.") from exc
        except httpx.HTTPError as exc:
            raise SaasAPIError(503, f"Falha de comunicação ao incluir créditos: {exc}") from exc
