import argparse
import csv
import json
import math
import os
import sys
import time
from fractions import Fraction
from typing import List, Literal

import requests
from pydantic import BaseModel, Field, ValidationError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.repositories.db import get_conn, TABLE_COLUMNS
from app.repositories.rule_repository import RuleRepository
from scripts.validate_data import validate, edge_cases, stats, read_dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS = os.path.join(ROOT, "prompts", "synthetic_data")

# LLM_PROVIDER=ollama  -> local Ollama (OLLAMA_BASE_URL, OLLAMA_MODEL)
# LLM_PROVIDER=api     -> any OpenAI-compatible API with a key (OpenAI, Groq, Gemini, OpenRouter...):
#                         LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
# if a key is set and no provider is given, use the API (so forgetting LLM_PROVIDER doesn't fall back to Ollama)
PROVIDER = os.getenv("LLM_PROVIDER", "api" if API_KEY else "ollama").strip().lower()
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
API_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
if PROVIDER == "api":
    MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
else:
    MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
TEMPERATURE = float(os.getenv("GEN_TEMPERATURE", "0.4"))
MAX_TRIES = int(os.getenv("GEN_MAX_TRIES", "4"))

GEN_DATE = "2026-10-06"      # thresholds for the edge cases are taken as of this date
MAY_DATE = "2026-05-01"      # exam session the results belong to

COURSES = [
    {"course_code": "CS201", "course_name": "Data Structures", "programme": "B.Tech CSE", "semester": 3, "credits": 4},
    {"course_code": "CS203", "course_name": "Database Management Systems", "programme": "B.Tech CSE", "semester": 3, "credits": 4},
    {"course_code": "MA201", "course_name": "Mathematics III", "programme": "B.Tech CSE", "semester": 3, "credits": 3},
    {"course_code": "EE201", "course_name": "Network Analysis", "programme": "B.Tech EE", "semester": 3, "credits": 4},
    {"course_code": "EE203", "course_name": "Electrical Machines I", "programme": "B.Tech EE", "semester": 3, "credits": 4},
    {"course_code": "MA203", "course_name": "Mathematics III (EE)", "programme": "B.Tech EE", "semester": 3, "credits": 3},
]

GROUPS = [("B.Tech CSE", 2024), ("B.Tech CSE", 2023), ("B.Tech EE", 2024), ("B.Tech EE", 2023)]


class GenResult(BaseModel):
    exam_session: Literal["2026-MAY", "2026-JUL"]
    exam_type: Literal["REGULAR", "SUPPLEMENTARY"]
    internal_marks: int = Field(ge=0, le=40)
    external_marks: int = Field(ge=0, le=60)
    total_marks: int = Field(ge=0, le=100)
    max_marks: int = Field(ge=1)
    result: Literal["PASS", "FAIL", "ABSENT", "DETAINED"]


class GenRecord(BaseModel):
    course_code: str
    classes_held: int = Field(gt=0)
    classes_attended: int = Field(ge=0)
    results: List[GenResult] = Field(min_length=1)


class GenStudent(BaseModel):
    student_id: str = Field(pattern=r"^S\d{4}$")
    full_name: str = Field(min_length=3)
    programme: Literal["B.Tech CSE", "B.Tech EE"]
    batch_year: Literal[2023, 2024]
    current_semester: int = Field(ge=1, le=10)
    cgpa: float = Field(ge=0, le=10)
    active_backlogs: int = Field(ge=0)
    records: List[GenRecord]


class GenBatch(BaseModel):
    students: List[GenStudent]


def read_prompt(name):
    with open(os.path.join(PROMPTS, name), encoding="utf-8") as f:
        return f.read()


def fill(text, vals):
    for k in vals:
        text = text.replace("{" + k + "}", str(vals[k]))
    return text


