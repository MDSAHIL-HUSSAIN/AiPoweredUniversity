from datetime import date

import pytest

from app.contracts import QuestionCategory, RouteDecision
from app.workflow.config import WorkflowSettings
from app.workflow.llm import MockWorkflowLLM, OllamaWorkflowLLM
from app.workflow.nodes.router import make_router_node


class StubStructuredRouter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def ainvoke(self, messages):
        del messages
        response = self.responses[self.calls]
        self.calls += 1
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.asyncio
async def test_mock_router_routes_policy_to_retrieval():
    outcome = await MockWorkflowLLM().route(
        "What is the minimum attendance requirement?",
        date(2026, 10, 6),
    )
    assert outcome.decision.category == QuestionCategory.POLICY_FACT
    assert outcome.decision.needs_retrieval is True
    assert outcome.decision.needs_student_tools is False


@pytest.mark.asyncio
async def test_mock_router_routes_eligibility_to_rule_and_tool():
    outcome = await MockWorkflowLLM().route(
        "Am I eligible for the supplementary exam in CS201?",
        date(2026, 10, 6),
    )
    assert outcome.decision.category == QuestionCategory.ELIGIBILITY
    assert outcome.decision.entities["course_code"] == "CS201"
    assert outcome.decision.requested_tools == [
        "check_supplementary_eligibility"
    ]
    assert outcome.decision.needs_retrieval is True
    assert outcome.decision.needs_student_tools is True


@pytest.mark.asyncio
async def test_mock_router_requests_course_clarification():
    outcome = await MockWorkflowLLM().route(
        "Am I eligible for the supplementary exam?",
        date(2026, 10, 6),
    )
    assert outcome.decision.clarification_question


@pytest.mark.asyncio
async def test_router_never_extracts_student_id_from_message():
    outcome = await MockWorkflowLLM().route(
        "Show attendance for student S1234 in CS201",
        date(2026, 10, 6),
    )
    assert "student_id" not in outcome.decision.entities


@pytest.mark.asyncio
async def test_ollama_adapter_retries_then_succeeds():
    expected = RouteDecision(
        category=QuestionCategory.PROCEDURE,
        entities={},
        needs_retrieval=True,
        needs_student_tools=False,
    )
    stub = StubStructuredRouter([ValueError("bad json"), expected])
    adapter = OllamaWorkflowLLM(
        WorkflowSettings(_env_file=None, router_max_attempts=2),
        structured_router=stub,
    )

    outcome = await adapter.route("How do I apply?", date(2026, 10, 6))

    assert outcome.decision == expected
    assert outcome.attempts == 2
    assert outcome.fallback_used is False
    assert len(outcome.errors) == 1


@pytest.mark.asyncio
async def test_semantic_guard_repairs_schema_valid_but_unsafe_eligibility_route():
    model_decision = RouteDecision(
        category=QuestionCategory.ELIGIBILITY,
        entities={
            "course_code": "CS201",
            "programme": "not specified",
            "batch": "not specified",
            "student_id": "S1234",
            "exam_type": "supplementary",
        },
        needs_retrieval=True,
        needs_student_tools=True,
        requested_tools=[],
        clarification_question="Please provide your student ID and batch year.",
    )
    adapter = OllamaWorkflowLLM(
        WorkflowSettings(_env_file=None),
        structured_router=StubStructuredRouter([model_decision]),
    )

    outcome = await adapter.route(
        "Am I eligible for the supplementary exam in CS201?",
        date(2026, 10, 6),
    )

    assert outcome.decision.requested_tools == [
        "check_supplementary_eligibility"
    ]
    assert outcome.decision.clarification_question is None
    assert "student_id" not in outcome.decision.entities
    assert "programme" not in outcome.decision.entities
    assert "batch" not in outcome.decision.entities


@pytest.mark.asyncio
async def test_ollama_adapter_falls_back_after_retry_exhaustion():
    stub = StubStructuredRouter([RuntimeError("offline"), RuntimeError("offline")])
    adapter = OllamaWorkflowLLM(
        WorkflowSettings(_env_file=None, router_max_attempts=2),
        structured_router=stub,
    )

    outcome = await adapter.route(
        "What is the minimum attendance requirement?",
        date(2026, 10, 6),
    )

    assert outcome.fallback_used is True
    assert outcome.decision.category == QuestionCategory.POLICY_FACT
    assert len(outcome.errors) == 2


@pytest.mark.asyncio
async def test_router_node_merges_operational_metadata():
    node = make_router_node(MockWorkflowLLM())
    update = await node(
        {
            "question": "How do I apply for a supplementary exam?",
            "as_of_date": date(2026, 10, 6),
            "llm_calls": 1,
            "errors": ["earlier warning"],
        }
    )
    assert update["route"].category == QuestionCategory.PROCEDURE
    assert update["llm_calls"] == 1
    assert update["errors"] == ["earlier warning"]

