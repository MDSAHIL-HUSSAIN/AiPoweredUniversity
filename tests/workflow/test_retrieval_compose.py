from datetime import date

import pytest

from app.contracts import QuestionCategory, RetrievedChunk, RouteDecision
from app.workflow.llm import MockWorkflowLLM
from app.workflow.mocks import FakeRetriever
from app.workflow.nodes.compose import make_compose_node
from app.workflow.nodes.retrieval import make_retrieval_node
from app.workflow.nodes.validate import NOT_FOUND_ANSWER, validate_answer


AS_OF = date(2026, 10, 6)


def chunk(**overrides):
    values = {
        "chunk_id": "chunk-1",
        "text": "The minimum attendance is 80 percent.",
        "doc_id": "ACAD-CIRC-2026-08-SYN",
        "title": "Attendance Circular",
        "issuer": "Dean Academics",
        "authority_level": 1,
        "doc_type": "circular",
        "section": "1",
        "page": 1,
        "version": "1.0",
        "effective_from": date(2026, 8, 1),
        "score": 0.95,
    }
    values.update(overrides)
    return RetrievedChunk(**values)


def route():
    return RouteDecision(
        category=QuestionCategory.POLICY_FACT,
        entities={"programme": "BTech", "batch": 2023},
        needs_retrieval=True,
        needs_student_tools=False,
    )


def test_retrieval_node_builds_typed_filters():
    seen = {}

    class RecordingRetriever(FakeRetriever):
        def retrieve(self, query, filters, top_k=5):
            seen.update(query=query, filters=filters, top_k=top_k)
            return super().retrieve(query, filters, top_k)

    node = make_retrieval_node(RecordingRetriever([chunk()]), top_k=7)
    update = node(
        {
            "question": "What is the attendance rule?",
            "as_of_date": AS_OF,
            "route": route(),
            "errors": [],
        }
    )

    assert len(update["retrieved_chunks"]) == 1
    assert seen["filters"].programme == "BTech"
    assert seen["filters"].batch == 2023
    assert seen["top_k"] == 7


@pytest.mark.asyncio
async def test_compose_builds_citation_from_chunk_not_model_metadata():
    source = chunk()
    node = make_compose_node(MockWorkflowLLM())
    update = await node(
        {
            "question": "What is the attendance rule?",
            "as_of_date": AS_OF,
            "current_evidence": [source],
            "upcoming_changes": [],
            "tool_results": [],
            "conflicts_detected": [],
            "applied_rules": [],
            "errors": [],
            "llm_calls": 0,
            "fallback_used": False,
        }
    )

    assert update["answer_type"] == "retrieved_fact"
    assert update["citations"][0].doc_id == source.doc_id
    assert update["citations"][0].effective_from == source.effective_from


def test_validator_rejects_uncited_retrieved_fact():
    update = validate_answer(
        {
            "answer": "The rule is 80 percent.",
            "answer_type": "retrieved_fact",
            "citations": [],
            "applied_rules": [],
            "conflicts_detected": [],
            "errors": [],
        }
    )

    assert update["answer_type"] == "not_found"
    assert update["answer"] == NOT_FOUND_ANSWER
