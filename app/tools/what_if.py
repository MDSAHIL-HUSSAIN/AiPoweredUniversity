import json
from fractions import Fraction

from app.repositories.rule_repository import check
from app.tools.common import done, fail, resolve_course, as_of_str, NOT_FOUND, ERROR, CLARIFY
from app.tools.eligibility import check_supplementary_eligibility, placement_check

NAME = "run_what_if"

# supported keys in `changes`
#   pass_courses:      ["CS201", ...]      student passes the supplementary / summer exam in these
#   cgpa:              7.25                assume this CGPA
#   active_backlogs:   0                   assume this many backlogs (overrides pass_courses)
#   classes_attended:  {"CS201": 34}       assume this many classes attended (classes held unchanged)
KNOWN = ["pass_courses", "cgpa", "active_backlogs", "classes_attended"]


def clean_changes(changes):
    if changes is None:
        return {}
    if isinstance(changes, str):
        try:
            changes = json.loads(changes)
        except ValueError:
            return {"_bad": changes}
    changes = dict(changes)
    # small aliases the router LLM tends to use
    if "pass_course" in changes and "pass_courses" not in changes:
        changes["pass_courses"] = changes.pop("pass_course")
    if isinstance(changes.get("pass_courses"), str):
        changes["pass_courses"] = [changes["pass_courses"]]
    return changes


def run_what_if(students, rules, student_id, changes, as_of_date=None):
    as_of = as_of_str(as_of_date)
    changes = clean_changes(changes)
    inputs = {"student_id": student_id, "changes": changes, "as_of_date": as_of}
    st = students.get_student(student_id)
    if st is None:
        return fail(NAME, inputs, NOT_FOUND, "student not found")

    applied = {}
    ignored = []
    for k in changes:
        if k in KNOWN:
            applied[k] = changes[k]
        else:
            ignored.append(k)
    if len(applied) == 0:
        return fail(NAME, inputs, CLARIFY, "What should change in the scenario? Supported: " + ", ".join(KNOWN),
                    {"options": KNOWN})

    assumptions = []
    used_rules = []
    possible = True

    # 1. supplementary passes -> fewer backlogs
    backlogs = st["active_backlogs"]
    supp_checks = []
    for course in applied.get("pass_courses", []) or []:
        s = check_supplementary_eligibility(students, rules, student_id, course, as_of)
        if s.output["status"] == CLARIFY:
            return fail(NAME, inputs, CLARIFY, s.output["message"], {"options": s.output.get("options", [])})
        if not s.success:
            return fail(NAME, inputs, s.output["status"], s.output.get("message", "supplementary check failed"))
        supp_checks.append(s.output)
        if len(s.applied_rule_ids) > 0:
            used_rules.append(rules.get_rule("supp_allowed_results", st["programme"], st["batch_year"], as_of)["rule"])
        code = s.output["course_code"]
        if s.output["result"] == "NOT_REQUIRED":
            assumptions.append(code + " is already passed, so nothing changes for it")
        elif s.output["result"] == "NOT_ELIGIBLE":
            possible = False
            assumptions.append("Scenario not possible for " + code + ": latest result is "
                               + s.output["latest_result"] + ", which does not allow the supplementary exam")
        else:
            backlogs = max(0, backlogs - 1)
            assumptions.append("Student passes the supplementary exam in " + code)
    if "pass_courses" in applied and backlogs != st["active_backlogs"]:
        assumptions.append("Active backlogs go from " + str(st["active_backlogs"]) + " to " + str(backlogs))

    if "active_backlogs" in applied:
        backlogs = int(applied["active_backlogs"])
        assumptions.append("Active backlogs assumed to be " + str(backlogs))

    cgpa = st["cgpa"]
    if "cgpa" in applied:
        cgpa = float(applied["cgpa"])
        assumptions.append("CGPA assumed to be " + str(cgpa))
    elif "pass_courses" in applied:
        assumptions.append("CGPA kept at " + str(st["cgpa"]) + ": grade points are not in the data, "
                           "so the CGPA change after passing is not modelled")

    # 2. placement before / after
    before, r_before = placement_check(students, rules, st, as_of)
    after, r_after = placement_check(students, rules, st, as_of, cgpa=cgpa, backlogs=backlogs)
    if before is None:
        return fail(NAME, inputs, ERROR, r_before)
    used_rules += r_after

    # 3. attendance changes -> exam eligibility after
    exam_after = []
    for course, attended in (applied.get("classes_attended") or {}).items():
        c = students.find_course(st, course)
        if c is None:
            return fail(NAME, inputs, CLARIFY, "Could not match course '" + str(course) + "'",
                        {"options": [x["course_code"] for x in students.courses_for(st["programme"])]})
        rows = students.attendance(student_id, c["course_code"])
        if len(rows) == 0:
            return fail(NAME, inputs, NOT_FOUND, "no attendance record for " + c["course_code"])
        held = rows[0]["classes_held"]
        attended = int(attended)
        r = rules.get_rule("min_attendance_pct", st["programme"], st["batch_year"], as_of)["rule"]
        if r is None:
            return fail(NAME, inputs, ERROR, "no attendance rule effective on " + as_of)
        if attended > held:
            assumptions.append(c["course_code"] + ": " + str(attended) + " attended is more than the "
                               + str(held) + " classes held, capped at " + str(held))
            attended = held
        pct = Fraction(attended * 100, held)
        exam_after.append({"course_code": c["course_code"], "classes_held": held,
                           "classes_attended_before": rows[0]["classes_attended"],
                           "classes_attended_after": attended, "attendance_pct_after": round(float(pct), 2),
                           "threshold": r["operator"] + " " + r["value"] + "%",
                           "result": "ELIGIBLE" if check(pct, r["operator"], r["value"]) else "NOT_ELIGIBLE"})
        assumptions.append("Classes held in " + c["course_code"] + " stay at " + str(held))
        used_rules.append(r)

    if len(applied) == 1 and "classes_attended" in applied and len(exam_after) == 1:
        result = exam_after[0]["result"]
    else:
        result = after["result"]

    out = {
        "check": "what_if",
        "result": result,
        "scenario_possible": possible,
        "changes_applied": applied,
        "ignored_changes": ignored,
        "placement_before": before,
        "placement_after": after,
        "supplementary_checks": supp_checks,
        "exam_eligibility_after": exam_after,
        "assumptions": assumptions,
        "as_of_date": as_of,
    }
    return done(NAME, inputs, out, used_rules)
