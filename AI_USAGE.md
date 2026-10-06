# AI-Usage Disclosure Statement

**Project**: AI-Powered University Student Services Assistant
**Event**: HCLTech | Future Ready AI Engineer Hackathon 2026 (NSUT, Delhi)
**Member**: Member 4 (API + Infra + UI)
**Date**: 6 October 2026

---

## 🤖 1. Overview of AI Assistance
In accordance with Section 8 & Section 10 of the Hackathon Participant Guide, AI coding assistance was utilized during development. All AI-generated code was strictly reviewed, modified, and empirically verified against the mandatory contracts and unit tests.

---

## 🛠️ 2. Summary of AI-Generated Components & Verification Methods

| Component / Subsystem | AI Assistance Used | Verification Method & Quality Checks |
| :--- | :--- | :--- |
| **FastAPI Endpoints & Pydantic v2 Models** (`main.py`, `app/contracts/`) | Initial boilerplate generation for Pydantic v2 schemas and FastAPI route handler signatures. | Verified payload structures with integration tests and FastAPI OpenAPI docs (`/docs`). Checked strict field typing and default value generators. |
| **Auth Node & Privacy Refusal Engine** (`app/auth/authorizer.py`) | Header identity and cross-student privacy checks. | Verified Rule R7 compliance with missing, matching, and mismatched student identities. Confirmed `answer_type: "refused"`. |
| **Audit Service & Annex D Logger** (`app/repositories/audit_repository.py`) | Audit persistence and Annex D record mapping. | Verified `GET /audit/{trace_id}` returns sources, tools, latency, model, tokens, fallback status, and errors. |
| **Deterministic Tools & SQLite Database** (`app/tools/`, `app/repositories/`) | Member 1 implementation integrated into the API. | Tested boundary cases and ensured zero LLM arithmetic was used for eligibility decisions. |
| **Source Precedence Policy Engine** (`app/workflow/precedence.py`) | Member 3 Annex A implementation integrated into the API. | Verified applicability, supersession, authority, recency, upcoming rules, and unresolved conflicts. |
| **Streamlit UI Dashboard** (`streamlit_app.py`) | Streamlit layout layout widgets, CSS formatting, and tabs configuration. | Interactively tested all 6 query scenarios in the browser UI, ensuring response badge colors, citations, tools invoked, and audit trace viewers render correctly. |

---

## 🔒 3. Verification & Compliance Guarantee
1. **Zero Hardcoded Demo Results**: All query answers, eligibility decisions, and attendance calculations are dynamically derived at runtime via SQLite tools and ChromaDB RAG.
2. **Zero Fabricated Student Data**: Only synthetic student data strictly adhering to Annex C schemas was generated and tested. No real student personal data was used anywhere in the codebase.
3. **Strict Contract Adherence**: All 5 mandatory API endpoints (`POST /ask`, `POST /ingest`, `GET /health`, `GET /audit/{trace_id}`, `GET /sources`) match Section 6 contracts with 100% schema fidelity.
