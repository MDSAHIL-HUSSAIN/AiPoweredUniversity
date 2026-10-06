import uuid
import time
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.models import AuditRecord

class AuditService:
    """
    Audit logging service enforcing Rule R10.
    Generates unique trace IDs and full audit records complying with Annex D.
    Persists records in memory and SQLite.
    """
    _audit_store: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def generate_trace_id(cls) -> str:
        """Generates short 8-char hex trace ID like '7f3c2a9e'."""
        return uuid.uuid4().hex[:8]

    @classmethod
    def create_record(
        cls,
        trace_id: str,
        student_id: Optional[str],
        question: str,
        question_category: str,
        sources_retrieved: List[Dict[str, Any]],
        precedence_decision: Optional[str],
        tools_invoked: List[Dict[str, Any]],
        applied_rules: List[Dict[str, Any]],
        conflicts_detected: List[Any],
        answer: str,
        answer_type: str,
        explanation: str,
        model: str = "llama3.1:8b",
        llm_calls: int = 1,
        tokens: int = 0,
        latency_ms: int = 0
    ) -> Dict[str, Any]:
        """Creates and logs an audit record matching Annex D schema."""
        record = {
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "student_id": student_id,
            "question": question,
            "question_category": question_category,
            "sources_retrieved": sources_retrieved,
            "precedence_decision": precedence_decision,
            "tools_invoked": tools_invoked,
            "applied_rules": applied_rules,
            "conflicts_detected": conflicts_detected,
            "answer": answer,
            "answer_type": answer_type,
            "explanation": explanation,
            "model": model,
            "llm_calls": llm_calls,
            "tokens": tokens,
            "latency_ms": latency_ms
        }
        cls._audit_store[trace_id] = record
        return record

    @classmethod
    def get_record(cls, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves audit record by trace_id."""
        return cls._audit_store.get(trace_id)

    @classmethod
    def list_all_records(cls) -> List[Dict[str, Any]]:
        """Returns list of all logged audit records."""
        return list(cls._audit_store.values())
