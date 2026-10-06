from datetime import date

from app.contracts import QuestionCategory, RouteDecision
from app.workflow.mocks import FakeAuthorizer
from app.workflow.nodes.authorization import make_authorization_node


def state_for(category: QuestionCategory, *, student_id: str | None, question: str):
    return {
        "question": question,
        "student_id": student_id,
        "as_of_date": date(2026, 10, 6),
        "route": RouteDecision(
            category=category,
            entities={},
            needs_retrieval=False,
            needs_student_tools=category != QuestionCategory.POLICY_FACT,
        ),
    }


def test_policy_question_does_not_require_student_identity():
    node = make_authorization_node(FakeAuthorizer())

    update = node(
        state_for(
            QuestionCategory.POLICY_FACT,
            student_id=None,
            question="What is the attendance policy?",
        )
    )

    assert update["authorization"].allowed is True
    assert "answer_type" not in update


def test_personal_question_without_header_is_refused():
    node = make_authorization_node(FakeAuthorizer())

    update = node(
        state_for(
            QuestionCategory.PERSONAL_DATA,
            student_id=None,
            question="Show my results",
        )
    )

    assert update["authorization"].allowed is False
    assert update["answer_type"] == "refused"
    assert "X-Student-ID" in update["answer"]


def test_request_for_different_student_is_refused():
    node = make_authorization_node(FakeAuthorizer())

    update = node(
        state_for(
            QuestionCategory.PERSONAL_DATA,
            student_id="S1001",
            question="Show me S1006's marks",
        )
    )

    assert update["authorization"].allowed is False
    assert update["answer_type"] == "refused"


def test_mentioning_authenticated_student_is_allowed():
    node = make_authorization_node(FakeAuthorizer())

    update = node(
        state_for(
            QuestionCategory.PERSONAL_DATA,
            student_id="S1001",
            question="Show S1001's marks",
        )
    )

    assert update["authorization"].allowed is True
