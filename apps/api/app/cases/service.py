"""Service layer for persistent cases, document links, and run records."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import ChangeSummary, FieldChangeRecord
from casegraph_agent_sdk.cases import (
    CaseDetailResponse,
    CaseDocumentListResponse,
    CaseDocumentReference,
    CaseListResponse,
    CaseRecord,
    CaseWorkflowBindingMetadata,
    CreateCaseRequest,
    LinkCaseDocumentRequest,
    NormalizedOperationError,
    RunInputReference,
    TimestampMetadata,
    UpdateCaseRequest,
    WorkflowRunListResponse,
    WorkflowRunOutputPlaceholderMetadata,
    WorkflowRunRecord,
    WorkflowRunRequest,
)
from casegraph_agent_sdk.domains import CaseDomainContext
from casegraph_agent_sdk.ingestion import (
    DocumentProcessingStatus,
    IngestionMode,
    IngestionModePreference,
    SourceFileMetadata,
)
from casegraph_workflows.schemas import WorkflowDefinition, WorkflowStepDefinition

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel, WorkflowRunRecordModel
from app.audit.service import AuditTrailService, audit_actor, entity_ref
from app.config import settings
from app.ingestion.models import DocumentRecord
from app.knowledge.dependencies import get_search_service
from app.rag.evidence import EvidenceSelector
from app.rag.registry import rag_task_registry
from app.rag.service import RagExecutionService
from app.runtime.service import RuntimeProxyService
from app.tasks.models import TaskExecutionRecordModel
from app.tasks.registry import task_registry
from app.tasks.service import TaskExecutionService
from app.target_packs.context import get_case_target_pack_selection
from app.persistence.database import isoformat_utc


GENERIC_TASK_WORKFLOW_ID = "provider-task-execution"
RAG_TASK_WORKFLOW_ID = "rag-task-execution"


class CaseServiceError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class CaseService:
    def __init__(
        self,
        session: Session,
        *,
        runtime_service: RuntimeProxyService | None = None,
        task_service: TaskExecutionService | None = None,
        rag_service: RagExecutionService | None = None,
    ) -> None:
        self._session = session
        self._runtime_service = runtime_service or RuntimeProxyService()
        self._task_service = task_service or TaskExecutionService(
            timeout_seconds=settings.provider_request_timeout_seconds,
        )
        if rag_service is None:
            search_service = get_search_service()
            if search_service is not None:
                rag_service = RagExecutionService(
                    evidence_selector=EvidenceSelector(search_service),
                    timeout_seconds=settings.provider_request_timeout_seconds,
                )
        self._rag_service = rag_service

    async def list_cases(self, *, status: str | None = None, limit: int = 100) -> CaseListResponse:
        statement = select(CaseRecordModel).order_by(desc(CaseRecordModel.updated_at)).limit(limit)
        if status is not None:
            statement = statement.where(CaseRecordModel.status == status)
        cases = self._session.exec(statement).all()
        return CaseListResponse(cases=[self._to_case_record(item) for item in cases])

    async def create_case(self, request: CreateCaseRequest) -> CaseRecord:
        title = request.title.strip()
        if not title:
            raise CaseServiceError("Case title is required.", status_code=400)

        now = datetime.now(UTC)
        workflow_binding = await self._build_workflow_binding(request.workflow_id, now)

        # --- Resolve domain context if provided ---
        domain_context = self._resolve_domain_context(request)

        record = CaseRecordModel(
            case_id=str(uuid4()),
            title=title,
            category=request.category.strip() if request.category else None,
            status="open",
            summary=request.summary.strip() if request.summary else None,
            case_metadata_json=request.metadata,
            selected_workflow_id=workflow_binding.workflow_id if workflow_binding else None,
            workflow_bound_at=now if workflow_binding else None,
            domain_pack_id=domain_context.domain_pack_id if domain_context else None,
            jurisdiction=domain_context.jurisdiction if domain_context else None,
            case_type_id=domain_context.case_type_id if domain_context else None,
            domain_category=domain_context.domain_category if domain_context else None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)

        AuditTrailService(self._session).append_event(
            case_id=record.case_id,
            category="case",
            event_type="case_created",
            actor=audit_actor("service", actor_id="cases.service", display_name="Case Service"),
            entity=entity_ref(
                "case",
                record.case_id,
                case_id=record.case_id,
                display_label=record.title,
            ),
            change_summary=ChangeSummary(
                message="Case created.",
                field_changes=[
                    FieldChangeRecord(field_path="title", new_value=record.title),
                    FieldChangeRecord(field_path="status", new_value=record.status),
                    FieldChangeRecord(field_path="selected_workflow_id", new_value=record.selected_workflow_id),
                    FieldChangeRecord(field_path="domain_pack_id", new_value=record.domain_pack_id),
                    FieldChangeRecord(field_path="case_type_id", new_value=record.case_type_id),
                ],
            ),
        )
        self._session.commit()
        self._session.refresh(record)
        return self._to_case_record(record)

    async def get_case_detail(self, case_id: str) -> CaseDetailResponse:
        case = self._require_case(case_id)
        documents = self._list_case_document_rows(case_id)
        runs = self._list_run_rows(case_id)
        return CaseDetailResponse(
            case=self._to_case_record(case),
            documents=[self._to_case_document_reference(link, doc) for link, doc in documents],
            runs=[self._to_run_record(run) for run in runs],
        )

    async def update_case(self, case_id: str, request: UpdateCaseRequest) -> CaseRecord:
        case = self._require_case(case_id)
        changes = request.model_dump(exclude_unset=True)
        now = datetime.now(UTC)
        original = {
            "title": case.title,
            "category": case.category,
            "status": case.status,
            "summary": case.summary,
            "metadata": dict(case.case_metadata_json),
            "selected_workflow_id": case.selected_workflow_id,
        }

        if "title" in changes and changes["title"] is not None:
            trimmed_title = changes["title"].strip()
            if not trimmed_title:
                raise CaseServiceError("Case title is required.", status_code=400)
            case.title = trimmed_title
        if "category" in changes:
            category = changes["category"]
            case.category = category.strip() if isinstance(category, str) and category else None
        if "status" in changes and changes["status"] is not None:
            case.status = changes["status"]
        if "summary" in changes:
            summary = changes["summary"]
            case.summary = summary.strip() if isinstance(summary, str) and summary else None
        if "metadata" in changes and changes["metadata"] is not None:
            case.case_metadata_json = changes["metadata"]
        if "workflow_id" in changes:
            workflow_binding = await self._build_workflow_binding(changes["workflow_id"], now)
            case.selected_workflow_id = workflow_binding.workflow_id if workflow_binding else None
            case.workflow_bound_at = now if workflow_binding else None

        case.updated_at = now
        self._session.add(case)

        field_changes: list[FieldChangeRecord] = []
        if original["title"] != case.title:
            field_changes.append(FieldChangeRecord(field_path="title", old_value=original["title"], new_value=case.title))
        if original["category"] != case.category:
            field_changes.append(FieldChangeRecord(field_path="category", old_value=original["category"], new_value=case.category))
        if original["status"] != case.status:
            field_changes.append(FieldChangeRecord(field_path="status", old_value=original["status"], new_value=case.status))
        if original["summary"] != case.summary:
            field_changes.append(FieldChangeRecord(field_path="summary", old_value=original["summary"], new_value=case.summary))
        if original["metadata"] != case.case_metadata_json:
            field_changes.append(FieldChangeRecord(field_path="metadata", old_value=original["metadata"], new_value=case.case_metadata_json))
        if original["selected_workflow_id"] != case.selected_workflow_id:
            field_changes.append(
                FieldChangeRecord(
                    field_path="selected_workflow_id",
                    old_value=original["selected_workflow_id"],
                    new_value=case.selected_workflow_id,
                )
            )

        if field_changes:
            AuditTrailService(self._session).append_event(
                case_id=case.case_id,
                category="case",
                event_type="case_updated",
                actor=audit_actor("service", actor_id="cases.service", display_name="Case Service"),
                entity=entity_ref("case", case.case_id, case_id=case.case_id, display_label=case.title),
                change_summary=ChangeSummary(
                    message="Case metadata updated.",
                    field_changes=field_changes,
                ),
            )

        self._session.commit()
        self._session.refresh(case)
        return self._to_case_record(case)

    def list_case_documents(self, case_id: str) -> CaseDocumentListResponse:
        self._require_case(case_id)
        rows = self._list_case_document_rows(case_id)
        return CaseDocumentListResponse(
            documents=[self._to_case_document_reference(link, doc) for link, doc in rows]
        )

    def link_document(self, case_id: str, request: LinkCaseDocumentRequest) -> CaseDocumentReference:
        self._require_case(case_id)
        document = self._session.get(DocumentRecord, request.document_id)
        if document is None:
            raise CaseServiceError("Document not found.", status_code=404)
        if document.processing_status != DocumentProcessingStatus.COMPLETED.value:
            raise CaseServiceError(
                "Only successfully ingested documents can be linked to a case.",
                status_code=400,
            )

        existing = self._session.exec(
            select(CaseDocumentLinkModel).where(
                CaseDocumentLinkModel.case_id == case_id,
                CaseDocumentLinkModel.document_id == request.document_id,
            )
        ).first()
        if existing is not None:
            return self._to_case_document_reference(existing, document)

        link = CaseDocumentLinkModel(
            link_id=str(uuid4()),
            case_id=case_id,
            document_id=request.document_id,
        )
        self._session.add(link)

        AuditTrailService(self._session).append_event(
            case_id=case_id,
            category="case",
            event_type="case_document_linked",
            actor=audit_actor("service", actor_id="cases.service", display_name="Case Service"),
            entity=entity_ref(
                "case_document_link",
                link.link_id,
                case_id=case_id,
                display_label=document.filename,
            ),
            change_summary=ChangeSummary(message="Document linked to case."),
            related_entities=[
                entity_ref("document", document.document_id, case_id=case_id, display_label=document.filename),
            ],
            metadata={"document_id": document.document_id},
        )
        self._session.commit()
        self._session.refresh(link)
        return self._to_case_document_reference(link, document)

    async def create_run(self, case_id: str, request: WorkflowRunRequest) -> WorkflowRunRecord:
        self._require_case(case_id)
        await self._require_workflow(request.workflow_id)
        self._validate_task_execution_request(request)

        linked_documents = self._list_case_document_rows(case_id)
        linked_document_ids = {doc.document_id for _, doc in linked_documents}
        linked_case_document_ids = {link.link_id for link, _ in linked_documents}

        invalid_document_ids = sorted(set(request.linked_document_ids) - linked_document_ids)
        if invalid_document_ids:
            raise CaseServiceError(
                "Run-linked documents must already be linked to the case.",
                status_code=400,
            )

        self._validate_input_references(
            case_id=case_id,
            input_references=request.input_references,
            linked_document_ids=linked_document_ids,
            linked_case_document_ids=linked_case_document_ids,
        )

        now = datetime.now(UTC)
        is_task_workflow = request.workflow_id == GENERIC_TASK_WORKFLOW_ID
        is_rag_workflow = request.workflow_id == RAG_TASK_WORKFLOW_ID
        run = WorkflowRunRecordModel(
            run_id=str(uuid4()),
            case_id=case_id,
            workflow_id=request.workflow_id,
            status="running" if (is_task_workflow or is_rag_workflow) else "created",
            input_references_json=[ref.model_dump() for ref in request.input_references],
            linked_document_ids_json=sorted(set(request.linked_document_ids)),
            output_json=WorkflowRunOutputPlaceholderMetadata(
                output_available=False,
                summary=None,
                artifact_refs=[],
            ).model_dump(),
            error_json=None,
            notes=request.notes.strip() if request.notes else None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)

        if is_task_workflow:
            await self._execute_task_backed_run(run, request)
            self._session.refresh(run)

        if is_rag_workflow:
            await self._execute_rag_backed_run(run, request, case_id)
            self._session.refresh(run)

        return self._to_run_record(run)

    def list_case_runs(self, case_id: str) -> WorkflowRunListResponse:
        self._require_case(case_id)
        rows = self._list_run_rows(case_id)
        return WorkflowRunListResponse(runs=[self._to_run_record(item) for item in rows])

    def get_run(self, run_id: str) -> WorkflowRunRecord:
        run = self._session.get(WorkflowRunRecordModel, run_id)
        if run is None:
            raise CaseServiceError("Run not found.", status_code=404)
        return self._to_run_record(run)

    def _require_case(self, case_id: str) -> CaseRecordModel:
        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise CaseServiceError("Case not found.", status_code=404)
        return case

    async def _build_workflow_binding(
        self,
        workflow_id: str | None,
        bound_at: datetime,
    ) -> CaseWorkflowBindingMetadata | None:
        if workflow_id is None:
            return None
        workflow = await self._require_workflow(workflow_id)
        return CaseWorkflowBindingMetadata(
            workflow_id=workflow.id,
            bound_at=isoformat_utc(bound_at),
        )

    async def _require_workflow(self, workflow_id: str) -> WorkflowDefinition:
        builtin_workflow = self._get_builtin_workflow(workflow_id)
        if builtin_workflow is not None:
            return builtin_workflow

        try:
            response = await self._runtime_service.list_workflows()
        except Exception as exc:
            raise CaseServiceError(
                f"Workflow metadata is unavailable: {exc}",
                status_code=502,
            ) from exc

        for workflow in response.workflows:
            if workflow.id == workflow_id:
                return workflow

        raise CaseServiceError(f"Workflow '{workflow_id}' is not available.", status_code=400)

    def _get_builtin_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        if workflow_id == GENERIC_TASK_WORKFLOW_ID:
            return WorkflowDefinition(
                id=GENERIC_TASK_WORKFLOW_ID,
                display_name="Provider Task Execution",
                description=(
                    "Single-step generic workflow that executes one registered provider-backed task "
                    "through the API task execution service."
                ),
                steps=[
                    WorkflowStepDefinition(
                        id="step-1",
                        display_name="Execute Task",
                        agent_id="provider_task_execution",
                        description="Invoke a registered task through the shared provider task service.",
                    )
                ],
            )

        if workflow_id == RAG_TASK_WORKFLOW_ID:
            return WorkflowDefinition(
                id=RAG_TASK_WORKFLOW_ID,
                display_name="RAG Task Execution",
                description=(
                    "Evidence-backed workflow that retrieves relevant knowledge chunks, "
                    "passes them as context to a provider-backed task, and returns "
                    "citations referencing the evidence sources."
                ),
                steps=[
                    WorkflowStepDefinition(
                        id="step-1",
                        display_name="Retrieve Evidence",
                        agent_id="evidence_retrieval",
                        description="Search indexed knowledge for relevant evidence chunks.",
                    ),
                    WorkflowStepDefinition(
                        id="step-2",
                        display_name="Execute with Evidence",
                        agent_id="rag_task_execution",
                        description="Execute the task with retrieved evidence as context.",
                    ),
                ],
            )

        return None

    def _validate_task_execution_request(self, request: WorkflowRunRequest) -> None:
        if request.workflow_id == GENERIC_TASK_WORKFLOW_ID:
            if request.task_execution is None:
                raise CaseServiceError(
                    "The provider-task-execution workflow requires a task_execution payload.",
                    status_code=400,
                )

            if task_registry.get(request.task_execution.task_id) is None:
                raise CaseServiceError(
                    f"Task '{request.task_execution.task_id}' is not registered.",
                    status_code=400,
                )

            provider = request.task_execution.provider_selection.provider
            if provider not in {"openai", "anthropic", "gemini"}:
                raise CaseServiceError(
                    f"Unknown provider: {provider}",
                    status_code=400,
                )
            return

        if request.workflow_id == RAG_TASK_WORKFLOW_ID:
            if request.rag_task_execution is None:
                raise CaseServiceError(
                    "The rag-task-execution workflow requires a rag_task_execution payload.",
                    status_code=400,
                )

            if rag_task_registry.get(request.rag_task_execution.task_id) is None:
                raise CaseServiceError(
                    f"RAG task '{request.rag_task_execution.task_id}' is not registered.",
                    status_code=400,
                )

            provider = request.rag_task_execution.provider_selection.provider
            if provider not in {"openai", "anthropic", "gemini"}:
                raise CaseServiceError(
                    f"Unknown provider: {provider}",
                    status_code=400,
                )
            return

        if request.task_execution is not None:
            raise CaseServiceError(
                "task_execution is only supported for the provider-task-execution workflow.",
                status_code=400,
            )
        if request.rag_task_execution is not None:
            raise CaseServiceError(
                "rag_task_execution is only supported for the rag-task-execution workflow.",
                status_code=400,
            )

    async def _execute_task_backed_run(
        self,
        run: WorkflowRunRecordModel,
        request: WorkflowRunRequest,
    ) -> None:
        if request.task_execution is None:
            raise CaseServiceError(
                "The provider-task-execution workflow requires a task_execution payload.",
                status_code=400,
            )

        result, events = await self._task_service.execute(request.task_execution)
        execution_id = str(uuid4())

        self._session.add(
            TaskExecutionRecordModel(
                execution_id=execution_id,
                task_id=result.task_id,
                provider=result.provider,
                model_id=result.model_id,
                finish_reason=result.finish_reason.value,
                output_text=result.output_text,
                structured_output_json=(
                    result.structured_output.model_dump() if result.structured_output else None
                ),
                usage_json=result.usage.model_dump() if result.usage else None,
                error_json=result.error.model_dump() if result.error else None,
                events_json=[event.model_dump() for event in events],
                duration_ms=result.duration_ms,
                provider_request_id=result.provider_request_id,
                run_id=run.run_id,
            )
        )

        output = WorkflowRunOutputPlaceholderMetadata(
            output_available=result.error is None,
            summary=self._summarize_task_result(result),
            artifact_refs=[],
            task_execution_id=execution_id,
            task_execution=result,
            events=events,
        )

        run.status = "failed" if result.error is not None else "completed"
        run.output_json = output.model_dump()
        run.error_json = (
            NormalizedOperationError(
                error_code=result.error.error_code,
                message=result.error.message,
                recoverable=result.error.recoverable,
            ).model_dump()
            if result.error is not None
            else None
        )
        run.updated_at = datetime.now(UTC)

        self._session.add(run)
        self._session.commit()

    async def _execute_rag_backed_run(
        self,
        run: WorkflowRunRecordModel,
        request: WorkflowRunRequest,
        case_id: str,
    ) -> None:
        if request.rag_task_execution is None:
            raise CaseServiceError(
                "The rag-task-execution workflow requires a rag_task_execution payload.",
                status_code=400,
            )

        if self._rag_service is None:
            raise CaseServiceError(
                "RAG execution service is not available. Ensure knowledge search is configured.",
                status_code=503,
            )

        # Resolve case-linked document IDs for scoping
        case_doc_ids: list[str] | None = None
        if request.rag_task_execution.retrieval_scope.kind == "case":
            links = self._session.exec(
                select(CaseDocumentLinkModel.document_id).where(
                    CaseDocumentLinkModel.case_id == case_id,
                )
            ).all()
            case_doc_ids = list(links) if links else None

            requested_document_ids = request.rag_task_execution.retrieval_scope.document_ids
            if requested_document_ids:
                linked_ids = set(case_doc_ids or [])
                invalid_ids = [doc_id for doc_id in requested_document_ids if doc_id not in linked_ids]
                if invalid_ids:
                    raise CaseServiceError(
                        "Case-scoped retrieval can only narrow to documents already linked to the case.",
                        status_code=400,
                    )

        result, events = await self._rag_service.execute(
            request.rag_task_execution,
            case_document_ids=case_doc_ids,
        )
        execution_id = str(uuid4())

        self._session.add(
            TaskExecutionRecordModel(
                execution_id=execution_id,
                task_id=result.task_id,
                provider=result.provider,
                model_id=result.model_id,
                finish_reason=result.finish_reason.value,
                output_text=result.output_text,
                structured_output_json=(
                    result.structured_output.model_dump() if result.structured_output else None
                ),
                usage_json=result.usage.model_dump() if result.usage else None,
                error_json=result.error.model_dump() if result.error else None,
                events_json=[event.model_dump() for event in events],
                duration_ms=result.duration_ms,
                provider_request_id=result.provider_request_id,
                run_id=run.run_id,
            )
        )

        output = WorkflowRunOutputPlaceholderMetadata(
            output_available=result.error is None,
            summary=self._summarize_task_result(result),
            artifact_refs=[],
            task_execution_id=execution_id,
            rag_task_execution=result,
            events=events,
        )

        run.status = "failed" if result.error is not None else "completed"
        run.output_json = output.model_dump()
        run.error_json = (
            NormalizedOperationError(
                error_code=result.error.error_code,
                message=result.error.message,
                recoverable=result.error.recoverable,
            ).model_dump()
            if result.error is not None
            else None
        )
        run.updated_at = datetime.now(UTC)

        self._session.add(run)
        self._session.commit()

    def _summarize_task_result(self, result) -> str | None:
        if result.structured_output is not None and result.structured_output.raw_text:
            raw_text = result.structured_output.raw_text
        elif result.output_text:
            raw_text = result.output_text
        elif result.error is not None:
            raw_text = result.error.message
        else:
            return None

        compact = " ".join(raw_text.split())
        if len(compact) <= 280:
            return compact
        return f"{compact[:277]}..."

    def _list_case_document_rows(self, case_id: str) -> list[tuple[CaseDocumentLinkModel, DocumentRecord]]:
        statement = (
            select(CaseDocumentLinkModel, DocumentRecord)
            .join(DocumentRecord, CaseDocumentLinkModel.document_id == DocumentRecord.document_id)
            .where(CaseDocumentLinkModel.case_id == case_id)
            .order_by(desc(CaseDocumentLinkModel.linked_at))
        )
        return list(self._session.exec(statement).all())

    def _list_run_rows(self, case_id: str) -> list[WorkflowRunRecordModel]:
        statement = (
            select(WorkflowRunRecordModel)
            .where(WorkflowRunRecordModel.case_id == case_id)
            .order_by(desc(WorkflowRunRecordModel.created_at))
        )
        return list(self._session.exec(statement).all())

    def _validate_input_references(
        self,
        *,
        case_id: str,
        input_references: list[RunInputReference],
        linked_document_ids: set[str],
        linked_case_document_ids: set[str],
    ) -> None:
        for ref in input_references:
            if ref.reference_type == "case" and ref.reference_id != case_id:
                raise CaseServiceError(
                    "Case input references must point to the current case.",
                    status_code=400,
                )
            if ref.reference_type == "document" and ref.reference_id not in linked_document_ids:
                raise CaseServiceError(
                    "Document input references must point to documents already linked to the case.",
                    status_code=400,
                )
            if ref.reference_type == "case_document" and ref.reference_id not in linked_case_document_ids:
                raise CaseServiceError(
                    "Case-document input references must point to a linked case document.",
                    status_code=400,
                )

    def _to_case_record(self, record: CaseRecordModel) -> CaseRecord:
        workflow_binding = None
        if record.selected_workflow_id and record.workflow_bound_at is not None:
            workflow_binding = CaseWorkflowBindingMetadata(
                workflow_id=record.selected_workflow_id,
                bound_at=isoformat_utc(record.workflow_bound_at),
            )
        domain_context = None
        if record.domain_pack_id and record.case_type_id:
            jurisdiction = record.jurisdiction
            domain_category = record.domain_category

            if jurisdiction is None or domain_category is None:
                from app.domains.packs import domain_pack_registry

                result = domain_pack_registry.get_case_type(record.case_type_id)
                if result is not None:
                    _case_type, pack_meta = result
                    if pack_meta.pack_id == record.domain_pack_id:
                        jurisdiction = jurisdiction or pack_meta.jurisdiction
                        domain_category = domain_category or pack_meta.domain_category

            if jurisdiction is not None and domain_category is not None:
                domain_context = CaseDomainContext(
                    domain_pack_id=record.domain_pack_id,
                    jurisdiction=jurisdiction,
                    case_type_id=record.case_type_id,
                    domain_category=domain_category,
                )
        return CaseRecord(
            case_id=record.case_id,
            title=record.title,
            category=record.category,
            status=record.status,
            summary=record.summary,
            metadata=record.case_metadata_json,
            domain_context=domain_context,
            workflow_binding=workflow_binding,
            target_pack_selection=get_case_target_pack_selection(record.case_metadata_json),
            timestamps=TimestampMetadata(
                created_at=isoformat_utc(record.created_at),
                updated_at=isoformat_utc(record.updated_at),
            ),
        )

    def _resolve_domain_context(
        self, request: CreateCaseRequest,
    ) -> CaseDomainContext | None:
        """Resolve domain context from a create-case request."""
        if not request.domain_pack_id or not request.case_type_id:
            return None

        from app.domains.packs import domain_pack_registry

        result = domain_pack_registry.get_case_type(request.case_type_id)
        if result is None:
            raise CaseServiceError(
                f"Case type '{request.case_type_id}' not found in any registered domain pack.",
                status_code=400,
            )

        case_type, pack_meta = result
        if pack_meta.pack_id != request.domain_pack_id:
            raise CaseServiceError(
                f"Case type '{request.case_type_id}' does not belong to pack '{request.domain_pack_id}'.",
                status_code=400,
            )

        return CaseDomainContext(
            domain_pack_id=pack_meta.pack_id,
            jurisdiction=pack_meta.jurisdiction,
            case_type_id=case_type.case_type_id,
            domain_category=pack_meta.domain_category,
        )

    def _to_case_document_reference(
        self,
        link: CaseDocumentLinkModel,
        document: DocumentRecord,
    ) -> CaseDocumentReference:
        return CaseDocumentReference(
            link_id=link.link_id,
            case_id=link.case_id,
            document_id=document.document_id,
            source_file=SourceFileMetadata(
                filename=document.filename,
                content_type=document.content_type,
                extension=document.extension,
                size_bytes=document.size_bytes,
                sha256=document.sha256,
                classification=document.classification,
            ),
            requested_mode=IngestionModePreference(document.requested_mode),
            resolved_mode=IngestionMode(document.resolved_mode),
            document_status=DocumentProcessingStatus(document.processing_status),
            linked_at=isoformat_utc(link.linked_at),
        )

    def _to_run_record(self, run: WorkflowRunRecordModel) -> WorkflowRunRecord:
        output = (
            WorkflowRunOutputPlaceholderMetadata.model_validate(run.output_json)
            if run.output_json is not None
            else None
        )
        return WorkflowRunRecord(
            run_id=run.run_id,
            case_id=run.case_id,
            workflow_id=run.workflow_id,
            status=run.status,
            input_references=[RunInputReference.model_validate(item) for item in run.input_references_json],
            linked_document_ids=run.linked_document_ids_json,
            output=output,
            events=list(output.events) if output is not None else [],
            error=(
                NormalizedOperationError.model_validate(run.error_json)
                if run.error_json is not None
                else None
            ),
            notes=run.notes,
            timestamps=TimestampMetadata(
                created_at=isoformat_utc(run.created_at),
                updated_at=isoformat_utc(run.updated_at),
            ),
        )