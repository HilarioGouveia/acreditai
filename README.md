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

## Integração local com a API SaaS

Configure o mesmo `SAAS_API_TOKEN` no Compose da API SaaS e no `.env` do agente.
Use `SAAS_API_URL=http://127.0.0.1:8002`. Para rotas administrativas no SaaS,
configure um `SAAS_ADMIN_TOKEN` distinto. O endpoint `/health` é público.

## Credenciais de aprovação

No `.env` do agente, configure um token secreto distinto por pessoa.
Use um objeto JSON em `ACREDITAI_APROVADORES`, por exemplo
`ACREDITAI_APROVADORES='{"Supervisor CS":"<token-secreto>"}'`.
Reinicie a API do agente após editar o arquivo.

No Streamlit, o supervisor informa seu token na área de Aprovações.
Para chamar `POST /agent/aprovacoes/{execucao_id}/decidir` diretamente, envie
`Authorization: Bearer <token-secreto>`. O nome na auditoria vem da credencial.
Use HTTPS se expuser os serviços fora do ambiente local.

## Demonstração em um único deploy

O modo demo executa o LangGraph no Streamlit e usa OpenAI ou Groq para interpretar
as solicitações. Empresas, assinaturas, saldos e registros de execução são
fictícios e isolados por sessão. O visitante pode decidir as aprovações da sua
sessão e usar **Reiniciar demonstração** para restaurar os dados iniciais.

No Streamlit Community Cloud, selecione a branch publicada e use
`src/acreditai/ui/app.py` como arquivo principal. Configure os Secrets:

```toml
ACREDITAI_MODE = "demo"
OPENAI_API_KEY = "sua-chave"
```

Para usar Groq no lugar da OpenAI, configure estes valores nos Secrets do deploy
ou no `.env` local. O modelo padrão do Groq é `openai/gpt-oss-20b`.

```toml
ACREDITAI_LLM_PROVIDER = "groq"
GROQ_API_KEY = "sua-chave-groq"
```

O valor opcional `GROQ_MODEL` permite selecionar outro modelo com suporte a
chamadas de ferramentas. O provedor padrão é `openai`.

Para testar localmente no PowerShell, configure a chave no `.env` ou no ambiente:

```powershell
$env:ACREDITAI_MODE = 'demo'
uv run streamlit run src/acreditai/ui/app.py
```

Experimente **Consulte o saldo da Logística Sul**, **Adicione 1500 créditos para a
Logística Sul** ou **Consulte o saldo da Horizonte**. Cada mensagem do chat usa
a chave do provedor configurado. O FastAPI e a API SaaS são necessários no modo integrado.

## Evidências dos três cenários

A API do agente foi exercitada com FastAPI TestClient e interpretação do LLM
simulada. As chamadas do cliente SaaS foram reais, com PostgreSQL 17 via Docker.
No cenário nominal, uma consulta antes e outra após o POST confirmaram o
incremento persistido de 1.500 créditos. Os JSONs abaixo foram capturados na
execução de verificação.

### 1. Fluxo nominal

`POST /agent/chat`

```json
{
  "mensagem": "Adicione 1500 créditos para Logística Sul",
  "exigir_aprovacao": false
}
```

Resposta HTTP 200

```json
{
  "execucao_id": "EXEC-2026-E2D978",
  "status": "concluido",
  "motivo": null,
  "empresa": {
    "empresa_id": 1,
    "nome": "Logística Sul"
  },
  "empresas_candidatas": [
    {
      "id": 1,
      "nome_fantasia": "Logística Sul",
      "cnpj": "11.222.333/0001-44",
      "dominio_corporativo": "logisticasul.com.br"
    }
  ],
  "assinatura": {
    "assinatura_id": 10,
    "plano": "STARTER",
    "status": "ATIVA"
  },
  "creditos": {
    "saldo_anterior": 1200,
    "creditos_adicionados": 1500,
    "creditos_solicitados": 1500,
    "saldo_final": 2700
  },
  "auditoria": [
    {
      "etapa": "Interpretar Solicitação",
      "status": "sucesso",
      "detalhe": "Intenção: incluir_creditos | Empresa: Logística Sul | Créditos: 1500",
      "timestamp": "2026-11-24 14:15:31 UTC"
    },
    {
      "etapa": "Buscar Empresa",
      "status": "sucesso",
      "detalhe": "Empresa única localizada: Logística Sul (ID: 1).",
      "timestamp": "2026-11-24 14:15:34 UTC"
    },
    {
      "etapa": "Consultar Assinatura",
      "status": "sucesso",
      "detalhe": "Assinatura ID 10 | Plano: STARTER | Status: ATIVA | Saldo: 1200",
      "timestamp": "2026-11-24 14:15:38 UTC"
    },
    {
      "etapa": "Validar Regras",
      "status": "sucesso",
      "detalhe": "Assinatura ATIVA e quantidade (1500 <= 3000) aprovadas.",
      "timestamp": "2026-11-24 14:15:38 UTC"
    },
    {
      "etapa": "Incluir Créditos",
      "status": "sucesso",
      "detalhe": "Adicionados +1500 créditos na assinatura 10. Novo saldo: 2700.",
      "timestamp": "2026-11-24 14:15:41 UTC"
    }
  ]
}
```

