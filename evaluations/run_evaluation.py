import argparse
import json
import math
import os
import time

import requests

NO_ANSWER_TYPES = ["not_found", "refused", "clarification_needed"]


def tool_name(t):
    # ToolInvocation field name is not final yet, accept the usual ones
    return t.get("tool_name") or t.get("tool") or t.get("name")


def pctl(vals, p):
    if len(vals) == 0:
        return None
    s = sorted(vals)
    k = math.ceil(p / 100 * len(s)) - 1
    if k < 0:
        k = 0
    return s[k]


def ratio(a, b):
    if b == 0:
        return None
    return round(a / b, 3)


def ask(base, q, timeout):
    headers = {}
    if q.get("student_id"):
        headers["X-Student-ID"] = q["student_id"]
    body = {"question": q["question"]}
    if q.get("as_of_date"):
        body["as_of_date"] = q["as_of_date"]
    start = time.time()
    r = requests.post(base + "/ask", json=body, headers=headers, timeout=timeout)
    ms = round((time.time() - start) * 1000)
    r.raise_for_status()
    return r.json(), ms


def get_audit(base, trace_id):
    try:
        r = requests.get(base + "/audit/" + str(trace_id), timeout=30)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def score(q, resp, audit):
    s = {}
    atype = resp.get("answer_type")
    text = (str(resp.get("answer", "")) + " " + str(resp.get("explanation", ""))).lower()

    s["answer_type_ok"] = atype == q["expected_answer_type"]
    contains_ok = True
    for x in q.get("expected_contains", []):
        if x.lower() not in text:
            contains_ok = False
    s["correct"] = s["answer_type_ok"] and contains_ok

    cited = []
    for c in resp.get("citations", []) or []:
        cited.append(c.get("doc_id"))
    exp_docs = q.get("expected_doc_ids", [])
    if len(exp_docs) > 0 and q["expected_answer_type"] not in NO_ANSWER_TYPES:
        ok = True
        for d in exp_docs:
            if d not in cited:
                ok = False
        s["citation_ok"] = ok

    s["abstain_expected"] = q["expected_answer_type"] == "not_found"
    s["abstain_pred"] = atype == "not_found"

    et = q.get("expected_tool")
    if et:
        found = False
        for t in resp.get("tools_invoked", []) or []:
            if tool_name(t) != et["name"]:
                continue
            if "result" not in et:
                found = True
            else:
                out = t.get("output") or {}
                if out.get("result") == et["result"]:
                    found = True
        s["tool_ok"] = found

    if audit is not None and len(exp_docs) > 0:
        got = []
        for x in audit.get("sources_retrieved", []) or []:
            got.append(x.get("doc_id"))
        hit = False
        for d in exp_docs:
            if d in got:
                hit = True
        s["retrieval_hit"] = hit

    if audit is not None:
        s["llm_calls"] = audit.get("llm_calls")
        s["tokens"] = audit.get("tokens")
    return s


def summarize(rows):
    total = len(rows)
    correct = 0
    cit_n = cit_ok = 0
    ab_ok = 0
    tp = fp = fn = 0
    tool_n = tool_ok = 0
    ret_n = ret_ok = 0
    lat = []
    calls = []
    toks = []
    by_cat = {}

    for r in rows:
        s = r["score"]
        if s.get("error"):
            cat = by_cat.setdefault(r["category"], [0, 0])
            cat[1] += 1
            continue
        if s["correct"]:
            correct += 1
        if "citation_ok" in s:
            cit_n += 1
            if s["citation_ok"]:
                cit_ok += 1
        if s["abstain_expected"] == s["abstain_pred"]:
            ab_ok += 1
        if s["abstain_expected"] and s["abstain_pred"]:
            tp += 1
        if not s["abstain_expected"] and s["abstain_pred"]:
            fp += 1
        if s["abstain_expected"] and not s["abstain_pred"]:
            fn += 1
        if "tool_ok" in s:
            tool_n += 1
            if s["tool_ok"]:
                tool_ok += 1
        if "retrieval_hit" in s:
            ret_n += 1
            if s["retrieval_hit"]:
                ret_ok += 1
        lat.append(r["latency_ms"])
        if s.get("llm_calls") is not None:
            calls.append(s["llm_calls"])
        if s.get("tokens") is not None:
            toks.append(s["tokens"])
        cat = by_cat.setdefault(r["category"], [0, 0])
        cat[1] += 1
        if s["correct"]:
            cat[0] += 1

    cats = {}
    for k in by_cat:
        cats[k] = str(by_cat[k][0]) + "/" + str(by_cat[k][1])

    return {
        "questions": total,
        "answer_correctness": ratio(correct, total),
        "citation_accuracy": ratio(cit_ok, cit_n),
        "abstention_accuracy": ratio(ab_ok, total),
        "abstention_precision": ratio(tp, tp + fp),
        "abstention_recall": ratio(tp, tp + fn),
        "tool_result_correctness": ratio(tool_ok, tool_n),
        "retrieval_hit_rate": ratio(ret_ok, ret_n),
        "latency_p50_ms": pctl(lat, 50),
        "latency_p95_ms": pctl(lat, 95),
        "avg_llm_calls": round(sum(calls) / len(calls), 2) if len(calls) > 0 else None,
        "avg_tokens": round(sum(toks) / len(toks)) if len(toks) > 0 else None,
        "correct_by_category": cats,
    }


