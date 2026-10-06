# Ollama integration guide

The production `/ask` endpoint calls the compiled LangGraph workflow through
`app/engine.py`. It must not separately call a second hard-coded routing engine.

## Local mode (Docker not required)

```powershell
ollama pull qwen3:4b
Copy-Item .env.example .env
.\scripts\run_dev.ps1 -RealLlm
```

Use these `.env` values:

```env
MOCK_LLM=false
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:4b
```

For offline development, set `MOCK_LLM=true` or run `scripts/run_dev.ps1`
without `-RealLlm`.

## Docker mode

Docker is optional. If installed, run:

```powershell
docker compose up --build
```

The API container reaches host Ollama through
`http://host.docker.internal:11434`. The Compose file already contains the
required `extra_hosts` mapping.

## Runtime telemetry

The graph records the selected model, LLM call count, prompt plus completion
tokens, total request latency, fallback status, router latency, composer latency,
tools, citations, applied rules, conflicts, and errors in its audit record.

See `docs/ollama_integration.md` for the Python compatibility facade and detailed
integration boundary.
