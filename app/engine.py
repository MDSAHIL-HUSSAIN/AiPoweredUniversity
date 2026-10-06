"""FastAPI-facing adapter around the Member 3 LangGraph workflow."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from time import perf_counter

from app.RAG import RAGEngine
from app.auth import HeaderAuthorizer
from app.contracts import (
    AskResponse,
    AuditRecord,
    RetrievedChunk,
    RetrievedSourceAudit,
    RetrievalFilters,
)
from app.ingestion import (
    ChromaStore,
    Chunker,
    DeterministicEmbeddingService,
    EmbeddingService,
    InMemoryChromaStore,
    IngestionService,
    SQLiteStore,
    UniversityRetriever,
)
from app.repositories.audit_repository import AuditRepository
from app.repositories.db import get_conn
from app.tools import UniversityTools, call_tool
from app.workflow import build_workflow, new_workflow_state
from app.workflow.config import WorkflowSettings
from app.workflow.llm import MockWorkflowLLM, OllamaWorkflowLLM
from app.workflow.tool_executor import CallToolExecutor


class RAGRetrieverAdapter:
    """Adapt Member 4's temporary RAG store to the shared retriever contract."""

    def __init__(self, engine: RAGEngine) -> None:
        self.engine = engine

    def retrieve(
        self,
        query: str,
        filters: RetrievalFilters,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        del filters  # applicability is enforced by the precedence node
        chunks = []
        for item in self.engine.query(query, top_k=top_k):
            metadata = item["metadata"]
            chunks.append(
                RetrievedChunk(
                    chunk_id=metadata["chunk_id"],
                    text=item["content"],
                    doc_id=metadata["doc_id"],
                    title=metadata.get("title", metadata["doc_id"]),
                    issuer=metadata.get("issuer", "University Office"),
                    authority_level=int(metadata.get("authority_level", 3)),
                    doc_type=metadata.get("doc_type", "document"),
                    section=metadata.get("section"),
                    page=int(metadata.get("page", 1)),
                    version=metadata.get("version", "1.0"),
                    effective_from=date.fromisoformat(metadata["effective_from"]),
                    effective_to=_optional_date(metadata.get("effective_to")),
                    supersedes=_list_value(metadata.get("supersedes")),
                    scope_programmes=_list_value(
                        metadata.get("scope_programmes"), default=["ALL"]
                    ),
                    scope_batches=_list_value(
                        metadata.get("scope_batches"), default=["ALL"]
                    ),
                    provenance=metadata.get("provenance"),
                    synthetic=bool(metadata.get("synthetic", False)),
                    score=max(0.0, min(1.0, float(item.get("score", 0)))),
                )
            )
        return chunks


class PrimaryWithFallbackRetriever:
    """Use Member 2's index, retaining demo evidence only while it is empty."""

    def __init__(self, primary, vector_store, fallback) -> None:
        self.primary = primary
        self.vector_store = vector_store
        self.fallback = fallback

    def retrieve(self, query, filters, top_k=5):
        if self.vector_store.count() == 0:
            return self.fallback.retrieve(query, filters, top_k)
        return self.primary.retrieve(query, filters, top_k)


class AssistantEngine:
    """Own runtime dependencies and expose one async question-processing method."""

    def __init__(self, settings: WorkflowSettings | None = None) -> None:
        self.settings = settings or WorkflowSettings()
        self.conn = get_conn(self.settings.sqlite_path)
        lightweight_retrieval = _env_bool("CHROMA_DISABLED", default=False)
        self.vector_store = (
            InMemoryChromaStore()
            if lightweight_retrieval
            else ChromaStore(self.settings.chroma_path)
        )
        self.embedding_service = (
            DeterministicEmbeddingService()
            if lightweight_retrieval
            else EmbeddingService(self.settings.embedding_model)
        )
        self.source_store = SQLiteStore(self.settings.sqlite_path)
        self.ingestion_service = IngestionService(
            chunker=Chunker(),
            embedding_service=self.embedding_service,
            chroma_store=self.vector_store,
            sqlite_store=self.source_store,
        )
        self.primary_retriever = UniversityRetriever(
            chroma_store=self.vector_store,
            sqlite_store=self.source_store,
            embedding_service=self.embedding_service,
        )
        # Temporary evidence is used only until Member 2's index has documents.
        self.rag_engine = RAGEngine(
            persist_dir=self.settings.chroma_path,
            use_chroma=False,
        )
        fallback_retriever = RAGRetrieverAdapter(self.rag_engine)
        self.retriever = PrimaryWithFallbackRetriever(
            self.primary_retriever,
            self.vector_store,
            fallback_retriever,
        )
        llm = (
            MockWorkflowLLM()
            if self.settings.mock_llm
            else OllamaWorkflowLLM(self.settings)
        )
        self.llm = llm
        self.audit_repository = AuditRepository(self.conn)
        self.graph = build_workflow(
            llm=llm,
            authorizer=HeaderAuthorizer(),
            retriever=self.retriever,
            tool_executor=CallToolExecutor(UniversityTools(self.conn), call_tool),
            top_k=self.settings.top_k,
        )

    async def process_question(
        self,
        *,
        question: str,
        header_student_id: str | None,
        as_of_date: date,
    ) -> AskResponse:
        started = perf_counter()
        result = await self.graph.ainvoke(
            new_workflow_state(question, header_student_id, as_of_date)
        )
        total_latency_ms = max(0, round((perf_counter() - started) * 1000))

        response = AskResponse(
            trace_id=result["trace_id"],
            answer=result["answer"],
            answer_type=result["answer_type"],
            citations=result.get("citations", []),
            tools_invoked=result.get("tools_invoked", []),
            applied_rules=result.get("applied_rules", []),
            conflicts_detected=result.get("conflicts_detected", []),
            explanation=result.get("explanation", ""),
            as_of_date=as_of_date,
        )
        route = result.get("route")
        record = AuditRecord(
            trace_id=result["trace_id"],
            timestamp=datetime.now(timezone.utc),
            student_id=header_student_id,
            question=question,
            question_category=route.category.value if route else "unknown",
            sources_retrieved=[
                RetrievedSourceAudit(
                    doc_id=chunk.doc_id,
                    section=chunk.section,
                    page=chunk.page,
                    version=chunk.version,
                    effective_from=chunk.effective_from.isoformat(),
                    score=chunk.score,
                )
                for chunk in result.get("retrieved_chunks", [])
            ],
            precedence_decision=result.get("precedence_decision"),
            conflicts_detected=result.get("conflicts_detected", []),
            tools_invoked=result.get("tools_invoked", []),
            applied_rules=result.get("applied_rules", []),
            answer_type=result["answer_type"],
            answer=result["answer"],
            explanation=result.get("explanation", ""),
            model=result.get("model_name"),
            llm_calls=result.get("llm_calls", 0),
            tokens=result.get("token_count", 0),
            latency_ms=total_latency_ms,
            fallback_used=result.get("fallback_used", False),
            errors=result.get("errors", []),
            metadata=result.get("audit_metadata", {}),
        )
        self.audit_repository.save(record)
        return response

    async def llm_health(self) -> bool:
        if isinstance(self.llm, MockWorkflowLLM):
            return True
        ok, _ = await self.llm.health_check()
        return ok

    def vector_health(self) -> bool:
        try:
            self.vector_store.count()
            return True
        except Exception:
            return False


def _optional_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _list_value(value, default=None) -> list[str]:
    if value is None or value == "":
        return list(default or [])
    if isinstance(value, list):
        return [str(item) for item in value]
    return [item.strip() for item in str(value).split(";") if item.strip()]


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
