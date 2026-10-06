# Team Contribution Statement & Declaration of Original Work

**Project**: AI-Powered University Student Services Assistant  
**Event**: HCLTech | Future Ready AI Engineer Hackathon 2026 (NSUT, Delhi)  
**Date**: 6 October 2026  

---

## 👥 1. Team Member Roles & Breakdown of Work

| Team Member | Module & Responsibility | Key Deliverables & Contributions |
| :--- | :--- | :--- |
| **Member 1** | **RAG & Knowledge Retrieval** | Ingested university documents into ChromaDB vector store; implemented MiniLM text embeddings, chunking strategy, citation mapping, and abstention handling (`answer_type: "not_found"`). |
| **Member 2** | **Deterministic Tools & SQLite Database** | Implemented Annex C SQLite database tables (`students`, `courses`, `attendance`, `results`, `rule_registry`); created deterministic calculation tools (`get_attendance`, `check_exam_eligibility`, `check_placement_eligibility`); synthetic student data kit. |
| **Member 3** | **LangGraph Orchestration & Precedence Policy** | Implemented Annex A Source Precedence Policy engine (authority levels 1-5, applicability, explicit supersession, recency); built decision workflow for multi-step & what-if queries. |
| **Member 4** *(Current Role)* | **API + Infra + Auth + Audit + Streamlit UI + Documentation** | • **FastAPI Backend**: Implemented all 5 mandatory Section 6 endpoints (`POST /ask`, `POST /ingest`, `GET /health`, `GET /audit/{trace_id}`, `GET /sources`) and student loader endpoint.<br>• **Auth Node**: Enforced Rule R7 header authorization (`X-Student-Id`), privacy refusal logic (`answer_type: "refused"`), and R8 prompt injection guard.<br>• **Audit Node**: Implemented Rule R10 auditability service generating Annex D compliant JSON records for every trace ID.<br>• **Streamlit UI**: Built interactive web application with student session switcher, date picker, quick test scenario buttons, answer badges, citations/tools viewer, live ingestion form, source register table, and audit log inspector.<br>• **Infrastructure & Deliverables**: Created `Dockerfile`, `docker-compose.yml`, `README.md` (with architecture diagrams & curl examples), 3 sample audit JSON records (`sample_audits/`), `AI_USAGE.md`, and `CONTRIBUTION.md`. |

---

## ✍️ 2. Signed Declaration of Original Work

We, the undersigned team members, hereby declare that:
1. The code submitted in this repository is our team's original work developed during the hackathon build window, except where external open-source libraries or AI coding assistants are explicitly disclosed in `AI_USAGE.md`.
2. No code was copied directly from uncredited tutorial projects or other participating hackathon teams.
3. No real student personal data (result lists with actual student names/roll numbers) has been used. All student data was synthetically generated.
4. All thresholds and rules applied by deterministic tools trace directly to cited document clauses in the rule registry.

**Signed:**

- **Member 1**: *[Signed - RAG Specialist]*  
- **Member 2**: *[Signed - Data & Tool Specialist]*  
- **Member 3**: *[Signed - Orchestration Lead]*  
- **Member 4**: *[Signed - API, Infra & UI Lead]*  

**Date**: 6 October 2026  
**Venue**: Netaji Subhas University of Technology (NSUT), Delhi  
