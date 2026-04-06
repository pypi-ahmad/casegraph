"""Tests for the RAG execution foundation.

Verifies evidence selection, citation extraction, RAG service integration,
and the case-linked RAG workflow path.
"""

import asyncio

import pytest
from pydantic import ValidationError
from sqlmodel import Session

from casegraph_agent_sdk.cases import CreateCaseRequest, WorkflowRunRequest
from casegraph_agent_sdk.rag import (
    EvidenceChunkReference,
    ProviderSelection,
    RagTaskExecutionRequest,
    RagTaskExecutionResult,
    RetrievalScope,
)
from casegraph_agent_sdk.retrieval import (
    SearchResult,
    SearchResultItem,
    SearchScoreMetadata,
    ChunkMetadata,
    SourceReference,
)
from casegraph_agent_sdk.tasks import (
    FinishReason,
    TaskExecutionEvent,
    TaskExecutionResult,
    UsageMetadata,
)

from app.cases.service import CaseService, RAG_TASK_WORKFLOW_ID
from app.persistence.database import configure_engine, get_engine, init_database
from app.rag.evidence import EvidenceSelector, format_evidence_context
from app.rag.registry import rag_task_registry
from app.rag.service import RagExecutionService


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeSearchService:
    """Fake search service that returns canned results."""

    def __init__(self, items: list[SearchResultItem] | None = None) -> None:
        self._items = items or []
        self.last_request = None

    def search(self, request):
        self.last_request = request
        return SearchResult(
            query=request.query,
            items=self._items,
            total_results=len(self._items),
            embedding_model="test-model",
            vector_store="test-store",
        )


class FakeRuntimeProxyService:
    async def list_workflows(self):
        from casegraph_workflows.schemas import WorkflowsResponse
        return WorkflowsResponse(workflows=[])


class FakeRagExecutionService:
    def __init__(self) -> None:
        self.requests: list[RagTaskExecutionRequest] = []

    async def execute(
        self,
        request: RagTaskExecutionRequest,
        *,
        case_document_ids: list[str] | None = None,
    ) -> tuple[RagTaskExecutionResult, list[TaskExecutionEvent]]:
        self.requests.append(request)
        return (
            RagTaskExecutionResult(
                task_id=request.task_id,
                provider=request.provider_selection.provider,
                model_id=request.provider_selection.model_id,
                finish_reason=FinishReason.COMPLETED,
                output_text="Based on [1], the answer is clear.",
                citations=[],
                evidence=[],
                usage=UsageMetadata(input_tokens=50, output_tokens=20, total_tokens=70),
                duration_ms=200,
                provider_request_id="req-rag-001",
            ),
            [
                TaskExecutionEvent(
                    kind="retrieval_started",
                    timestamp="2026-04-04T00:00:00Z",
                    metadata={"query": request.query},
                ),
                TaskExecutionEvent(
                    kind="model_completed",
                    timestamp="2026-04-04T00:00:01Z",
                    metadata={"provider": request.provider_selection.provider},
                ),
            ],
        )


# ---------------------------------------------------------------------------
# Evidence tests
# ---------------------------------------------------------------------------


def _make_search_items(count: int) -> list[SearchResultItem]:
    items = []
    for i in range(count):
        items.append(SearchResultItem(
            chunk_id=f"chunk-{i}",
            text=f"Evidence text chunk {i}.",
            score=SearchScoreMetadata(raw_score=0.9 - i * 0.1, normalized_score=0.9 - i * 0.1),
            metadata=ChunkMetadata(
                document_id=f"doc-{i % 2}",
                page_number=i + 1,
                source_filename=f"file-{i % 2}.pdf",
            ),
            source_reference=SourceReference(
                document_id=f"doc-{i % 2}",
                page_number=i + 1,
            ),
        ))
    return items


def test_evidence_selector_returns_chunks_and_summary() -> None:
    items = _make_search_items(3)
    search = FakeSearchService(items=items)
    selector = EvidenceSelector(search)

    result = selector.select("test query", top_k=5)

    assert len(result.chunks) == 3
    assert result.summary.total_retrieved == 3
    assert result.summary.total_selected == 3
    assert result.summary.embedding_model == "test-model"
    assert result.chunks[0].chunk_id == "chunk-0"


