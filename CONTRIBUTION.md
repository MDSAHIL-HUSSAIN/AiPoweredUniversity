# Team Contribution Statement & Declaration of Original Work

**Project**: AI-Powered University Student Services Assistant
**Event**: HCLTech | Future Ready AI Engineer Hackathon 2026 (NSUT, Delhi)
**Date**: 6 October 2026

---

## 👥 1. Team Member Roles & Breakdown of Work

| Team Member | Module & Responsibility | Key Deliverables & Contributions |
| :--- | :--- | :--- |
| **Member 1** | **Data, Rules, Tools & Evaluation** | Implemented synthetic datasets, Annex C SQLite tables, rule registry, deterministic tools, edge cases, evaluation set, and data card. |
| **Member 2** | **Documents, Ingestion & Retrieval** | Owns source collection, source register, OCR/text extraction, section chunking, embeddings, ChromaDB retrieval, metadata filters, and retrieval configuration evaluation. |
| **Member 3** | **LangGraph & Local LLM** | Implemented typed routing, authorization/tool orchestration, Annex A precedence, evidence-only composition, citation validation, Ollama/mock modes, fallback behavior, and graph wiring. |
| **Member 4** *(Current Role)* | **API + Infra + Auth + Audit + Streamlit UI + Documentation** | • **FastAPI Backend**: Implemented all 5 mandatory Section 6 endpoints (`POST /ask`, `POST /ingest`, `GET /health`, `GET /audit/{trace_id}`, `GET /sources`) and student loader endpoint.<br>• **Auth Node**: Enforced Rule R7 header authorization (`X-Student-Id`), privacy refusal logic (`answer_type: "refused"`), and R8 prompt injection guard.<br>• **Audit Node**: Implemented Rule R10 auditability service generating Annex D compliant JSON records for every trace ID.<br>• **Streamlit UI**: Built interactive web application with student session switcher, date picker, quick test scenario buttons, answer badges, citations/tools viewer, live ingestion form, source register table, and audit log inspector.<br>• **Infrastructure & Deliverables**: Created `Dockerfile`, `docker-compose.yml`, `README.md` (with architecture diagrams & curl examples), 3 sample audit JSON records (`sample_audits/`), `AI_USAGE.md`, and `CONTRIBUTION.md`. |

---

## ✍️ 2. Signed Declaration of Original Work

We, the undersigned team members, hereby declare that:
1. The code submitted in this repository is our team's original work developed during the hackathon build window, except where external open-source libraries or AI coding assistants are explicitly disclosed in `AI_USAGE.md`.
2. No code was copied directly from uncredited tutorial projects or other participating hackathon teams.
3. No real student personal data (result lists with actual student names/roll numbers) has been used. All student data was synthetically generated.
4. All thresholds and rules applied by deterministic tools trace directly to cited document clauses in the rule registry.

**Signed:**

- **Member 1**: *[Signed - Data, Tools & Evaluation]*
- **Member 2**: *[Signed - Documents, Ingestion & Retrieval]*
- **Member 3**: *[Signed - LangGraph & LLM]*
- **Member 4**: *[Signed - API, Infra & UI Lead]*

**Date**: 6 October 2026
**Venue**: Netaji Subhas University of Technology (NSUT), Delhi
