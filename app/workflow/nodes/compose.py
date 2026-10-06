"""Evidence-only answer composition with deterministic citation construction."""

from collections.abc import Callable
from typing import Awaitable

from app.contracts import Citation
from app.workflow.llm import WorkflowLLM
from app.workflow.state import WorkflowState


def make_compose_node(
    llm: WorkflowLLM,
) -> Callable[[WorkflowState], Awaitable[dict]]:
    async def compose_node(state: WorkflowState) -> dict:
        if state.get("answer_type") in {
            "not_found",
            "clarification_needed",
            "refused",
        }:
            return {}

        current = state.get("current_evidence", [])
        upcoming = state.get("upcoming_changes", [])
        outcome = await llm.compose(
            question=state["question"],
            as_of_date=state["as_of_date"],
            current_evidence=current,
            upcoming_changes=upcoming,
            tool_results=state.get("tool_results", []),
            conflicts=state.get("conflicts_detected", []),
        )

        chunks = {chunk.chunk_id: chunk for chunk in [*current, *upcoming]}
        selected_ids = list(outcome.draft.citation_chunk_ids)
        rule_doc_ids = {rule.source_doc_id for rule in state.get("applied_rules", [])}
        selected_ids.extend(
            chunk.chunk_id
            for chunk in current
            if chunk.doc_id in rule_doc_ids
        )

        citations: list[Citation] = []
        invalid_ids: list[str] = []
        for chunk_id in dict.fromkeys(selected_ids):
            chunk = chunks.get(chunk_id)
            if chunk is None:
                invalid_ids.append(chunk_id)
                continue
            citations.append(
                Citation(
                    doc_id=chunk.doc_id,
                    title=chunk.title,
                    section=chunk.section,
                    page=chunk.page,
                    version=chunk.version,
                    effective_from=chunk.effective_from,
                )
            )

        citation_errors = [
            f"composer requested unknown citation chunk {chunk_id}"
            for chunk_id in invalid_ids
        ]
        return {
            "answer": outcome.draft.answer,
            "answer_type": outcome.draft.answer_type,
            "explanation": outcome.draft.explanation,
            "citations": citations,
            "llm_calls": state.get("llm_calls", 0) + outcome.attempts,
            "token_count": state.get("token_count", 0) + outcome.token_count,
            "latency_ms": state.get("latency_ms", 0) + outcome.latency_ms,
            "model_name": outcome.model_name,
            "fallback_used": state.get("fallback_used", False)
            or outcome.fallback_used,
            "errors": [
                *state.get("errors", []),
                *outcome.errors,
                *citation_errors,
            ],
            "audit_metadata": {
                **state.get("audit_metadata", {}),
                "compose_latency_ms": outcome.latency_ms,
            },
        }

    return compose_node
