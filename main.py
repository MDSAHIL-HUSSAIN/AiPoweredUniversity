"""FastAPI entry point wired to the shared LangGraph workflow."""

import json
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.api.models import IngestResponse, StudentLoaderResponse
from app.contracts import (
    AskRequest,
    AskResponse,
    AuditRecord,
    HealthResponse,
    IngestMetadata,
    SourceRegisterEntry,
)
from app.engine import AssistantEngine
from app.repositories.rule_repository import RuleRepository
from app.repositories.source_repository import SourceRepository
from scripts.load_students import load_dir


engine = AssistantEngine()
sources = SourceRepository(engine.conn)


def _load_demo_data() -> None:
    student_count = engine.conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    if student_count == 0:
        data_dir = os.getenv("STUDENT_DATA_DIR", "./data/synthetic")
        if os.path.isdir(data_dir):
            load_dir(engine.conn, data_dir)
    rule_count = engine.conn.execute("SELECT COUNT(*) FROM rule_registry").fetchone()[0]
    rules_path = os.getenv("RULE_REGISTRY_PATH", "./data/rule_registry.csv")
    if rule_count == 0 and os.path.exists(rules_path):
        RuleRepository(engine.conn).load_csv(rules_path)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _load_demo_data()
    yield


app = FastAPI(
    title="AI-Powered University Student Services Assistant API",
    description="Section 6 API backed by LangGraph, deterministic tools, and audit logging.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/ask", response_model=AskResponse)
async def ask_question(
    request_data: AskRequest,
    x_student_id: str | None = Header(None, alias="X-Student-Id"),
):
    return await engine.process_question(
        question=request_data.question,
        header_student_id=x_student_id,
        as_of_date=request_data.as_of_date or date.today(),
    )


@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    metadata: str = Form(...),
):
    try:
        ingest_metadata = IngestMetadata.model_validate_json(metadata)
    except (ValidationError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid ingestion metadata: {exc}")

    contents = await file.read()
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=415,
            detail="The ingestion pipeline accepts PDF documents.",
        )
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF exceeds the 20 MB upload limit.")

    metadata_dict = ingest_metadata.model_dump(mode="json")
    source = SourceRegisterEntry(**metadata_dict, retrieved_on=date.today())
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary:
            temporary.write(contents)
            temporary_path = temporary.name
        chunks = engine.ingestion_service.ingest(temporary_path, source)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)
    return IngestResponse(
        doc_id=ingest_metadata.doc_id,
        chunks_indexed=chunks,
        status="success",
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    sqlite_ok = True
    try:
        engine.conn.execute("SELECT 1").fetchone()
    except Exception:
        sqlite_ok = False
    llm_ok = await engine.llm_health()
    vector_ok = engine.vector_health()
    return HealthResponse(
        status="ok" if sqlite_ok and vector_ok and llm_ok else "degraded",
        api=True,
        vector_store=vector_ok,
        sqlite=sqlite_ok,
        llm=llm_ok,
    )


@app.get("/audit/{trace_id}", response_model=AuditRecord)
async def get_audit_record(trace_id: str):
    record = engine.audit_repository.get(trace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Audit record not found")
    return record


@app.get("/sources", response_model=list[SourceRegisterEntry])
async def get_sources():
    return sources.list_all()


@app.post("/test-student-loader", response_model=StudentLoaderResponse)
async def load_test_students():
    data_dir = os.getenv("STUDENT_DATA_DIR", "./data/synthetic")
    if not os.path.isdir(data_dir):
        raise HTTPException(status_code=404, detail=f"Data directory not found: {data_dir}")
    report = load_dir(engine.conn, data_dir)
    rules_path = os.getenv("RULE_REGISTRY_PATH", "./data/rule_registry.csv")
    rules_loaded = (
        RuleRepository(engine.conn).load_csv(rules_path)
        if os.path.exists(rules_path)
        else 0
    )
    loaded = report["loaded"]
    return StudentLoaderResponse(
        students_loaded=loaded.get("students", 0),
        courses_loaded=loaded.get("courses", 0),
        attendance_records_loaded=loaded.get("attendance", 0),
        results_records_loaded=loaded.get("results", 0),
        rules_loaded=rules_loaded,
        status="success",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
