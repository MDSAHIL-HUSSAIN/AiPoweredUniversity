from datetime import date

from app.contracts import RetrievedChunk, RouteDecision
from app.workflow.nodes.precedence import resolve_source_precedence
from app.workflow.precedence import batch_matches, resolve_precedence


AS_OF_DATE = date(2026, 10, 6)


def chunk(**overrides) -> RetrievedChunk:
    values = {
        "chunk_id": "chunk-a",
        "text": "Minimum attendance is 75 percent.",
        "doc_id": "DOC-A",
        "title": "Academic Rules",
        "issuer": "Dean Academics",
        "authority_level": 1,
        "doc_type": "regulation",
        "section": "7.2",
        "page": 14,
        "version": "1.0",
        "effective_from": date(2026, 1, 1),
        "score": 0.9,
    }
    values.update(overrides)
    return RetrievedChunk(**values)


def test_classifies_current_upcoming_expired_and_wrong_scope():
    current = chunk()
    upcoming = chunk(
        chunk_id="future",
        doc_id="DOC-FUTURE",
        effective_from=date(2026, 11, 1),
    )
    expired = chunk(
        chunk_id="expired",
        doc_id="DOC-EXPIRED",
        effective_from=date(2025, 1, 1),
        effective_to=date(2025, 12, 31),
    )
    wrong_programme = chunk(
        chunk_id="wrong-programme",
        doc_id="DOC-MBA",
        scope_programmes=["MBA"],
    )
    resolution = resolve_precedence(
        [current, upcoming, expired, wrong_programme],
        as_of_date=AS_OF_DATE,
        programme="B.Tech CSE",
    )

    assert [item.doc_id for item in resolution.current_evidence] == ["DOC-A"]
    assert [item.doc_id for item in resolution.upcoming_changes] == [
        "DOC-FUTURE"
    ]
    assert {item.doc_id for item in resolution.inapplicable_chunks} == {
        "DOC-EXPIRED",
        "DOC-MBA",
    }


def test_batch_scope_supports_exact_plus_and_range():
    assert batch_matches(["2023"], 2023)
    assert batch_matches(["2023+"], 2025)
    assert batch_matches(["2021-2023"], 2022)
    assert not batch_matches(["2023+"], 2022)


def test_level_two_explicit_supersession_removes_old_source():
    old = chunk(
        chunk_id="old",
        doc_id="OLD",
        authority_level=1,
        conflict_key="attendance",
    )
    new = chunk(
        chunk_id="new",
        doc_id="NEW",
        authority_level=2,
        effective_from=date(2026, 9, 1),
        supersedes=["OLD#7.2"],
        conflict_key="attendance",
    )
    resolution = resolve_precedence([old, new], as_of_date=AS_OF_DATE)

    assert [item.doc_id for item in resolution.current_evidence] == ["NEW"]
    assert [item.doc_id for item in resolution.inapplicable_chunks] == ["OLD"]
    assert resolution.conflicts[0].resolved is True
    assert resolution.conflicts[0].selected_doc_id == "NEW"


def test_level_three_supersession_claim_is_ignored():
    authoritative = chunk(
        chunk_id="authoritative",
        doc_id="REGULATION",
        authority_level=1,
        conflict_key="attendance",
    )
    department = chunk(
        chunk_id="department",
        doc_id="DEPARTMENT",
        authority_level=3,
        effective_from=date(2026, 9, 1),
        supersedes=["REGULATION"],
        conflict_key="attendance",
    )
    resolution = resolve_precedence(
        [authoritative, department], as_of_date=AS_OF_DATE
    )

    assert [item.doc_id for item in resolution.current_evidence] == [
        "REGULATION"
    ]
    assert resolution.conflicts[0].selected_doc_id == "REGULATION"
    assert "authority level 1" in resolution.conflicts[0].reason


