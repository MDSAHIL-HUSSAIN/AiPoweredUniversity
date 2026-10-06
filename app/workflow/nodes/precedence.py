"""LangGraph node for Annex A source precedence."""

from app.workflow.precedence import resolve_precedence
from app.workflow.state import WorkflowState


def _optional_batch(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def resolve_source_precedence(state: WorkflowState) -> dict:
    route = state.get("route")
    entities = route.entities if route else {}
    resolution = resolve_precedence(
        state.get("retrieved_chunks", []),
        as_of_date=state["as_of_date"],
        programme=entities.get("programme"),
        batch=_optional_batch(entities.get("batch")),
    )
    return {
        "current_evidence": resolution.current_evidence,
        "upcoming_changes": resolution.upcoming_changes,
        "inapplicable_chunks": resolution.inapplicable_chunks,
        "conflicts_detected": [
            *state.get("conflicts_detected", []),
            *resolution.conflicts,
        ],
        "precedence_decision": resolution.decision_summary,
    }

