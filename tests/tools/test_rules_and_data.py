import json
import os

from app.repositories.db import get_conn
from app.repositories.rule_repository import RuleRepository, check, in_scope, check_rule
from scripts.validate_data import read_dir, validate, edge_cases
from scripts.generate_students import edge_problems
from scripts.generate_students import thresholds

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_check_operators():
    assert check(75, ">=", "75")
    assert not check("74.99", ">=", "75")
    assert check("absent", "in", "FAIL;ABSENT")
    assert check(5, "between", "1;10")
    assert in_scope("2023+", 2024) and not in_scope("2025+", 2024)
    assert in_scope("B.Tech", "B.Tech CSE")


def test_new_circular_supersedes_without_restart(conn):
    rules = RuleRepository(conn)
    new = {"rule_id": "ATT-MIN-03", "description": "test", "parameter": "min_attendance_pct", "operator": ">=",
           "value": "85", "effective_from": "2026-12-01", "source_doc_id": "X", "source_section": "1"}
    out = rules.add_rule(new, supersedes="ATT-MIN-02")
    assert out["old_rule_effective_to"] == "2026-11-30"
    assert rules.get_rule("min_attendance_pct", as_of="2026-11-30")["rule"]["rule_id"] == "ATT-MIN-02"
    assert rules.get_rule("min_attendance_pct", as_of="2026-12-01")["rule"]["rule_id"] == "ATT-MIN-03"


def test_rules_csv_with_excel_bom(tmp_path):
    raw = open(os.path.join(ROOT, "data", "rule_registry.csv"), encoding="utf-8").read()
    p = tmp_path / "bom.csv"
    p.write_text("﻿" + raw, encoding="utf-8")
    assert RuleRepository(get_conn(":memory:")).load_csv(str(p)) == raw.strip().count("\n")


def test_check_rule_flags_missing_doc():
    r = {"rule_id": "A", "description": "d", "parameter": "p", "operator": ">=", "value": "1",
         "effective_from": "2026-01-01", "source_doc_id": "NOPE", "source_section": "TBD"}
    probs = check_rule(r, {"OTHER"})
    assert any("not in source register" in p for p in probs)
    assert any(p.startswith("WARNING") for p in probs)


def test_fixture_data_is_clean_and_covers_edge_cases(conn):
    t = read_dir(os.path.join(ROOT, "data", "fixtures"))
    issues = [i for i in validate(t, conn, own=True, as_of="2026-10-06") if i["severity"] != "warning"]
    assert issues == []
    for k, v in edge_cases(t, conn, "2026-10-06").items():
        assert len(v) > 0, k
    # the generator's own edge checks agree with the fixture
    assert edge_problems(t, thresholds(conn)) == []


def test_validator_catches_typical_llm_mistakes(conn):
    t = read_dir(os.path.join(ROOT, "data", "fixtures"))
    t["results"][0]["total_marks"] = str(int(t["results"][0]["total_marks"]) + 5)    # total != int + ext
    t["students"][0]["active_backlogs"] = "2"                                          # backlog mismatch
    msgs = " ".join(i["msg"] for i in validate(t, conn, own=True, as_of="2026-10-06"))
    assert "internal + external" in msgs and "active_backlogs" in msgs


def test_questions_file_is_consistent():
    qs = json.load(open(os.path.join(ROOT, "evaluations", "questions.json"), encoding="utf-8"))["questions"]
    ids = [q["id"] for q in qs]
    assert len(ids) == len(set(ids))
    for q in qs:
        assert q["expected_answer_type"] in ["retrieved_fact", "calculated", "not_found",
                                             "clarification_needed", "refused", "conflict_flagged"]


def test_audit_repository_roundtrip(conn):
    from app.repositories.audit_repository import AuditRepository
    a = AuditRepository(conn)
    a.save({"trace_id": "t1", "student_id": "S1001", "answer_type": "calculated"})
    assert a.get("t1")["answer_type"] == "calculated"
    assert a.get("nope") is None
