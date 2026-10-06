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

    def __init__(self, persist_dir: str = "chroma_db"):
        self.persist_dir = persist_dir
        self.documents_store: Dict[str, Dict[str, Any]] = {}
        self.chunks_store: List[Dict[str, Any]] = []

        if HAS_CHROMADB:
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.client.get_or_create_collection(name="university_docs")
        else:
            self.client = None
            self.collection = None

        # Pre-populate initial university documents
        self._seed_default_documents()

    def _seed_default_documents(self):
        """Seed initial official documents into the RAG vector index."""
        doc1_text = """
        [DOC_ID: ACAD-REG-2024, TITLE: Academic Regulations for B.Tech Programmes, ISSUER: Office of Dean (Academics), AUTHORITY: 1, VERSION: 3.1, EFFECTIVE_FROM: 2024-07-01]
        
        Section 7.2 Attendance Minimum Requirement:
        Every student is required to attend a minimum of 75% of the total classes held in each course during the semester to be eligible to appear in the end-semester regular examination.
        
        Section 7.3 Attendance Condonation:
        The Dean (Academics) may condone attendance shortfall up to a maximum of 10% (i.e. between 65% and 74.9%) on genuine medical grounds supported by a valid medical certificate submitted within 7 days of illness.
        
        Section 9.1 Supplementary Examination Eligibility:
        A student who obtains a 'FAIL' grade in a regular course examination but has satisfied the minimum attendance criteria of 75% shall be eligible to apply for and appear in the supplementary examination. Students with 'DETAINED' status due to low attendance cannot sit for supplementary exams and must re-register for the course.
        """

        doc2_text = """
        [DOC_ID: ACAD-2026-08, TITLE: Circular on Special Attendance Allowance for 2023 Batch, ISSUER: Dean (Academics), AUTHORITY: 2, VERSION: 1.0, EFFECTIVE_FROM: 2026-08-01, SUPERSEDES: ACAD-REG-2024#7.2]
        
        Clause 1 Special Attendance Relief:
        Notice is hereby given that for B.Tech CSE students of the 2023 batch onwards, the minimum attendance threshold required for end-semester exam eligibility is revised to 70% for the Academic Year 2026-27 due to university campus renovation and technical workshops. This clause explicitly supersedes Section 7.2 of ACAD-REG-2024 for the specified scope.
        """

        doc3_text = """
        [DOC_ID: PLACEMENT-POLICY-2025, TITLE: Training and Placement Policy 2025-26, ISSUER: Training & Placement Cell, AUTHORITY: 2, VERSION: 2.0, EFFECTIVE_FROM: 2025-01-01]
        
        Clause 3.1 CGPA Cutoff:
        Students participating in campus placement drives must maintain a minimum cumulative grade point average (CGPA) of 6.50 at the end of the 6th semester.
        
        Clause 3.2 Backlog Restrictions:
        Students having any active backlogs at the time of placement registration shall not be permitted to register or appear for company interviews.
        """

        self.ingest_document("ACAD-REG-2024", doc1_text, {
            "doc_id": "ACAD-REG-2024",
            "title": "Academic Regulations for B.Tech Programmes",
            "version": "3.1",
            "effective_from": "2024-07-01",
            "authority_level": 1
        })
        self.ingest_document("ACAD-2026-08", doc2_text, {
            "doc_id": "ACAD-2026-08",
            "title": "Circular on Special Attendance Allowance for 2023 Batch",
            "version": "1.0",
            "effective_from": "2026-08-01",
            "authority_level": 2
        })
        self.ingest_document("PLACEMENT-POLICY-2025", doc3_text, {
            "doc_id": "PLACEMENT-POLICY-2025",
            "title": "Training and Placement Policy 2025-26",
            "version": "2.0",
            "effective_from": "2025-01-01",
            "authority_level": 2
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
                "page": 1,
                "chunk_id": chunk_id
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
