from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# --- Section 6 API Request & Response Models ---

class Citation(BaseModel):
    doc_id: str = Field(..., description="Document ID, e.g. ACAD-REG-2024")
    title: str = Field(..., description="Document title")
    section: str = Field(..., description="Clause or section reference, e.g. 7.2")
    page: Optional[int] = Field(None, description="Page number if applicable")
    version: str = Field(..., description="Document version, e.g. 3.1")
    effective_from: str = Field(..., description="Effective date YYYY-MM-DD")

class ToolInvocation(BaseModel):
    tool: str = Field(..., description="Name of tool invoked, e.g. get_attendance")
    input: Dict[str, Any] = Field(default_factory=dict, description="Input parameters passed to tool")
    output: Dict[str, Any] = Field(default_factory=dict, description="Output returned by tool")
    status: Optional[str] = Field("ok", description="Execution status: ok or error")
    ms: Optional[int] = Field(0, description="Latency in milliseconds")

class AppliedRule(BaseModel):
    rule_id: str = Field(..., description="Rule ID, e.g. ATT-MIN-01")
    value: str = Field(..., description="Threshold or rule condition applied, e.g. >=75%")
    source_doc_id: str = Field(..., description="Source document doc_id, e.g. ACAD-REG-2024")

class ConflictDetected(BaseModel):
    doc_id_1: str = Field(..., description="First conflicting document ID")
    doc_id_2: str = Field(..., description="Second conflicting document ID")
    clause_1: str = Field(..., description="Clause from document 1")
    clause_2: str = Field(..., description="Clause from document 2")
    description: str = Field(..., description="Description of the conflict")

class AskRequest(BaseModel):
    question: str = Field(..., description="Student's query text")
    as_of_date: Optional[str] = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d"),
        description="Target evaluation date YYYY-MM-DD, defaults to current date"
    )

class AskResponse(BaseModel):
    trace_id: str = Field(..., description="Unique UUID or trace identifier")
    answer: str = Field(..., description="Direct answer to student query")
    answer_type: Literal[
        "retrieved_fact",
        "calculated",
        "not_found",
        "clarification_needed",
        "refused",
        "conflict_flagged"
    ] = Field(..., description="Standardized answer classification enum")
    citations: List[Citation] = Field(default_factory=list, description="Authorised sources supporting answer")
    tools_invoked: List[ToolInvocation] = Field(default_factory=list, description="Deterministic tools run")
    applied_rules: List[AppliedRule] = Field(default_factory=list, description="Rules applied from SQLite rule registry")
    conflicts_detected: List[ConflictDetected] = Field(default_factory=list, description="Document conflicts identified")
    explanation: str = Field(..., description="Plain language step-by-step breakdown")
    as_of_date: str = Field(..., description="Effective reference date used")

class IngestResponse(BaseModel):
    doc_id: str = Field(..., description="Unique document ID created/updated")
    chunks_indexed: int = Field(..., description="Number of text chunks embedded in vector store")
    status: str = Field("success", description="Ingestion status")

class SourceRegisterItem(BaseModel):
    doc_id: str = Field(..., description="Unique identifier, e.g. ACAD-REG-2024")
    title: str = Field(..., description="Document title")
    issuer: str = Field(..., description="Issuing authority office")
    authority_level: int = Field(..., description="Authority level 1 (highest) to 5 (untrusted)")
    doc_type: str = Field(..., description="regulation, circular, notice, faq, handbook, unofficial")
    version: str = Field(..., description="Version string")
    effective_from: str = Field(..., description="Effective start date YYYY-MM-DD")
    effective_to: Optional[str] = Field("", description="Effective end date YYYY-MM-DD or empty")
    supersedes: Optional[str] = Field("", description="Doc IDs or clauses superseded, semicolon separated")
    scope_programmes: str = Field("ALL", description="Programmes covered or ALL")
    scope_batches: str = Field("ALL", description="Admission years or ALL")
    provenance: Optional[str] = Field("", description="URL or source details")
    retrieved_on: str = Field(..., description="Date downloaded YYYY-MM-DD")
    synthetic: str = Field("N", description="Y if mock/synthetic document, N if official")

class AuditRecord(BaseModel):
    trace_id: str = Field(..., description="Trace UUID")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    student_id: Optional[str] = Field(None, description="Requesting student ID if authenticated")
    question: str = Field(..., description="User query text")
    question_category: str = Field(..., description="Question classification category")
    sources_retrieved: List[Dict[str, Any]] = Field(default_factory=list)
    precedence_decision: Optional[str] = Field(None, description="Resolution step details")
    tools_invoked: List[Dict[str, Any]] = Field(default_factory=list)
    applied_rules: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts_detected: List[Any] = Field(default_factory=list)
    answer: str = Field(..., description="Returned answer")
    answer_type: str = Field(..., description="Classification type")
    explanation: str = Field(..., description="Detailed explanation")
    model: str = Field("llama3.1:8b", description="LLM engine used")
    llm_calls: int = Field(1, description="Number of LLM calls made")
    tokens: int = Field(0, description="Total prompt + completion tokens used")
    latency_ms: int = Field(0, description="Total execution latency in milliseconds")

class StudentLoaderRequest(BaseModel):
    source_dir: Optional[str] = Field(None, description="Directory containing CSV files or loads default sample kit")

class StudentLoaderResponse(BaseModel):
    students_loaded: int
    courses_loaded: int
    attendance_records_loaded: int
    results_records_loaded: int
    status: str