### 2. Empresa ambígua

`POST /agent/chat`

```json
{
  "mensagem": "Adicione 500 créditos para Alpha",
  "exigir_aprovacao": true
}
```

Resposta HTTP 200

```json
{
  "execucao_id": "EXEC-2026-E583AD",
  "status": "aguardando_desambiguacao",
  "motivo": "Foram encontradas 2 empresas para 'Alpha'. Selecione qual deseja utilizar.",
  "empresa": null,
  "empresas_candidatas": [
    {
      "id": 3,
      "nome_fantasia": "Alpha Varejo Brasil",
      "cnpj": "33.444.555/0001-66",
      "dominio_corporativo": "alphavarejo.com.br"
    },
    {
      "id": 4,
      "nome_fantasia": "Alpha Cloud Sistemas",
      "cnpj": "44.555.666/0001-77",
      "dominio_corporativo": "alphacloud.com.br"
    }
  ],
  "assinatura": null,
  "creditos": null,
  "auditoria": [
    {
      "etapa": "Interpretar Solicitação",
      "status": "sucesso",
      "detalhe": "Intenção: incluir_creditos | Empresa: Alpha | Créditos: 500",
      "timestamp": "2026-11-24 14:15:41 UTC"
    },
    {
      "etapa": "Buscar Empresa",
      "status": "alerta",
      "detalhe": "Foram encontradas 2 empresas para 'Alpha'. Selecione qual deseja utilizar.",
      "timestamp": "2026-11-24 14:15:44 UTC"
    }
  ]
}
```

### 3. Limite excedido

`POST /agent/chat`

```json
{
  "mensagem": "Adicione 5000 créditos para Logística Sul",
  "exigir_aprovacao": false
}
```

Resposta HTTP 200

```json
{
  "execucao_id": "EXEC-2026-A469DB",
  "status": "negado",
  "motivo": "Operação negada: a quantidade solicitada (5000) excede o limite operacional máximo de 3000 créditos por operação.",
  "empresa": {
    "empresa_id": 1,
    "nome": "Logística Sul"
  },
  "empresas_candidatas": [
    {
      "id": 1,
      "nome_fantasia": "Logística Sul",
      "cnpj": "11.222.333/0001-44",
      "dominio_corporativo": "logisticasul.com.br"
    }
  ],
  "assinatura": {
    "assinatura_id": 10,
    "plano": "STARTER",
    "status": "ATIVA"
  },
  "creditos": {
    "saldo_anterior": 2700,
    "creditos_adicionados": 0,
    "creditos_solicitados": 5000,
    "saldo_final": 2700
  },
  "auditoria": [
    {
      "etapa": "Interpretar Solicitação",
      "status": "sucesso",
      "detalhe": "Intenção: incluir_creditos | Empresa: Logística Sul | Créditos: 5000",
      "timestamp": "2026-11-24 14:15:44 UTC"
    },
    {
      "etapa": "Buscar Empresa",
      "status": "sucesso",
      "detalhe": "Empresa única localizada: Logística Sul (ID: 1).",
      "timestamp": "2026-11-24 14:15:47 UTC"
    },
    {
      "etapa": "Consultar Assinatura",
      "status": "sucesso",
      "detalhe": "Assinatura ID 10 | Plano: STARTER | Status: ATIVA | Saldo: 2700",
      "timestamp": "2026-11-24 14:15:51 UTC"
    },
    {
      "etapa": "Validar Regras",
      "status": "bloqueado",
      "detalhe": "Operação negada: a quantidade solicitada (5000) excede o limite operacional máximo de 3000 créditos por operação.",
      "timestamp": "2026-11-24 14:15:51 UTC"
    }
  ]
}
```
