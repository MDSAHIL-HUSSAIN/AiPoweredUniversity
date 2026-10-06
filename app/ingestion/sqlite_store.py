import json
import sqlite3
from datetime import date

from app.contracts.documents import SourceRegisterEntry


class SQLiteStore:

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS source_register (
                    doc_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    issuer TEXT NOT NULL,
                    authority_level INTEGER NOT NULL,
                    doc_type TEXT NOT NULL,
                    version TEXT NOT NULL,
                    effective_from TEXT,
                    effective_to TEXT,
                    supersedes TEXT NOT NULL,
                    scope_programmes TEXT NOT NULL,
                    scope_batches TEXT NOT NULL,
                    provenance TEXT NOT NULL,
                    retrieved_on TEXT NOT NULL,
                    synthetic INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            conn.commit()

    def register_source(
        self,
        source: SourceRegisterEntry,
    ) -> None:

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO source_register (
                    doc_id,
                    title,
                    issuer,
                    authority_level,
                    doc_type,
                    version,
                    effective_from,
                    effective_to,
                    supersedes,
                    scope_programmes,
                    scope_batches,
                    provenance,
                    retrieved_on,
                    synthetic
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.doc_id,
                    source.title,
                    source.issuer,
                    source.authority_level,
                    source.doc_type,
                    source.version,
                    source.effective_from.isoformat(),
                    (
                        source.effective_from.isoformat()
                        if source.effective_from
                        else None
                    ),
                    (
                        source.effective_to.isoformat()
                        if source.effective_to
                        else None
                    ),
                    json.dumps(source.supersedes),
                    json.dumps(source.scope_programmes),
                    json.dumps(source.scope_batches),
                    source.provenance,
                    source.retrieved_on.isoformat(),
                    int(source.synthetic),
                ),
            )

            conn.commit()

    def get_sources(
        self,
        doc_ids: list[str],
    ) -> dict[str, dict]:

        if not doc_ids:
            return {}

        placeholders = ",".join(
            "?" for _ in doc_ids
        )

        query = f"""
            SELECT
                doc_id,
                title,
                issuer,
                authority_level,
                doc_type,
                version,
                effective_from,
                effective_to,
                supersedes,
                scope_programmes,
                scope_batches,
                provenance,
                retrieved_on,
                synthetic
            FROM source_register
            WHERE doc_id IN ({placeholders})
        """

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            rows = conn.execute(
                query,
                doc_ids,
            ).fetchall()

        return {
            row["doc_id"]: dict(row)
            for row in rows
        }