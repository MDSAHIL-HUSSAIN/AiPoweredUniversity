# Member 1: data, rule registry, tools, evaluation

Branch: `feature/data-tools`. Everything here follows the team folder structure.

```
app/contracts/tools.py               ToolResult (copied from the team guide)
app/repositories/db.py               SQLite schema + get_conn() (env SQLITE_PATH)
app/repositories/rule_repository.py  rule lookup by as_of_date/scope, exact comparisons, supersession
app/repositories/student_repository.py
app/repositories/audit_repository.py save(record) / get(trace_id) on SQLite
app/tools/                           6 tools + UniversityTools + call_tool + TOOL_SPECS
scripts/generate_students.py         LLM generator (Ollama, Pydantic, retry with feedback)
scripts/validate_data.py             schema + logic checks, edge-case coverage, stats
scripts/load_students.py             judge loader: python scripts/load_students.py --dir test_students/
scripts/load_rules.py                load rules / add a new rule that supersedes an old one
scripts/build_fixture_data.py        16 deterministic test students (no LLM) -> data/fixtures/
scripts/seed_test_db.py              rules + students into a DB; build_test_conn() for tests
data/rule_registry.csv               every threshold, linked to source_doc_id + source_section
evaluations/questions.json           27 questions
evaluations/run_evaluation.py        runs questions against POST /ask, writes json + md
evaluations/run_tool_checks.py       offline: expected tool results, no API/LLM
evaluations/expected_tool_outputs.json  real ToolResult per question, for Member 3's fake tools
tests/tools/                         23 pytest tests
docs/data_card.md                    Annex E
```

## Run order (PowerShell, repo root)
```
pip install -r requirements.txt            # needs pydantic, requests, pytest
python scripts/seed_test_db.py             # fixture DB at SQLITE_PATH, works without Ollama
pytest -q tests/tools
python evaluations/run_tool_checks.py

# generate with an API key (any OpenAI-compatible endpoint)
$env:LLM_PROVIDER="api"; $env:LLM_API_KEY="<key>"; $env:LLM_BASE_URL="<base url>"; $env:LLM_MODEL="<model>"
python scripts/generate_students.py        # -> data/synthetic/ (+ generation_log.json, stats.json)
# or locally: ollama pull llama3.1:8b; $env:LLM_PROVIDER="ollama"; python scripts/generate_students.py
python scripts/validate_data.py --dir data/synthetic --own --as-of 2026-10-06
python scripts/seed_test_db.py --students data/synthetic
python scripts/load_rules.py --csv data/rule_registry.csv   # checks doc_ids against source_register.csv

# once the API is up
python evaluations/run_evaluation.py --config baseline
python evaluations/compare_configs.py evaluations/results/baseline.json evaluations/results/<other>.json
```

## For Member 3 (LangGraph)
```python
from app.repositories.db import get_conn
from app.tools import UniversityTools, call_tool, TOOL_SPECS

tools = UniversityTools(get_conn())
res = call_tool(tools, router.tool, header_student_id, router.args, request.as_of_date)   # -> ToolResult
```
- `student_id` always comes from the `X-Student-ID` header. `call_tool` drops any `student_id` the LLM puts in args and returns `status=refused` if there is no identity.
- `TOOL_SPECS` has a description and the LLM-fillable args for each tool; use it in the router prompt. `as_of_date` is passed by `call_tool`, never by the LLM.
- `res.output["status"]` is one of `ok`, `not_found`, `clarification_needed` (with `options`), `refused`, `error`. `res.success` is True only for `ok`. NOT_ELIGIBLE is still `ok`.
- Decisions are in `res.output["result"]` (ELIGIBLE / NOT_ELIGIBLE / NOT_REQUIRED).
- Citations for thresholds: `res.applied_rule_ids` + `res.output["rules"]` (rule_id, value, source_doc_id, source_section). Use these for `applied_rules`; the LLM should not invent them.
- `upcoming_rules` / `conflicting_rules` appear in exam-eligibility output when a rule change is coming or two rules clash.
- `run_what_if(student_id, changes, as_of_date)`, `changes` keys: `pass_courses` [list], `cgpa`, `active_backlogs`, `classes_attended` {course: n}. Example: "if I pass Data Structures in the supplementary" -> `{"pass_courses": ["Data Structures"]}`. Output has `placement_before`, `placement_after`, `scenario_possible`, `assumptions`.
- Courses can be given by code or name ("Data Structures", "CS201").
- For tests: `from scripts.seed_test_db import build_test_conn` gives an in-memory DB with the fixture students. `evaluations/expected_tool_outputs.json` has the real outputs if you prefer a FakeUniversityTools that replays them.

## For Member 4 (API)
- `AuditRepository(conn).save(record)` takes a dict or the AuditRecord model; `get(trace_id)` for `GET /audit/{trace_id}`.
- Admin endpoints can call `load_dir(conn, folder)` (scripts/load_students.py) and `RuleRepository(conn).add_rule(rule, supersedes)`. Tools read the registry on every call, so a new rule works with no restart.
- `run_evaluation.py` sends `X-Student-ID` and `{"question", "as_of_date"}` to `POST /ask`, and reads `answer_type`, `answer`, `explanation`, `citations[].doc_id`, `tools_invoked[]` (tool_name/output), `trace_id`.

## For Member 2 (documents)
Rule registry currently points to:
- ATT-MIN-01 (75%) -> `NSUT-20260422-ATT75`
- ATT-MIN-02 (80% from 2026-08-01) -> `ACAD-CIRC-2026-08-SYN` (your synthetic circular, must be added to the register with synthetic=Y)
- SUPP-ELIG-01 -> `NSUT-20260508-SUMMER`
- PASS-MIN-01 (40%) -> no document in the register yet
- PLC-CGPA-01 (6.5), PLC-BKLG-01 (0) -> no T&P document in the register yet

## How a new circular changes a rule
`python scripts/load_rules.py --add new_rule.json --supersedes ATT-MIN-02` inserts the new row and sets the old rule's `effective_to` to the day before. Questions with an older `as_of_date` still get the old rule.

## Design decisions
- Attendance is compared with `Fraction`, not floats, so 32/40 against ">= 80" is exactly equal. Exactly-at-threshold counts as eligible because the rule operator is `>=`.
- Thresholds are never in code: `get_rule` picks the rule effective on `as_of_date` for the student's programme and batch, and also returns upcoming rules.
- The loader only skips rows that cannot be stored (bad types, missing keys, unknown student/course). Logical problems in judge data are reported but still loaded, because judges may load odd cases on purpose.
- What-if keeps CGPA unchanged unless the scenario sets it, because the schema has no grade points; this is listed in `assumptions`.
