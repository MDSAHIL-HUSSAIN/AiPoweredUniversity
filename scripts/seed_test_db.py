# Build a ready-to-use DB: rule registry + student CSVs.
#   python scripts/seed_test_db.py                          -> fixture students into SQLITE_PATH
#   python scripts/seed_test_db.py --students data/synthetic -> LLM-generated students
# In tests: from scripts.seed_test_db import build_test_conn; conn = build_test_conn()
import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.repositories.db import get_conn, SQLITE_PATH
from app.repositories.rule_repository import RuleRepository
from scripts.load_students import load_dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_test_conn(path=":memory:", students_dir=None, rules_csv=None):
    conn = get_conn(path)
    RuleRepository(conn).load_csv(rules_csv or os.path.join(ROOT, "data", "rule_registry.csv"))
    rep = load_dir(conn, students_dir or os.path.join(ROOT, "data", "fixtures"))
    return conn, rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=SQLITE_PATH)
    ap.add_argument("--students", default=os.path.join(ROOT, "data", "fixtures"))
    ap.add_argument("--rules-csv", default=os.path.join(ROOT, "data", "rule_registry.csv"))
    args = ap.parse_args()
    if args.db != ":memory:" and os.path.exists(args.db):
        os.remove(args.db)      # start clean every time
    conn, rep = build_test_conn(args.db, args.students, args.rules_csv)
    print("db:", args.db)
    print("loaded:", rep["loaded"], "issues:", len(rep["issues"]))


if __name__ == "__main__":
    main()
