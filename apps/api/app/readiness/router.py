"""Route handlers for case readiness and requirement checklists."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from casegraph_agent_sdk.readiness import (
    ChecklistItem,
    ChecklistResponse,
    GenerateChecklistRequest,
    ReadinessResponse,
    UpdateChecklistItemRequest,
)

from app.persistence.database import get_session
from app.readiness.service import ReadinessService, ReadinessServiceError

router = APIRouter(tags=["readiness"])


def _get_service(session: Session = Depends(get_session)) -> ReadinessService:
    return ReadinessService(session)


def _handle(exc: ReadinessServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get(
    "/cases/{case_id}/checklist",
    response_model=ChecklistResponse,
)
async def get_checklist(
    case_id: str,
    service: ReadinessService = Depends(_get_service),
) -> ChecklistResponse:
    result = service.get_checklist(case_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No checklist exists for this case. Generate one first.",
        )
    return result


@router.post(
    "/cases/{case_id}/checklist/generate",
    response_model=ChecklistResponse,
)
async def generate_checklist(
    case_id: str,
    body: GenerateChecklistRequest | None = None,
    service: ReadinessService = Depends(_get_service),
) -> ChecklistResponse:
    try:
        force = body.force if body else False
        return service.generate_checklist(case_id, force=force)
    except ReadinessServiceError as exc:
        raise _handle(exc)


@router.post(
    "/cases/{case_id}/checklist/evaluate",
    response_model=ReadinessResponse,
)
async def evaluate_checklist(
    case_id: str,
    service: ReadinessService = Depends(_get_service),
) -> ReadinessResponse:
    try:
        return service.evaluate(case_id)
    except ReadinessServiceError as exc:
        raise _handle(exc)


@router.get(
    "/cases/{case_id}/readiness",
    response_model=ReadinessResponse,
)
async def get_readiness(
    case_id: str,
    service: ReadinessService = Depends(_get_service),
) -> ReadinessResponse:
    result = service.get_readiness(case_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No checklist or readiness data exists for this case.",
        )
    return result


@router.patch(
    "/cases/{case_id}/checklist/items/{item_id}",
    response_model=ChecklistItem,
)
async def update_checklist_item(
    case_id: str,
    item_id: str,
    body: UpdateChecklistItemRequest,
    service: ReadinessService = Depends(_get_service),
) -> ChecklistItem:
    try:
        return service.update_item(case_id, item_id, body)
    except ReadinessServiceError as exc:
        raise _handle(exc)
