from datetime import date

from app.contracts import QuestionCategory, RouteDecision, ToolResult
from app.workflow.mocks import FakeToolExecutor
from app.workflow.nodes.tools import make_tool_node
from app.workflow.tool_executor import CallToolExecutor


AS_OF = date(2026, 10, 6)


def state_for(
    tool: str,
    *,
    entities: dict | None = None,
    student_id: str | None = "S1001",
    clarification: str | None = None,
):
    return {
        "question": "test question",
        "student_id": student_id,
        "as_of_date": AS_OF,
        "route": RouteDecision(
            category=QuestionCategory.ELIGIBILITY,
            entities=entities or {},
            needs_retrieval=True,
            needs_student_tools=True,
            requested_tools=[tool],
            clarification_question=clarification,
        ),
        "errors": [],
    }


def test_call_tool_adapter_matches_member_one_signature():
    seen = {}

    def call_tool(tools, tool_name, student_id, args, as_of_date):
        seen.update(
            tools=tools,
            tool_name=tool_name,
            student_id=student_id,
            args=args,
            as_of_date=as_of_date,
        )
        return ToolResult(
            tool_name=tool_name,
            success=True,
            inputs=args,
            output={"status": "ok"},
        )

    executor = CallToolExecutor("tools-instance", call_tool)
    executor.execute("get_results", "S1001", {}, AS_OF)

    assert seen == {
        "tools": "tools-instance",
        "tool_name": "get_results",
        "student_id": "S1001",
        "args": {},
        "as_of_date": AS_OF,
    }


def test_tool_node_passes_identity_and_date_outside_model_args():
    executor = FakeToolExecutor()
    node = make_tool_node(executor)
    state = state_for(
        "check_exam_eligibility",
        entities={
            "course_code": "CS201",
            "student_id": "S9999",
            "as_of_date": "1999-01-01",
        },
    )

    update = node(state)

    assert executor.calls[0] == {
        "tool_name": "check_exam_eligibility",
        "student_id": "S1001",
        "args": {"course_code": "CS201"},
        "as_of_date": AS_OF,
    }
    assert update["tools_invoked"][0].input == {"course_code": "CS201"}
    assert update["tools_invoked"][0].status == "ok"


def test_what_if_only_forwards_allowed_change_keys():
    executor = FakeToolExecutor()
    node = make_tool_node(executor)

    node(
        state_for(
            "run_what_if",
            entities={
                "changes": {
                    "active_backlogs": 0,
                    "cgpa": 7.1,
                    "student_id": "S9999",
                    "overwrite_database": True,
                }
            },
        )
    )

    assert executor.calls[0]["args"] == {
        "changes": {"active_backlogs": 0, "cgpa": 7.1}
    }


def test_router_clarification_prevents_tool_execution():
    executor = FakeToolExecutor()
    node = make_tool_node(executor)

    update = node(
        state_for(
            "check_exam_eligibility",
            clarification="Which course code should I use for this request?",
        )
    )

    assert executor.calls == []
    assert update["answer_type"] == "clarification_needed"


def test_not_eligible_is_still_successful_ok_status():
    class NotEligibleExecutor:
        def execute(self, tool_name, student_id, args, as_of_date):
            return ToolResult(
                tool_name=tool_name,
                success=True,
                inputs=args,
                output={"status": "ok", "result": "NOT_ELIGIBLE", "rules": []},
            )

    update = make_tool_node(NotEligibleExecutor())(
        state_for(
            "check_exam_eligibility",
            entities={"course_code": "CS201"},
        )
    )

    assert update["tools_invoked"][0].status == "ok"
    assert "answer_type" not in update


def test_tool_status_drives_not_found_terminal_answer():
    class MissingExecutor:
        def execute(self, tool_name, student_id, args, as_of_date):
            return ToolResult(
                tool_name=tool_name,
                success=False,
                inputs=args,
                output={"status": "not_found", "message": "Course was not found."},
            )

    update = make_tool_node(MissingExecutor())(
        state_for("get_results", entities={"course_code": "ZZ999"})
    )

    assert update["answer_type"] == "not_found"
    assert update["answer"] == "Course was not found."


def test_tool_rules_are_mapped_to_public_applied_rule_contract():
    class RuleExecutor:
        def execute(self, tool_name, student_id, args, as_of_date):
            return ToolResult(
                tool_name=tool_name,
                success=True,
                inputs=args,
                applied_rule_ids=["ATT-MIN-02"],
                output={
                    "status": "ok",
                    "rules": [
                        {
                            "rule_id": "ATT-MIN-02",
                            "source_doc_id": "ACAD-CIRC-2026-08-SYN",
                            "source_section": "2",
                            "value": 80,
                        }
                    ],
                },
            )

    update = make_tool_node(RuleExecutor())(
        state_for(
            "check_exam_eligibility",
            entities={"course_code": "CS201"},
        )
    )

    assert update["applied_rules"][0].rule_id == "ATT-MIN-02"
    assert update["applied_rules"][0].source_section == "2"


def test_executor_exception_becomes_controlled_error():
    class BrokenExecutor:
        def execute(self, tool_name, student_id, args, as_of_date):
            raise RuntimeError("database unavailable")

    update = make_tool_node(BrokenExecutor())(
        state_for("get_results", entities={})
    )

    assert update["tools_invoked"][0].status == "error"
    assert "database unavailable" in update["errors"][0]
