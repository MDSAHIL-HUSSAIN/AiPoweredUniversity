import argparse
import csv
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.repositories.db import get_conn, SQLITE_PATH
from app.repositories.rule_repository import RuleRepository, register_ids, check_rule


def main():
    ap = argparse.ArgumentParser(description="Load or update the rule registry")
    ap.add_argument("--db", default=SQLITE_PATH)
    ap.add_argument("--csv", default=None, help="load all rules from this CSV")
    ap.add_argument("--add", default=None, help="JSON file with one new rule")
    ap.add_argument("--supersedes", default=None, help="rule_id the new rule replaces")
    ap.add_argument("--register", default=os.getenv("SOURCE_REGISTER_PATH", "./data/source_register.csv"))
    args = ap.parse_args()

    conn = get_conn(args.db)
    docs = register_ids(args.register)
    if docs is None:
        print("note: source register not found at", args.register, "- skipping doc_id check")

    if args.csv:
        bad = False
        with open(args.csv, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                probs = check_rule(r, docs)
                for p in probs:
                    print(" ", r.get("rule_id"), ":", p)
                    if not p.startswith("WARNING"):
                        bad = True
        if bad:
            print("fix the problems above first")
            sys.exit(1)
        n = RuleRepository(conn).load_csv(args.csv)
        print("loaded", n, "rules")

    if args.add:
        with open(args.add, encoding="utf-8") as f:
            r = json.load(f)
        probs = check_rule(r, docs)
        for p in probs:
            print(" ", p)
        if any(not p.startswith("WARNING") for p in probs):
            print("fix the problems above first, rule not added")
            sys.exit(1)
        print(RuleRepository(conn).add_rule(r, args.supersedes))

    rows = conn.execute("SELECT rule_id, parameter, operator, value, effective_from, effective_to, "
                        "source_doc_id, source_section FROM rule_registry ORDER BY parameter, effective_from").fetchall()
    for x in rows:
        print(" ", dict(x))


if __name__ == "__main__":
    main()
