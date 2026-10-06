"""Deterministic tools (Member 1). The LLM never calculates attendance or eligibility.

    from app.repositories.db import get_conn
    from app.tools import UniversityTools, call_tool

    tools = UniversityTools(get_conn())
    res = tools.check_exam_eligibility("S1001", "CS201", date(2026, 10, 6))   # -> ToolResult
    res = call_tool(tools, "check_exam_eligibility", header_student_id, router_args, as_of_date)
"""
import time

from app.contracts.tools import ToolResult
from app.repositories.rule_repository import RuleRepository
from app.repositories.student_repository import StudentRepository
from app.tools import attendance, results, eligibility, what_if


class UniversityTools:
    def __init__(self, conn):
        self.conn = conn
        self.students = StudentRepository(conn)
        self.rules = RuleRepository(conn)

    def get_attendance(self, student_id, course_code=None):
        return attendance.get_attendance(self.students, student_id, course_code)

    def get_results(self, student_id, course_code=None):
        return results.get_results(self.students, student_id, course_code)

    def check_exam_eligibility(self, student_id, course_code, as_of_date=None):
        return eligibility.check_exam_eligibility(self.students, self.rules, student_id, course_code, as_of_date)

    def check_supplementary_eligibility(self, student_id, course_code, as_of_date=None):
        return eligibility.check_supplementary_eligibility(self.students, self.rules, student_id, course_code, as_of_date)

    def check_placement_eligibility(self, student_id, as_of_date=None):
        return eligibility.check_placement_eligibility(self.students, self.rules, student_id, as_of_date)

    def run_what_if(self, student_id, changes, as_of_date=None):
        return what_if.run_what_if(self.students, self.rules, student_id, changes, as_of_date)

    def registry(self):
        reg = {}
        for name in TOOL_SPECS:
            reg[name] = getattr(self, name)
        return reg


# for the router prompt: what each tool does and which args the LLM may fill.
# student_id and as_of_date are never LLM args - they come from the header and the request
TOOL_SPECS = {
    "get_attendance": {
        "description": "Attendance (classes held/attended, %) of the logged-in student, one course or all.",
        "args": {"course_code": "course code or name, optional"},
    },
    "get_results": {
        "description": "Exam results, CGPA and active backlogs of the logged-in student.",
        "args": {"course_code": "course code or name, optional"},
    },
    "check_exam_eligibility": {
        "description": "Can the logged-in student appear in the end-semester exam of a course (attendance rule).",
        "args": {"course_code": "course code or name, required"},
    },
    "check_supplementary_eligibility": {
        "description": "Can the logged-in student take the supplementary / summer semester exam in a course.",
        "args": {"course_code": "course code or name, required"},
    },
    "check_placement_eligibility": {
        "description": "Can the logged-in student register for campus placement (CGPA and backlog rules).",
        "args": {},
    },
    "run_what_if": {
        "description": "Eligibility in a hypothetical scenario, e.g. after passing a supplementary exam.",
        "args": {"changes": "object with any of: pass_courses [list], cgpa (number), active_backlogs (int), "
                            "classes_attended {course: int}"},
    },
}

TAKES_AS_OF = ["check_exam_eligibility", "check_supplementary_eligibility",
               "check_placement_eligibility", "run_what_if"]


def call_tool(tools, name, student_id, args=None, as_of_date=None):
    # safe entry point for the graph: student_id comes from the trusted header, never from args
    args = dict(args or {})
    if "course" in args and "course_code" not in args:
        args["course_code"] = args.pop("course")
    if name not in TOOL_SPECS:
        return ToolResult(tool_name=name, success=False, inputs=args,
                          output={"status": "error", "message": "unknown tool " + name},
                          applied_rule_ids=[], error="unknown tool " + name)
    if not student_id:
        return ToolResult(tool_name=name, success=False, inputs=args,
                          output={"status": "refused", "message": "no student identity in request"},
                          applied_rule_ids=[], error="no student identity in request")
    clean = {}
    for k in TOOL_SPECS[name]["args"]:
        if k in args:
            clean[k] = args[k]
    if name == "run_what_if" and "changes" not in clean:
        clean["changes"] = {}
    if name in TAKES_AS_OF:
        clean["as_of_date"] = as_of_date
    start = time.time()
    try:
        res = getattr(tools, name)(student_id, **clean)
    except Exception as e:   # a tool bug must not crash the graph
        res = ToolResult(tool_name=name, success=False, inputs={"student_id": student_id, **clean},
                         output={"status": "error", "message": str(e)}, applied_rule_ids=[], error=str(e))
    res.output["elapsed_ms"] = round((time.time() - start) * 1000, 2)
    return res
