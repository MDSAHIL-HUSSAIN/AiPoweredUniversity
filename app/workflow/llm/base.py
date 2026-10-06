"""Provider-neutral LLM contracts used by workflow nodes."""

from datetime import date
from typing import Protocol

from pydantic import BaseModel, Field

from app.contracts import Conflict, RetrievedChunk, RouteDecision, ToolResult
from app.contracts.responses import AnswerType


class RouteOutcome(BaseModel):
    """A routing decision plus operational metadata for the audit trail."""

    decision: RouteDecision
    attempts: int = Field(ge=0)
    fallback_used: bool = False
    errors: list[str] = Field(default_factory=list)
    model_name: str
    token_count: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)


class DraftAnswer(BaseModel):
    """LLM draft; citations remain chunk IDs until verified by the workflow."""

    answer: str
    answer_type: AnswerType
    citation_chunk_ids: list[str] = Field(default_factory=list)
    explanation: str


class ComposeOutcome(BaseModel):
    draft: DraftAnswer
    attempts: int = Field(ge=0)
    fallback_used: bool = False
    errors: list[str] = Field(default_factory=list)
    model_name: str
    token_count: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)


class WorkflowLLM(Protocol):
    """Provider-neutral surface required by the completed workflow."""

    async def route(self, question: str, as_of_date: date) -> RouteOutcome: ...

    async def compose(
        self,
        question: str,
        as_of_date: date,
        current_evidence: list[RetrievedChunk],
        upcoming_changes: list[RetrievedChunk],
        tool_results: list[ToolResult],
        conflicts: list[Conflict],
    ) -> ComposeOutcome: ...

