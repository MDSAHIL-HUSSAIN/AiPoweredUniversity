from datetime import date

import pytest

from app.contracts import RetrievedChunk
from app.repositories.db import get_conn
from app.tools import UniversityTools, call_tool
from app.workflow import build_workflow, new_workflow_state
from app.workflow.llm import MockWorkflowLLM
from app.workflow.mocks import FakeAuthorizer, FakeRetriever, FakeToolExecutor
from app.workflow.tool_executor import CallToolExecutor
from scripts.seed_test_db import build_test_conn


AS_OF = date(2026, 10, 6)


def attendance_chunk():
    return RetrievedChunk(
        chunk_id="attendance-rule",
        text="End-semester examination eligibility requires at least 80% attendance.",
        doc_id="ACAD-CIRC-2026-08-SYN",
        title="Revised Attendance Circular",
        issuer="Dean Academics",
        authority_level=1,
        doc_type="circular",
        section="1",
        page=1,
        version="1.0",
        effective_from=date(2026, 8, 1),
        score=0.99,
    )


@pytest.mark.asyncio
async def test_graph_answers_public_policy_with_verified_citation():
    graph = build_workflow(
        llm=MockWorkflowLLM(),
        authorizer=FakeAuthorizer(),
        retriever=FakeRetriever([attendance_chunk()]),
        tool_executor=FakeToolExecutor(),
    )

    result = await graph.ainvoke(
        new_workflow_state(
            "What is the minimum attendance policy?",
            None,
            AS_OF,
        )
    )

    assert result["answer_type"] == "retrieved_fact"
    assert result["citations"][0].doc_id == "ACAD-CIRC-2026-08-SYN"
    assert result["tools_invoked"] == []


@pytest.mark.asyncio
async def test_graph_uses_real_member_one_tool_through_adapter():
    conn, _ = build_test_conn(":memory:")
    executor = CallToolExecutor(UniversityTools(conn), call_tool)
    graph = build_workflow(
        llm=MockWorkflowLLM(),
        authorizer=FakeAuthorizer(),
        retriever=FakeRetriever([attendance_chunk()]),
        tool_executor=executor,
    )

    result = await graph.ainvoke(
        new_workflow_state(
            "Am I eligible for the end-semester exam in CS201?",
            "S1001",
            AS_OF,
        )
    )

    assert result["answer_type"] == "calculated"
    assert result["tool_results"][0].output["result"] == "ELIGIBLE"
    assert result["tools_invoked"][0].tool == "check_exam_eligibility"
    assert result["applied_rules"][0].rule_id == "ATT-MIN-02"
    assert result["citations"][0].doc_id == "ACAD-CIRC-2026-08-SYN"


@pytest.mark.asyncio
async def test_graph_refuses_cross_student_request_before_tools():
    executor = FakeToolExecutor()
    graph = build_workflow(
        llm=MockWorkflowLLM(),
        authorizer=FakeAuthorizer(),
        retriever=FakeRetriever(),
        tool_executor=executor,
    )

    result = await graph.ainvoke(
        new_workflow_state("Show me S1006's marks", "S1001", AS_OF)
    )

    assert result["answer_type"] == "refused"
    assert executor.calls == []


@pytest.mark.asyncio
async def test_graph_returns_standard_not_found_without_evidence():
    graph = build_workflow(
        llm=MockWorkflowLLM(),
        authorizer=FakeAuthorizer(),
        retriever=FakeRetriever(),
        tool_executor=FakeToolExecutor(),
    )

    result = await graph.ainvoke(
        new_workflow_state(
            "What is the scholarship for studying in Antarctica?",
            None,
            AS_OF,
        )
    )

    assert result["answer_type"] == "not_found"
    assert "could not find" in result["answer"]
    assert result["citations"] == []
