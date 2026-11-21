import os
import httpx
import streamlit as st

API_URL = os.getenv("ACREDITAI_API_URL", "http://localhost:8000")

st.set_page_config(page_title="AcreditAi Copilot", page_icon="⚡", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; color: #e6edf3; }
    .card-box {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "ultimo_resultado" not in st.session_state:
    st.session_state.ultimo_resultado = None


def _get(path: str):
    try:
        r = httpx.get(f"{API_URL}{path}", timeout=10.0)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.error(f"Erro ao conectar à API do AcreditAi ({API_URL}): {exc}")
        return None


def _post(path: str, payload: dict):
    try:
        r = httpx.post(f"{API_URL}{path}", json=payload, timeout=20.0)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.error(f"Erro na requisição: {exc}")
        return None


pendentes_data = _get("/agent/aprovacoes") or {"pendentes": []}
qtd_pendentes = len(pendentes_data.get("pendentes", []))

with st.sidebar:
    st.title("⚡ AcreditAi Copilot")
    solicitante = st.text_input("Analista CS", value="João Silva")
    exigir_aprovacao = st.toggle("Exigir Aprovação Humana (HITL)", value=True)
    st.divider()
    pagina = st.radio(
        "Navegação",
        [
            "💬 Assistente",
            f"✅ Aprovações ({qtd_pendentes})",
            "📋 Histórico",
            "📊 Auditoria",
        ],
    )

if pagina == "💬 Assistente":
    col_chat, col_ctx = st.columns([2, 1])

    with col_chat:
        st.subheader("Chat Operacional")
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
        res = st.session_state.ultimo_resultado
        if not res:
            st.info("Envie uma solicitação no chat para visualizar os dados da conta e o impacto previsto.")
        else:
            emp = res.get("empresa") or {}
            ass = res.get("assinatura") or {}
            cred = res.get("creditos") or {}
            st.markdown(
                f"""
                <div class="card-box">
                    <strong>Execução:</strong> {res.get('execucao_id')}<br>
                    <strong>Status:</strong> <code>{res.get('status')}</code><br><hr>
                    <strong>Empresa:</strong> {emp.get('nome', '—')} (ID: {emp.get('empresa_id', '—')})<br>
                    <strong>Plano:</strong> {ass.get('plano', '—')}<br>
                    <strong>Assinatura:</strong> {ass.get('status', '—')} (ID: {ass.get('assinatura_id', '—')})<br><hr>
                    <strong>Saldo Anterior:</strong> {cred.get('saldo_anterior', '—')}<br>
                    <strong>Solicitado:</strong> +{cred.get('creditos_solicitados', 0)}<br>
                    <strong>Saldo Final:</strong> {cred.get('saldo_final', '—')}
                </div>
                """,
                unsafe_allow_html=True,
            )

elif pagina.startswith("✅ Aprovações"):
    st.subheader(f"Centro de Aprovações e Desambiguação ({qtd_pendentes})")
    pendentes = pendentes_data.get("pendentes", [])
    if not pendentes:
        st.success("Nenhuma pendência aguardando revisão humana.")
    for item in pendentes:
        exec_id = item["execucao_id"]
        resp = item["resposta"]
        with st.container(border=True):
            st.markdown(f"### `{exec_id}` — Solicitado por **{item['solicitante']}**")
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
                    _post(
                        f"/agent/aprovacoes/{exec_id}/decidir",
                        {"decisao": "aprovar", "aprovador": solicitante, "empresa_id": opcoes[escolha]},
                    )
                    st.rerun()
                if c2.button("Rejeitar", key=f"rej_{exec_id}"):
                    _post(f"/agent/aprovacoes/{exec_id}/decidir", {"decisao": "rejeitar", "aprovador": solicitante})
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
                    _post(f"/agent/aprovacoes/{exec_id}/decidir", {"decisao": "aprovar", "aprovador": solicitante})
                    st.rerun()
                if c2.button("Rejeitar", key=f"rej_{exec_id}"):
                    _post(f"/agent/aprovacoes/{exec_id}/decidir", {"decisao": "rejeitar", "aprovador": solicitante})
                    st.rerun()

elif pagina == "📋 Histórico":
    st.subheader("Histórico de Operações")
    hist = (_get("/agent/historico") or {}).get("historico", [])
    if hist:
        st.dataframe(hist, use_container_width=True)
    else:
        st.info("Nenhuma execução registrada ainda.")

elif pagina == "📊 Auditoria":
    st.subheader("Auditoria Completa por Execução")
    hist = (_get("/agent/historico") or {}).get("historico", [])
    ids = [h["execucao_id"] for h in hist]
    if not ids:
        st.info("Nenhuma execução disponível para auditoria.")
    else:
        selecionado = st.selectbox("Selecione a Execução", ids)
        detalhe = _get(f"/agent/auditoria/{selecionado}")
        if detalhe:
            st.markdown(f"**Prompt Recebido:** `{detalhe['prompt_original']}`")
            st.markdown(f"**Solicitante:** {detalhe['solicitante']} | **Aprovador:** {detalhe.get('aprovador') or 'Automático'}")
            for etapa in detalhe["resposta"].get("auditoria", []):
                with st.container(border=True):
                    st.markdown(f"**{etapa['etapa']}** — `{etapa['status'].upper()}`")
                    st.write(etapa["detalhe"])
                    st.caption(etapa["timestamp"])
