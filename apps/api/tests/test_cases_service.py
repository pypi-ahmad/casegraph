import asyncio
import json
import sqlite3

import pytest
from sqlmodel import Session, select

from casegraph_agent_sdk.cases import CreateCaseRequest, LinkCaseDocumentRequest, WorkflowRunRequest
from casegraph_agent_sdk.ingestion import (
    DocumentProcessingStatus,
    FileTypeClassification,
    IngestionMode,
    IngestionModePreference,
    IngestionResultSummary,
    SourceFileMetadata,
)
from casegraph_agent_sdk.tasks import (
    FinishReason,
    ProviderSelection,
    TaskExecutionEvent,
    TaskExecutionRequest,
    TaskExecutionResult,
    TaskInput,
    UsageMetadata,
)
from casegraph_workflows.schemas import WorkflowDefinition, WorkflowStepDefinition, WorkflowsResponse

from app.cases.service import GENERIC_TASK_WORKFLOW_ID, CaseService, CaseServiceError
from app.ingestion.registry import DocumentRegistryService
from app.persistence.database import configure_engine, get_engine, init_database
from app.tasks.models import TaskExecutionRecordModel


class FakeRuntimeProxyService:
    async def list_workflows(self) -> WorkflowsResponse:
        return WorkflowsResponse(
            workflows=[
                WorkflowDefinition(
                    id="intake-review",
                    display_name="Intake Review",
                    description="Two-step placeholder workflow.",
                    steps=[
                        WorkflowStepDefinition(
                            id="step-1",
                            display_name="Intake",
                            agent_id="intake",
                        )
                    ],
                )
            ]
        )


class FakeTaskExecutionService:
    def __init__(self) -> None:
        self.requests: list[TaskExecutionRequest] = []

    async def execute(
        self,
        request: TaskExecutionRequest,
    ) -> tuple[TaskExecutionResult, list[TaskExecutionEvent]]:
        self.requests.append(request)
        return (
            TaskExecutionResult(
                task_id=request.task_id,
                provider=request.provider_selection.provider,
                model_id=request.provider_selection.model_id,
                finish_reason=FinishReason.COMPLETED,
                output_text='{"summary":"Short summary."}',
                usage=UsageMetadata(input_tokens=12, output_tokens=8, total_tokens=20),
                duration_ms=123,
                provider_request_id="req-123",
            ),
            [
                TaskExecutionEvent(
                    kind="task_selected",
                    timestamp="2026-04-04T00:00:00Z",
                    metadata={"task_id": request.task_id},
                ),
                TaskExecutionEvent(
                    kind="model_completed",
                    timestamp="2026-04-04T00:00:01Z",
                    metadata={"provider": request.provider_selection.provider},
                ),
            ],
        )


def _summary(document_id: str) -> IngestionResultSummary:
    return IngestionResultSummary(
        document_id=document_id,
        source_file=SourceFileMetadata(
            filename="sample.pdf",
            content_type="application/pdf",
            extension=".pdf",
            size_bytes=1024,
            sha256="abc123",
            classification=FileTypeClassification.PDF,
        ),
        status=DocumentProcessingStatus.COMPLETED,
        requested_mode=IngestionModePreference.AUTO,
        resolved_mode=IngestionMode.READABLE_PDF,
        extractor_name="test-extractor",
        page_count=2,
        text_block_count=4,
        geometry_present=True,
        geometry_sources=[],
    )


def test_case_lifecycle_persists_document_links_and_run_records(tmp_path) -> None:
    configure_engine(f"sqlite:///{(tmp_path / 'cases.db').as_posix()}")
    init_database()

    with Session(get_engine()) as session:
        registry = DocumentRegistryService(session)
        registry.record_summary(_summary("doc-001"))
        persisted_documents = registry.list_documents()
        assert persisted_documents[0].page_count == 2
        assert persisted_documents[0].text_block_count == 4
        assert persisted_documents[0].geometry_present is True

        service = CaseService(session, runtime_service=FakeRuntimeProxyService())
        created_case = asyncio.run(
            service.create_case(
                CreateCaseRequest(
                    title="Example case",
                    category="general",
                    summary="Persistent case foundation test.",
                    metadata={"priority": "normal"},
                    workflow_id="intake-review",
                )
            )
        )

        linked = service.link_document(
            created_case.case_id,
            LinkCaseDocumentRequest(document_id="doc-001"),
        )
        assert linked.document_id == "doc-001"

        run = asyncio.run(
            service.create_run(
                created_case.case_id,
                WorkflowRunRequest(
                    workflow_id="intake-review",
                    linked_document_ids=["doc-001"],
                    notes="Tracking record only.",
                ),
            )
        )

        detail = asyncio.run(service.get_case_detail(created_case.case_id))

        assert detail.case.case_id == created_case.case_id
        assert detail.case.workflow_binding is not None
        assert detail.documents[0].document_id == "doc-001"
        assert detail.runs[0].run_id == run.run_id
        assert detail.runs[0].status == "created"
        assert detail.runs[0].linked_document_ids == ["doc-001"]


