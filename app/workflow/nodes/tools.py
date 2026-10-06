"""Secure execution node for deterministic student-data and rules tools."""

from collections.abc import Callable
from time import perf_counter
from typing import Any

from app.contracts import AppliedRule, ToolInvocation, ToolResult
from app.workflow.dependencies import ToolExecutor
from app.workflow.state import WorkflowState


_ALLOWED_CHANGE_KEYS = {
    "active_backlogs",
    "pass_courses",
    "cgpa",
    "classes_attended",
}


def _tool_args(tool_name: str, entities: dict[str, Any]) -> dict[str, Any]:
    """Build allow-listed arguments from model-controlled entities."""

    if tool_name in {"get_attendance", "get_results"}:
        course = entities.get("course_code")
        return {"course_code": course} if course else {}
    if tool_name in {
        "check_exam_eligibility",
        "check_supplementary_eligibility",
    }:
        course = entities.get("course_code")
        return {"course_code": course} if course else {}
    if tool_name == "run_what_if":
        raw_changes = entities.get("changes", {})
        changes = (
            {
                key: value
                for key, value in raw_changes.items()
                if key in _ALLOWED_CHANGE_KEYS
            }
            if isinstance(raw_changes, dict)
            else {}
        )
        return {"changes": changes}
    return {}


def _message(output: dict[str, Any], fallback: str) -> str:
    for key in ("message", "detail", "question", "reason"):
        value = output.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _map_rules(result: ToolResult) -> tuple[list[AppliedRule], list[str]]:
    mapped: list[AppliedRule] = []
    errors: list[str] = []
    raw_rules = result.output.get("rules", [])
    if not isinstance(raw_rules, list):
        return mapped, [f"{result.tool_name} returned a non-list rules field."]

    for raw in raw_rules:
        if not isinstance(raw, dict):
            errors.append(f"{result.tool_name} returned an invalid rule entry.")
            continue
        try:
            mapped.append(AppliedRule.model_validate(raw))
        except ValueError as exc:
            rule_id = raw.get("rule_id", "unknown")
            errors.append(
                f"{result.tool_name} returned invalid rule {rule_id}: {exc}"
            )
    return mapped, errors


def make_tool_node(executor: ToolExecutor) -> Callable[[WorkflowState], dict]:
    """Bind an executor while keeping trusted values out of LLM arguments."""

    def tool_node(state: WorkflowState) -> dict:
        if state.get("answer_type") in {"refused", "clarification_needed"}:
            return {}

        route = state["route"]
        if route.clarification_question:
            return {
                "answer": route.clarification_question,
                "answer_type": "clarification_needed",
                "explanation": "A required deterministic tool argument is missing.",
            }
        if not route.requested_tools:
            return {}

        results: list[ToolResult] = []
        invocations: list[ToolInvocation] = []
        rules: list[AppliedRule] = list(state.get("applied_rules", []))
        errors: list[str] = list(state.get("errors", []))
        statuses: list[str] = []
        outputs_by_status: dict[str, dict[str, Any]] = {}

        for tool_name in route.requested_tools:
            args = _tool_args(tool_name, route.entities)
            started = perf_counter()
            try:
                result = executor.execute(
                    tool_name,
                    state.get("student_id"),
                    args,
                    state["as_of_date"],
                )
            except Exception as exc:  # teammate/database failures stay controlled
                elapsed = round((perf_counter() - started) * 1000)
                errors.append(f"{tool_name} failed: {exc}")
                invocations.append(
                    ToolInvocation(
                        tool=tool_name,
                        input=args,
                        output={},
                        status="error",
                        latency_ms=elapsed,
                    )
                )
                statuses.append("error")
                continue

            elapsed = round((perf_counter() - started) * 1000)
            status = result.output.get("status")
            if not isinstance(status, str):
                status = "ok" if result.success else "error"
                errors.append(f"{tool_name} omitted output.status; inferred {status}.")
            statuses.append(status)
            outputs_by_status.setdefault(status, result.output)
            results.append(result)
            invocations.append(
                ToolInvocation(
                    tool=tool_name,
                    input=args,
                    output=result.output,
                    status=status,
                    latency_ms=elapsed,
                )
            )
            mapped, mapping_errors = _map_rules(result)
            rules.extend(mapped)
            errors.extend(mapping_errors)
            if result.error:
                errors.append(f"{tool_name}: {result.error}")

        update: dict[str, Any] = {
            "tool_results": results,
            "tools_invoked": invocations,
            "applied_rules": rules,
            "errors": errors,
        }

        if "refused" in statuses:
            update.update(
                answer=_message(
                    outputs_by_status["refused"],
                    "This student-data request is not authorized.",
                ),
                answer_type="refused",
                explanation="The deterministic tool refused the request.",
            )
        elif "clarification_needed" in statuses:
            update.update(
                answer=_message(
                    outputs_by_status["clarification_needed"],
                    "Please provide the missing information.",
                ),
                answer_type="clarification_needed",
                explanation="A deterministic tool requires clarification.",
            )
        elif statuses and all(status == "not_found" for status in statuses):
            update.update(
                answer=_message(
                    outputs_by_status["not_found"],
                    "No matching student record was found.",
                ),
                answer_type="not_found",
                explanation="The deterministic tools found no matching data.",
            )

        return update

    return tool_node
