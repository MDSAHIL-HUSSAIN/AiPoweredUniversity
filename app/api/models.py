"""Endpoint-only response models not carried by the workflow."""

from pydantic import BaseModel, Field


class IngestResponse(BaseModel):
    doc_id: str
    chunks_indexed: int = Field(ge=0)
    status: str


class StudentLoaderResponse(BaseModel):
    students_loaded: int = Field(ge=0)
    courses_loaded: int = Field(ge=0)
    attendance_records_loaded: int = Field(ge=0)
    results_records_loaded: int = Field(ge=0)
    rules_loaded: int = Field(ge=0)
    status: str
