import json
import sys

METRICS = ["answer_correctness", "citation_accuracy", "abstention_accuracy", "tool_result_correctness",
           "retrieval_hit_rate", "latency_p50_ms", "latency_p95_ms", "avg_llm_calls", "avg_tokens"]

if len(sys.argv) < 3:
    print("usage: python evaluations/compare_configs.py evaluations/results/a.json evaluations/results/b.json [...]")
    sys.exit(1)

runs = []
for p in sys.argv[1:]:
    with open(p, encoding="utf-8") as f:
        runs.append(json.load(f))

head = "| Metric |"
sep = "|---|"
for r in runs:
    head += " " + r["config"] + " |"
    sep += "---|"
print(head)
print(sep)
for m in METRICS:
    line = "| " + m + " |"
    for r in runs:
        line += " " + str(r["summary"].get(m)) + " |"
    print(line)
