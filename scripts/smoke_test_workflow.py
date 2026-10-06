"""Run one end-to-end LangGraph request with Ollama and deterministic tools."""

import asyncio
from datetime import date

from app.contracts import RetrievedChunk
from app.tools import UniversityTools, call_tool
from app.workflow import build_workflow, new_workflow_state
from app.workflow.config import get_settings
from app.workflow.llm import OllamaWorkflowLLM
from app.workflow.mocks import FakeAuthorizer, FakeRetriever
from app.workflow.tool_executor import CallToolExecutor
from scripts.seed_test_db import build_test_conn


async def main() -> None:
    settings = get_settings()
    llm = OllamaWorkflowLLM(settings)
    conn, _ = build_test_conn(":memory:")
    retriever = FakeRetriever(
        [
            RetrievedChunk(
                chunk_id="attendance-rule",
                text=(
                    "Students need at least 80 percent attendance to appear in "
                    "the end-semester examination."
                ),
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
        ]
    )
    graph = build_workflow(
        llm=llm,
        authorizer=FakeAuthorizer(),
        retriever=retriever,
        tool_executor=CallToolExecutor(UniversityTools(conn), call_tool),
        top_k=settings.top_k,
    )
    result = await graph.ainvoke(
        new_workflow_state(
            "Am I eligible for the end-semester exam in CS201?",
            "S1001",
            date(2026, 10, 6),
        )
    )
    print("answer_type:", result["answer_type"])
    print("answer:", result["answer"])
    print("citations:", [item.model_dump(mode="json") for item in result["citations"]])
    print("tool:", result["tools_invoked"][0].model_dump(mode="json"))
    print("fallback_used:", result["fallback_used"])
    print("errors:", result["errors"])


if __name__ == "__main__":
    asyncio.run(main())
