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

