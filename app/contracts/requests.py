"""API request contracts shared by the API and workflow layers."""

from datetime import date

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Question body for POST /ask.

    The authenticated student ID is deliberately not part of the body. FastAPI
    obtains it from the trusted X-Student-ID request header.
    """

    question: str = Field(min_length=1, max_length=4_000)
    as_of_date: date | None = None


class IngestMetadata(BaseModel):
    """Metadata submitted with a document to POST /ingest."""

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
    synthetic: bool = False

