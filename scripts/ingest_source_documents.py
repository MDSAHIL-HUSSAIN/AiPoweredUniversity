"""Build the local source register and vector index from downloaded PDFs."""

from __future__ import annotations

import argparse
import csv
import re
from datetime import date
from pathlib import Path

from app.contracts.documents import SourceRegisterEntry
from app.ingestion import (
    ChromaStore,
    Chunker,
    DeterministicEmbeddingService,
    EmbeddingService,
    InMemoryChromaStore,
    IngestionService,
    SQLiteStore,
)


UNKNOWN = {"", "unknown", "n/a", "none", "null"}


def _date(value: str, doc_id: str) -> date:
    if value.strip().lower() not in UNKNOWN:
        return date.fromisoformat(value.strip())
    match = re.match(r"NSUT-(\d{4})(\d{2})(\d{2})-", doc_id)
    if not match:
        raise ValueError(f"No effective date is available for {doc_id}")
    return date(*(int(part) for part in match.groups()))


def _optional_date(value: str) -> date | None:
    return None if value.strip().lower() in UNKNOWN else date.fromisoformat(value.strip())


def _scope(value: str) -> list[str]:
    normalized = value.strip()
    if normalized.lower() in UNKNOWN or normalized.lower().startswith("all "):
        return ["ALL"]
    return [part.strip() for part in normalized.split(",") if part.strip()] or ["ALL"]


def _supersedes(value: str) -> list[str]:
    if value.strip().lower() in UNKNOWN:
        return []
    return [part.strip() for part in re.split(r"[;,]", value) if part.strip()]


def load_source(row: dict[str, str]) -> SourceRegisterEntry:
    return SourceRegisterEntry(
        doc_id=row["doc_id"],
        title=row["title"],
        issuer=row["issuer"],
        authority_level=int(float(row["authority_level"])),
        doc_type=row["doc_type"],
        version=row["version"] if row["version"].lower() not in UNKNOWN else "unknown",
        effective_from=_date(row["effective_from"], row["doc_id"]),
        effective_to=_optional_date(row["effective_to"]),
        supersedes=_supersedes(row["supersedes"]),
        scope_programmes=_scope(row["scope_programmes"]),
        scope_batches=_scope(row["scope_batches"]),
        provenance=row["provenance"],
        retrieved_on=date.fromisoformat(row["retrieved_on"]),
        synthetic=row["synthetic"].strip().lower() in {"y", "yes", "true", "1"},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", type=Path, default=Path("data/source_register.csv"))
    parser.add_argument("--documents", type=Path, default=Path("data/documents"))
    parser.add_argument("--sqlite", default="data/runtime/university.db")
    parser.add_argument("--chroma", default="data/runtime/chroma")
    parser.add_argument("--embedding-model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument(
        "--lightweight",
        action="store_true",
        help="Validate extraction with deterministic in-memory embeddings.",
    )
    args = parser.parse_args()

    vectors = InMemoryChromaStore() if args.lightweight else ChromaStore(args.chroma)
    embeddings = (
        DeterministicEmbeddingService()
        if args.lightweight
        else EmbeddingService(args.embedding_model)
    )
    service = IngestionService(
        Chunker(), embeddings, vectors, SQLiteStore(args.sqlite)
    )

    indexed = 0
    total = 0
    failures: list[str] = []
    with args.register.open(newline="", encoding="utf-8") as source_file:
        for row in csv.DictReader(source_file):
            total += 1
            source = load_source(row)
            pdf_path = args.documents / f"{source.doc_id}.pdf"
            try:
                chunks = service.ingest(str(pdf_path), source)
                indexed += chunks
                print(f"indexed {source.doc_id}: {chunks} chunks")
            except Exception as exc:  # continue so one scanned/corrupt PDF is visible but non-fatal
                failures.append(f"{source.doc_id}: {type(exc).__name__}: {exc}")
                print(f"FAILED {failures[-1]}")

    print(f"indexed {indexed} chunks from {total - len(failures)}/{total} documents")
    if failures:
        print("Failures:")
        for failure in failures:
            print(f"- {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
