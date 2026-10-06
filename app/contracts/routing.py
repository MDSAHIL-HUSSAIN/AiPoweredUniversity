"""Structured router and authorization contracts."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class QuestionCategory(StrEnum):
    POLICY_FACT = "policy_fact"
    PROCEDURE = "procedure"
    PERSONAL_DATA = "personal_data"
    ELIGIBILITY = "eligibility"
    MULTI_STEP = "multi_step"
    NOT_ANSWERABLE = "not_answerable"


AllowedTool = Literal[
    "get_attendance",
    "get_results",
    "check_exam_eligibility",
    "check_supplementary_eligibility",
    "check_placement_eligibility",
    "run_what_if",
]


class RouteDecision(BaseModel):
    category: QuestionCategory
    entities: dict[str, Any] = Field(default_factory=dict)
    needs_retrieval: bool
    needs_student_tools: bool
    requested_tools: list[AllowedTool] = Field(default_factory=list)
    clarification_question: str | None = None


class AuthorizationResult(BaseModel):
    allowed: bool
    reason: str | None = None

