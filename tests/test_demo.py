from unittest.mock import Mock

from acreditai.agent.nodes import InterpretacaoOutput
from acreditai.ui.demo import Demo


def test_demo_aprovacao_auditoria_e_isolamento(monkeypatch):
    interpretador = Mock()
    interpretador.return_value.with_structured_output.return_value.invoke.side_effect = [
        InterpretacaoOutput(intencao="incluir_creditos", empresa_nome="Logistica Sul", creditos_solicitados=1500),
        InterpretacaoOutput(intencao="consultar", empresa_nome="Horizonte"),
        InterpretacaoOutput(intencao="consultar", empresa_nome="Logística Sul"),
    ]
    monkeypatch.setattr("acreditai.agent.nodes.ChatOpenAI", interpretador)
    demo = Demo()
    outra_sessao = Demo()

    try:
        pendente = demo.post("/agent/chat", {"mensagem": "Adicione 1500 créditos", "exigir_aprovacao": True})
        assert pendente["status"] == "aguardando_aprovacao"
        assert pendente["creditos"]["saldo_final"] == 2400
        assert len(demo.get("/agent/aprovacoes")["pendentes"]) == 1
        assert outra_sessao.get("/agent/historico") == {"historico": []}

        execucao = pendente["execucao_id"]
        concluida = demo.post(f"/agent/aprovacoes/{execucao}/decidir", {"decisao": "aprovar"})
        assert concluida["creditos"]["saldo_final"] == 3900
        assert demo.get("/agent/aprovacoes") == {"pendentes": []}
        assert demo.get(f"/agent/auditoria/{execucao}")["resposta"]["auditoria"][-1]["etapa"] == "Incluir Créditos"

        ambigua = demo.post("/agent/chat", {"mensagem": "Consulte a Horizonte"})
        assert ambigua["status"] == "aguardando_desambiguacao"
        execucao = ambigua["execucao_id"]
        consulta = demo.post(
            f"/agent/aprovacoes/{execucao}/decidir", {"decisao": "aprovar", "empresa_id": 2}
        )
        assert consulta["status"] == "concluido"
        assert consulta["creditos"]["saldo_anterior"] == 5200

        isolada = outra_sessao.post("/agent/chat", {"mensagem": "Consulte a Logística Sul"})
        assert isolada["creditos"]["saldo_anterior"] == 2400
        assert interpretador.call_count == 3
    finally:
        demo.close()
        outra_sessao.close()
