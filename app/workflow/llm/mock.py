"""Deterministic LLM replacement for local and integration testing."""

import re
from datetime import date

from app.contracts import QuestionCategory, RouteDecision
from app.workflow.llm.base import RouteOutcome
from app.workflow.routing_policy import normalize_route_decision


_COURSE_CODE = re.compile(r"\b[A-Z]{2,4}\d{3}\b")


class MockWorkflowLLM:
    """Route common university questions without making an LLM call."""

    model_name = "mock-llm"

    async def route(self, question: str, as_of_date: date) -> RouteOutcome:
        del as_of_date
        decision = normalize_route_decision(
            question,
            self.route_deterministically(question),
        )
        return RouteOutcome(
            decision=decision,
            attempts=0,
            fallback_used=False,
            model_name=self.model_name,
        )

    @staticmethod
    def route_deterministically(question: str) -> RouteDecision:
        normalized = " ".join(question.lower().split())
        course_match = _COURSE_CODE.search(question.upper())
        entities: dict[str, str] = {}
        if course_match:
            entities["course_code"] = course_match.group(0)

        what_if = any(term in normalized for term in ("what if", "if i ", "suppose"))
        placement = "placement" in normalized
        supplementary = "supplementary" in normalized or "backlog" in normalized
        eligibility = "eligible" in normalized or "eligibility" in normalized
        attendance = "attendance" in normalized
        result = any(term in normalized for term in ("result", "marks", "grade"))
        procedure = any(
            term in normalized
            for term in ("how do i", "how can i", "procedure", "steps to", "apply for")
        )

        if what_if:
            requested_tools = ["run_what_if"]
            category = QuestionCategory.MULTI_STEP
            needs_retrieval = True
            needs_tools = True
        elif eligibility:
            category = QuestionCategory.ELIGIBILITY
            needs_retrieval = True
            needs_tools = True
            if placement:
                requested_tools = ["check_placement_eligibility"]
            elif supplementary:
                requested_tools = ["check_supplementary_eligibility"]
            else:
                requested_tools = ["check_exam_eligibility"]
        elif attendance and any(
            term in normalized for term in ("my attendance", "attendance do i", "attendance in")
        ):
            category = QuestionCategory.PERSONAL_DATA
            needs_retrieval = False
            needs_tools = True
            requested_tools = ["get_attendance"]
        elif result and any(term in normalized for term in ("my ", "i got", "did i")):
            category = QuestionCategory.PERSONAL_DATA
            needs_retrieval = False
            needs_tools = True
            requested_tools = ["get_results"]
        elif procedure:
            category = QuestionCategory.PROCEDURE
            needs_retrieval = True
            needs_tools = False
            requested_tools = []
        else:
            category = QuestionCategory.POLICY_FACT
            needs_retrieval = True
            needs_tools = False
            requested_tools = []

        requires_course = bool(
            set(requested_tools)
            & {
                "get_attendance",
                "check_exam_eligibility",
                "check_supplementary_eligibility",
            }
        )
        clarification = None
        if requires_course and "course_code" not in entities:
            clarification = "Which course code should I use for this request?"

        return RouteDecision(
            category=category,
            entities=entities,
            needs_retrieval=needs_retrieval,
            needs_student_tools=needs_tools,
            requested_tools=requested_tools,
            clarification_question=clarification,
        )

