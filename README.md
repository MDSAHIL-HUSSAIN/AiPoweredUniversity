# AI-Powered University Student Services Assistant

Shared repository for the HCLTech Future Ready AI Engineer Hackathon.

## Branches

- `main`: stable, demo-ready code
- `develop`: shared integration branch
- `feature/data-tools`: data, deterministic tools, and evaluation
- `feature/ingestion`: documents, ingestion, and retrieval
- `feature/langgraph`: LangGraph orchestration and LLM integration
- `feature/api-ui`: API, authentication, audit persistence, infrastructure, and UI

All feature pull requests target `develop`. Only tested integration changes move from
`develop` to `main`.

## Local setup

Python 3.11 is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Run the contract tests:

```powershell
pytest
```

Run a real structured-routing smoke test against the Ollama model configured in
`.env`:

```powershell
python -m scripts.smoke_test_router
```

Set `MOCK_LLM=true` to develop the workflow without Ollama. The real router applies
deterministic policy guards after model parsing, so identity always comes from the
trusted request context and only allowlisted university tools can be selected.

Member 4's API/engine integration contract, Docker host configuration, supported
model overrides, and compatibility facade are documented in
[`docs/ollama_integration.md`](docs/ollama_integration.md).

After installing the requirements, the merged API and UI can run without Docker:

```powershell
.\scripts\run_dev.ps1            # deterministic mock mode
.\scripts\run_dev.ps1 -RealLlm   # local Ollama mode
```

Docker is an optional reproducible demo path: `docker compose up --build`.

## Integration boundaries

Shared Pydantic models live in `app/contracts`. Change them only through a pull
request and notify every affected team member.

- Member 1 implements `UniversityTools` and data loaders.
- Member 2 implements `Retriever` and ingestion.
- Member 3 builds and wires the LangGraph workflow.
- Member 4 implements FastAPI, authorization, audit persistence, Docker, and UI.

During independent development, use the mock implementations in
`app/workflow/mocks.py`.

## Data policy

Do not commit real student data, secrets, generated SQLite databases, or ChromaDB
indexes. Commit schemas, loaders, public source documents or download links,
synthetic datasets, and reproducible setup scripts.

