"""Dependency interfaces that isolate LangGraph from teammate implementations."""

from datetime import date
from typing import Any, Protocol

from app.contracts import (
    AuditRecord,
    AuthorizationResult,
    RetrievedChunk,
    RetrievalFilters,
    ToolResult,
)


class Retriever(Protocol):
    def retrieve(
        self,
        query: str,
        filters: RetrievalFilters,
        top_k: int = 5,
    ) -> list[RetrievedChunk]: ...


class UniversityTools(Protocol):
    def get_attendance(self, student_id: str, course_code: str) -> ToolResult: ...

    def get_results(
        self, student_id: str, course_code: str | None = None
    ) -> ToolResult: ...

    def check_exam_eligibility(
        self, student_id: str, course_code: str, as_of_date: date
    ) -> ToolResult: ...

    def check_supplementary_eligibility(
        self, student_id: str, course_code: str, as_of_date: date
    ) -> ToolResult: ...

    def check_placement_eligibility(
        self, student_id: str, as_of_date: date
    ) -> ToolResult: ...

    def run_what_if(
        self, student_id: str, changes: dict[str, Any], as_of_date: date
    ) -> ToolResult: ...


class Authorizer(Protocol):
    def authorize(
        self, student_id: str | None, question_category: str
    ) -> AuthorizationResult: ...


class AuditRepository(Protocol):
    def save(self, record: AuditRecord) -> None: ...

