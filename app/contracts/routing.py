"""Structured router and authorization contracts."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class QuestionCategory(StrEnum):
    POLICY_FACT = "policy_fact"
    PROCEDURE = "procedure"
    PERSONAL_DATA = "personal_data"
    ELIGIBILITY = "eligibility"
    MULTI_STEP = "multi_step"
    UNKNOWN = "unknown"


class RouteDecision(BaseModel):
    category: QuestionCategory
    entities: dict[str, Any] = Field(default_factory=dict)
    needs_retrieval: bool
    needs_student_tools: bool
    requested_tool: str | None = None
    clarification_question: str | None = None


class AuthorizationResult(BaseModel):
    allowed: bool
    reason: str | None = None

