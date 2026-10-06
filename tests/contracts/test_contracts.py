from datetime import date

import pytest
from pydantic import ValidationError

from app.contracts import AskRequest, RetrievedChunk, RetrievalFilters
from app.workflow.mocks import FakeRetriever


def make_chunk(**overrides):
    values = {
        "chunk_id": "chunk-1",
        "text": "Minimum attendance is 75 percent.",
        "doc_id": "ACAD-REG-2024",
        "title": "Academic Regulations",
        "issuer": "Dean Academics",
        "authority_level": 1,
        "doc_type": "regulation",
        "section": "7.2",
        "page": 14,
        "version": "3.1",
        "effective_from": date(2024, 7, 1),
        "score": 0.91,
    }
    values.update(overrides)
    return RetrievedChunk(**values)


def test_ask_request_rejects_empty_question():
    with pytest.raises(ValidationError):
        AskRequest(question="")


def test_retrieved_chunk_rejects_invalid_effective_window():
    with pytest.raises(ValidationError):
        make_chunk(
            effective_from=date(2026, 1, 2),
            effective_to=date(2026, 1, 1),
        )


def test_fake_retriever_applies_effective_date():
    current = make_chunk()
    future = make_chunk(
        chunk_id="future",
        doc_id="FUTURE-2027",
        effective_from=date(2027, 1, 1),
    )
    retriever = FakeRetriever([current, future])

    results = retriever.retrieve(
        "attendance",
        RetrievalFilters(as_of_date=date(2026, 10, 6)),
    )

    assert [result.doc_id for result in results] == ["ACAD-REG-2024"]

