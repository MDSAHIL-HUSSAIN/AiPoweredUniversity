"""Shared state carried between LangGraph nodes."""

from datetime import date
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
    question: str
    student_id: str | None
    as_of_date: date
    route: RouteDecision
    retrieved_chunks: list[RetrievedChunk]
    resolved_evidence: list[RetrievedChunk]
    conflicts_detected: list[Conflict]
    tool_results: list[ToolResult]
    tools_invoked: list[ToolInvocation]
    applied_rules: list[AppliedRule]
    answer: str
    answer_type: str
    citations: list[Citation]
    explanation: str
    errors: list[str]
    audit_metadata: dict[str, Any]

