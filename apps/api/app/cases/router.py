"""Route handlers for persistent cases and workflow run records."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from casegraph_agent_sdk.cases import (
    CaseDetailResponse,
    CaseDocumentListResponse,
    CaseDocumentReference,
    CaseListResponse,
    CaseRecord,
    CreateCaseRequest,
    LinkCaseDocumentRequest,
    UpdateCaseRequest,
    WorkflowRunListResponse,
    WorkflowRunRecord,
    WorkflowRunRequest,
)

from app.cases.schemas import CaseListFilters
from app.cases.service import CaseService, CaseServiceError
from app.persistence.database import get_session

router = APIRouter(tags=["cases"])


def get_case_service(session: Session = Depends(get_session)) -> CaseService:
    return CaseService(session)


def _translate_error(exc: CaseServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/cases", response_model=CaseListResponse)
async def list_cases(
    filters: CaseListFilters = Depends(),
    service: CaseService = Depends(get_case_service),
) -> CaseListResponse:
    try:
        return await service.list_cases(status=filters.status, limit=filters.limit)
    except CaseServiceError as exc:
        raise _translate_error(exc) from exc


@router.post("/cases", response_model=CaseRecord)
async def create_case(
    request: CreateCaseRequest,
    service: CaseService = Depends(get_case_service),
) -> CaseRecord:
    try:
        return await service.create_case(request)
    except CaseServiceError as exc:
        raise _translate_error(exc) from exc


@router.get("/cases/{case_id}", response_model=CaseDetailResponse)
async def get_case_detail(
    case_id: str,
    service: CaseService = Depends(get_case_service),
) -> CaseDetailResponse:
    try:
        return await service.get_case_detail(case_id)
    except CaseServiceError as exc:
        raise _translate_error(exc) from exc


@router.patch("/cases/{case_id}", response_model=CaseRecord)
async def update_case(
    case_id: str,
    request: UpdateCaseRequest,
    service: CaseService = Depends(get_case_service),
) -> CaseRecord:
    try:
        return await service.update_case(case_id, request)
    except CaseServiceError as exc:
        raise _translate_error(exc) from exc


@router.post("/cases/{case_id}/documents", response_model=CaseDocumentReference)
async def link_case_document(
    case_id: str,
    request: LinkCaseDocumentRequest,
    service: CaseService = Depends(get_case_service),
) -> CaseDocumentReference:
    try:
        return service.link_document(case_id, request)
    except CaseServiceError as exc:
        raise _translate_error(exc) from exc


@router.get("/cases/{case_id}/documents", response_model=CaseDocumentListResponse)
async def list_case_documents(
    case_id: str,
    service: CaseService = Depends(get_case_service),
) -> CaseDocumentListResponse:
    try:
        return service.list_case_documents(case_id)
    except CaseServiceError as exc:
        raise _translate_error(exc) from exc


@router.post("/cases/{case_id}/runs", response_model=WorkflowRunRecord)
async def create_case_run(
    case_id: str,
    request: WorkflowRunRequest,
    service: CaseService = Depends(get_case_service),
) -> WorkflowRunRecord:
    try:
        return await service.create_run(case_id, request)
    except CaseServiceError as exc:
        raise _translate_error(exc) from exc


@router.get("/cases/{case_id}/runs", response_model=WorkflowRunListResponse)
async def list_case_runs(
    case_id: str,
    service: CaseService = Depends(get_case_service),
) -> WorkflowRunListResponse:
    try:
        return service.list_case_runs(case_id)
    except CaseServiceError as exc:
        raise _translate_error(exc) from exc


@router.get("/runs/{run_id}", response_model=WorkflowRunRecord)
async def get_run(
    run_id: str,
    service: CaseService = Depends(get_case_service),
) -> WorkflowRunRecord:
    try:
        return service.get_run(run_id)
    except CaseServiceError as exc:
        raise _translate_error(exc) from exc