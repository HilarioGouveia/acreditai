# AcreditAi — Copiloto Operacional de Créditos B2B

Agente de IA orquestrado com **LangChain** e **LangGraph**, exposto via **FastAPI** e interface operacional em **Streamlit**, com suporte a **Human-in-the-Loop (HITL)** e trilha de auditoria.

## Como executar com `uv`

1. Instale as dependências e crie o ambiente virtual:
```bash
uv sync
```

2. Configure o arquivo `.env`:
```bash
cp .env.example .env
```

3. Inicie a API do Agente (FastAPI):
```bash
uv run uvicorn acreditai.api.main:app --reload --port 8000
```

4. Em outro terminal, inicie a interface Copiloto (Streamlit):
```bash
uv run streamlit run src/acreditai/ui/app.py
```

5. Execute os testes automatizados:
```bash
uv run pytest -v
```
