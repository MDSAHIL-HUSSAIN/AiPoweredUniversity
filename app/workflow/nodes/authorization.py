"""Authorization node for personal and student-specific questions."""

from collections.abc import Callable

from app.workflow.dependencies import Authorizer
from app.workflow.state import WorkflowState


def make_authorization_node(authorizer: Authorizer) -> Callable[[WorkflowState], dict]:
    def authorization_node(state: WorkflowState) -> dict:
        route = state["route"]
        result = authorizer.authorize(
            state.get("student_id"),
            route.category.value,
            state["question"],
        )
        update: dict = {"authorization": result}
        if not result.allowed:
            update.update(
                answer=result.reason or "This request is not authorized.",
                answer_type="refused",
                explanation=(
                    "Access was refused using the authenticated request context; "
                    "identity was not inferred from the message."
                ),
            )
        return update

    return authorization_node
