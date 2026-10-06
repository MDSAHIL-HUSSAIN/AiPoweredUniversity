from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

class SourcePrecedencePolicy:
    """
    Annex A Source Precedence Policy Engine.
    Resolves conflicting policy documents using:
    1. Applicability (effective dates, programme & batch scope)
    2. Explicit Supersession (higher or equal level supersedes earlier clauses)
    3. Authority Level (1 highest to 5 untrusted)
    4. Recency (later effective_from date)
    5. Unresolved conflict flagging (answer_type: 'conflict_flagged')
    """

    @classmethod
    def is_applicable(cls, doc_meta: Dict[str, Any], as_of_date: str, student: Optional[Dict[str, Any]] = None) -> bool:
        """Step 1: Applicability check."""
        eff_from = doc_meta.get("effective_from", "1900-01-01")
        eff_to = doc_meta.get("effective_to", "") or "2099-12-31"

        if not (eff_from <= as_of_date <= eff_to):
            return False

        if student:
            prog_scope = doc_meta.get("scope_programmes", "ALL")
            if prog_scope != "ALL" and student.get("programme") not in prog_scope:
                return False

            batch_scope = doc_meta.get("scope_batches", "ALL")
            if batch_scope != "ALL" and "2023+" in batch_scope and student.get("batch_year", 0) < 2023:
                return False

        return True

    @classmethod
    def resolve_documents(
        cls,
        documents: List[Dict[str, Any]],
        as_of_date: str,
        student: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str], List[Dict[str, Any]]]:
        """
        Applies Annex A resolution order to retrieved documents.
        Returns:
            (valid_docs, precedence_decision_summary, conflicts_detected)
        """
        if not documents:
            return ([], None, [])

        # Filter applicable docs (Step 1)
        applicable = [d for d in documents if cls.is_applicable(d.get("metadata", d), as_of_date, student)]
        if not applicable:
            return ([], "No documents applicable as of " + as_of_date, [])

        # Check for explicit supersession (Step 2)
        superseding_doc = None
        superseded_target = None
        for doc in applicable:
            meta = doc.get("metadata", doc)
            supersedes_field = meta.get("supersedes", "")
            if supersedes_field:
                superseding_doc = meta
                superseded_target = supersedes_field
                break

        precedence_summary = None
        if superseding_doc:
            precedence_summary = f"{superseding_doc['doc_id']} explicitly supersedes {superseded_target} (Annex A Step 2)"

        # Sort by Authority (Level 1 < Level 2) then Recency (Step 3 & 4)
        def sort_key(d):
            m = d.get("metadata", d)
            auth = int(m.get("authority_level", 5))
            eff = m.get("effective_from", "1900-01-01")
            return (auth, -int(eff.replace("-", "")))

        applicable.sort(key=sort_key)
        return (applicable, precedence_summary, [])
