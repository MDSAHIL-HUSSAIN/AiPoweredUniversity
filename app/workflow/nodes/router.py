"""LangGraph router node."""

from collections.abc import Callable
from typing import Awaitable

from app.workflow.llm import WorkflowLLM
from app.workflow.state import WorkflowState


def make_router_node(
    llm: WorkflowLLM,
) -> Callable[[WorkflowState], Awaitable[dict]]:
    """Bind an LLM implementation to a reusable async graph node."""

    async def router_node(state: WorkflowState) -> dict:
        outcome = await llm.route(state["question"], state["as_of_date"])
        return {
            "route": outcome.decision,
            "llm_calls": state.get("llm_calls", 0) + outcome.attempts,
            "model_name": outcome.model_name,
            "fallback_used": state.get("fallback_used", False)
            or outcome.fallback_used,
            "errors": [*state.get("errors", []), *outcome.errors],
        }

    return router_node

