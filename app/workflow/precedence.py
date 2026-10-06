"""Deterministic implementation of the Annex A source precedence policy."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from app.contracts import Conflict, RetrievedChunk


_SCOPE_SEPARATOR = re.compile(r"[,;]")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
class PrecedenceResolution:
    """Classified evidence and an auditable record of precedence decisions."""

    current_evidence: list[RetrievedChunk] = field(default_factory=list)
    upcoming_changes: list[RetrievedChunk] = field(default_factory=list)
    inapplicable_chunks: list[RetrievedChunk] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    decision_summary: str = ""

    @property
    def has_unresolved_conflict(self) -> bool:
        return any(not conflict.resolved for conflict in self.conflicts)


def _normalize_scope(value: str) -> str:
    return _NON_ALPHANUMERIC.sub("", value.strip().lower())


def _scope_values(values: list[str]) -> list[str]:
    expanded: list[str] = []
    for value in values:
        expanded.extend(part.strip() for part in _SCOPE_SEPARATOR.split(value))
    return [value for value in expanded if value]


def programme_matches(scopes: list[str], programme: str | None) -> bool:
    """Return whether a source covers the requested programme.

    A missing request programme means a general policy question, so scoped sources
    remain candidates and their scope can be explained in the answer.
    """

    values = _scope_values(scopes)
    if not values or any(value.upper() == "ALL" for value in values):
        return True
    if programme is None:
        return True
    requested = _normalize_scope(programme)
    return any(_normalize_scope(value) == requested for value in values)


def _batch_value_matches(scope: str, batch: int) -> bool:
    value = scope.strip().upper()
    if value == "ALL":
        return True
    if value.endswith("+") and value[:-1].isdigit():
        return batch >= int(value[:-1])
    if "-" in value:
        start, end = (part.strip() for part in value.split("-", maxsplit=1))
        if start.isdigit() and end.isdigit():
            return int(start) <= batch <= int(end)
    return value.isdigit() and int(value) == batch


def batch_matches(scopes: list[str], batch: int | None) -> bool:
    values = _scope_values(scopes)
    if not values or any(value.upper() == "ALL" for value in values):
        return True
    if batch is None:
        return True
    return any(_batch_value_matches(value, batch) for value in values)


def _precedence_sort_key(chunk: RetrievedChunk) -> tuple:
    return (
        chunk.authority_level,
        -chunk.effective_from.toordinal(),
        -chunk.score,
        chunk.doc_id,
        chunk.chunk_id,
    )


def _deduplicate(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    by_id: dict[str, RetrievedChunk] = {}
    for chunk in chunks:
        by_id.setdefault(chunk.chunk_id, chunk)
    return list(by_id.values())


def _parse_supersedes(reference: str) -> list[tuple[str, str | None]]:
    parsed: list[tuple[str, str | None]] = []
    for item in re.split(r"[;,]", reference):
        item = item.strip()
        if not item:
            continue
        doc_id, separator, section = item.partition("#")
        parsed.append((doc_id.strip(), section.strip() if separator else None))
    return parsed


def _matches_superseded_reference(
    chunk: RetrievedChunk,
    target_doc_id: str,
    target_section: str | None,
) -> bool:
    if chunk.doc_id.casefold() != target_doc_id.casefold():
        return False
    if target_section is None:
        return True
    return (chunk.section or "").casefold() == target_section.casefold()


def _document_ids(chunks: list[RetrievedChunk]) -> list[str]:
    return sorted({chunk.doc_id for chunk in chunks})


def resolve_precedence(
    chunks: list[RetrievedChunk],
    *,
    as_of_date: date,
    programme: str | None = None,
    batch: int | None = None,
) -> PrecedenceResolution:
    """Apply Annex A without using an LLM.

    Only chunks sharing a non-empty ``conflict_key`` are treated as contradictory.
    Other chunks are preserved as potentially complementary evidence.
    """

    current_candidates: list[RetrievedChunk] = []
    upcoming: list[RetrievedChunk] = []
    inapplicable: list[RetrievedChunk] = []
    conflicts: list[Conflict] = []

    # A.2 step 1: applicability by scope and effective dates.
    for chunk in chunks:
        if not programme_matches(chunk.scope_programmes, programme) or not batch_matches(
            chunk.scope_batches, batch
        ):
            inapplicable.append(chunk)
        elif chunk.effective_from > as_of_date:
            upcoming.append(chunk)
        elif chunk.effective_to is not None and chunk.effective_to < as_of_date:
            inapplicable.append(chunk)
        else:
            current_candidates.append(chunk)

    # A.2 step 2: explicit supersession is authoritative only at levels 1 and 2.
    superseded_chunk_ids: set[str] = set()
    for superseder in current_candidates:
        if superseder.authority_level not in {1, 2}:
            continue
        references = [
            parsed
            for reference in superseder.supersedes
            for parsed in _parse_supersedes(reference)
        ]
        for target_doc_id, target_section in references:
            targets = [
                chunk
                for chunk in current_candidates
                if chunk.chunk_id != superseder.chunk_id
                and _matches_superseded_reference(
                    chunk, target_doc_id, target_section
                )
            ]
            if not targets:
                continue
            superseded_chunk_ids.update(chunk.chunk_id for chunk in targets)
            conflicts.append(
                Conflict(
                    doc_ids=sorted({superseder.doc_id, *(_document_ids(targets))}),
                    reason=(
                        f"{superseder.doc_id} explicitly supersedes "
                        f"{target_doc_id}"
                        + (f" section {target_section}" if target_section else "")
                        + "; supersession is valid because the issuing source has "
                        f"authority level {superseder.authority_level}."
                    ),
                    resolved=True,
                    selected_doc_id=superseder.doc_id,
                )
            )

    remaining = [
        chunk
        for chunk in current_candidates
        if chunk.chunk_id not in superseded_chunk_ids
    ]
    inapplicable.extend(
        chunk
        for chunk in current_candidates
        if chunk.chunk_id in superseded_chunk_ids
    )

    # A.2 steps 3-5 apply only to sources declared to be about the same rule.
    conflict_groups: dict[str, list[RetrievedChunk]] = defaultdict(list)
    ungrouped: list[RetrievedChunk] = []
    for chunk in remaining:
        if chunk.conflict_key:
            conflict_groups[chunk.conflict_key].append(chunk)
        else:
            ungrouped.append(chunk)

    selected = list(ungrouped)
    for conflict_key, group in conflict_groups.items():
        doc_ids = _document_ids(group)
        if len(doc_ids) < 2:
            selected.extend(group)
            continue

        highest_authority = min(chunk.authority_level for chunk in group)
        authority_winners = [
            chunk for chunk in group if chunk.authority_level == highest_authority
        ]
        most_recent = max(chunk.effective_from for chunk in authority_winners)
        finalists = [
            chunk
            for chunk in authority_winners
            if chunk.effective_from == most_recent
        ]
        finalist_doc_ids = _document_ids(finalists)

        if len(finalist_doc_ids) == 1:
            selected_doc_id = finalist_doc_ids[0]
            winners = [
                chunk for chunk in finalists if chunk.doc_id == selected_doc_id
            ]
            losers = [
                chunk for chunk in group if chunk.doc_id != selected_doc_id
            ]
            selected.extend(winners)
            inapplicable.extend(losers)

            if any(chunk.authority_level != highest_authority for chunk in group):
                reason = (
                    f"Conflict {conflict_key!r} resolved by authority level "
                    f"{highest_authority}; {selected_doc_id} prevails."
                )
            else:
                reason = (
                    f"Conflict {conflict_key!r} resolved by the later effective "
                    f"date {most_recent.isoformat()}; {selected_doc_id} prevails."
                )
            conflicts.append(
                Conflict(
                    doc_ids=doc_ids,
                    reason=reason,
                    resolved=True,
                    selected_doc_id=selected_doc_id,
                )
            )
        else:
            selected.extend(group)
            conflicts.append(
                Conflict(
                    doc_ids=doc_ids,
                    reason=(
                        f"Conflict {conflict_key!r} remains unresolved: the sources "
                        f"have the same authority level ({highest_authority}) and "
                        f"effective date ({most_recent.isoformat()})."
                    ),
                    resolved=False,
                    selected_doc_id=None,
                )
            )

    current = sorted(_deduplicate(selected), key=_precedence_sort_key)
    upcoming = sorted(_deduplicate(upcoming), key=_precedence_sort_key)
    inapplicable = sorted(_deduplicate(inapplicable), key=_precedence_sort_key)
    unresolved_count = sum(not conflict.resolved for conflict in conflicts)
    summary = (
        f"As of {as_of_date.isoformat()}: {len(current)} current chunks, "
        f"{len(upcoming)} upcoming chunks, {len(inapplicable)} inapplicable or "
        f"superseded chunks, {len(conflicts)} conflicts detected "
        f"({unresolved_count} unresolved)."
    )

    return PrecedenceResolution(
        current_evidence=current,
        upcoming_changes=upcoming,
        inapplicable_chunks=inapplicable,
        conflicts=conflicts,
        decision_summary=summary,
    )

