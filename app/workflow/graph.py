"""LangGraph assembly for the student-services workflow."""

from datetime import date, datetime, timezone
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from app.workflow.dependencies import Authorizer, Retriever, ToolExecutor
from app.workflow.llm import WorkflowLLM
from app.workflow.nodes.authorization import make_authorization_node
from app.workflow.nodes.compose import make_compose_node
from app.workflow.nodes.precedence import resolve_source_precedence
from app.workflow.nodes.retrieval import make_retrieval_node
from app.workflow.nodes.router import make_router_node
from app.workflow.nodes.tools import make_tool_node
from app.workflow.nodes.validate import validate_answer
from app.workflow.state import WorkflowState


def new_workflow_state(
    question: str,
    student_id: str | None,
    as_of_date: date,
    trace_id: str | None = None,
) -> WorkflowState:
    return WorkflowState(
        trace_id=trace_id or str(uuid4()),
        started_at=datetime.now(timezone.utc),
        question=question,
        student_id=student_id,
        as_of_date=as_of_date,
        retrieved_chunks=[],
        current_evidence=[],
        upcoming_changes=[],
        inapplicable_chunks=[],
        conflicts_detected=[],
        tool_results=[],
        tools_invoked=[],
        applied_rules=[],
        citations=[],
        errors=[],
        llm_calls=0,
        token_count=0,
        fallback_used=False,
        latency_ms=0,
        audit_metadata={},
    )


def _after_authorization(state: WorkflowState) -> str:
    if state.get("answer_type") == "refused":
        return "validate"
    route = state["route"]
    if route.needs_retrieval:
        return "retrieve"
    if route.needs_student_tools:
        return "tools"
    return "compose"


def _after_precedence(state: WorkflowState) -> str:
    return "tools" if state["route"].needs_student_tools else "compose"


def build_workflow(
    *,
    llm: WorkflowLLM,
    authorizer: Authorizer,
    retriever: Retriever,
    tool_executor: ToolExecutor,
    top_k: int = 5,
):
    """Build a dependency-injected graph that teammates can assemble safely."""

    graph = StateGraph(WorkflowState)
    graph.add_node("router", make_router_node(llm))
    graph.add_node("authorize", make_authorization_node(authorizer))
    graph.add_node("retrieve", make_retrieval_node(retriever, top_k=top_k))
    graph.add_node("precedence", resolve_source_precedence)
    graph.add_node("tools", make_tool_node(tool_executor))
    graph.add_node("compose", make_compose_node(llm))
    graph.add_node("validate", validate_answer)

    graph.add_edge(START, "router")
    graph.add_edge("router", "authorize")
    graph.add_conditional_edges(
        "authorize",
        _after_authorization,
        {
            "retrieve": "retrieve",
            "tools": "tools",
            "compose": "compose",
            "validate": "validate",
        },
    )
    graph.add_edge("retrieve", "precedence")
    graph.add_conditional_edges(
        "precedence",
        _after_precedence,
        {"tools": "tools", "compose": "compose"},
    )
    graph.add_edge("tools", "compose")
    graph.add_edge("compose", "validate")
    graph.add_edge("validate", END)
    return graph.compile()
