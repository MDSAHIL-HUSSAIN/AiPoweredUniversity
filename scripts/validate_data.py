import argparse
import csv
import json
import math
import os
import re
import sys
from datetime import date, timedelta
from fractions import Fraction

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.repositories.db import get_conn, TABLE_COLUMNS, row_key
from app.repositories.rule_repository import RuleRepository, session_date

ORDER = ["courses", "students", "attendance", "results"]
BAD = ["FAIL", "ABSENT", "DETAINED"]


def read_dir(folder):
    tables = {}
    for t in ORDER:
        path = os.path.join(folder, t + ".csv")
        rows = []
        if os.path.exists(path):
            with open(path, newline="", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    clean = {}
                    for k in r:
                        if k is None:
                            continue
                        v = r[k]
                        if v is None:
                            v = ""
                        clean[k.strip()] = v.strip()
                    rows.append(clean)
        tables[t] = rows
    return tables


def read_db(conn):
    tables = {}
    for t in ORDER:
        rows = []
        for r in conn.execute("SELECT * FROM " + t).fetchall():
            d = {}
            for k in r.keys():
                if r[k] is None:
                    d[k] = ""
                else:
                    d[k] = str(r[k])
            rows.append(d)
        tables[t] = rows
    return tables


def to_int(x):
    try:
        s = str(x).strip()
        if "." in s:
            f = float(s)
            if f != int(f):
                return None
            return int(f)
        return int(s)
    except (ValueError, TypeError):
        return None


def to_float(x):
    try:
        return float(str(x).strip())
    except (ValueError, TypeError):
        return None


def rule_value(conn, param, programme, batch, as_of):
    r = RuleRepository(conn).get_rule(param, programme, batch, as_of)["rule"]
    if r is None:
        return None
    return r["value"]


def validate(tables, conn, own=False, as_of=None):
    # severity: error = row can't be loaded, violation = logical rule broken, warning = looks odd
    if as_of is None:
        as_of = date.today().isoformat()
    issues = []

    def add(sev, table, row, msg):
        issues.append({"severity": sev, "table": table, "key": row_key(table, row), "msg": msg})

    for t in ORDER:
        if len(tables.get(t, [])) == 0:
            continue
        cols = tables[t][0].keys()
        for c in TABLE_COLUMNS[t]:
            if c not in cols:
                issues.append({"severity": "error", "table": t, "key": "*", "msg": "missing column " + c})

    courses = {}
    students = {}
    programmes = set()

    for r in tables.get("students", []):
        sid = r.get("student_id", "")
        if not re.match(r"^S\d{4}$", sid):
            add("error", "students", r, "student_id must be S + 4 digits")
            continue
        if sid in students:
            add("error", "students", r, "duplicate student_id")
            continue
        if own and 9000 <= int(sid[1:]) <= 9999:
            add("violation", "students", r, "S9000-S9999 is reserved for judges")
        if r.get("full_name", "") == "":
            add("error", "students", r, "full_name empty")
        if r.get("programme", "") == "":
            add("error", "students", r, "programme empty")
        b = to_int(r.get("batch_year"))
        if b is None:
            add("error", "students", r, "batch_year not an integer")
        elif b < 2000 or b > 2035:
            add("warning", "students", r, "batch_year looks wrong: " + str(b))
        sem = to_int(r.get("current_semester"))
        if sem is None:
            add("error", "students", r, "current_semester not an integer")
        elif sem < 1 or sem > 10:
            add("violation", "students", r, "current_semester must be 1-10")
        cg = to_float(r.get("cgpa"))
        if cg is None:
            add("error", "students", r, "cgpa not a number")
        elif cg < 0 or cg > 10:
            add("violation", "students", r, "cgpa must be 0.00-10.00")
        bl = to_int(r.get("active_backlogs"))
        if bl is None:
            add("error", "students", r, "active_backlogs not an integer")
        elif bl < 0:
            add("violation", "students", r, "active_backlogs must be >= 0")
        students[sid] = r
        programmes.add(r.get("programme", ""))

    for r in tables.get("courses", []):
        code = r.get("course_code", "")
        if code == "":
            add("error", "courses", r, "course_code empty")
            continue
        if code in courses:
            add("error", "courses", r, "duplicate course_code")
            continue
        if own and code.upper().startswith("JDG"):
            add("violation", "courses", r, "JDG course codes are reserved for judges")
        if r.get("course_name", "") == "":
            add("error", "courses", r, "course_name empty")
        if r.get("programme", "") == "":
            add("error", "courses", r, "programme empty")
        elif len(programmes) > 0 and r["programme"] not in programmes:
            add("warning", "courses", r, "programme '" + r["programme"] + "' not used by any student")
        cr = to_int(r.get("credits"))
        if r.get("credits", "") != "" and (cr is None or cr <= 0):
            add("warning", "courses", r, "credits should be a positive integer")
        courses[code] = r

    att = {}
    for r in tables.get("attendance", []):
        sid = r.get("student_id", "")
        code = r.get("course_code", "")
        if sid not in students:
            add("error", "attendance", r, "unknown student_id " + sid)
            continue
        if code not in courses:
            add("error", "attendance", r, "unknown course_code " + code)
            continue
        k = sid + "|" + code
        if k in att:
            add("error", "attendance", r, "duplicate (student_id, course_code)")
            continue
        held = to_int(r.get("classes_held"))
        got = to_int(r.get("classes_attended"))
        if held is None or got is None:
            add("error", "attendance", r, "classes_held / classes_attended must be integers")
            continue
        if held <= 0:
            add("violation", "attendance", r, "classes_held must be > 0")
        if got < 0 or got > held:
            add("violation", "attendance", r, "need 0 <= classes_attended <= classes_held, got "
                + str(got) + "/" + str(held))
        if courses[code]["programme"] != students[sid]["programme"]:
            add("warning", "attendance", r, "course programme differs from student programme")
        att[k] = (got, held)

    latest = {}
    seen = set()
    for r in tables.get("results", []):
        sid = r.get("student_id", "")
        code = r.get("course_code", "")
        if sid not in students:
            add("error", "results", r, "unknown student_id " + sid)
            continue
        if code not in courses:
            add("error", "results", r, "unknown course_code " + code)
            continue
        k = row_key("results", r)
        if k in seen:
            add("error", "results", r, "duplicate result row")
            continue
        seen.add(k)

        et = r.get("exam_type", "").upper()
        res = r.get("result", "").upper()
        if et not in ["REGULAR", "SUPPLEMENTARY"]:
            add("error", "results", r, "exam_type must be REGULAR or SUPPLEMENTARY")
            continue
        if res not in ["PASS", "FAIL", "ABSENT", "DETAINED"]:
            add("error", "results", r, "result must be PASS, FAIL, ABSENT or DETAINED")
            continue
        sdate = session_date(r.get("exam_session"))
        if sdate is None:
            add("error", "results", r, "exam_session must look like 2026-MAY")
            continue

        im = to_int(r.get("internal_marks"))
        em = to_int(r.get("external_marks"))
        tm = to_int(r.get("total_marks"))
        mx = to_int(r.get("max_marks"))
        if im is None or em is None or tm is None or mx is None:
            add("error", "results", r, "marks must be integers")
            continue
        if im < 0 or em < 0:
            add("violation", "results", r, "marks cannot be negative")
        if mx <= 0:
            add("violation", "results", r, "max_marks must be > 0")
            continue
        if tm != im + em:
            add("violation", "results", r, "total_marks " + str(tm) + " != internal + external ("
                + str(im + em) + ")")
        if tm > mx:
            add("violation", "results", r, "total_marks above max_marks")

        st = students[sid]
        pass_pct = rule_value(conn, "min_pass_pct", st["programme"], st["batch_year"], sdate)
        if pass_pct is not None:
            passed = Fraction(tm * 100, mx) >= Fraction(pass_pct)
            if res == "PASS" and not passed:
                add("violation", "results", r, "result PASS but total below pass mark")
            if res == "FAIL" and passed:
                add("violation", "results", r, "result FAIL but total at/above pass mark")
        if res in ["ABSENT", "DETAINED"] and em != 0:
            add("violation", "results", r, res + " but external_marks is not 0")
        if et == "REGULAR" and (sid + "|" + code) in att:
            got, held = att[sid + "|" + code]
            need = rule_value(conn, "min_attendance_pct", st["programme"], st["batch_year"], sdate)
            if need is not None and held > 0:
                meets = Fraction(got * 100, held) >= Fraction(need)
                if res == "DETAINED" and meets:
                    add("violation", "results", r, "DETAINED but attendance meets the rule on " + sdate)
                if res != "DETAINED" and not meets:
                    # attendance below the rule on the exam date, yet the student sat the exam
                    add("violation" if own else "warning", "results", r,
                        "attendance " + str(got) + "/" + str(held) + " is below the rule on " + sdate
                        + " but result is " + res + ", expected DETAINED")

        order = sdate + ("-2" if et == "SUPPLEMENTARY" else "-1")
        lk = sid + "|" + code
        if lk not in latest or order > latest[lk][0]:
            latest[lk] = (order, res)

    for sid in students:
        bl = to_int(students[sid].get("active_backlogs"))
        if bl is None:
            continue
        cnt = 0
        has_results = False
        for lk in latest:
            if lk.split("|")[0] == sid:
                has_results = True
                if latest[lk][1] in BAD:
                    cnt += 1
        if has_results and cnt != bl:
            add("violation", "students", students[sid],
                "active_backlogs is " + str(bl) + " but results show " + str(cnt))

    return issues


def edge_cases(tables, conn, as_of=None):
    if as_of is None:
        as_of = date.today().isoformat()
    students = {}
    for r in tables.get("students", []):
        students[r["student_id"]] = r

    found = {
        "attendance_exactly_at_threshold": [],
        "attendance_one_class_below": [],
        "fail_just_below_pass_mark": [],
        "absent_result": [],
        "detained_student": [],
        "multiple_backlogs": [],
        "cgpa_exactly_at_placement_cutoff": [],
        "cgpa_just_below_placement_cutoff": [],
        "attendance_at_old_threshold_only": [],
        "failed_then_passed_supplementary": [],
    }

    for r in tables.get("attendance", []):
        st = students.get(r["student_id"])
        if st is None:
            continue
        need = rule_value(conn, "min_attendance_pct", st["programme"], st["batch_year"], as_of)
        got = to_int(r["classes_attended"])
        held = to_int(r["classes_held"])
        if need is None or got is None or not held:
            continue
        need = Fraction(need)
        tag = r["student_id"] + ":" + r["course_code"]
        cur = RuleRepository(conn).get_rule("min_attendance_pct", st["programme"], st["batch_year"], as_of)["rule"]
        if cur is not None:
            prev_day = (date.fromisoformat(cur["effective_from"]) - timedelta(days=1)).isoformat()
            old = rule_value(conn, "min_attendance_pct", st["programme"], st["batch_year"], prev_day)
            if old is not None and Fraction(old) < need and Fraction(got * 100, held) == Fraction(old):
                found["attendance_at_old_threshold_only"].append(tag)
        if Fraction(got * 100, held) == need:
            found["attendance_exactly_at_threshold"].append(tag)
        elif Fraction(got * 100, held) < need and Fraction((got + 1) * 100, held) >= need:
            found["attendance_one_class_below"].append(tag)

    for r in tables.get("results", []):
        st = students.get(r["student_id"])
        if st is None:
            continue
        tag = r["student_id"] + ":" + r["course_code"]
        res = r.get("result", "").upper()
        if res == "ABSENT":
            found["absent_result"].append(tag)
        if res == "DETAINED":
            found["detained_student"].append(tag)
        if res == "FAIL":
            sdate = session_date(r.get("exam_session")) or as_of
            p = rule_value(conn, "min_pass_pct", st["programme"], st["batch_year"], sdate)
            tm = to_int(r.get("total_marks"))
            mx = to_int(r.get("max_marks"))
            if p is not None and tm is not None and mx:
                pass_marks = math.ceil(Fraction(p) * mx / 100)
                if tm == pass_marks - 1:
                    found["fail_just_below_pass_mark"].append(tag)

    first_fail = set()
    for r in tables.get("results", []):
        if r.get("exam_type", "").upper() == "REGULAR" and r.get("result", "").upper() == "FAIL":
            first_fail.add(r["student_id"] + ":" + r["course_code"])
    for r in tables.get("results", []):
        tag = r["student_id"] + ":" + r["course_code"]
        if r.get("exam_type", "").upper() == "SUPPLEMENTARY" and r.get("result", "").upper() == "PASS" and tag in first_fail:
            found["failed_then_passed_supplementary"].append(tag)

    for sid in students:
        st = students[sid]
        bl = to_int(st.get("active_backlogs"))
        if bl is not None and bl >= 2:
            found["multiple_backlogs"].append(sid)
        cut = rule_value(conn, "min_placement_cgpa", st["programme"], st["batch_year"], as_of)
        cg = to_float(st.get("cgpa"))
        if cut is not None and cg is not None:
            if Fraction(str(cg)) == Fraction(cut):
                found["cgpa_exactly_at_placement_cutoff"].append(sid)
            elif Fraction(str(cg)) == Fraction(cut) - Fraction(1, 100):
                found["cgpa_just_below_placement_cutoff"].append(sid)
    return found


def stats(tables):
    s = {}
    groups = {}
    cg = []
    for r in tables.get("students", []):
        k = r.get("programme", "") + " / " + r.get("batch_year", "")
        groups[k] = groups.get(k, 0) + 1
        v = to_float(r.get("cgpa"))
        if v is not None:
            cg.append(v)
    s["students_total"] = len(tables.get("students", []))
    s["students_by_programme_batch"] = groups
    s["courses_total"] = len(tables.get("courses", []))
    if len(cg) > 0:
        s["cgpa_min_mean_max"] = [min(cg), round(sum(cg) / len(cg), 2), max(cg)]

    buckets = {"<60": 0, "60-74.99": 0, "75-79.99": 0, "80-89.99": 0, "90-100": 0}
    for r in tables.get("attendance", []):
        got = to_int(r.get("classes_attended"))
        held = to_int(r.get("classes_held"))
        if got is None or not held:
            continue
        p = got * 100 / held
        if p < 60:
            buckets["<60"] += 1
        elif p < 75:
            buckets["60-74.99"] += 1
        elif p < 80:
            buckets["75-79.99"] += 1
        elif p < 90:
            buckets["80-89.99"] += 1
        else:
            buckets["90-100"] += 1
    s["attendance_pct_distribution"] = buckets

    marks = {"<40": 0, "40-59": 0, "60-79": 0, "80-100": 0}
    res_cnt = {}
    for r in tables.get("results", []):
        res = r.get("result", "")
        res_cnt[res] = res_cnt.get(res, 0) + 1
        tm = to_int(r.get("total_marks"))
        if tm is None:
            continue
        if tm < 40:
            marks["<40"] += 1
        elif tm < 60:
            marks["40-59"] += 1
        elif tm < 80:
            marks["60-79"] += 1
        else:
            marks["80-100"] += 1
    s["total_marks_distribution"] = marks
    s["result_counts"] = res_cnt
    return s


def rules_conn(db, rules_csv):
    if db:
        return get_conn(db)
    conn = get_conn(":memory:")
    RuleRepository(conn).load_csv(rules_csv)
    return conn


def main():
    ap = argparse.ArgumentParser(description="Validate student data CSVs (Annex C schema)")
    ap.add_argument("--dir", default="data/synthetic")
    ap.add_argument("--db", default=None, help="read rules from this DB instead of the rules CSV")
    ap.add_argument("--rules-csv", default="data/rule_registry.csv")
    ap.add_argument("--own", action="store_true", help="our own data: also check reserved IDs and edge cases")
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    conn = rules_conn(args.db, args.rules_csv)
    tables = read_dir(args.dir)
    issues = validate(tables, conn, own=args.own, as_of=args.as_of)

    cnt = {"error": 0, "violation": 0, "warning": 0}
    for i in issues:
        cnt[i["severity"]] += 1

    report = {"dir": args.dir, "as_of_date": args.as_of, "counts": cnt, "issues": issues,
              "stats": stats(tables)}
    if args.own:
        report["edge_cases"] = edge_cases(tables, conn, args.as_of)

    print("rows:", {t: len(tables[t]) for t in ORDER})
    print("errors:", cnt["error"], " violations:", cnt["violation"], " warnings:", cnt["warning"])
    for i in issues:
        print(" [" + i["severity"] + "] " + i["table"] + " " + i["key"] + ": " + i["msg"])
    if args.own:
        print("edge cases:")
        for k in report["edge_cases"]:
            v = report["edge_cases"][k]
            print("  " + ("OK  " if len(v) > 0 else "MISSING ") + k + ": " + ", ".join(v))

    out = args.out
    if out is None:
        out = os.path.join(args.dir, "validation_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("report written to", out)

    if cnt["error"] > 0 or cnt["violation"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
