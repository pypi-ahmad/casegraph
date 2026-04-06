"""Route handlers for case work-management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from casegraph_agent_sdk.domains import CaseTypeTemplateId, DomainPackId
from casegraph_agent_sdk.work_management import (
    AssignmentHistoryResponse,
    AssignmentStatus,
    CaseAssignmentResponse,
    CaseSLAResponse,
    CaseWorkStatusResponse,
    EscalationReadinessState,
    SLAState,
    UpdateCaseAssignmentRequest,
    UpdateCaseSLARequest,
    WorkQueueFilters,
    WorkQueueResponse,
    WorkSummaryResponse,
)

from app.persistence.database import get_session
from app.work_management.service import WorkManagementService, WorkManagementServiceError

router = APIRouter(tags=["work-management"])


def _handle(exc: WorkManagementServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _get_service(session: Session = Depends(get_session)) -> WorkManagementService:
    return WorkManagementService(session)


def _filters(
    assignee_id: str | None = Query(default=None),
    assignment_status: AssignmentStatus | None = Query(default=None),
    sla_state: SLAState | None = Query(default=None),
    escalation_state: EscalationReadinessState | None = Query(default=None),
    domain_pack_id: DomainPackId | None = Query(default=None),
    case_type_id: CaseTypeTemplateId | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> WorkQueueFilters:
    return WorkQueueFilters(
        assignee_id=assignee_id,
        assignment_status=assignment_status,
        sla_state=sla_state,
        escalation_state=escalation_state,
        domain_pack_id=domain_pack_id,
        case_type_id=case_type_id,
        limit=limit,
    )


@router.get("/work/queue", response_model=WorkQueueResponse)
async def get_work_queue(
    filters: WorkQueueFilters = Depends(_filters),
    service: WorkManagementService = Depends(_get_service),
) -> WorkQueueResponse:
    try:
        return service.list_queue(filters)
    except WorkManagementServiceError as exc:
        raise _handle(exc) from exc


@router.get("/work/summary", response_model=WorkSummaryResponse)
async def get_work_summary(
    filters: WorkQueueFilters = Depends(_filters),
    service: WorkManagementService = Depends(_get_service),
) -> WorkSummaryResponse:
    try:
        return service.get_summary(filters)
    except WorkManagementServiceError as exc:
        raise _handle(exc) from exc


@router.patch("/cases/{case_id}/assignment", response_model=CaseAssignmentResponse)
async def patch_case_assignment(
    case_id: str,
    body: UpdateCaseAssignmentRequest,
    service: WorkManagementService = Depends(_get_service),
) -> CaseAssignmentResponse:
    try:
        return service.update_assignment(case_id, body)
    except WorkManagementServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/assignment-history", response_model=AssignmentHistoryResponse)
async def get_assignment_history(
    case_id: str,
    service: WorkManagementService = Depends(_get_service),
) -> AssignmentHistoryResponse:
    try:
        return service.list_assignment_history(case_id)
    except WorkManagementServiceError as exc:
        raise _handle(exc) from exc


@router.patch("/cases/{case_id}/sla", response_model=CaseSLAResponse)
async def patch_case_sla(
    case_id: str,
    body: UpdateCaseSLARequest,
    service: WorkManagementService = Depends(_get_service),
) -> CaseSLAResponse:
    try:
        return service.update_sla(case_id, body)
    except WorkManagementServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/work-status", response_model=CaseWorkStatusResponse)
async def get_case_work_status(
    case_id: str,
    service: WorkManagementService = Depends(_get_service),
) -> CaseWorkStatusResponse:
    try:
        return service.get_work_status(case_id)
    except WorkManagementServiceError as exc:
        raise _handle(exc) from exc