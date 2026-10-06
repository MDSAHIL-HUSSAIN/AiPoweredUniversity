"""Audit record contract shared by workflow and persistence layers."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.contracts.tools import ToolInvocation


class RetrievedSourceAudit(BaseModel):
    doc_id: str
    section: str | None = None
    page: int | None = None
    score: float | None = None


class AuditRecord(BaseModel):
    trace_id: str
    timestamp: datetime
    student_id: str | None = None
    question_category: str
    sources_retrieved: list[RetrievedSourceAudit] = Field(default_factory=list)
    precedence_decision: str | None = None
    tools_invoked: list[ToolInvocation] = Field(default_factory=list)
    answer_type: str
    model: str | None = None
    llm_calls: int = Field(default=0, ge=0)
    tokens: int | None = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