def thresholds(conn):
    def val(param, as_of):
        r = RuleRepository(conn).get_rule(param, None, None, as_of)["rule"]
        if r is None:
            raise SystemExit("rule " + param + " not effective on " + as_of + ", load the rule registry first")
        return Fraction(r["value"])

    now_att = val("min_attendance_pct", GEN_DATE)
    may_att = val("min_attendance_pct", MAY_DATE)
    pass_pct = val("min_pass_pct", MAY_DATE)
    cut = val("min_placement_cgpa", GEN_DATE)

    th = {}
    th["now_att"] = now_att
    th["now_need"] = math.ceil(now_att * 40 / 100)
    th["now_one_below"] = th["now_need"] - 1
    th["old_need"] = math.ceil(may_att * 40 / 100)
    th["may_att_pct"] = float(may_att)
    th["may_att_need"] = th["old_need"]
    th["pass_marks"] = math.ceil(pass_pct * 100 / 100)
    th["fail_total"] = th["pass_marks"] - 1
    th["cgpa_cut"] = "%.2f" % float(cut)
    th["cgpa_below"] = "%.2f" % (float(cut) - 0.01)
    th["cgpa_cut_plus"] = "%.2f" % (float(cut) + 0.10)
    th["normal_low"] = th["now_need"] + 2
    return th


def strip_fences(text):
    # some APIs wrap JSON in ```json ... ``` even in JSON mode
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def call_ollama(messages):
    body = {
        "model": MODEL,
        "messages": messages,
        "format": "json",
        "stream": False,
        "options": {"temperature": TEMPERATURE},
    }
    r = requests.post(OLLAMA_URL + "/api/chat", json=body, timeout=600)
    r.raise_for_status()
    return r.json()["message"]["content"]


def call_api(messages):
    if API_KEY == "":
        raise SystemExit("LLM_PROVIDER=api but LLM_API_KEY is not set")
    headers = {"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"}
    body = {"model": MODEL, "messages": messages, "temperature": TEMPERATURE,
            "response_format": {"type": "json_object"}}
    for attempt in range(5):
        r = requests.post(API_URL + "/chat/completions", json=body, headers=headers, timeout=300)
        if r.status_code == 429 or r.status_code >= 500:
            # rate limit / server hiccup: wait and try again (free tiers hit this a lot)
            wait = int(r.headers.get("retry-after", "0") or 0) or 5 * (attempt + 1)
            print("  api", r.status_code, "- waiting", wait, "s")
            time.sleep(wait)
            continue
        if r.status_code == 400 and "response_format" in body:
            # provider without JSON mode: drop it, the prompt already asks for JSON only
            body.pop("response_format")
            continue
        if r.status_code >= 400:
            raise SystemExit("API error " + str(r.status_code) + ": " + r.text[:300])
        return strip_fences(r.json()["choices"][0]["message"]["content"] or "")
    raise SystemExit("API kept failing (rate limit?) - try again later")


def call_llm(messages):
    if PROVIDER == "api":
        return call_api(messages)
    return call_ollama(messages)


def flatten(batch):
    t = {"students": [], "attendance": [], "results": []}
    for s in batch.students:
        t["students"].append({
            "student_id": s.student_id, "full_name": s.full_name, "programme": s.programme,
            "batch_year": str(s.batch_year), "current_semester": str(s.current_semester),
            "cgpa": "%.2f" % s.cgpa, "active_backlogs": str(s.active_backlogs),
        })
        for rec in s.records:
            t["attendance"].append({
                "student_id": s.student_id, "course_code": rec.course_code,
                "classes_held": str(rec.classes_held), "classes_attended": str(rec.classes_attended),
            })
            for res in rec.results:
                t["results"].append({
                    "student_id": s.student_id, "course_code": rec.course_code,
                    "exam_session": res.exam_session, "exam_type": res.exam_type,
                    "internal_marks": str(res.internal_marks), "external_marks": str(res.external_marks),
                    "total_marks": str(res.total_marks), "max_marks": str(res.max_marks),
                    "result": res.result,
                })
    return t


