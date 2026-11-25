import sqlite3
from functools import partial
from unicodedata import normalize

from fastapi import HTTPException

from acreditai.agent.graph import build_graph
from acreditai.agent.nodes import buscar_empresa_node, consultar_assinatura_node, incluir_creditos_node
from acreditai.agent.service import decidir_aprovacao, executar_agente
from acreditai.schemas.api import ChatRequest, DecisaoAprovacaoRequest
from acreditai.storage.repository import ExecucaoRepository


class RepositorioDemo(ExecucaoRepository):
    def __init__(self):
        self.conexao = sqlite3.connect(":memory:", check_same_thread=False)
        self.conexao.row_factory = sqlite3.Row
        self._init_db()

    def _conn(self):
        return self.conexao


def normalizar_nome(nome):
    return normalize("NFKD", nome.casefold().strip()).encode("ascii", "ignore").decode("ascii")


class Demo:
    def __init__(self):
        self.empresas = {
            1: "Logística Sul",
            2: "Horizonte Tecnologia",
            3: "Horizonte Serviços",
        }
        self.assinaturas = {
            1: {"id": 101, "plano": "Pro", "status": "ATIVA", "saldo_creditos_api": 2400},
            2: {"id": 102, "plano": "Enterprise", "status": "ATIVA", "saldo_creditos_api": 5200},
            3: {"id": 103, "plano": "Pro", "status": "INATIVA", "saldo_creditos_api": 300},
        }
        self.repo = RepositorioDemo()
        self.consultar = partial(consultar_assinatura_node, consultar=self._consultar)
        self.incluir = partial(incluir_creditos_node, incluir=self._incluir)
        self.graph = build_graph(
            buscar=partial(buscar_empresa_node, buscar=self._buscar),
            consultar=self.consultar,
            incluir=self.incluir,
        )

    def _buscar(self, parametros):
        nome = normalizar_nome(parametros["nome"])
        empresas = [
            {"id": empresa_id, "nome": fantasia}
            for empresa_id, fantasia in self.empresas.items()
            if nome and nome in normalizar_nome(fantasia)
        ]
        return {"ok": True, "empresas": empresas}

    def _consultar(self, parametros):
        assinatura = self.assinaturas.get(parametros["empresa_id"])
        return {"ok": True, "assinatura": [assinatura.copy()] if assinatura else []}

    def _incluir(self, parametros):
        for assinatura in self.assinaturas.values():
            if assinatura["id"] == parametros["assinatura_id"] and assinatura["status"] == "ATIVA":
                assinatura["saldo_creditos_api"] += parametros["quantidade"]
                return {"ok": True, "resultado": assinatura.copy()}
        return {"ok": False, "erro": "Assinatura ativa não encontrada na demonstração."}

    def get(self, caminho):
        if caminho == "/agent/aprovacoes":
            return {"pendentes": self.repo.listar_pendentes()}
        if caminho == "/agent/historico":
            return {"historico": self.repo.listar_historico()}
        if caminho.startswith("/agent/auditoria/"):
            registro = self.repo.obter_execucao(caminho.rsplit("/", 1)[-1])
            if registro:
                return registro
        raise HTTPException(status_code=404, detail="Registro de demonstração não encontrado.")

    def post(self, caminho, payload):
        if caminho == "/agent/chat":
            return executar_agente(ChatRequest(**payload), self.repo, graph=self.graph)
        prefixo, execucao_id, acao = caminho.rsplit("/", 2)
        if prefixo == "/agent/aprovacoes" and acao == "decidir":
            return decidir_aprovacao(
                execucao_id,
                DecisaoAprovacaoRequest(**payload),
                "Aprovador da demonstração",
                self.repo,
                consultar=self.consultar,
                incluir=self.incluir,
            )
        raise HTTPException(status_code=404, detail="Operação de demonstração não encontrada.")

    def close(self):
        self.repo.conexao.close()
