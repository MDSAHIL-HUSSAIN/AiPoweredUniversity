"""Provider-neutral LLM contracts used by workflow nodes."""

from datetime import date
from typing import Protocol

from pydantic import BaseModel, Field

from app.contracts import RouteDecision


class RouteOutcome(BaseModel):
    """A routing decision plus operational metadata for the audit trail."""

    decision: RouteDecision
    attempts: int = Field(ge=0)
    fallback_used: bool = False
    errors: list[str] = Field(default_factory=list)
    model_name: str


class WorkflowLLM(Protocol):
    """Minimum LLM surface required by the router milestone."""

    async def route(self, question: str, as_of_date: date) -> RouteOutcome: ...

