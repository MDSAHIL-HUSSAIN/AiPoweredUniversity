# Offline check of the deterministic layer: calls the expected tool of every personal question straight
# against the DB (no API, no LLM). If this fails the full evaluation cannot pass either.
# Also writes expected_tool_outputs.json for Member 3's workflow tests (fake tools can replay it).
import argparse
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tools import UniversityTools, call_tool
from scripts.seed_test_db import build_test_conn
from app.repositories.db import get_conn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="existing DB; default = fresh in-memory DB with fixture students")
    ap.add_argument("--students", default=None, help="student CSV folder for the in-memory DB")
    ap.add_argument("--set", default="evaluations/questions.json")
    ap.add_argument("--save", default="evaluations/expected_tool_outputs.json")
    args = ap.parse_args()

    if args.db:
        conn = get_conn(args.db)
    else:
        conn, _ = build_test_conn(":memory:", args.students)
    tools = UniversityTools(conn)
    with open(args.set, encoding="utf-8") as f:
        qs = json.load(f)["questions"]

    n = ok = 0
    saved = {}
    for q in qs:
        et = q.get("expected_tool")
        if not et:
            continue
        n += 1
        res = call_tool(tools, et["name"], q["student_id"], et.get("args", {}), q["as_of_date"])
        o = res.output
        probs = []
        if not res.success:
            probs.append("status " + str(o.get("status")) + " " + str(o.get("message")))
        if "result" in et and o.get("result") != et["result"]:
            probs.append("result " + str(o.get("result")) + " != " + et["result"])
        docs = set()
        for r in o.get("rules", []):
            docs.add(r["source_doc_id"])
        for d in q.get("expected_doc_ids", []):
            if d not in docs:
                probs.append("rule source " + d + " not used (got " + ", ".join(sorted(docs)) + ")")
        if len(probs) == 0:
            ok += 1
        d = res.model_dump(mode="json")
        d["output"].pop("elapsed_ms", None)
        saved[q["id"]] = {"student_id": q["student_id"], "as_of_date": q["as_of_date"], "tool_result": d}
        print(q["id"], q["student_id"], et["name"], "->", o.get("result"), "OK" if not probs else "FAIL: " + "; ".join(probs))

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump(saved, f, indent=2)
    print()
    print("tool checks passed:", ok, "/", n)
    if ok != n:
        sys.exit(1)


if __name__ == "__main__":
    main()