def course_problems(tables):
    probs = []
    prog = {}
    for c in COURSES:
        prog[c["course_code"]] = c["programme"]
    for s in tables["students"]:
        needed = []
        for c in COURSES:
            if c["programme"] == s["programme"]:
                needed.append(c["course_code"])
        have = []
        for a in tables["attendance"]:
            if a["student_id"] == s["student_id"]:
                have.append(a["course_code"])
        for code in needed:
            if code not in have:
                probs.append(s["student_id"] + ": missing record for " + code)
        for code in have:
            if code not in prog:
                probs.append(s["student_id"] + ": unknown course " + code)
            elif prog[code] != s["programme"]:
                probs.append(s["student_id"] + ": " + code + " belongs to another programme")
    return probs


EDGE_IDS = ["S1001", "S1002", "S1003", "S1004", "S1005", "S1006", "S1007", "S1008", "S1009", "S1010"]
EDGE_GROUPS = [["S1001", "S1002"], ["S1003", "S1004"], ["S1005", "S1006"], ["S1007", "S1008"], ["S1009", "S1010"]]


def edge_problems(tables, th, ids=None):
    # exact checks for the edge-case students in `ids` (default: all 10)
    if ids is None:
        ids = EDGE_IDS
    st = {}
    for s in tables["students"]:
        st[s["student_id"]] = s
    att = {}
    for a in tables["attendance"]:
        att[a["student_id"] + "|" + a["course_code"]] = int(a["classes_attended"])
    res = {}
    for r in tables["results"]:
        res[r["student_id"] + "|" + r["course_code"] + "|" + r["exam_type"]] = r

    p = []

    def need(sid, cond, msg):
        if sid in ids and sid in st and not cond():
            p.append(msg)

    for sid in ids:
        if sid not in st:
            p.append(sid + " is missing")

    def result_is(key, value, total=None):
        r = res.get(key)
        if r is None or r["result"] != value:
            return False
        return total is None or int(r["total_marks"]) == total

    need("S1001", lambda: att.get("S1001|CS201") == th["now_need"], "S1001 CS201 classes_attended must be " + str(th["now_need"]))
    need("S1002", lambda: att.get("S1002|CS201") == th["now_one_below"], "S1002 CS201 classes_attended must be " + str(th["now_one_below"]))
    need("S1003", lambda: result_is("S1003|CS201|REGULAR", "FAIL", th["fail_total"]),
         "S1003 CS201 must be FAIL with total_marks " + str(th["fail_total"]))
    need("S1003", lambda: st["S1003"]["active_backlogs"] == "1", "S1003 active_backlogs must be 1")
    need("S1003", lambda: float(st["S1003"]["cgpa"]) >= float(th["cgpa_cut_plus"]), "S1003 cgpa must be >= " + th["cgpa_cut_plus"])
    need("S1004", lambda: result_is("S1004|MA201|REGULAR", "ABSENT"), "S1004 MA201 must be ABSENT")
    need("S1005", lambda: result_is("S1005|EE203|REGULAR", "DETAINED"), "S1005 EE203 must be DETAINED")
    need("S1006", lambda: st["S1006"]["active_backlogs"] == "3", "S1006 active_backlogs must be 3")
    need("S1007", lambda: st["S1007"]["cgpa"] == th["cgpa_cut"], "S1007 cgpa must be exactly " + th["cgpa_cut"])
    need("S1008", lambda: st["S1008"]["cgpa"] == th["cgpa_below"], "S1008 cgpa must be exactly " + th["cgpa_below"])
    need("S1009", lambda: result_is("S1009|CS203|REGULAR", "FAIL"), "S1009 CS203 REGULAR must be FAIL")
    need("S1009", lambda: result_is("S1009|CS203|SUPPLEMENTARY", "PASS"),
         "S1009 CS203 SUPPLEMENTARY must be PASS (2026-JUL), as a second entry in the results list of the same CS203 record")
    need("S1010", lambda: att.get("S1010|EE201") == th["old_need"], "S1010 EE201 classes_attended must be " + str(th["old_need"]))
    return p