def test_higher_authority_beats_more_recent_lower_authority():
    regulation = chunk(
        chunk_id="regulation",
        doc_id="REGULATION",
        authority_level=1,
        effective_from=date(2025, 1, 1),
        conflict_key="attendance",
    )
    faq = chunk(
        chunk_id="faq",
        doc_id="FAQ",
        authority_level=4,
        effective_from=date(2026, 9, 1),
        conflict_key="attendance",
    )
    resolution = resolve_precedence([faq, regulation], as_of_date=AS_OF_DATE)

    assert [item.doc_id for item in resolution.current_evidence] == [
        "REGULATION"
    ]
    assert resolution.conflicts[0].selected_doc_id == "REGULATION"


def test_recency_breaks_tie_at_same_authority():
    older = chunk(
        chunk_id="older",
        doc_id="OLDER",
        authority_level=2,
        effective_from=date(2026, 1, 1),
        conflict_key="attendance",
    )
    newer = chunk(
        chunk_id="newer",
        doc_id="NEWER",
        authority_level=2,
        effective_from=date(2026, 8, 1),
        conflict_key="attendance",
    )
    resolution = resolve_precedence([older, newer], as_of_date=AS_OF_DATE)

    assert [item.doc_id for item in resolution.current_evidence] == ["NEWER"]
    assert "later effective date" in resolution.conflicts[0].reason


def test_equal_authority_and_date_remains_unresolved():
    first = chunk(
        chunk_id="first",
        doc_id="FIRST",
        authority_level=2,
        conflict_key="attendance",
    )
    second = chunk(
        chunk_id="second",
        doc_id="SECOND",
        authority_level=2,
        conflict_key="attendance",
    )
    resolution = resolve_precedence([first, second], as_of_date=AS_OF_DATE)

    assert {item.doc_id for item in resolution.current_evidence} == {
        "FIRST",
        "SECOND",
    }
    assert resolution.has_unresolved_conflict is True
    assert resolution.conflicts[0].selected_doc_id is None


def test_level_five_never_overrides_authoritative_source():
    regulation = chunk(
        chunk_id="regulation",
        doc_id="REGULATION",
        authority_level=1,
        effective_from=date(2025, 1, 1),
        conflict_key="attendance",
    )
    unofficial = chunk(
        chunk_id="unofficial",
        doc_id="FORUM",
        authority_level=5,
        effective_from=date(2026, 10, 1),
        conflict_key="attendance",
    )
    resolution = resolve_precedence(
        [unofficial, regulation], as_of_date=AS_OF_DATE
    )

    assert [item.doc_id for item in resolution.current_evidence] == [
        "REGULATION"
    ]


def test_complementary_sources_are_preserved_without_conflict_key():
    regulation = chunk(chunk_id="reg", doc_id="REG")
    procedure = chunk(
        chunk_id="procedure",
        doc_id="PROCEDURE",
        authority_level=2,
        text="Submit the form to the examinations office.",
    )
    resolution = resolve_precedence(
        [procedure, regulation], as_of_date=AS_OF_DATE
    )

    assert {item.doc_id for item in resolution.current_evidence} == {
        "REG",
        "PROCEDURE",
    }
    assert resolution.conflicts == []


def test_langgraph_node_uses_route_scope_and_merges_conflicts():
    btech = chunk(scope_programmes=["B.Tech CSE"], scope_batches=["2023+"])
    mba = chunk(
        chunk_id="mba",
        doc_id="MBA",
        scope_programmes=["MBA"],
    )
    state = {
        "as_of_date": AS_OF_DATE,
        "route": RouteDecision(
            category="policy_fact",
            entities={"programme": "B.Tech CSE", "batch": 2023},
            needs_retrieval=True,
            needs_student_tools=False,
        ),
        "retrieved_chunks": [btech, mba],
        "conflicts_detected": [],
    }

    update = resolve_source_precedence(state)

    assert [item.doc_id for item in update["current_evidence"]] == ["DOC-A"]
    assert [item.doc_id for item in update["inapplicable_chunks"]] == ["MBA"]
    assert "1 current chunks" in update["precedence_decision"]

