"""Audit record contract shared by workflow and persistence layers."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.contracts.responses import AppliedRule, Conflict
from app.contracts.tools import ToolInvocation


class RetrievedSourceAudit(BaseModel):
    doc_id: str
    section: str | None = None
    page: int | None = None
    version: str | None = None
    effective_from: str | None = None
    score: float | None = None


class AuditRecord(BaseModel):
    trace_id: str
    timestamp: datetime
    student_id: str | None = None
    question: str
    question_category: str
    sources_retrieved: list[RetrievedSourceAudit] = Field(default_factory=list)
    precedence_decision: str | None = None
    conflicts_detected: list[Conflict] = Field(default_factory=list)
    tools_invoked: list[ToolInvocation] = Field(default_factory=list)
    applied_rules: list[AppliedRule] = Field(default_factory=list)
    answer_type: str
    answer: str
    explanation: str
    model: str | None = None
    llm_calls: int = Field(default=0, ge=0)
    tokens: int | None = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)
    fallback_used: bool = False
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

