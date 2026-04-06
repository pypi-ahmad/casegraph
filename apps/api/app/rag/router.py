"""Route handlers for evidence-backed RAG task execution."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from casegraph_agent_sdk.rag import (
    ProviderSelection,
    RagTaskExecutionRequest,
    RagTaskRegistryResponse,
    RetrievalScope,
    StructuredOutputSchema,
)

from app.cases.models import CaseDocumentLinkModel
from app.config import settings
from app.knowledge.dependencies import get_search_service
from app.knowledge.search import SearchService
from app.persistence.database import get_session
from app.rag.evidence import EvidenceSelector
from app.rag.registry import rag_task_registry
from app.rag.schemas import RagExecuteRequestBody, RagExecuteResponseBody
from app.rag.service import RagExecutionService, RagExecutionServiceError
from app.tasks.models import TaskExecutionRecordModel

router = APIRouter(tags=["rag"])


def _get_search_service_or_fail() -> SearchService:
    service = get_search_service()
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Knowledge search is not available. Ensure sentence-transformers and a vector store are installed.",
        )
    return service


def _get_rag_execution_service(
    search: SearchService = Depends(_get_search_service_or_fail),
) -> RagExecutionService:
    return RagExecutionService(
        evidence_selector=EvidenceSelector(search),
        timeout_seconds=settings.provider_request_timeout_seconds,
    )


def _resolve_case_document_ids(
    scope: RetrievalScope,
    session: Session,
) -> list[str] | None:
    """Resolve document IDs linked to a case for case-scoped retrieval."""
    if scope.kind != "case" or scope.case_id is None:
        return None

    links = session.exec(
        select(CaseDocumentLinkModel.document_id).where(
            CaseDocumentLinkModel.case_id == scope.case_id,
        )
    ).all()

    if not links:
        return None

    return list(links)


def _validate_case_scope_document_ids(
    scope: RetrievalScope,
    case_document_ids: list[str] | None,
) -> None:
    if scope.kind != "case" or not scope.document_ids:
        return

    linked_ids = set(case_document_ids or [])
    invalid_ids = [doc_id for doc_id in scope.document_ids if doc_id not in linked_ids]
    if invalid_ids:
        raise HTTPException(
            status_code=400,
            detail="Case-scoped retrieval can only narrow to documents already linked to the case.",
        )


@router.get("/rag/tasks", response_model=RagTaskRegistryResponse)
async def list_rag_tasks() -> RagTaskRegistryResponse:
    """Return metadata for all registered evidence-backed tasks."""
    return RagTaskRegistryResponse(tasks=rag_task_registry.list_metadata())


@router.post("/rag/execute", response_model=RagExecuteResponseBody)
async def execute_rag_task(
    body: RagExecuteRequestBody,
    service: RagExecutionService = Depends(_get_rag_execution_service),
    session: Session = Depends(get_session),
) -> RagExecuteResponseBody:
    """Execute an evidence-backed task: retrieve → generate → cite."""
    task_def = rag_task_registry.get(body.task_id)
    if task_def is None:
        raise HTTPException(status_code=404, detail=f"RAG task '{body.task_id}' is not registered.")

    # Resolve structured output
    structured_output: StructuredOutputSchema | None = None
    if body.use_structured_output and task_def.meta.supports_structured_output:
        structured_output = StructuredOutputSchema(
            json_schema=task_def.meta.output_schema,
            strict=False,
        )

    # Resolve case-scoped document IDs
    case_document_ids = _resolve_case_document_ids(body.retrieval_scope, session)
    _validate_case_scope_document_ids(body.retrieval_scope, case_document_ids)

    request = RagTaskExecutionRequest(
        task_id=body.task_id,
        query=body.query,
        parameters=body.parameters,
        provider_selection=ProviderSelection(
            provider=body.provider,
            model_id=body.model_id,
            api_key=body.api_key.get_secret_value(),
        ),
        retrieval_scope=body.retrieval_scope,
        top_k=body.top_k,
        structured_output=structured_output,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
    )

    try:
        result, events = await service.execute(
            request,
            case_document_ids=case_document_ids,
        )
    except RagExecutionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    session.add(
        TaskExecutionRecordModel(
            execution_id=str(uuid4()),
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
        )
    )
    session.commit()

    return RagExecuteResponseBody(result=result, events=events)