def write_md(path, config, summary, rows):
    lines = []
    lines.append("# Eval results: " + config)
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    for k in summary:
        if k == "correct_by_category":
            continue
        lines.append("| " + k + " | " + str(summary[k]) + " |")
    lines.append("")
    lines.append("Correct by category: " + json.dumps(summary["correct_by_category"]))
    lines.append("")
    lines.append("| ID | Category | Expected | Got | Correct | Citation | Tool | Retrieval | ms |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        s = r["score"]
        if s.get("error"):
            lines.append("| " + r["id"] + " | " + r["category"] + " | " + r["expected_answer_type"]
                         + " | ERROR: " + s["error"][:60] + " | - | - | - | - | - |")
            continue
        lines.append("| " + r["id"] + " | " + r["category"] + " | " + r["expected_answer_type"] + " | "
                     + str(r["answer_type"]) + " | " + str(s["correct"]) + " | " + str(s.get("citation_ok", "-"))
                     + " | " + str(s.get("tool_ok", "-")) + " | " + str(s.get("retrieval_hit", "-"))
                     + " | " + str(r["latency_ms"]) + " |")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Run the eval set against POST /ask")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--set", default="evaluations/questions.json")
    ap.add_argument("--config", default="baseline", help="label for this run, e.g. section_chunks_bge_k5")
    ap.add_argument("--out", default="evaluations/results")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--only", default=None, help="comma separated question ids")
    args = ap.parse_args()

    with open(args.set, encoding="utf-8") as f:
        qs = json.load(f)["questions"]
    if args.only:
        keep = args.only.split(",")
        sel = []
        for q in qs:
            if q["id"] in keep:
                sel.append(q)
        qs = sel

    rows = []
    for q in qs:
        row = {"id": q["id"], "category": q["category"], "question": q["question"],
               "expected_answer_type": q["expected_answer_type"]}
        try:
            resp, ms = ask(args.base, q, args.timeout)
            audit = get_audit(args.base, resp.get("trace_id"))
            row["answer_type"] = resp.get("answer_type")
            row["answer"] = resp.get("answer")
            row["trace_id"] = resp.get("trace_id")
            row["latency_ms"] = ms
            row["score"] = score(q, resp, audit)
        except Exception as e:
            row["answer_type"] = None
            row["latency_ms"] = None
            row["score"] = {"error": str(e)}
        rows.append(row)
        s = row["score"]
        print(q["id"], q["category"], "->", row["answer_type"],
              "OK" if s.get("correct") else ("ERROR " + s["error"] if s.get("error") else "WRONG"))

    summary = summarize(rows)
    os.makedirs(args.out, exist_ok=True)
    out = {"config": args.config, "base": args.base, "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "method": "automatic: exact answer_type match + expected strings in answer; citation = expected "
                     "doc_id present in citations (then spot-checked by hand against the cited page); "
                     "tool = expected tool called with expected result; retrieval = expected doc_id in "
                     "audit sources_retrieved",
           "summary": summary, "rows": rows}
    with open(os.path.join(args.out, args.config + ".json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    write_md(os.path.join(args.out, args.config + ".md"), args.config, summary, rows)

    print()
    for k in summary:
        print(k, ":", summary[k])
    print("saved to", os.path.join(args.out, args.config + ".json / .md"))


if __name__ == "__main__":
    main()
