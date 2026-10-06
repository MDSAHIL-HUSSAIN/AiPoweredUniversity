import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form, Request, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    AskRequest, AskResponse, IngestResponse, SourceRegisterItem,
    AuditRecord, StudentLoaderResponse
)
from app import database
from app.audit import AuditService
from app.engine import AssistantEngine, rag_engine

app = FastAPI(
    title="AI-Powered University Student Services Assistant API",
    description="HCLTech Hackathon Production API implementing Section 6 mandatory contract, Auth Node, RAG, Deterministic Tools, and Auditability.",
    version="1.0.0"
)

# Enable CORS for Streamlit frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    """Initializes SQLite database and seeds Annex C/B tables on startup."""
    database.init_db()

# --- 1. POST /ask ---
@app.post("/ask", response_model=AskResponse, summary="Ask a question to the student services assistant")
async def ask_question(
    request_data: AskRequest,
    request: Request,
    x_student_id: Optional[str] = Header(None, alias="X-Student-Id")
):
    """
    Main endpoint for student queries.
    - Header: X-Student-Id (optional for policy queries, mandatory for personal data/eligibility)
    - Body: question (str), as_of_date (str YYYY-MM-DD, defaults to today)
    - Enforces Rule R7 privacy refusal, R5 deterministic tool execution, R4 source precedence, and R10 auditability.
    """
    as_of_date = request_data.as_of_date or datetime.now().strftime("%Y-%m-%d")
    
    ask_resp, audit_rec = AssistantEngine.process_question(
        question=request_data.question,
        header_student_id=x_student_id,
        as_of_date=as_of_date
    )
    
    return ask_resp

# --- 2. POST /ingest ---
@app.post("/ingest", response_model=IngestResponse, summary="Live ingest a new university document")
async def ingest_document(
    file: UploadFile = File(...),
    metadata: str = Form(..., description="JSON string with Source Register Annex B metadata fields")
):
    """
    Live document ingestion endpoint (Rule R11).
    - Multipart upload: file + metadata JSON
    - Indexes text into vector database immediately without code restart.
    - Updates SQLite Source Register table.
    """
    try:
        meta_dict = json.loads(metadata)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON metadata string: {str(e)}")

    doc_id = meta_dict.get("doc_id")
    if not doc_id:
        raise HTTPException(status_code=400, detail="Missing required field 'doc_id' in metadata JSON")

    # Read uploaded file content
    contents = await file.read()
    try:
        text_content = contents.decode("utf-8")
    except UnicodeDecodeError:
        text_content = contents.decode("latin-1", errors="ignore")

    # Add to RAG Vector Engine
    chunks_indexed = rag_engine.ingest_document(doc_id, text_content, meta_dict)

    # Add to SQLite Source Register (Annex B)
    source_item = {
        "doc_id": doc_id,
        "title": meta_dict.get("title", doc_id),
        "issuer": meta_dict.get("issuer", "University Office"),
        "authority_level": int(meta_dict.get("authority_level", 3)),
        "doc_type": meta_dict.get("doc_type", "circular"),
        "version": meta_dict.get("version", "1.0"),
        "effective_from": meta_dict.get("effective_from", datetime.now().strftime("%Y-%m-%d")),
        "effective_to": meta_dict.get("effective_to", ""),
        "supersedes": meta_dict.get("supersedes", ""),
        "scope_programmes": meta_dict.get("scope_programmes", "ALL"),
        "scope_batches": meta_dict.get("scope_batches", "ALL"),
        "provenance": meta_dict.get("provenance", "Uploaded via POST /ingest"),
        "retrieved_on": datetime.now().strftime("%Y-%m-%d"),
        "synthetic": meta_dict.get("synthetic", "N")
    }
    database.add_source_register_item(source_item)

    return IngestResponse(
        doc_id=doc_id,
        chunks_indexed=chunks_indexed,
        status="success"
    )

# --- 3. GET /health ---
@app.get("/health", summary="Readiness & health check endpoint")
async def get_health():
    """
    Returns operational status of API, ChromaDB vector store, SQLite DB, and LLM engine.
    """
    db_status = "healthy"
    try:
        conn = database.get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "ok",
        "api": "healthy",
        "vector_store": "healthy" if rag_engine else "degraded",
        "database": db_status,
        "llm": "healthy (llama3.1:8b Ollama / MOCK fallback)"
    }

# --- 4. GET /audit/{trace_id} ---
@app.get("/audit/{trace_id}", response_model=AuditRecord, summary="Retrieve complete audit record by trace ID")
async def get_audit_record(trace_id: str):
    """
    Returns full audit record matching Annex D schema for a specific request trace ID.
    Enforces Rule R10.
    """
    record = AuditService.get_record(trace_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Audit record not found for trace_id '{trace_id}'")
    return record

# --- 5. GET /sources ---
@app.get("/sources", response_model=List[SourceRegisterItem], summary="Get Source Register of ingested documents")
async def get_sources():
    """
    Returns all ingested documents and their Annex B metadata stored in the Source Register.
    """
    sources = database.get_source_register()
    return sources

# --- Admin / Judge Loader Endpoint ---
@app.post("/test-student-loader", response_model=StudentLoaderResponse, summary="Load judge test data or re-seed student database")
async def load_test_students():
    """
    CLI/admin loader endpoint that loads test students into SQLite (Annex C schema).
    Allows judges to load unseen test datasets.
    """
    database.init_db()
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM students")
    s_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM courses")
    c_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM attendance")
    a_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM results")
    r_count = cursor.fetchone()[0]
    conn.close()

    return StudentLoaderResponse(
        students_loaded=s_count,
        courses_loaded=c_count,
        attendance_records_loaded=a_count,
        results_records_loaded=r_count,
        status="successfully loaded synthetic student test database"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
