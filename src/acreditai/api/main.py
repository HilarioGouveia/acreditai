from secrets import compare_digest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from acreditai.agent.service import decidir_aprovacao as decidir
from acreditai.agent.service import executar_agente as executar
from acreditai.config import settings
from acreditai.schemas.api import AgentResponse, ChatRequest, DecisaoAprovacaoRequest
from acreditai.storage.repository import ExecucaoRepository

app = FastAPI(
    title="AcreditAi - Copiloto Operacional de Créditos B2B",
    version="0.1.0",
    description="API do Agente de IA orquestrado com LangChain e LangGraph para gestão de créditos de API.",
)

repo = ExecucaoRepository()


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "acreditai", "saas_url": settings.saas_api_url}


@app.post("/agent/chat", response_model=AgentResponse)
def executar_agente(payload: ChatRequest):
    return executar(payload, repo)


@app.get("/agent/aprovacoes")
def listar_aprovacoes():
    return {"pendentes": repo.listar_pendentes()}


bearer_aprovador = HTTPBearer(auto_error=False)


def identificar_aprovador(
    credencial: HTTPAuthorizationCredentials | None = Depends(bearer_aprovador),
) -> str:
    if credencial:
        for nome, token in settings.acreditai_aprovadores.items():
            if token and compare_digest(token.encode(), credencial.credentials.encode()):
                return nome
    raise HTTPException(
        status_code=401,
        detail="Credencial de aprovador inválida.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.post("/agent/aprovacoes/{execucao_id}/decidir", response_model=AgentResponse)
def decidir_aprovacao(
    execucao_id: str,
    payload: DecisaoAprovacaoRequest,
    aprovador: str = Depends(identificar_aprovador),
):
    return decidir(execucao_id, payload, aprovador, repo)


@app.get("/agent/historico")
def listar_historico():
    return {"historico": repo.listar_historico()}


@app.get("/agent/auditoria/{execucao_id}")
def detalhar_auditoria(execucao_id: str):
    registro = repo.obter_execucao(execucao_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    return registro
