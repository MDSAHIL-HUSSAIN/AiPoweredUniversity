"""Document, source-register, and retrieval contracts."""

from datetime import date

from pydantic import BaseModel, Field, model_validator


class RetrievalFilters(BaseModel):
    as_of_date: date
    programme: str | None = None
    batch: int | None = None


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str = Field(min_length=1)
    doc_id: str
    title: str
    issuer: str
    authority_level: int = Field(ge=1, le=5)
    doc_type: str
    section: str | None = None
    page: int | None = Field(default=None, ge=1)
    version: str
    effective_from: date
    effective_to: date | None = None
    supersedes: list[str] = Field(default_factory=list)
    scope_programmes: list[str] = Field(default_factory=lambda: ["ALL"])
    scope_batches: list[str] = Field(default_factory=lambda: ["ALL"])
    synthetic: bool = False
    score: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_effective_window(self) -> "RetrievedChunk":
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        return self


class SourceRegisterEntry(BaseModel):
    doc_id: str
    title: str
    issuer: str
    authority_level: int = Field(ge=1, le=5)
    doc_type: str
    version: str
    effective_from: date
    effective_to: date | None = None
    supersedes: list[str] = Field(default_factory=list)
    scope_programmes: list[str] = Field(default_factory=lambda: ["ALL"])
    scope_batches: list[str] = Field(default_factory=lambda: ["ALL"])
    provenance: str
    retrieved_on: date
    synthetic: bool = False