def generate(name, prompt, expected_ids, conn, th, log, is_edge=False):
    system = read_prompt("system.txt")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]

    for attempt in range(1, MAX_TRIES + 1):
        start = time.time()
        raw = call_llm(messages)
        ms = round((time.time() - start) * 1000)
        errors = []
        tables = None

        try:
            batch = GenBatch.model_validate_json(raw)
            tables = flatten(batch)
        except ValidationError as e:
            for err in e.errors()[:15]:
                loc = ".".join(str(x) for x in err["loc"])
                errors.append("schema: " + loc + ": " + err["msg"])

        if tables is not None:
            ids = []
            for s in tables["students"]:
                ids.append(s["student_id"])
            if sorted(ids) != sorted(expected_ids):
                errors.append("expected student_ids " + ", ".join(expected_ids) + " but got " + ", ".join(ids))
            errors += course_problems(tables)
            check_tables = {"courses": [], "students": tables["students"],
                            "attendance": tables["attendance"], "results": tables["results"]}
            for c in COURSES:
                row = {}
                for k in c:
                    row[k] = str(c[k])
                check_tables["courses"].append(row)
            for i in validate(check_tables, conn, own=True, as_of=GEN_DATE):
                if i["severity"] != "warning":
                    errors.append(i["table"] + " " + i["key"] + ": " + i["msg"])
            if is_edge:
                errors += edge_problems(tables, th, expected_ids)

        log.append({"batch": name, "attempt": attempt, "provider": PROVIDER, "model": MODEL, "temperature": TEMPERATURE,
                    "ms": ms, "ok": len(errors) == 0, "errors": errors})
        print(name, "attempt", attempt, "->", "ok" if len(errors) == 0 else str(len(errors)) + " problems")

        if len(errors) == 0:
            return tables

        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content":
                         "Your JSON has these problems:\n- " + "\n- ".join(errors[:25])
                         + "\nFix all of them and return the complete corrected JSON object only."})

    print(name, "failed after", MAX_TRIES, "attempts - see generation_log.json")
    return None


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    global MODEL
    ap = argparse.ArgumentParser(description="Generate synthetic students with an LLM (Ollama or an API key)")
    ap.add_argument("--out", default="data/synthetic")
    ap.add_argument("--rules-csv", default="data/rule_registry.csv")
    ap.add_argument("--regular", type=int, default=25, help="number of normal students after the 10 edge cases")
    ap.add_argument("--batch-size", type=int, default=5)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--only", choices=["all", "edge", "regular"], default="all",
                    help="regenerate only these batches and keep the other students already in --out")
    args = ap.parse_args()
    MODEL = args.model

    os.makedirs(args.out, exist_ok=True)
    rendered_dir = os.path.join(args.out, "prompts_rendered")
    os.makedirs(rendered_dir, exist_ok=True)

    conn = get_conn(":memory:")
    RuleRepository(conn).load_csv(args.rules_csv)
    th = thresholds(conn)

    course_text = ""
    for c in COURSES:
        course_text += "- " + c["course_code"] + " " + c["course_name"] + " (" + c["programme"] + ")\n"

    common = fill(read_prompt("common_rules.txt"),
                  {"courses": course_text, "schema": read_prompt("student_schema.txt"),
                   "pass_marks": th["pass_marks"], "may_att_pct": th["may_att_pct"],
                   "may_att_need": th["may_att_need"]})

    jobs = []
    # edge cases in small groups: one call with all 10 was too much for small models
    edge_text = p = fill(read_prompt("edge_students.txt"), th).replace("{common}", common)
    for g in EDGE_GROUPS:
        p = edge_text + ("\n\nReturn ONLY these students in this reply: " + ", ".join(g)
                         + " (the others are generated separately). Each of them needs exactly one record for "
                         "each of the 3 courses of their programme.")
        jobs.append(("edge_" + g[0] + "_" + g[1], p, g, True))

    nxt = 1011
    left = args.regular
    k = 0
    b = 1
    while left > 0:
        n = min(args.batch_size, left)
        ids = []
        lines = ""
        for j in range(n):
            sid = "S" + str(nxt)
            g = GROUPS[k % len(GROUPS)]
            ids.append(sid)
            lines += "- " + sid + ": " + g[0] + ", batch " + str(g[1]) + "\n"
            nxt += 1
            k += 1
        vals = dict(th)
        vals["n"] = n
        vals["assignments"] = lines
        p = fill(read_prompt("regular_students.txt"), vals)
        p = p.replace("{common}", common)
        jobs.append(("regular_" + str(b), p, ids, False))
        left -= n
        b += 1

    if args.only == "edge":
        jobs = [j for j in jobs if j[3]]
    elif args.only == "regular":
        jobs = [j for j in jobs if not j[3]]

    all_t = {"students": [], "attendance": [], "results": []}
    log = []
    failed = []
    if args.only != "all":
        # keep students from the earlier run that are not regenerated now, and keep the earlier log
        redo = set()
        for j in jobs:
            redo.update(j[2])
        old = read_dir(args.out)
        for key in all_t:
            for r in old.get(key, []):
                if r["student_id"] not in redo:
                    all_t[key].append(r)
        old_log = os.path.join(args.out, "generation_log.json")
        if os.path.exists(old_log):
            with open(old_log, encoding="utf-8") as f:
                for c in json.load(f).get("calls", []):
                    if c["batch"] not in [j[0] for j in jobs]:
                        log.append(c)
    print("LLM:", PROVIDER, MODEL, "at", API_URL if PROVIDER == "api" else OLLAMA_URL)
    for name, prompt, ids, is_edge in jobs:
        with open(os.path.join(rendered_dir, name + ".txt"), "w", encoding="utf-8") as f:
            f.write("=== SYSTEM ===\n" + read_prompt("system.txt") + "\n=== USER ===\n" + prompt)
        t = generate(name, prompt, ids, conn, th, log, is_edge)
        if t is None:
            failed.append(name)
            continue
        for key in all_t:
            all_t[key] += t[key]

    for key in all_t:
        all_t[key].sort(key=lambda r: r["student_id"])
    course_rows = []
    for c in COURSES:
        course_rows.append(c)
    write_csv(os.path.join(args.out, "courses.csv"), TABLE_COLUMNS["courses"], course_rows)
    write_csv(os.path.join(args.out, "students.csv"), TABLE_COLUMNS["students"], all_t["students"])
    write_csv(os.path.join(args.out, "attendance.csv"), TABLE_COLUMNS["attendance"], all_t["attendance"])
    write_csv(os.path.join(args.out, "results.csv"), TABLE_COLUMNS["results"], all_t["results"])

    with open(os.path.join(args.out, "generation_log.json"), "w", encoding="utf-8") as f:
        json.dump({"provider": PROVIDER, "base_url": API_URL if PROVIDER == "api" else OLLAMA_URL,
                   "model": MODEL, "temperature": TEMPERATURE, "gen_date": GEN_DATE,
                   "llm_calls": len(log), "failed_batches": failed, "max_tries": MAX_TRIES, "calls": log}, f, indent=2)

    final = {"courses": [], "students": all_t["students"],
             "attendance": all_t["attendance"], "results": all_t["results"]}
    for c in COURSES:
        row = {}
        for key in c:
            row[key] = str(c[key])
        final["courses"].append(row)
    s = stats(final)
    s["edge_cases"] = edge_cases(final, conn, GEN_DATE)
    with open(os.path.join(args.out, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)

    print("done:", len(all_t["students"]), "students,", len(log), "LLM calls, failed batches:", failed)
    print("now run: python scripts/validate_data.py --dir", args.out, "--own --as-of", GEN_DATE)


if __name__ == "__main__":
    main()
