"""Route handlers for case audit timeline, decisions, and lineage."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from casegraph_agent_sdk.audit import (
    ArtifactLineageResponse,
    AuditTimelineResponse,
    DecisionLedgerResponse,
    LineageResponse,
)

from app.audit.service import AuditServiceError, AuditTrailService
from app.persistence.database import get_session

router = APIRouter(tags=["audit"])


def get_audit_service(session: Session = Depends(get_session)) -> AuditTrailService:
    return AuditTrailService(session)


def _handle(exc: AuditServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/cases/{case_id}/audit", response_model=AuditTimelineResponse)
async def get_case_audit(
    case_id: str,
    category: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    service: AuditTrailService = Depends(get_audit_service),
) -> AuditTimelineResponse:
    try:
        return service.get_case_timeline(case_id, category=category, event_type=event_type)
    except AuditServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/decisions", response_model=DecisionLedgerResponse)
async def get_case_decisions(
    case_id: str,
    service: AuditTrailService = Depends(get_audit_service),
) -> DecisionLedgerResponse:
    try:
        return service.get_case_decisions(case_id)
    except AuditServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/lineage", response_model=LineageResponse)
async def get_case_lineage(
    case_id: str,
    service: AuditTrailService = Depends(get_audit_service),
) -> LineageResponse:
    try:
        return service.get_case_lineage(case_id)
    except AuditServiceError as exc:
        raise _handle(exc) from exc


@router.get(
    "/artifacts/{artifact_type}/{artifact_id}/lineage",
    response_model=ArtifactLineageResponse,
)
async def get_artifact_lineage(
    artifact_type: str,
    artifact_id: str,
    service: AuditTrailService = Depends(get_audit_service),
) -> ArtifactLineageResponse:
    return service.get_artifact_lineage(artifact_type, artifact_id)