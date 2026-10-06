import csv
import os
import re
from datetime import date, timedelta
from fractions import Fraction

MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
          "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}

OPERATORS = [">=", "<=", ">", "<", "==", "in", "between"]

REQUIRED = ["rule_id", "description", "parameter", "operator", "value",
            "effective_from", "source_doc_id", "source_section"]


def iso(d):
    # accepts date, "YYYY-MM-DD" or None (= today)
    if d is None or d == "":
        return date.today().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d).strip()[:10]


def session_date(session):
    # "2026-MAY" -> "2026-05-01"
    if session is None:
        return None
    parts = str(session).strip().upper().split("-")
    if len(parts) != 2 or parts[1] not in MONTHS:
        return None
    return parts[0] + "-" + str(MONTHS[parts[1]]).zfill(2) + "-01"


def in_scope(scope, value):
    if value is None:
        return True
    if scope is None or str(scope).strip() == "" or str(scope).strip().upper() == "ALL":
        return True
    value = str(value).strip().lower()
    for p in str(scope).split(";"):
        p = p.strip().lower()
        if p == "":
            continue
        if p.endswith("+"):
            if value.isdigit() and p[:-1].isdigit() and int(value) >= int(p[:-1]):
                return True
        elif value.startswith(p):
            return True
    return False


def to_frac(x):
    if isinstance(x, Fraction):
        return x
    return Fraction(str(x).strip())


def check(value, op, rule_value):
    # exact comparison, Fraction instead of float so 32/40 >= 80 is exactly true
    op = op.strip().lower()
    if op == "in":
        allowed = []
        for x in str(rule_value).split(";"):
            allowed.append(x.strip().upper())
        return str(value).strip().upper() in allowed

    v = to_frac(value)
    if op == "between":
        lo, hi = str(rule_value).split(";")
        return to_frac(lo) <= v <= to_frac(hi)

    t = to_frac(rule_value)
    if op == ">=":
        return v >= t
    if op == "<=":
        return v <= t
    if op == ">":
        return v > t
    if op == "<":
        return v < t
    if op == "==":
        return v == t
    raise ValueError("unknown operator " + op)


def rule_info(r):
    if r is None:
        return None
    return {
        "rule_id": r["rule_id"],
        "description": r["description"],
        "parameter": r["parameter"],
        "operator": r["operator"],
        "value": r["value"],
        "effective_from": r["effective_from"],
        "effective_to": r["effective_to"],
        "source_doc_id": r["source_doc_id"],
        "source_section": r["source_section"],
    }


def register_ids(path):
    # doc_ids from Member 2's source_register.csv, None if the file is not there
    if path is None or not os.path.exists(path):
        return None
    ids = set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ids.add(r.get("doc_id", "").strip())
    return ids


def check_rule(r, docs=None):
    probs = []
    for k in REQUIRED:
        if str(r.get(k, "") or "").strip() == "":
            probs.append("missing " + k)
    if r.get("operator") and r["operator"].strip() not in OPERATORS:
        probs.append("operator must be one of " + ", ".join(OPERATORS))
    for k in ["effective_from", "effective_to"]:
        v = str(r.get(k, "") or "").strip()
        if v != "" and not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            probs.append(k + " must be YYYY-MM-DD")
    if str(r.get("source_section", "")).strip().upper() == "TBD":
        probs.append("WARNING source_section is TBD - fill the real clause from the document")
    if docs is not None and str(r.get("source_doc_id", "")).strip() not in docs:
        probs.append("source_doc_id " + str(r.get("source_doc_id")) + " not in source register")
    return probs


class RuleRepository:
    def __init__(self, conn):
        self.conn = conn

    def all_rules(self):
        rows = self.conn.execute("SELECT * FROM rule_registry ORDER BY parameter, effective_from").fetchall()
        out = []
        for r in rows:
            out.append(dict(r))
        return out

    def get_rule(self, parameter, programme=None, batch=None, as_of=None):
        # rule effective on as_of for this programme/batch + rules that start later
        as_of = iso(as_of)
        rows = self.conn.execute("SELECT * FROM rule_registry WHERE parameter = ?", (parameter,)).fetchall()
        active = []
        upcoming = []
        for r in rows:
            r = dict(r)
            if not in_scope(r["scope_programmes"], programme):
                continue
            if not in_scope(r["scope_batches"], batch):
                continue
            if r["effective_from"] > as_of:
                upcoming.append(r)
                continue
            if r["effective_to"] and r["effective_to"] < as_of:
                continue
            active.append(r)

        # supersession closes the old rule when a new one is added, so normally one is active.
        # if more, the latest effective_from wins and same-date rules with other values are conflicts
        best = None
        for r in active:
            if best is None or r["effective_from"] > best["effective_from"]:
                best = r
        conflicts = []
        for r in active:
            if r is best:
                continue
            if r["effective_from"] == best["effective_from"] and r["value"] != best["value"]:
                conflicts.append(r)
        upcoming.sort(key=lambda x: x["effective_from"])
        return {"rule": best, "conflicts": conflicts, "upcoming": upcoming}

    def load_csv(self, path):
        cnt = 0
        with open(path, newline="", encoding="utf-8-sig") as f:   # -sig: Excel on Windows adds a BOM
            for row in csv.DictReader(f):
                if row.get("rule_id", "").strip() == "":
                    continue
                eff_to = (row.get("effective_to") or "").strip() or None
                self.conn.execute(
                    "INSERT OR REPLACE INTO rule_registry VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (row["rule_id"].strip(), row["description"].strip(), row["parameter"].strip(),
                     row["operator"].strip(), row["value"].strip(),
                     (row.get("scope_programmes") or "ALL").strip() or "ALL",
                     (row.get("scope_batches") or "ALL").strip() or "ALL",
                     row["effective_from"].strip(), eff_to,
                     row["source_doc_id"].strip(), row["source_section"].strip()))
                cnt += 1
        self.conn.commit()
        return cnt

    def add_rule(self, r, supersedes=None):
        # new circular changes a rule: insert the new row and close the old one the day before
        if supersedes:
            old = self.conn.execute("SELECT * FROM rule_registry WHERE rule_id = ?", (supersedes,)).fetchone()
            if old is None:
                raise ValueError("rule to supersede not found: " + supersedes)
        self.conn.execute("INSERT OR REPLACE INTO rule_registry VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (r["rule_id"], r["description"], r["parameter"], r["operator"], str(r["value"]),
                           r.get("scope_programmes") or "ALL", r.get("scope_batches") or "ALL",
                           r["effective_from"], r.get("effective_to") or None,
                           r["source_doc_id"], str(r["source_section"])))
        closed = None
        if supersedes:
            closed = (date.fromisoformat(r["effective_from"]) - timedelta(days=1)).isoformat()
            self.conn.execute("UPDATE rule_registry SET effective_to = ? WHERE rule_id = ?", (closed, supersedes))
        self.conn.commit()
        return {"added": r["rule_id"], "superseded": supersedes, "old_rule_effective_to": closed}
