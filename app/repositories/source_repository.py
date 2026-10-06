"""SQLite persistence for the Annex B source register."""

import json

from app.contracts import SourceRegisterEntry


class SourceRepository:
    def __init__(self, conn) -> None:
        self.conn = conn

    def save(self, entry: SourceRegisterEntry) -> None:
        data = entry.model_dump(mode="json")
        self.conn.execute(
            """INSERT OR REPLACE INTO source_register VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["doc_id"], data["title"], data["issuer"],
                data["authority_level"], data["doc_type"], data["version"],
                data["effective_from"], data["effective_to"],
                json.dumps(data["supersedes"]),
                json.dumps(data["scope_programmes"]),
                json.dumps(data["scope_batches"]), data["provenance"],
                data["retrieved_on"], int(data["synthetic"]),
            ),
        )
        self.conn.commit()

    def list_all(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM source_register ORDER BY effective_from DESC, doc_id"
        ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            for key in ("supersedes", "scope_programmes", "scope_batches"):
                item[key] = json.loads(item[key])
            item["synthetic"] = bool(item["synthetic"])
            output.append(item)
        return output
