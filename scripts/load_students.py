import argparse
import os
import sys
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.repositories.db import get_conn, SQLITE_PATH, TABLE_COLUMNS, row_key
from scripts.validate_data import read_dir, read_db, validate, ORDER, to_int, to_float

INT_COLS = ["batch_year", "current_semester", "active_backlogs", "semester", "credits",
            "classes_held", "classes_attended", "internal_marks", "external_marks",
            "total_marks", "max_marks"]


def convert(col, v):
    if v == "":
        return None
    if col in INT_COLS:
        return to_int(v)
    if col == "cgpa":
        return to_float(v)
    if col in ["exam_type", "result"]:
        return v.upper()
    return v


def load_dir(conn, folder):
    new = read_dir(folder)
    old = read_db(conn)

    # validate new rows together with what is already in the DB (so FKs to existing rows work)
    merged = {}
    for t in ORDER:
        rows = {}
        for r in old[t]:
            rows[row_key(t, r)] = r
        for r in new[t]:
            rows[row_key(t, r)] = r
        merged[t] = list(rows.values())

    issues = validate(merged, conn, own=False, as_of=date.today().isoformat())

    new_keys = {}
    for t in ORDER:
        new_keys[t] = set()
        for r in new[t]:
            new_keys[t].add(row_key(t, r))

    skip = {}
    for t in ORDER:
        skip[t] = set()
    report_issues = []
    for i in issues:
        if i["key"] == "*" or i["key"] in new_keys[i["table"]]:
            report_issues.append(i)
            if i["severity"] == "error":
                skip[i["table"]].add(i["key"])

    loaded = {}
    for t in ORDER:
        cols = TABLE_COLUMNS[t]
        cnt = 0
        for r in new[t]:
            if row_key(t, r) in skip[t]:
                continue
            vals = []
            for c in cols:
                vals.append(convert(c, r.get(c, "")))
            q = "INSERT OR REPLACE INTO " + t + " (" + ",".join(cols) + ") VALUES (" + ",".join(["?"] * len(cols)) + ")"
            try:
                conn.execute(q, vals)
                cnt += 1
            except Exception as e:
                report_issues.append({"severity": "error", "table": t, "key": row_key(t, r), "msg": str(e)})
        loaded[t] = cnt
    conn.commit()

    skipped = {}
    for t in ORDER:
        skipped[t] = len(new[t]) - loaded[t]
    return {"loaded": loaded, "skipped": skipped, "issues": report_issues}


def main():
    ap = argparse.ArgumentParser(description="Load student CSVs (Annex C schema) into SQLite")
    ap.add_argument("--dir", required=True, help="folder with students.csv, courses.csv, attendance.csv, results.csv (any subset)")
    ap.add_argument("--db", default=SQLITE_PATH)
    args = ap.parse_args()

    if not os.path.isdir(args.dir):
        print("folder not found:", args.dir)
        sys.exit(1)

    conn = get_conn(args.db)
    rep = load_dir(conn, args.dir)

    print("loaded:", rep["loaded"])
    print("skipped:", rep["skipped"])
    for i in rep["issues"]:
        print(" [" + i["severity"] + "] " + i["table"] + " " + i["key"] + ": " + i["msg"])
    print("rows with only violations/warnings are still loaded; only errors are skipped")


if __name__ == "__main__":
    main()