def test_evidence_selector_applies_document_filter() -> None:
    search = FakeSearchService(items=[])
    selector = EvidenceSelector(search)

    scope = RetrievalScope(kind="document", document_ids=["doc-abc"])
    selector.select("query", top_k=3, scope=scope)

    assert search.last_request is not None
    assert any(f.field == "document_id" and f.value == "doc-abc" for f in search.last_request.filters)


def test_evidence_selector_case_scope_without_linked_documents_returns_empty() -> None:
    search = FakeSearchService(items=_make_search_items(2))
    selector = EvidenceSelector(search)

    result = selector.select(
        "query",
        top_k=3,
        scope=RetrievalScope(kind="case", case_id="case-123"),
    )

    assert result.chunks == []
    assert result.summary.total_retrieved == 0
    assert search.last_request is None


def test_evidence_selector_case_scope_can_narrow_to_requested_linked_document() -> None:
    search = FakeSearchService(items=[])
    selector = EvidenceSelector(search)

    selector.select(
        "query",
        top_k=3,
        scope=RetrievalScope(kind="case", case_id="case-123", document_ids=["doc-b"]),
        document_ids=["doc-a", "doc-b"],
    )

    assert search.last_request is not None
    assert any(f.field == "document_id" and f.value == "doc-b" for f in search.last_request.filters)


def test_retrieval_scope_requires_scope_specific_identifiers() -> None:
    with pytest.raises(ValidationError):
        RetrievalScope(kind="case")

    with pytest.raises(ValidationError):
        RetrievalScope(kind="document")


def test_format_evidence_context_numbers_chunks() -> None:
    items = _make_search_items(2)
    search = FakeSearchService(items=items)
    selector = EvidenceSelector(search)
    result = selector.select("test", top_k=5)

    context = format_evidence_context(result.chunks)
    assert "[1]" in context
    assert "[2]" in context
    assert "Evidence text chunk 0" in context


def test_format_evidence_context_empty_returns_empty() -> None:
    context = format_evidence_context([])
    assert context == ""


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


def test_rag_task_registry_has_builtin_tasks() -> None:
    metadata_list = rag_task_registry.list_metadata()
    task_ids = {m.task_id for m in metadata_list}
    assert "answer_with_evidence" in task_ids
    assert "summarize_with_evidence" in task_ids
    assert "extract_with_evidence" in task_ids


def test_rag_task_definition_builds_prompt() -> None:
    task_def = rag_task_registry.get("answer_with_evidence")
    assert task_def is not None
    prompt = task_def.build_user_prompt("What is X?", "[1] X is Y.")
    assert "What is X?" in prompt
    assert "[1] X is Y." in prompt


# ---------------------------------------------------------------------------
# Citation extraction tests
# ---------------------------------------------------------------------------


def test_citation_extraction_from_output() -> None:
    from app.rag.service import RagExecutionService

    chunks = [
        EvidenceChunkReference(
            chunk_id="c1", text="Text 1",
            score=SearchScoreMetadata(raw_score=0.9),
            source_reference=SourceReference(document_id="d1", page_number=1),
            source_filename="file.pdf", page_number=1,
        ),
        EvidenceChunkReference(
            chunk_id="c2", text="Text 2",
            score=SearchScoreMetadata(raw_score=0.8),
            source_reference=SourceReference(document_id="d2", page_number=2),
            source_filename="other.pdf", page_number=2,
        ),
    ]

    citations = RagExecutionService._extract_citations(
        "According to [1] and [2], the answer is clear.", chunks,
    )

    assert len(citations) == 2
    assert citations[0].citation_index == 1
    assert citations[0].chunk_id == "c1"
    assert citations[0].document_id == "d1"
    assert citations[1].citation_index == 2
    assert citations[1].chunk_id == "c2"


def test_citation_extraction_ignores_invalid_indices() -> None:
    from app.rag.service import RagExecutionService

    chunks = [
        EvidenceChunkReference(
            chunk_id="c1", text="Only one chunk",
            score=SearchScoreMetadata(raw_score=0.9),
            source_reference=SourceReference(document_id="d1"),
            source_filename=None, page_number=None,
        ),
    ]

    citations = RagExecutionService._extract_citations(
        "See [1] and [99] for details.", chunks,
    )

    assert len(citations) == 1
    assert citations[0].citation_index == 1


# ---------------------------------------------------------------------------
# RAG workflow path test (case service integration)
# ---------------------------------------------------------------------------


