# Deterministic test students (no LLM) so the graph/API can be built and tested before the Ollama run.
# Same IDs and edge cases as the generated data (S1001-S1010), plus 6 plain students.
# Thresholds are read from the rule registry, so a rule change flows into the fixture too.
import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.repositories.db import get_conn, TABLE_COLUMNS
from app.repositories.rule_repository import RuleRepository
from scripts.generate_students import COURSES, write_csv, thresholds

PROG = {"B.Tech CSE": ["CS201", "CS203", "MA201"], "B.Tech EE": ["EE201", "EE203", "MA203"]}
NAMES = ["Aarav Mehta", "Ishita Rao", "Kabir Sethi", "Ananya Iyer", "Rohan Bhatia", "Meera Pillai",
         "Vivaan Kapoor", "Diya Malhotra", "Arjun Nair", "Sanya Gupta", "Kunal Joshi", "Tara Menon",
         "Nikhil Arora", "Pooja Reddy", "Yash Chawla", "Neha Saxena"]


def res(total, result="PASS", exam_type="REGULAR", session="2026-MAY", external=None):
    if external is None:
        internal = min(30, total // 2)
        external = total - internal
    else:
        internal = total - external
    return {"exam_session": session, "exam_type": exam_type, "internal_marks": internal,
            "external_marks": external, "total_marks": internal + external, "max_marks": 100, "result": result}


def build(th):
    students = []

    def stu(i, sid, prog, batch, cgpa, backlogs, special=None):
        special = special or {}
        recs = {}
        for c in PROG[prog]:
            recs[c] = special.get(c, (38 - (i % 3), [res(62 + (i * 7) % 25)]))
        students.append({"student_id": sid, "full_name": NAMES[i], "programme": prog, "batch_year": batch,
                         "current_semester": 7 if batch == 2023 else 5, "cgpa": cgpa,
                         "active_backlogs": backlogs, "records": recs})

    fail_t = th["fail_total"]
    stu(0, "S1001", "B.Tech CSE", 2024, 8.02, 0, {"CS201": (th["now_need"], [res(71)])})
    stu(1, "S1002", "B.Tech CSE", 2024, 7.40, 0, {"CS201": (th["now_one_below"], [res(66)])})
    stu(2, "S1003", "B.Tech CSE", 2024, 7.10, 1, {"CS201": (37, [res(fail_t, "FAIL")])})
    stu(3, "S1004", "B.Tech CSE", 2023, 7.30, 1, {"MA201": (36, [res(25, "ABSENT", external=0)])})
    stu(4, "S1005", "B.Tech EE", 2024, 6.90, 1, {"EE203": (24, [res(15, "DETAINED", external=0)])})
    stu(5, "S1006", "B.Tech EE", 2023, 5.40, 3, {c: (35, [res(24 + k * 4, "FAIL")]) for k, c in enumerate(PROG["B.Tech EE"])})
    stu(6, "S1007", "B.Tech CSE", 2023, float(th["cgpa_cut"]), 0)
    stu(7, "S1008", "B.Tech EE", 2024, float(th["cgpa_below"]), 0)
    stu(8, "S1009", "B.Tech CSE", 2023, 7.60, 0,
        {"CS203": (36, [res(30, "FAIL"), res(50, "PASS", "SUPPLEMENTARY", "2026-JUL")])})
    stu(9, "S1010", "B.Tech EE", 2023, 7.00, 0, {"EE201": (th["old_need"], [res(70)])})
    plain = [("B.Tech CSE", 2024, 8.85), ("B.Tech CSE", 2023, 6.95), ("B.Tech EE", 2024, 9.12),
             ("B.Tech EE", 2023, 7.75), ("B.Tech CSE", 2024, 5.95), ("B.Tech EE", 2024, 8.10)]
    for k, (prog, batch, cg) in enumerate(plain):
        stu(10 + k, "S" + str(1011 + k), prog, batch, cg, 0)
    return students


def flatten(students):
    t = {"students": [], "attendance": [], "results": []}
    for s in students:
        row = {}
        for k in TABLE_COLUMNS["students"]:
            row[k] = s[k]
        row["cgpa"] = "%.2f" % s["cgpa"]
        t["students"].append(row)
        for code in s["records"]:
            att, rs = s["records"][code]
            t["attendance"].append({"student_id": s["student_id"], "course_code": code,
                                    "classes_held": 40, "classes_attended": att})
            for r in rs:
                x = {"student_id": s["student_id"], "course_code": code}
                x.update(r)
                t["results"].append(x)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/fixtures")
    ap.add_argument("--rules-csv", default="data/rule_registry.csv")
    args = ap.parse_args()
    conn = get_conn(":memory:")
    RuleRepository(conn).load_csv(args.rules_csv)
    t = flatten(build(thresholds(conn)))
    os.makedirs(args.out, exist_ok=True)
    write_csv(os.path.join(args.out, "courses.csv"), TABLE_COLUMNS["courses"], COURSES)
    for name in t:
        write_csv(os.path.join(args.out, name + ".csv"), TABLE_COLUMNS[name], t[name])
    print("wrote", len(t["students"]), "students to", args.out)


if __name__ == "__main__":
    main()
