import json
from datetime import datetime, timezone


class AuditRepository:
    # SQLite audit store. save() takes a dict or a pydantic model (AuditRecord from app/contracts/audit.py)
    def __init__(self, conn):
        self.conn = conn

    def save(self, record):
        if hasattr(record, "model_dump"):
            data = record.model_dump(mode="json")
        else:
            data = dict(record)
        trace_id = str(data.get("trace_id") or "")
        if trace_id == "":
            raise ValueError("audit record needs a trace_id")
        self.conn.execute("INSERT OR REPLACE INTO audit_log VALUES (?,?,?,?)",
                          (trace_id, datetime.now(timezone.utc).isoformat(), data.get("student_id"),
                           json.dumps(data, default=str)))
        self.conn.commit()

    def get(self, trace_id):
        row = self.conn.execute("SELECT record_json FROM audit_log WHERE trace_id = ?", (trace_id,)).fetchone()
        if row is None:
            return None
        return json.loads(row["record_json"])

    def recent(self, limit=50):
        rows = self.conn.execute("SELECT record_json FROM audit_log ORDER BY created_at DESC LIMIT ?",
                                 (limit,)).fetchall()
        out = []
        for r in rows:
            out.append(json.loads(r["record_json"]))
        return out
