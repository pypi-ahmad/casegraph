"""Route handlers for case-scoped communication drafts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from casegraph_agent_sdk.communications import (
    CommunicationDraftDetailResponse,
    CommunicationDraftGenerateRequest,
    CommunicationDraftGenerateResponse,
    CommunicationDraftListResponse,
    CommunicationDraftReviewUpdateRequest,
    CommunicationDraftReviewUpdateResponse,
    CommunicationDraftSourceResponse,
    CommunicationTemplateListResponse,
)

from app.communications.errors import CommunicationDraftServiceError
from app.communications.service import CommunicationDraftService
from app.persistence.database import get_session

router = APIRouter(tags=["communication-drafts"])


def _handle(exc: CommunicationDraftServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _get_service(session: Session = Depends(get_session)) -> CommunicationDraftService:
    return CommunicationDraftService(session)


@router.get("/communication/templates", response_model=CommunicationTemplateListResponse)
async def list_communication_templates() -> CommunicationTemplateListResponse:
    return CommunicationDraftService.list_templates()


@router.post("/cases/{case_id}/communication-drafts", response_model=CommunicationDraftGenerateResponse)
async def create_communication_draft(
    case_id: str,
    body: CommunicationDraftGenerateRequest,
    service: CommunicationDraftService = Depends(_get_service),
) -> CommunicationDraftGenerateResponse:
    try:
        return await service.generate_draft(case_id, body)
    except CommunicationDraftServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/communication-drafts", response_model=CommunicationDraftListResponse)
async def list_communication_drafts(
    case_id: str,
    service: CommunicationDraftService = Depends(_get_service),
) -> CommunicationDraftListResponse:
    try:
        return service.list_drafts(case_id)
    except CommunicationDraftServiceError as exc:
        raise _handle(exc) from exc


@router.get("/communication-drafts/{draft_id}", response_model=CommunicationDraftDetailResponse)
async def get_communication_draft(
    draft_id: str,
    service: CommunicationDraftService = Depends(_get_service),
) -> CommunicationDraftDetailResponse:
    try:
        return service.get_draft(draft_id)
    except CommunicationDraftServiceError as exc:
        raise _handle(exc) from exc


@router.get("/communication-drafts/{draft_id}/sources", response_model=CommunicationDraftSourceResponse)
async def get_communication_draft_sources(
    draft_id: str,
    service: CommunicationDraftService = Depends(_get_service),
) -> CommunicationDraftSourceResponse:
    try:
        return service.get_sources(draft_id)
    except CommunicationDraftServiceError as exc:
        raise _handle(exc) from exc


@router.patch(
    "/communication-drafts/{draft_id}/review",
    response_model=CommunicationDraftReviewUpdateResponse,
)
async def patch_communication_draft_review(
    draft_id: str,
    body: CommunicationDraftReviewUpdateRequest,
    service: CommunicationDraftService = Depends(_get_service),
) -> CommunicationDraftReviewUpdateResponse:
    try:
        return service.update_review(draft_id, body)
    except CommunicationDraftServiceError as exc:
        raise _handle(exc) from exc