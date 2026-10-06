import os
import re
from typing import List, Dict, Any, Tuple, Optional

# Attempt ChromaDB & SentenceTransformer imports with fallback
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

class RAGEngine:
    """
    RAG & Knowledge Retrieval Engine.
    Handles chunking, vector embedding, document retrieval, and citation mapping.
    Enforces Rule R1, R2, R3, R11.
    """

    def __init__(
        self,
        persist_dir: str = "chroma_db",
        seed_defaults: bool = True,
        use_chroma: bool = True,
    ):
        self.persist_dir = persist_dir
        self.documents_store: Dict[str, Dict[str, Any]] = {}
        self.chunks_store: List[Dict[str, Any]] = []

        chroma_disabled = os.getenv("CHROMA_DISABLED", "false").lower() in {
            "1", "true", "yes", "on"
        }
        if HAS_CHROMADB and use_chroma and not chroma_disabled:
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.client.get_or_create_collection(name="university_docs")
        else:
            self.client = None
            self.collection = None

        if seed_defaults:
            self._seed_default_documents()

    def _seed_default_documents(self):
        """Seed initial official documents into the RAG vector index."""
        doc1_text = """
        [DOC_ID: NSUT-20260422-ATT75, TITLE: Attendance Requirements Notice, ISSUER: Office of Dean (Academics), AUTHORITY: 1, VERSION: 1.0, EFFECTIVE_FROM: 2024-07-01]

        Section 7.2 Attendance Minimum Requirement:
        Every student is required to attend a minimum of 75% of the total classes held in each course during the semester to be eligible to appear in the end-semester regular examination.

        Section 7.3 Attendance Condonation:
        The Dean (Academics) may condone attendance shortfall up to a maximum of 10% (i.e. between 65% and 74.9%) on genuine medical grounds supported by a valid medical certificate submitted within 7 days of illness.

        """

        doc2_text = """
        [DOC_ID: ACAD-CIRC-2026-08-SYN, TITLE: Revised Attendance Circular, ISSUER: Dean (Academics), AUTHORITY: 1, VERSION: 1.0, EFFECTIVE_FROM: 2026-08-01, SUPERSEDES: NSUT-20260422-ATT75]

        Clause 1 Special Attendance Relief:
        The minimum attendance threshold required for end-semester exam eligibility is revised to 80 percent. This clause supersedes the earlier 75 percent attendance notice.
        """

        doc3_text = """
        [DOC_ID: TNP-POLICY-2024, TITLE: Training and Placement Policy, ISSUER: Training & Placement Cell, AUTHORITY: 2, VERSION: 1.0, EFFECTIVE_FROM: 2024-07-01]

        Clause 3.1 CGPA Cutoff:
        Students participating in campus placement drives must maintain a minimum cumulative grade point average (CGPA) of 6.50 at the end of the 6th semester.

        Clause 3.2 Backlog Restrictions:
        Students having any active backlogs at the time of placement registration shall not be permitted to register or appear for company interviews.
        """

        doc4_text = """
        [DOC_ID: NSUT-20260508-SUMMER, TITLE: Summer Semester Examination Notice, ISSUER: Controller of Examinations, AUTHORITY: 1, VERSION: 1.0, EFFECTIVE_FROM: 2024-07-01]

        Supplementary Examination Eligibility:
        A latest result of FAIL or ABSENT permits a student to apply for the supplementary examination. A student who has already passed is not eligible.
        """

        self.ingest_document("NSUT-20260422-ATT75", doc1_text, {
            "doc_id": "NSUT-20260422-ATT75",
            "title": "Attendance Requirements Notice",
            "version": "1.0",
            "effective_from": "2024-07-01",
            "authority_level": 1
        })
        self.ingest_document("ACAD-CIRC-2026-08-SYN", doc2_text, {
            "doc_id": "ACAD-CIRC-2026-08-SYN",
            "title": "Revised Attendance Circular",
            "version": "1.0",
            "effective_from": "2026-08-01",
            "authority_level": 2,
            "issuer": "Dean Academics",
            "doc_type": "circular",
            "supersedes": ["NSUT-20260422-ATT75"],
            "synthetic": True
        })
        self.ingest_document("TNP-POLICY-2024", doc3_text, {
            "doc_id": "TNP-POLICY-2024",
            "title": "Training and Placement Policy",
            "version": "1.0",
            "effective_from": "2024-07-01",
            "authority_level": 2
        })
        self.ingest_document("NSUT-20260508-SUMMER", doc4_text, {
            "doc_id": "NSUT-20260508-SUMMER",
            "title": "Summer Semester Examination Notice",
            "version": "1.0",
            "effective_from": "2024-07-01",
            "authority_level": 1,
            "issuer": "Controller of Examinations",
            "doc_type": "notice",
        })

    def ingest_document(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> int:
        """Splits document content into chunks and adds them to ChromaDB and memory store."""
        chunks = self._chunk_text(content)
        indexed_count = 0

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{idx}"
            sec_match = re.search(r'(Section\s+\d+(\.\d+)?|Clause\s+\d+(\.\d+)?)', chunk, re.IGNORECASE)
            section = sec_match.group(1) if sec_match else "General"

            chunk_meta = {
                "doc_id": doc_id,
                "title": metadata.get("title", doc_id),
                "section": section,
                "version": metadata.get("version", "1.0"),
                "effective_from": metadata.get("effective_from", "2024-01-01"),
                "authority_level": int(metadata.get("authority_level", 3)),
                "issuer": metadata.get("issuer", "University Office"),
                "doc_type": metadata.get("doc_type", "document"),
                "page": 1,
                "chunk_id": chunk_id,
                "effective_to": metadata.get("effective_to") or None,
                "supersedes": metadata.get("supersedes", []),
                "scope_programmes": metadata.get("scope_programmes", ["ALL"]),
                "scope_batches": metadata.get("scope_batches", ["ALL"]),
                "provenance": metadata.get("provenance"),
                "synthetic": bool(metadata.get("synthetic", False)),
            }

            self.chunks_store.append({
                "chunk_id": chunk_id,
                "content": chunk,
                "metadata": chunk_meta
            })

            if HAS_CHROMADB and self.collection:
                try:
                    self.collection.upsert(
                        ids=[chunk_id],
                        documents=[chunk],
                        metadatas=[chunk_meta]
                    )
                except Exception:
                    pass

            indexed_count += 1

        self.documents_store[doc_id] = {
            "content": content,
            "metadata": metadata,
            "chunks_count": indexed_count
        }
        return indexed_count

    def _chunk_text(self, text: str, max_words: int = 150) -> List[str]:
        """Simple paragraph / clause text chunker."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text]
        return paragraphs

    def query(self, query_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieves top_k relevant chunks with similarity score."""
        results = []

        if HAS_CHROMADB and self.collection:
            try:
                chroma_res = self.collection.query(
                    query_texts=[query_text],
                    n_results=top_k
                )
                if chroma_res and chroma_res["documents"] and chroma_res["documents"][0]:
                    docs = chroma_res["documents"][0]
                    metas = chroma_res["metadatas"][0]
                    distances = chroma_res["distances"][0] if "distances" in chroma_res and chroma_res["distances"] else [0.2] * len(docs)
                    for d, m, dist in zip(docs, metas, distances):
                        score = round(max(0.0, 1.0 - (dist if dist is not None else 0.5)), 2)
                        results.append({
                            "content": d,
                            "metadata": m,
                            "score": score if score > 0 else 0.85
                        })
                    return results
            except Exception:
                pass

        # In-memory keyword overlap fallback
        q_words = set(query_text.lower().split())
        scored_chunks = []
        for c in self.chunks_store:
            c_words = set(c["content"].lower().split())
            overlap = len(q_words.intersection(c_words))
            score = round(min(0.95, 0.4 + (overlap * 0.1)), 2)
            if overlap > 0:
                scored_chunks.append((score, c))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        for score, c in scored_chunks[:top_k]:
            results.append({
                "content": c["content"],
                "metadata": c["metadata"],
                "score": score
            })

        return results