def test_rag_workflow_run_executes_through_case_service(tmp_path) -> None:
    configure_engine(f"sqlite:///{(tmp_path / 'cases-rag.db').as_posix()}")
    init_database()

    with Session(get_engine()) as session:
        service = CaseService(
            session,
            runtime_service=FakeRuntimeProxyService(),
            rag_service=FakeRagExecutionService(),
        )

        case = asyncio.run(
            service.create_case(
                CreateCaseRequest(
                    title="RAG test case",
                    category="general",
                    summary="Test RAG workflow integration.",
                    metadata={},
                    workflow_id=None,
                )
            )
        )

        run = asyncio.run(
            service.create_run(
                case.case_id,
                WorkflowRunRequest(
                    workflow_id=RAG_TASK_WORKFLOW_ID,
                    input_references=[],
                    linked_document_ids=[],
                    notes="RAG workflow test.",
                    rag_task_execution=RagTaskExecutionRequest(
                        task_id="answer_with_evidence",
                        query="What is the meaning of life?",
                        parameters={},
                        provider_selection=ProviderSelection(
                            provider="openai",
                            model_id="gpt-4.1-mini",
                            api_key="sk-test-rag-secret",
                        ),
                        retrieval_scope=RetrievalScope(kind="global"),
                        top_k=5,
                    ),
                ),
            )
        )

        assert run.status == "completed"
        assert run.output is not None
        assert run.output.output_available is True
        assert run.output.rag_task_execution is not None
        assert run.output.rag_task_execution.task_id == "answer_with_evidence"
        assert len(run.events) == 2

        # Verify API key not leaked in serialization
        import json
        serialized = json.dumps(run.output.model_dump())
        assert "sk-test-rag-secret" not in serialized


def test_case_service_wires_default_rag_service_when_search_is_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    async def fake_execute_prepared_prompt(self, **kwargs):  # noqa: ARG001
        return (
            TaskExecutionResult(
                task_id="answer_with_evidence",
                provider="openai",
                model_id="gpt-4.1-mini",
                finish_reason=FinishReason.COMPLETED,
                output_text="Answer grounded in [1].",
                usage=UsageMetadata(input_tokens=10, output_tokens=5, total_tokens=15),
                duration_ms=123,
                provider_request_id="req-live-rag-001",
            ),
            [
                TaskExecutionEvent(
                    kind="provider_resolved",
                    timestamp="2026-04-04T00:00:00Z",
                    metadata={"provider": "openai", "model_id": "gpt-4.1-mini"},
                ),
                TaskExecutionEvent(
                    kind="model_completed",
                    timestamp="2026-04-04T00:00:01Z",
                    metadata={"finish_reason": "completed"},
                ),
            ],
        )

    monkeypatch.setattr("app.cases.service.get_search_service", lambda: FakeSearchService(items=_make_search_items(1)))
    monkeypatch.setattr("app.tasks.service.TaskExecutionService.execute_prepared_prompt", fake_execute_prepared_prompt)

    configure_engine(f"sqlite:///{(tmp_path / 'cases-rag-default.db').as_posix()}")
    init_database()

    with Session(get_engine()) as session:
        service = CaseService(
            session,
            runtime_service=FakeRuntimeProxyService(),
        )

        case = asyncio.run(
            service.create_case(
                CreateCaseRequest(
                    title="RAG default wiring",
                    category="general",
                    summary="Exercise default RAG service wiring.",
                    metadata={},
                    workflow_id=None,
                )
            )
        )

        run = asyncio.run(
            service.create_run(
                case.case_id,
                WorkflowRunRequest(
                    workflow_id=RAG_TASK_WORKFLOW_ID,
                    rag_task_execution=RagTaskExecutionRequest(
                        task_id="answer_with_evidence",
                        query="What does the evidence say?",
                        parameters={},
                        provider_selection=ProviderSelection(
                            provider="openai",
                            model_id="gpt-4.1-mini",
                            api_key="sk-test-rag-default",
                        ),
                        retrieval_scope=RetrievalScope(kind="global"),
                        top_k=5,
                    ),
                ),
            )
        )

        assert run.status == "completed"
        assert run.output is not None
        assert run.output.rag_task_execution is not None
        assert run.output.rag_task_execution.output_text == "Answer grounded in [1]."
        assert len(run.output.rag_task_execution.evidence) == 1
        assert [event.kind for event in run.events] == [
            "retrieval_started",
            "retrieval_completed",
            "evidence_selected",
            "context_assembled",
            "provider_resolved",
            "model_completed",
            "citations_attached",
        ]
