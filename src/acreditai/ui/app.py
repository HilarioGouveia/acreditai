import os
from base64 import b64encode
from html import escape
from pathlib import Path

import httpx
import streamlit as st

API_URL = os.getenv("ACREDITAI_API_URL", "http://localhost:8000")
MODO_DEMO = os.getenv("ACREDITAI_MODE", "").strip().lower() == "demo"
ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"

MARCA_JPEG = b64encode((ASSETS_DIR / "acreditai-brand.jpg").read_bytes()).decode("ascii")
# Mesmo recorte da barra lateral, centralizado num quadrado para o favicon.
MARCA_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -5.5 36 36" width="36" height="36">
    <clipPath id="marca">
        <polygon transform="scale(36 25)" points="0,.99 .36,.04 .40,0 .52,0 .55,.03 .67,.30 .74,.20 .70,.16
                         1,.10 .91,.55 .85,.47 .77,.60 .92,.99 .69,.99 .59,.80
                         .48,.99 .35,.99 .50,.58 .43,.37 .21,.99"/>
    </clipPath>
    <image clip-path="url(#marca)" x="-13.5" y="-49.75" width="168.84" height="126.07"
           href="data:image/jpeg;base64,{MARCA_JPEG}"/>
</svg>"""
MARCA_URL = "data:image/svg+xml;base64," + b64encode(MARCA_SVG.encode("utf-8")).decode("ascii")

st.set_page_config(page_title="ACreditAi Copilot", page_icon=MARCA_URL, layout="wide")

st.html(ASSETS_DIR / "estilos.css")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "ultimo_resultado" not in st.session_state:
    st.session_state.ultimo_resultado = None

if MODO_DEMO:
    from fastapi import HTTPException
    from acreditai.config import settings
    from acreditai.ui.demo import Demo

    if "acreditai_demo" not in st.session_state:
        st.session_state.acreditai_demo = Demo()


def reiniciar_demo():
    st.session_state.acreditai_demo.close()
    del st.session_state.acreditai_demo
    st.session_state.messages = []
    st.session_state.ultimo_resultado = None


def _get(path: str):
    if MODO_DEMO:
        try:
            return st.session_state.acreditai_demo.get(path)
        except HTTPException as exc:
            st.error(exc.detail)
            return None
    try:
        r = httpx.get(f"{API_URL}{path}", timeout=10.0)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.error(f"Erro ao conectar à API do AcreditAi ({API_URL}): {exc}")
        return None


def _post(path: str, payload: dict, token: str = ""):
    if MODO_DEMO:
        if path == "/agent/chat" and not settings.openai_api_key:
            st.error("Configure OPENAI_API_KEY para usar o chat da demonstração.")
            return None
        try:
            resultado = st.session_state.acreditai_demo.post(path, payload)
        except HTTPException as exc:
            st.error(exc.detail)
            return None
        except Exception:
            st.error("Não foi possível executar a solicitação de demonstração.")
            return None
        ultimo = st.session_state.ultimo_resultado
        if ultimo and ultimo.get("execucao_id") == resultado.get("execucao_id"):
            st.session_state.ultimo_resultado = resultado
        return resultado
    try:
        r = httpx.post(f"{API_URL}{path}", json=payload, headers={"Authorization": f"Bearer {token}"} if token else {}, timeout=20.0)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.error(f"Erro na requisição: {exc}")
        return None


pendentes_data = _get("/agent/aprovacoes") or {"pendentes": []}
qtd_pendentes = len(pendentes_data.get("pendentes", []))


def render_assistente():
    col_chat, col_ctx = st.columns([2, 1])

    with col_chat:
        st.subheader("Chat Operacional")
        if MODO_DEMO:
            st.caption(
                "Experimente consultar o saldo da Logística Sul, pedir 1500 créditos "
                "para a Logística Sul ou consultar o saldo da Horizonte."
            )
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        prompt = st.chat_input("Ex.: Consulte a Logística Sul e adicione 1500 créditos")
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            res = _post(
                "/agent/chat",
                {
                    "mensagem": prompt,
                    "solicitante": solicitante,
                    "exigir_aprovacao": exigir_aprovacao,
                },
            )
            if res:
                st.session_state.ultimo_resultado = res
                status = res.get("status")
                exec_id = res.get("execucao_id")
                if status == "concluido":
                    texto = f"**Execução `{exec_id}` concluída com sucesso.**"
                elif status == "aguardando_aprovacao":
                    texto = f"⏳ **Execução `{exec_id}` enviada para aprovação humana.** Acesse a aba **Aprovações**."
                elif status == "aguardando_desambiguacao":
                    texto = f"⚠️ **Múltiplas empresas encontradas (`{exec_id}`).** Selecione a empresa correta na aba **Aprovações**."
                else:
                    texto = f"🚫 **Operação não executada (`{status}`):** {res.get('motivo')}"

                st.session_state.messages.append({"role": "assistant", "content": texto})
                st.rerun()

    with col_ctx:
        st.subheader("Painel Contextual")
        render_contexto(st.session_state.ultimo_resultado)


def render_contexto(resultado):
    if not resultado:
        st.info("Envie uma solicitação no chat para visualizar os dados da conta e o impacto previsto.")
        return

    render_desfecho(resultado)
    empresa = resultado.get("empresa") or {}
    assinatura = resultado.get("assinatura") or {}
    creditos = resultado.get("creditos") or {}
    status = resultado.get("status")
    solicitados = creditos.get("creditos_solicitados") or 0
    incluidos = status == "concluido" and (creditos.get("creditos_adicionados") or 0) > 0
    if resultado.get("execucao_id"):
        st.caption(f"Execução {resultado['execucao_id']}")

    if empresa or assinatura:
        campos = [
            ("Empresa", empresa.get("nome")),
            ("ID da empresa", empresa.get("empresa_id")),
            ("Plano", assinatura.get("plano")),
            ("Status da assinatura", assinatura.get("status")),
            ("ID da assinatura", assinatura.get("assinatura_id")),
        ]
        linhas = "".join(
            f"<dt>{rotulo}</dt><dd>{escape(str(valor))}</dd>"
            for rotulo, valor in campos
            if valor is not None and valor != ""
        )
        st.html(f'<div class="ac-card ac-context"><h3>Empresa e assinatura</h3><dl>{linhas}</dl></div>')

    saldo_anterior = creditos.get("saldo_anterior")
    if solicitados > 0 or incluidos:
        with st.container(border=True):
            st.markdown("**Impacto no saldo**")
            if saldo_anterior is not None:
                st.metric("Saldo anterior", saldo_anterior)
            st.metric("Créditos solicitados", solicitados)
            saldo_final = creditos.get("saldo_final")
            if incluidos and saldo_final is not None:
                st.metric("Saldo final", saldo_final)
            elif status == "aguardando_aprovacao" and saldo_anterior is not None:
                st.metric("Saldo projetado", saldo_anterior + solicitados)
    elif saldo_anterior is not None:
        st.metric("Saldo atual", saldo_anterior)

    with st.expander("Etapas da execução", icon=":material/timeline:"):
        render_eventos(resultado.get("auditoria"))


def render_desfecho(resultado):
    status = resultado.get("status")
    creditos = resultado.get("creditos") or {}
    desfechos = {
        "concluido": ("blue", "Consulta respondida"),
        "aguardando_aprovacao": ("orange", "Aguardando aprovação"),
        "aguardando_desambiguacao": ("orange", "Aguardando seleção da empresa"),
        "negado": ("red", "Operação bloqueada"),
        "rejeitado": ("red", "Operação rejeitada"),
        "erro": ("red", "Erro na operação"),
    }
    cor, rotulo = desfechos.get(status, ("blue", "Status indisponível"))
    if status == "concluido" and (creditos.get("creditos_adicionados") or 0) > 0:
        cor, rotulo = "green", "Créditos incluídos"
    st.html(f'<span class="badge badge-{cor}">{rotulo}</span>')


def render_eventos(eventos):
    if not eventos:
        st.caption("Nenhuma etapa registrada para esta execução.")
        return

    icones = {
        "Interpretar Solicitação": "chat",
        "Buscar Empresa": "apartment",
        "Consultar Assinatura": "description",
        "Validar Regras": "policy",
        "Validar Regras (HITL)": "policy",
        "Incluir Créditos": "database",
        "Decisão Humana (HITL)": "fact_check",
        "Desambiguação Humana": "fact_check",
        "Aprovação Humana (HITL)": "fact_check",
    }
    estados = {
        "sucesso": ("green", "Concluída"),
        "pendente": ("orange", "Aguardando aprovação"),
        "alerta": ("orange", "Atenção"),
        "bloqueado": ("red", "Bloqueada"),
        "erro": ("red", "Falhou"),
        "rejeitado": ("red", "Rejeitada"),
    }
    for evento in eventos:
        with st.container(border=True):
            etapa = evento.get("etapa") or "Etapa"
            status = evento.get("status") or "Status indisponível"
            cor, rotulo = estados.get(status, ("blue", status))
            icone = icones.get(etapa, "timeline")
            st.markdown(f":material/{icone}: **{escape(etapa)}**")
            st.html(f'<span class="badge badge-{cor}">{escape(rotulo)}</span>')
            if evento.get("detalhe"):
                st.write(evento["detalhe"])
            if evento.get("timestamp"):
                st.caption(evento["timestamp"])

def render_estado_vazio(icone, mensagem):
    with st.container(key="estado-vazio"):
        st.markdown(f":material/{icone}: {mensagem}")


def render_aprovacoes():
    token_aprovador = "" if MODO_DEMO else st.text_input("Token do aprovador", type="password")
    st.subheader(f"Centro de Aprovações e Desambiguação ({qtd_pendentes})")
    pendentes = pendentes_data.get("pendentes", [])
    if not pendentes:
        render_estado_vazio("fact_check", "Nenhuma aprovação pendente.")
    for item in pendentes:
        exec_id = item["execucao_id"]
        resp = item["resposta"]
        with st.container(border=True):
            st.markdown(f"### `{exec_id}` — Solicitado por **{item['solicitante']}**")
            render_desfecho(item)
            st.caption(f"Prompt: '{item['prompt_original']}'")

            if item["status"] == "aguardando_desambiguacao":
                st.warning(resp.get("motivo"))
                candidatas = resp.get("empresas_candidatas", [])
                opcoes = {
                    f"{c.get('nome') or c.get('nome_fantasia')} (ID: {c.get('empresa_id') or c.get('id')})": (
                        c.get("empresa_id") or c.get("id")
                    )
                    for c in candidatas
                }
                escolha = st.radio("Selecione a empresa correta:", list(opcoes.keys()), key=f"rad_{exec_id}")
                c1, c2 = st.columns(2)
                if c1.button("Confirmar Seleção", key=f"conf_{exec_id}", type="primary"):
                    if _post(
                        f"/agent/aprovacoes/{exec_id}/decidir",
                        {"decisao": "aprovar", "empresa_id": opcoes[escolha]},
                        token_aprovador,
                    ):
                        st.rerun()
                if c2.button("Rejeitar", key=f"rej_{exec_id}"):
                    if _post(f"/agent/aprovacoes/{exec_id}/decidir", {"decisao": "rejeitar"}, token_aprovador):
                        st.rerun()
            else:
                emp = resp.get("empresa") or {}
                ass = resp.get("assinatura") or {}
                cred = resp.get("creditos") or {}
                col1, col2, col3 = st.columns(3)
                col1.metric("Empresa", emp.get("nome", "—"), f"ID {emp.get('empresa_id')}")
                col2.metric("Saldo Atual", cred.get("saldo_anterior", 0))
                col3.metric(
                    "Saldo Após Aprovação",
                    (cred.get("saldo_anterior", 0) + cred.get("creditos_solicitados", 0)),
                    f"+{cred.get('creditos_solicitados', 0)}",
                )
                st.caption(f"Plano: {ass.get('plano')} | Assinatura ID: {ass.get('assinatura_id')} | Status: {ass.get('status')}")
                c1, c2 = st.columns(2)
                if c1.button("Aprovar Inclusão", key=f"apr_{exec_id}", type="primary"):
                    if _post(f"/agent/aprovacoes/{exec_id}/decidir", {"decisao": "aprovar"}, token_aprovador):
                        st.rerun()
                if c2.button("Rejeitar", key=f"rej_{exec_id}"):
                    if _post(f"/agent/aprovacoes/{exec_id}/decidir", {"decisao": "rejeitar"}, token_aprovador):
                        st.rerun()


def render_historico():
    st.subheader("Histórico de Operações")
    hist = (_get("/agent/historico") or {}).get("historico", [])
    if hist:
        st.dataframe(hist, use_container_width=True)
    else:
        render_estado_vazio("history", "Nenhuma operação registrada.")


def render_auditoria():
    st.subheader("Auditoria Completa por Execução")
    hist = (_get("/agent/historico") or {}).get("historico", [])
    ids = [h["execucao_id"] for h in hist]
    if not ids:
        render_estado_vazio("policy", "Nenhuma execução disponível para auditoria.")
    else:
        selecionado = st.selectbox("Selecione a Execução", ids)
        detalhe = _get(f"/agent/auditoria/{selecionado}")
        if detalhe:
            st.markdown(f"**Prompt Recebido:** `{detalhe['prompt_original']}`")
            st.markdown(f"**Solicitante:** {detalhe['solicitante']} | **Aprovador:** {detalhe.get('aprovador') or 'Automático'}")
            render_desfecho(detalhe["resposta"])
            render_eventos(detalhe["resposta"].get("auditoria"))


paginas = [
    st.Page(render_assistente, title="Assistente", icon=":material/chat:", default=True),
    st.Page(
        render_aprovacoes,
        title=f"Aprovações ({qtd_pendentes})",
        icon=":material/fact_check:",
        url_path="aprovacoes",
    ),
    st.Page(render_historico, title="Histórico", icon=":material/history:", url_path="historico"),
    st.Page(render_auditoria, title="Auditoria", icon=":material/policy:", url_path="auditoria"),
]
pagina = st.navigation(paginas, position="hidden")

with st.sidebar:
    st.html(
        f"""
        <h1 class="ac-sidebar-brand">
            <img class="ac-sidebar-symbol" src="{MARCA_URL}" alt="">
            ACreditAi Copilot
        </h1>
        """
    )
    if MODO_DEMO:
        st.caption("Modo demonstração · Dados fictícios")
        st.button("Reiniciar demonstração", on_click=reiniciar_demo)
    for destino in paginas:
        if destino == pagina:
            with st.container(key="sidebar-nav-active"):
                st.page_link(destino)
        else:
            st.page_link(destino)
    st.divider()
    solicitante = st.text_input("Analista CS", value="João Silva")
    exigir_aprovacao = st.toggle("Exigir Aprovação Humana (HITL)", value=True)

pagina.run()
