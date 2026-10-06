"""Response objects returned by the workflow and API."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.contracts.tools import ToolInvocation


AnswerType = Literal[
    "retrieved_fact",
    "calculated",
    "not_found",
    "clarification_needed",
    "refused",
    "conflict_flagged",
]


class Citation(BaseModel):
    doc_id: str
    title: str
    section: str | None = None
    page: int | None = None
    version: str
    effective_from: date


class AppliedRule(BaseModel):
    rule_id: str
    source_doc_id: str
    source_section: str
    value: Any


class Conflict(BaseModel):
    doc_ids: list[str] = Field(min_length=2)
    reason: str
    resolved: bool
    selected_doc_id: str | None = None


class AskResponse(BaseModel):
    trace_id: str
    answer: str
    answer_type: AnswerType
    citations: list[Citation] = Field(default_factory=list)
    tools_invoked: list[ToolInvocation] = Field(default_factory=list)
    applied_rules: list[AppliedRule] = Field(default_factory=list)
    conflicts_detected: list[Conflict] = Field(default_factory=list)
    explanation: str
    as_of_date: date


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    api: bool
    vector_store: bool
    sqlite: bool
    llm: bool

