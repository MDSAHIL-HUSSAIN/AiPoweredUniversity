import json
from pathlib import Path

from app.contracts.documents import SourceRegisterEntry
from app.ingestion.parser import parse_pdf
from app.ingestion.chunker import Chunker
from app.ingestion.embeddings import EmbeddingService
from app.ingestion.chroma_store import ChromaStore
from app.ingestion.sqlite_store import SQLiteStore


class IngestionService:

    def __init__(
        self,
        chunker: Chunker,
        embedding_service: EmbeddingService,
        chroma_store: ChromaStore,
        sqlite_store: SQLiteStore,
    ):
        self.chunker = chunker
        self.embeddings = embedding_service
        self.chroma = chroma_store
        self.sqlite = sqlite_store

    def ingest(
        self,
        file_path: str,
        source: SourceRegisterEntry,
    ) -> int:

        path = Path(file_path)

        pages = parse_pdf(path)

        chunks = self.chunker.chunk_pages(
            doc_id=source.doc_id,
            pages=pages,
        )

        if not chunks:
            return 0

        texts = [
            chunk.text
            for chunk in chunks
        ]

        embeddings = self.embeddings.embed_documents(
            texts
        )

        metadatas = [
            self._build_chroma_metadata(
                source,
                chunk,
            )
            for chunk in chunks
        ]

        self.chroma.upsert(
            ids=[
                chunk.chunk_id
                for chunk in chunks
            ],
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        # Register the document only after Chroma
        # ingestion succeeds.
        self.sqlite.register_source(source)

        return len(chunks)

    @staticmethod
    def _build_chroma_metadata(
        source: SourceRegisterEntry,
        chunk,
    ) -> dict:

        return {
            "doc_id": source.doc_id,
            "title": source.title,
            "issuer": source.issuer,
            "authority_level": source.authority_level,
            "doc_type": source.doc_type,
            "version": source.version,
            "effective_from": source.effective_from.isoformat(),
            "effective_to": (
                source.effective_to.isoformat()
                if source.effective_to
                else ""
            ),
            "supersedes": json.dumps(
                source.supersedes
            ),
            "scope_programmes": json.dumps(
                source.scope_programmes
            ),
            "scope_batches": json.dumps(
                source.scope_batches
            ),
            "synthetic": source.synthetic,
            "section": chunk.section or "",
            "page": chunk.page,
        }