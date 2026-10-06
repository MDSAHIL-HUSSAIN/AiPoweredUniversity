"""Deterministic final-answer and citation validation."""

from app.workflow.state import WorkflowState


NOT_FOUND_ANSWER = (
    "I could not find this information in the available university sources."
)


def validate_answer(state: WorkflowState) -> dict:
    answer_type = state.get("answer_type")
    conflicts = state.get("conflicts_detected", [])
    unresolved = [conflict for conflict in conflicts if not conflict.resolved]

    if answer_type in {"refused", "clarification_needed", "not_found"}:
        return {"citations": []}

    if unresolved:
        return {
            "answer_type": "conflict_flagged",
            "explanation": (
                "The applicable sources remain tied after scope, supersession, "
                "authority, and recency checks."
            ),
        }

    citations = state.get("citations", [])
    requires_document_citation = answer_type == "retrieved_fact" or bool(
        state.get("applied_rules")
    )
    if requires_document_citation and not citations:
        return {
            "answer": NOT_FOUND_ANSWER,
            "answer_type": "not_found",
            "citations": [],
            "explanation": (
                "The workflow could not verify a required citation against the "
                "retrieved source metadata."
            ),
            "errors": [
                *state.get("errors", []),
                "answer rejected because required citations were absent",
            ],
        }

    if not state.get("answer"):
        return {
            "answer": NOT_FOUND_ANSWER,
            "answer_type": "not_found",
            "citations": [],
            "explanation": "No supported answer was produced.",
        }
    return {}
