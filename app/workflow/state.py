"""Shared state carried between LangGraph nodes."""

from datetime import date, datetime
from typing import Any, TypedDict

from app.contracts import (
    AppliedRule,
    Citation,
    Conflict,
    RetrievedChunk,
    RouteDecision,
    ToolInvocation,
    ToolResult,
)


class WorkflowState(TypedDict, total=False):
    trace_id: str
    started_at: datetime
    question: str
    student_id: str | None
    as_of_date: date
    route: RouteDecision
    retrieved_chunks: list[RetrievedChunk]
    current_evidence: list[RetrievedChunk]
    upcoming_changes: list[RetrievedChunk]
    inapplicable_chunks: list[RetrievedChunk]
    precedence_decision: str
    conflicts_detected: list[Conflict]
    tool_results: list[ToolResult]
    tools_invoked: list[ToolInvocation]
    applied_rules: list[AppliedRule]
    answer: str
    answer_type: str
    citations: list[Citation]
    explanation: str
    errors: list[str]
    model_name: str
    llm_calls: int
    token_count: int | None
    fallback_used: bool
    latency_ms: int
    audit_metadata: dict[str, Any]