def test_run_creation_rejects_unlinked_documents(tmp_path) -> None:
    configure_engine(f"sqlite:///{(tmp_path / 'cases-invalid.db').as_posix()}")
    init_database()

    with Session(get_engine()) as session:
        registry = DocumentRegistryService(session)
        registry.record_summary(_summary("doc-002"))

        service = CaseService(session, runtime_service=FakeRuntimeProxyService())
        created_case = asyncio.run(
            service.create_case(
                CreateCaseRequest(
                    title="Validation case",
                    category=None,
                    summary=None,
                    metadata={},
                    workflow_id="intake-review",
                )
            )
        )

        with pytest.raises(CaseServiceError):
            asyncio.run(
                service.create_run(
                    created_case.case_id,
                    WorkflowRunRequest(
                        workflow_id="intake-review",
                        linked_document_ids=["doc-002"],
                        notes=None,
                    ),
                )
            )


def test_task_workflow_run_executes_and_persists_normalized_result(tmp_path) -> None:
    configure_engine(f"sqlite:///{(tmp_path / 'cases-task-run.db').as_posix()}")
    init_database()

    with Session(get_engine()) as session:
        service = CaseService(
            session,
            runtime_service=FakeRuntimeProxyService(),
            task_service=FakeTaskExecutionService(),
        )

        created_case = asyncio.run(
            service.create_case(
                CreateCaseRequest(
                    title="Task execution case",
                    category="general",
                    summary="Exercises the provider-backed task workflow path.",
                    metadata={},
                    workflow_id=None,
                )
            )
        )

        run = asyncio.run(
            service.create_run(
                created_case.case_id,
                WorkflowRunRequest(
                    workflow_id=GENERIC_TASK_WORKFLOW_ID,
                    input_references=[],
                    linked_document_ids=[],
                    notes="Execute a generic task through the run foundation.",
                    task_execution=TaskExecutionRequest(
                        task_id="summarize_text",
                        input=TaskInput(text="Example text to summarize.", parameters={}),
                        provider_selection=ProviderSelection(
                            provider="openai",
                            model_id="gpt-4.1-mini",
                            api_key="sk-test-secret",
                        ),
                        structured_output=None,
                        max_tokens=128,
                        temperature=0.2,
                    ),
                ),
            )
        )

        persisted_records = session.exec(select(TaskExecutionRecordModel)).all()
        assert len(persisted_records) == 1

        serialized_payload = json.dumps(
            {
                "run_output": run.output.model_dump() if run.output else None,
                "task_record": {
                    "run_id": persisted_records[0].run_id,
                    "output_text": persisted_records[0].output_text,
                    "structured_output_json": persisted_records[0].structured_output_json,
                    "usage_json": persisted_records[0].usage_json,
                    "error_json": persisted_records[0].error_json,
                    "events_json": persisted_records[0].events_json,
                },
            }
        )

        assert run.status == "completed"
        assert run.output is not None
        assert run.output.output_available is True
        assert run.output.task_execution_id == persisted_records[0].execution_id
        assert run.output.task_execution is not None
        assert run.output.task_execution.task_id == "summarize_text"
        assert len(run.events) == 2
        assert persisted_records[0].run_id == run.run_id
        assert "sk-test-secret" not in serialized_payload


def test_init_database_upgrades_legacy_document_table(tmp_path) -> None:
    db_path = tmp_path / "legacy-documents.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE documents (
                document_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                content_type TEXT,
                extension TEXT,
                size_bytes INTEGER,
                sha256 TEXT,
                classification TEXT NOT NULL,
                requested_mode TEXT NOT NULL,
                resolved_mode TEXT NOT NULL,
                processing_status TEXT NOT NULL,
                extractor_name TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()

    configure_engine(f"sqlite:///{db_path.as_posix()}")
    init_database()

    with Session(get_engine()) as session:
        registry = DocumentRegistryService(session)
        registry.record_summary(_summary("doc-legacy"))
        persisted = registry.get_document("doc-legacy")

    assert persisted is not None
    assert persisted.page_count == 2
    assert persisted.text_block_count == 4
    assert persisted.geometry_present is True