# Ollama integration contract

Member 3 owns the structured Ollama/LangGraph integration. Member 4 should invoke
the compiled workflow for `/ask`; the workflow already performs routing,
authorization, retrieval, precedence resolution, deterministic tool calls,
evidence-only composition, and citation validation.

## Environment

Local development:

```powershell
ollama pull qwen3:4b
Copy-Item .env.example .env
```

The following model names are configurable and do not require code changes:

- `qwen3:4b` (current development default)
- `llama3.1:8b`
- `qwen2.5:7b-instruct`

Set `MOCK_LLM=true` for deterministic offline tests. For a local API process use
`OLLAMA_BASE_URL=http://localhost:11434`. From Docker use
`OLLAMA_BASE_URL=http://host.docker.internal:11434` and add this Compose setting:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## API integration

The preferred `/ask` integration is to construct the graph with
`app.workflow.build_workflow(...)`, create input with `new_workflow_state(...)`,
and await `graph.ainvoke(state)`. The final state includes `model_name`,
`token_count`, accumulated LLM `latency_ms`, `fallback_used`, and node-level latency in
`audit_metadata`, in addition to the public answer fields.

Legacy or isolated `AssistantEngine` code may use the compatibility facade:

```python
from app.llm import OllamaLLM

llm_result = OllamaLLM.synthesize_explanation(
    question=question,
    retrieved_context=str(sources_retrieved),
    tool_results=str(tools_invoked),
    answer_type=answer_type,
)
```

It returns `text`, `model`, `tokens`, `latency_ms`, and `fallback_used`. This
facade calls Ollama `/api/generate`; it must not replace the full graph for the
production `/ask` path because it does not run routing, authorization, source
precedence, tools, or citation validation.
