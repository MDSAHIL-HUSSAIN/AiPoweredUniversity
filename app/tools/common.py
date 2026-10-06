from app.contracts.tools import ToolResult
from app.repositories.rule_repository import iso, rule_info

# output["status"] is always one of these, so the graph can branch without reading error text
OK = "ok"
NOT_FOUND = "not_found"
CLARIFY = "clarification_needed"
ERROR = "error"


def done(name, inputs, output, rules=None):
    # build a ToolResult. rules = list of rule rows that decided the answer
    ids = []
    infos = []
    for r in rules or []:
        if r is None:
            continue
        if r["rule_id"] not in ids:
            ids.append(r["rule_id"])
            infos.append(rule_info(r))
    output = dict(output)
    output.setdefault("status", OK)
    if len(infos) > 0:
        output["rules"] = infos      # source_doc_id + source_section for citations
    return ToolResult(tool_name=name, success=output["status"] == OK, inputs=inputs,
                      output=output, applied_rule_ids=ids, error=None)


def fail(name, inputs, status, msg, extra=None):
    output = {"status": status, "message": msg}
    if extra:
        output.update(extra)
    return ToolResult(tool_name=name, success=False, inputs=inputs, output=output,
                      applied_rule_ids=[], error=msg)


def resolve_course(students, name, inputs, student, course_code):
    # returns (course, None) or (None, ToolResult asking which course)
    c = students.find_course(student, course_code)
    if c is not None:
        return c, None
    options = []
    for x in students.courses_for(student["programme"]):
        options.append(x["course_code"] + " - " + x["course_name"])
    if course_code:
        msg = "Could not match course '" + str(course_code) + "'. Which course do you mean?"
    else:
        msg = "Which course do you mean?"
    return None, fail(name, inputs, CLARIFY, msg, {"options": options})


def as_of_str(as_of_date):
    return iso(as_of_date)
