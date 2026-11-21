import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional
from acreditai.config import settings


class ExecucaoRepository:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.acreditai_db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS execucoes (
                    execucao_id TEXT PRIMARY KEY,
                    solicitante TEXT NOT NULL,
                    aprovador TEXT,
                    prompt_original TEXT NOT NULL,
                    status TEXT NOT NULL,
                    empresa_nome TEXT,
                    creditos_solicitados INTEGER,
                    state_json TEXT NOT NULL,
                    resposta_json TEXT NOT NULL,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """
            )

    def salvar_execucao(
        self,
        execucao_id: str,
        solicitante: str,
        prompt_original: str,
        state: dict[str, Any],
        resposta: dict[str, Any],
        aprovador: Optional[str] = None,
    ) -> None:
        agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        empresa_nome = (resposta.get("empresa") or {}).get("nome") or state.get("empresa_nome")
        creditos = state.get("creditos_solicitados") or 0

        # Serializa estado removendo objetos LangChain Message
        serializable_state = {k: v for k, v in state.items() if k != "messages"}

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO execucoes (
                    execucao_id, solicitante, aprovador, prompt_original, status,
                    empresa_nome, creditos_solicitados, state_json, resposta_json, criado_em, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(execucao_id) DO UPDATE SET
                    aprovador=excluded.aprovador,
                    status=excluded.status,
                    empresa_nome=excluded.empresa_nome,
                    creditos_solicitados=excluded.creditos_solicitados,
                    state_json=excluded.state_json,
                    resposta_json=excluded.resposta_json,
                    atualizado_em=excluded.atualizado_em
                """,
                (
                    execucao_id,
                    solicitante,
                    aprovador,
                    prompt_original,
                    resposta.get("status", "erro"),
                    empresa_nome,
                    creditos,
                    json.dumps(serializable_state, ensure_ascii=False),
                    json.dumps(resposta, ensure_ascii=False),
                    agora,
                    agora,
                ),
            )

    def obter_execucao(self, execucao_id: str) -> Optional[dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM execucoes WHERE execucao_id = ?", (execucao_id,)).fetchone()
            if not row:
                return None
            return {
                "execucao_id": row["execucao_id"],
                "solicitante": row["solicitante"],
                "aprovador": row["aprovador"],
                "prompt_original": row["prompt_original"],
                "status": row["status"],
                "empresa_nome": row["empresa_nome"],
                "creditos_solicitados": row["creditos_solicitados"],
                "state": json.loads(row["state_json"]),
                "resposta": json.loads(row["resposta_json"]),
                "criado_em": row["criado_em"],
                "atualizado_em": row["atualizado_em"],
            }

    def listar_pendentes(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM execucoes
                WHERE status IN ('aguardando_aprovacao', 'aguardando_desambiguacao')
                ORDER BY criado_em DESC
                """
            ).fetchall()
            return [
                {
                    "execucao_id": r["execucao_id"],
                    "solicitante": r["solicitante"],
                    "prompt_original": r["prompt_original"],
                    "status": r["status"],
                    "empresa_nome": r["empresa_nome"],
                    "creditos_solicitados": r["creditos_solicitados"],
                    "resposta": json.loads(r["resposta_json"]),
                    "criado_em": r["criado_em"],
                }
                for r in rows
            ]

    def listar_historico(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM execucoes ORDER BY atualizado_em DESC").fetchall()
            return [
                {
                    "execucao_id": r["execucao_id"],
                    "solicitante": r["solicitante"],
                    "aprovador": r["aprovador"],
                    "prompt_original": r["prompt_original"],
                    "status": r["status"],
                    "empresa_nome": r["empresa_nome"],
                    "creditos_solicitados": r["creditos_solicitados"],
                    "criado_em": r["criado_em"],
                    "atualizado_em": r["atualizado_em"],
                }
                for r in rows
            ]
