import json
from datetime import date

from app.contracts.documents import RetrievedChunk, RetrievalFilters


class UniversityRetriever:

    def __init__(
        self,
        chroma_store,
        sqlite_store,
        embedding_service,
    ):
        self.chroma = chroma_store
        self.sqlite = sqlite_store
        self.embeddings = embedding_service

    def retrieve(
        self,
        query: str,
        filters: RetrievalFilters,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:

        query_embedding = self.embeddings.embed_query(query)

        # Retrieve extra candidates because some will
        # be removed by applicability filtering.
        candidate_count = max(top_k * 5, 20)

        results = self.chroma.search(
            query_embedding=query_embedding,
            n_results=candidate_count,
        )

        chunks = self._convert_results(results)

        doc_ids = list({
            chunk["doc_id"]
            for chunk in chunks
        })

        sources = self.sqlite.get_sources(doc_ids)

        retrieved = []

        for chunk in chunks:

            source = sources.get(chunk["doc_id"])

            if source is None:
                continue

            if not self._is_applicable(source, filters):
                continue

            retrieved.append(
                self._build_retrieved_chunk(
                    chunk,
                    source,
                )
            )

        retrieved.sort(
            key=lambda x: x.score,
            reverse=True,
        )

        return retrieved[:top_k]

    def _convert_results(
        self,
        results: dict,
    ) -> list[dict]:

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        chunks = []

        for i, chunk_id in enumerate(ids):

            metadata = metadatas[i] or {}

            distance = (
                distances[i]
                if i < len(distances)
                else 0.0
            )

            # Convert distance into a non-negative
            # similarity score.
            score = 1.0 / (1.0 + distance)

            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": documents[i],
                    "doc_id": metadata.get("doc_id"),
                    "section": metadata.get("section") or None,
                    "page": metadata.get("page") or None,
                    "score": score,
                }
            )

        return chunks

    def _is_applicable(
        self,
        source: dict,
        filters: RetrievalFilters,
    ) -> bool:

        effective_from = (
            date.fromisoformat(source["effective_from"])
            if source.get("effective_from")
            else None
        )

        effective_to = source.get("effective_to")

        if effective_to:
            effective_to = date.fromisoformat(
                effective_to
            )

        # Document must be effective on the requested date.
        if effective_from and filters.as_of_date < effective_from:
            return False

        if effective_to and filters.as_of_date > effective_to:
            return False

        # Programme applicability.
        programmes = self._parse_list(
            source.get("scope_programmes")
        )

        if (
            filters.programme is not None
            and "ALL" not in programmes
            and filters.programme not in programmes
        ):
            return False

        # Batch applicability.
        batches = self._parse_list(
            source.get("scope_batches")
        )

        if (
            filters.batch is not None
            and "ALL" not in batches
            and str(filters.batch) not in batches
        ):
            return False

        return True

    def _build_retrieved_chunk(
        self,
        chunk: dict,
        source: dict,
    ) -> RetrievedChunk:

        return RetrievedChunk(
            chunk_id=chunk["chunk_id"],
            text=chunk["text"],
            doc_id=source["doc_id"],
            title=source["title"],
            issuer=source["issuer"],
            authority_level=int(
                source["authority_level"]
            ),
            doc_type=source["doc_type"],
            section=chunk.get("section"),
            page=chunk.get("page"),
            version=source["version"],
            effective_from=date.fromisoformat(
                source["effective_from"]
            ),
            effective_to=(
                date.fromisoformat(source["effective_to"])
                if source.get("effective_to")
                else None
            ),
            supersedes=self._parse_list(
                source.get("supersedes")
            ),
            scope_programmes=self._parse_list(
                source.get("scope_programmes")
            ),
            scope_batches=self._parse_list(
                source.get("scope_batches")
            ),
            provenance=source.get("provenance"),
            synthetic=bool(
                source.get("synthetic", False)
            ),
            score=chunk["score"],
        )

    @staticmethod
    def _parse_list(value) -> list[str]:

        if value is None or value == "":
            return ["ALL"]

        if isinstance(value, list):
            return [str(item) for item in value]

        try:
            parsed = json.loads(value)

            if isinstance(parsed, list):
                return [str(item) for item in parsed]

        except (json.JSONDecodeError, TypeError):
            pass

        return [str(value)]
