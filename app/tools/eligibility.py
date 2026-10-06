from fractions import Fraction

from app.repositories.rule_repository import check, rule_info
from app.tools.common import done, fail, resolve_course, as_of_str, NOT_FOUND, ERROR


def check_exam_eligibility(students, rules, student_id, course_code, as_of_date=None):
    name = "check_exam_eligibility"
    as_of = as_of_str(as_of_date)
    inputs = {"student_id": student_id, "course_code": course_code, "as_of_date": as_of}
    st = students.get_student(student_id)
    if st is None:
        return fail(name, inputs, NOT_FOUND, "student not found")
    c, ask = resolve_course(students, name, inputs, st, course_code)
    if ask:
        return ask

    rows = students.attendance(student_id, c["course_code"])
    if len(rows) == 0:
        return fail(name, inputs, NOT_FOUND, "no attendance record for " + c["course_code"])
    a = rows[0]

    found = rules.get_rule("min_attendance_pct", st["programme"], st["batch_year"], as_of)
    r = found["rule"]
    if r is None:
        return fail(name, inputs, ERROR, "no attendance rule effective on " + as_of)

    held = a["classes_held"]
    att = a["classes_attended"]
    pct = Fraction(att * 100, held)
    ok = check(pct, r["operator"], r["value"])

    out = {
        "check": "end_sem_exam_eligibility",
        "course_code": c["course_code"],
        "course_name": c["course_name"],
        "classes_held": held,
        "classes_attended": att,
        "attendance_pct": round(float(pct), 2),
        "threshold": r["operator"] + " " + r["value"] + "%",
        "result": "ELIGIBLE" if ok else "NOT_ELIGIBLE",
        "as_of_date": as_of,
    }
    if not ok:
        # smallest number of attended classes (out of the classes held so far) that meets the rule
        need = 0
        while need <= held and not check(Fraction(need * 100, held), r["operator"], r["value"]):
            need += 1
        out["classes_needed_for_threshold"] = need
        out["short_by_classes"] = need - att
    if len(found["upcoming"]) > 0:
        out["upcoming_rules"] = [rule_info(u) for u in found["upcoming"]]
    if len(found["conflicts"]) > 0:
        out["conflicting_rules"] = [rule_info(x) for x in found["conflicts"]]
    return done(name, inputs, out, [r])


def check_supplementary_eligibility(students, rules, student_id, course_code, as_of_date=None):
    # NSUT documents call this the summer semester / backlog exam
    name = "check_supplementary_eligibility"
    as_of = as_of_str(as_of_date)
    inputs = {"student_id": student_id, "course_code": course_code, "as_of_date": as_of}
    st = students.get_student(student_id)
    if st is None:
        return fail(name, inputs, NOT_FOUND, "student not found")
    c, ask = resolve_course(students, name, inputs, st, course_code)
    if ask:
        return ask

    last = students.latest_result(student_id, c["course_code"])
    if last is None:
        return fail(name, inputs, NOT_FOUND, "no result found for " + c["course_code"])

    out = {
        "check": "supplementary_eligibility",
        "course_code": c["course_code"],
        "course_name": c["course_name"],
        "latest_result": last["result"],
        "latest_session": last["exam_session"],
        "latest_exam_type": last["exam_type"],
        "as_of_date": as_of,
    }
    if last["result"] == "PASS":
        out["result"] = "NOT_REQUIRED"
        return done(name, inputs, out)

    r = rules.get_rule("supp_allowed_results", st["programme"], st["batch_year"], as_of)["rule"]
    if r is None:
        return fail(name, inputs, ERROR, "no supplementary rule effective on " + as_of)
    ok = check(last["result"], r["operator"], r["value"])
    out["result"] = "ELIGIBLE" if ok else "NOT_ELIGIBLE"
    out["allowed_results"] = r["value"].split(";")
    return done(name, inputs, out, [r])


def placement_check(students, rules, st, as_of, cgpa=None, backlogs=None):
    # shared by check_placement_eligibility and run_what_if. returns (output dict, rules) or (None, msg)
    if cgpa is None:
        cgpa = st["cgpa"]
    if backlogs is None:
        backlogs = st["active_backlogs"]
    r1 = rules.get_rule("min_placement_cgpa", st["programme"], st["batch_year"], as_of)["rule"]
    r2 = rules.get_rule("max_active_backlogs", st["programme"], st["batch_year"], as_of)["rule"]
    if r1 is None or r2 is None:
        return None, "placement rules not found for " + as_of
    ok1 = check(cgpa, r1["operator"], r1["value"])
    ok2 = check(backlogs, r2["operator"], r2["value"])
    out = {
        "check": "placement_eligibility",
        "result": "ELIGIBLE" if (ok1 and ok2) else "NOT_ELIGIBLE",
        "checks": [
            {"parameter": "cgpa", "value": cgpa, "required": r1["operator"] + " " + r1["value"],
             "passed": ok1, "rule_id": r1["rule_id"]},
            {"parameter": "active_backlogs", "value": backlogs, "required": r2["operator"] + " " + r2["value"],
             "passed": ok2, "rule_id": r2["rule_id"]},
        ],
        "as_of_date": as_of,
    }
    return out, [r1, r2]


def check_placement_eligibility(students, rules, student_id, as_of_date=None):
    name = "check_placement_eligibility"
    as_of = as_of_str(as_of_date)
    inputs = {"student_id": student_id, "as_of_date": as_of}
    st = students.get_student(student_id)
    if st is None:
        return fail(name, inputs, NOT_FOUND, "student not found")
    out, used = placement_check(students, rules, st, as_of)
    if out is None:
        return fail(name, inputs, ERROR, used)
    return done(name, inputs, out, used)
