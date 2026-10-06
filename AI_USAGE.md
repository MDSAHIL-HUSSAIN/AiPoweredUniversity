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
| **FastAPI Endpoints & Pydantic v2 Models** (`main.py`, `app/models.py`) | Initial boilerplate generation for Pydantic v2 schemas and FastAPI route handler signatures. | Verified exact JSON payload structures against Section 6.1 specification using `curl` commands and FastAPI OpenAPI docs (`/docs`). Checked strict field typing and default value generators. |
| **Auth Node & Privacy Refusal Engine** (`app/auth.py`) | Pattern matching logic for regex extraction of `X-Student-Id` headers and prompt injection keyword list. | Verified Rule R7 compliance by sending requests without headers, with matching headers, and with mismatched student IDs (`S1001` requesting `S1002`). Confirmed return of `answer_type: "refused"`. |
| **Audit Service & Annex D Logger** (`app/audit.py`) | Trace ID hex generator and Annex D JSON format dictionary structure. | Verified `GET /audit/{trace_id}` endpoint returns complete metadata including sources retrieved, tools invoked, latency, model, and token count. Validated against `sample_audits/*.json`. |
| **Deterministic Tools & SQLite Database** (`app/tools.py`, `app/database.py`) | SQL schema creation scripts for Annex C tables and SQLite row mapping. | Tested threshold boundary cases (S1001 with 77.5%, S1007 with exact 75.0%, S1002 with 70.0% failure, S1004 detained). Ensured zero LLM arithmetic was used in calculations. |
| **Source Precedence Policy Engine** (`app/precedence.py`) | Step 1-5 resolution ordering logic for Annex A precedence policy. | Executed test queries comparing `ACAD-REG-2024` clause 7.2 vs superseding circular `ACAD-2026-08` clause 1 for B.Tech CSE 2023 batch. |
| **Streamlit UI Dashboard** (`streamlit_app.py`) | Streamlit layout layout widgets, CSS formatting, and tabs configuration. | Interactively tested all 6 query scenarios in the browser UI, ensuring response badge colors, citations, tools invoked, and audit trace viewers render correctly. |

---

## 🔒 3. Verification & Compliance Guarantee
1. **Zero Hardcoded Demo Results**: All query answers, eligibility decisions, and attendance calculations are dynamically derived at runtime via SQLite tools and ChromaDB RAG.
2. **Zero Fabricated Student Data**: Only synthetic student data strictly adhering to Annex C schemas was generated and tested. No real student personal data was used anywhere in the codebase.
3. **Strict Contract Adherence**: All 5 mandatory API endpoints (`POST /ask`, `POST /ingest`, `GET /health`, `GET /audit/{trace_id}`, `GET /sources`) match Section 6 contracts with 100% schema fidelity.
