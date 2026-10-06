"""Deterministic mocks used while real teammate components are unavailable."""

import re
from datetime import date
from typing import Any

from app.contracts import (
    AuditRecord,
    AuthorizationResult,
    RetrievedChunk,
    RetrievalFilters,
    ToolResult,
)


class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk] | None = None) -> None:
        self.chunks = chunks or []

    def retrieve(
        self,
        query: str,
        filters: RetrievalFilters,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        del query
        applicable = [
            chunk
            for chunk in self.chunks
            if chunk.effective_from <= filters.as_of_date
            and (chunk.effective_to is None or chunk.effective_to >= filters.as_of_date)
        ]
        return applicable[:top_k]


class FakeUniversityTools:
    def _result(self, name: str, **inputs: Any) -> ToolResult:
        return ToolResult(
            tool_name=name,
            success=True,
            inputs=inputs,
            output={"status": "ok", "result": {"mock": True}, "rules": []},
            applied_rule_ids=[],
        )

    def get_attendance(
        self, student_id: str, course_code: str | None = None
    ) -> ToolResult:
        return self._result(
            "get_attendance", student_id=student_id, course_code=course_code
        )

    def get_results(
        self, student_id: str, course_code: str | None = None
    ) -> ToolResult:
        return self._result(
            "get_results", student_id=student_id, course_code=course_code
        )

    def check_exam_eligibility(
        self, student_id: str, course_code: str, as_of_date: date
    ) -> ToolResult:
        return self._result(
            "check_exam_eligibility",
            student_id=student_id,
            course_code=course_code,
            as_of_date=as_of_date.isoformat(),
        )

    def check_supplementary_eligibility(
        self, student_id: str, course_code: str, as_of_date: date
    ) -> ToolResult:
        return self._result(
            "check_supplementary_eligibility",
            student_id=student_id,
            course_code=course_code,
            as_of_date=as_of_date.isoformat(),
        )

    def check_placement_eligibility(
        self, student_id: str, as_of_date: date
    ) -> ToolResult:
        return self._result(
            "check_placement_eligibility",
            student_id=student_id,
            as_of_date=as_of_date.isoformat(),
        )

    def run_what_if(
        self, student_id: str, changes: dict[str, Any], as_of_date: date
    ) -> ToolResult:
        return self._result(
            "run_what_if",
            student_id=student_id,
            changes=changes,
            as_of_date=as_of_date.isoformat(),
        )


class FakeAuthorizer:
    def authorize(
        self,
        student_id: str | None,
        question_category: str,
        question: str = "",
    ) -> AuthorizationResult:
        personal_categories = {"personal_data", "eligibility", "multi_step"}
        if question_category in personal_categories and not student_id:
            return AuthorizationResult(
                allowed=False,
                reason="X-Student-ID is required for personal questions.",
            )
        mentioned_ids = set(re.findall(r"\bS\d{4,}\b", question.upper()))
        if (
            question_category in personal_categories
            and student_id
            and any(value != student_id.upper() for value in mentioned_ids)
        ):
            return AuthorizationResult(
                allowed=False,
                reason="Requests for another student's personal data are not allowed.",
            )
        return AuthorizationResult(allowed=True)


class FakeToolExecutor:
    """Dispatcher-shaped fake for graph tests before Member 1 is merged."""

    def __init__(self, tools: FakeUniversityTools | None = None) -> None:
        self.tools = tools or FakeUniversityTools()
        self.calls: list[dict[str, Any]] = []

    def execute(
        self,
        tool_name: str,
        student_id: str | None,
        args: dict[str, Any],
        as_of_date: date,
    ) -> ToolResult:
        self.calls.append(
            {
                "tool_name": tool_name,
                "student_id": student_id,
                "args": args,
                "as_of_date": as_of_date,
            }
        )
        if not student_id:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                inputs=args,
                output={"status": "refused"},
                error="X-Student-ID is required.",
            )

        method = getattr(self.tools, tool_name)
        if tool_name in {
            "check_exam_eligibility",
            "check_supplementary_eligibility",
        }:
            return method(student_id, args["course_code"], as_of_date)
        if tool_name == "check_placement_eligibility":
            return method(student_id, as_of_date)
        if tool_name == "run_what_if":
            return method(student_id, args.get("changes", {}), as_of_date)
        return method(student_id, args.get("course_code"))


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self.records: dict[str, AuditRecord] = {}

    def save(self, record: AuditRecord) -> None:
        self.records[record.trace_id] = record

    def get(self, trace_id: str) -> AuditRecord | None:
        return self.records.get(trace_id)

