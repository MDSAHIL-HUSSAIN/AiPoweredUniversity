"""Deterministic guardrails applied to every LLM routing decision."""

import re
from typing import Any

from app.contracts import QuestionCategory, RouteDecision


_COURSE_CODE = re.compile(r"\b[A-Z]{2,4}\d{3}\b")
_EMPTY_ENTITY_VALUES = {
    "",
    "unknown",
    "not specified",
    "not provided",
    "none",
    "null",
    "n/a",
}
_COURSE_TOOLS = {
    "get_attendance",
    "check_exam_eligibility",
    "check_supplementary_eligibility",
}


def _clean_entities(question: str, entities: dict[str, Any]) -> dict[str, Any]:
    cleaned = {
        key: value
        for key, value in entities.items()
        if key != "student_id"
        and value is not None
        and not (
            isinstance(value, str)
            and value.strip().lower() in _EMPTY_ENTITY_VALUES
        )
    }
    match = _COURSE_CODE.search(question.upper())
    if match:
        cleaned["course_code"] = match.group(0)
    return cleaned


def normalize_route_decision(
    question: str,
    decision: RouteDecision,
) -> RouteDecision:
    """Enforce workflow policy after model parsing.

    Structured output guarantees shape, not semantic correctness. This guard keeps
    identity out of model-controlled state and ensures required deterministic tools
    are selected for personal and eligibility questions.
    """

    normalized = " ".join(question.lower().split())
    entities = _clean_entities(question, decision.entities)
    category = decision.category
    tools = list(dict.fromkeys(decision.requested_tools))
    needs_retrieval = decision.needs_retrieval
    needs_tools = decision.needs_student_tools

    if category == QuestionCategory.ELIGIBILITY:
        needs_retrieval = True
        needs_tools = True
        if "placement" in normalized:
            tools = ["check_placement_eligibility"]
        elif "supplementary" in normalized or "backlog" in normalized:
            tools = ["check_supplementary_eligibility"]
        else:
            tools = ["check_exam_eligibility"]
    elif category == QuestionCategory.PERSONAL_DATA:
        needs_tools = True
        if "attendance" in normalized:
            tools = ["get_attendance"]
        elif any(term in normalized for term in ("result", "marks", "grade")):
            tools = ["get_results"]
    elif category == QuestionCategory.MULTI_STEP:
        needs_retrieval = True
        needs_tools = True
        if any(term in normalized for term in ("what if", "if i ", "suppose")):
            tools = ["run_what_if"]
    elif category in {
        QuestionCategory.POLICY_FACT,
        QuestionCategory.PROCEDURE,
        QuestionCategory.NOT_ANSWERABLE,
    }:
        # Whether a question is truly unanswerable is decided only after retrieval.
        needs_retrieval = True

    clarification = decision.clarification_question
    requires_course = bool(set(tools) & _COURSE_TOOLS)
    if requires_course and "course_code" not in entities:
        clarification = "Which course code should I use for this request?"
    elif not requires_course or "course_code" in entities:
        # Authentication obtains identity from X-Student-ID; the LLM must never ask
        # for a roll number or student ID in message text.
        clarification = None

    return RouteDecision(
        category=category,
        entities=entities,
        needs_retrieval=needs_retrieval,
        needs_student_tools=needs_tools,
        requested_tools=tools,
        clarification_question=clarification,
    )

