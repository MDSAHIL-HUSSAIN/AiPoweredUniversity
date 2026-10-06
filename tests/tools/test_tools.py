from datetime import date

from app.contracts.tools import ToolResult
from app.tools import call_tool, TOOL_SPECS, UniversityTools

NOW = date(2026, 10, 6)
OLD = "2026-07-15"


def test_every_tool_returns_toolresult(tools):
    assert isinstance(tools.get_attendance("S1001"), ToolResult)
    assert set(tools.registry()) == set(TOOL_SPECS)


def test_attendance_pct(tools):
    r = tools.get_attendance("S1002", "Data Structures")
    assert r.success and r.output["attendance"][0]["attendance_pct"] == 77.5


def test_exactly_at_threshold_is_eligible(tools):
    r = tools.check_exam_eligibility("S1001", "CS201", NOW)
    assert r.output["result"] == "ELIGIBLE"
    assert r.applied_rule_ids == ["ATT-MIN-02"]
    assert r.output["rules"][0]["source_doc_id"] == "ACAD-CIRC-2026-08-SYN"


def test_one_class_below(tools):
    r = tools.check_exam_eligibility("S1002", "CS201", NOW)
    assert r.output["result"] == "NOT_ELIGIBLE"
    assert r.output["classes_needed_for_threshold"] == 32 and r.output["short_by_classes"] == 1


def test_rule_depends_on_as_of_date(tools):
    old = tools.check_exam_eligibility("S1010", "EE201", OLD)
    now = tools.check_exam_eligibility("S1010", "EE201", NOW)
    assert old.output["result"] == "ELIGIBLE" and old.applied_rule_ids == ["ATT-MIN-01"]
    assert old.output["upcoming_rules"][0]["rule_id"] == "ATT-MIN-02"
    assert now.output["result"] == "NOT_ELIGIBLE" and now.applied_rule_ids == ["ATT-MIN-02"]


def test_supplementary(tools):
    assert tools.check_supplementary_eligibility("S1003", "CS201", NOW).output["result"] == "ELIGIBLE"
    assert tools.check_supplementary_eligibility("S1004", "MA201", NOW).output["result"] == "ELIGIBLE"
    assert tools.check_supplementary_eligibility("S1005", "EE203", NOW).output["result"] == "NOT_ELIGIBLE"
    r = tools.check_supplementary_eligibility("S1009", "CS203", NOW)   # failed, then passed supplementary
    assert r.output["result"] == "NOT_REQUIRED" and r.applied_rule_ids == []


def test_placement_cutoff(tools):
    assert tools.check_placement_eligibility("S1007", NOW).output["result"] == "ELIGIBLE"
    assert tools.check_placement_eligibility("S1008", NOW).output["result"] == "NOT_ELIGIBLE"
    assert set(tools.check_placement_eligibility("S1007", NOW).applied_rule_ids) == {"PLC-CGPA-01", "PLC-BKLG-01"}


def test_what_if_pass_supplementary(tools):
    r = tools.run_what_if("S1003", {"pass_courses": ["Data Structures"]}, NOW)
    assert r.output["placement_before"]["result"] == "NOT_ELIGIBLE"
    assert r.output["result"] == "ELIGIBLE" and r.output["scenario_possible"]
    assert "SUPP-ELIG-01" in r.applied_rule_ids
    r = tools.run_what_if("S1006", {"pass_courses": "EE201"}, NOW)    # 3 backlogs -> 2
    assert r.output["result"] == "NOT_ELIGIBLE"
    assert r.output["placement_after"]["checks"][1]["value"] == 2


def test_what_if_detained_not_possible(tools):
    r = tools.run_what_if("S1005", {"pass_courses": ["EE203"]}, NOW)
    assert r.output["scenario_possible"] is False
    assert r.output["placement_after"]["checks"][1]["value"] == 1


def test_what_if_attendance_and_cgpa(tools):
    r = tools.run_what_if("S1002", {"classes_attended": {"CS201": 32}}, NOW)
    assert r.output["result"] == "ELIGIBLE"
    r = tools.run_what_if("S1008", '{"cgpa": 6.5}', NOW)              # JSON string from the LLM is fine
    assert r.output["result"] == "ELIGIBLE"
    r = tools.run_what_if("S1008", {"weather": "sunny"}, NOW)
    assert r.output["status"] == "clarification_needed"


def test_missing_or_unknown_course_asks_back(tools):
    for c in [None, "Quantum Basket Weaving", "Mathematics III"]:    # last one: name exists in both programmes? no
        r = tools.check_exam_eligibility("S1001", c, NOW)
        if c == "Mathematics III":
            assert r.success
        else:
            assert r.output["status"] == "clarification_needed" and len(r.output["options"]) == 3


def test_unknown_student(tools):
    r = tools.get_results("S0000")
    assert not r.success and r.output["status"] == "not_found"


def test_call_tool_ignores_student_id_in_args(tools):
    r = call_tool(tools, "get_attendance", "S1001", {"course": "CS201", "student_id": "S1002"}, NOW)
    assert r.inputs["student_id"] == "S1001"
    assert r.output["attendance"][0]["classes_attended"] == 32


def test_call_tool_without_identity_refuses(tools):
    r = call_tool(tools, "get_attendance", None, {"course_code": "CS201"}, NOW)
    assert r.output["status"] == "refused" and not r.success


def test_call_tool_unknown_tool_and_crash(tools, conn):
    assert call_tool(tools, "delete_everything", "S1001").output["status"] == "error"
    broken = UniversityTools(conn)
    broken.students = None
    r = call_tool(broken, "get_results", "S1001")
    assert r.output["status"] == "error"
