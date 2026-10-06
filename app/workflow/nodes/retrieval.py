"""Document retrieval node using Member 2's stable retriever interface."""

from collections.abc import Callable

from app.contracts import RetrievalFilters
from app.workflow.dependencies import Retriever
from app.workflow.state import WorkflowState


def _batch(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def make_retrieval_node(
    retriever: Retriever,
    top_k: int = 5,
) -> Callable[[WorkflowState], dict]:
    def retrieval_node(state: WorkflowState) -> dict:
        entities = state["route"].entities
        filters = RetrievalFilters(
            as_of_date=state["as_of_date"],
            programme=entities.get("programme"),
            batch=_batch(entities.get("batch")),
        )
        try:
            chunks = retriever.retrieve(state["question"], filters, top_k=top_k)
            return {"retrieved_chunks": chunks}
        except Exception as exc:
            return {
                "retrieved_chunks": [],
                "errors": [
                    *state.get("errors", []),
                    f"retrieval failed: {type(exc).__name__}: {exc}",
                ],
            }

    return retrieval_node
