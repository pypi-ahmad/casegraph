"""Route handlers for submission targets, drafts, dry-run plans, and approval metadata."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from casegraph_agent_sdk.submissions import (
    AutomationPlanGenerateResponse,
    AutomationPlanResponse,
    CreateSubmissionDraftRequest,
    GenerateAutomationPlanRequest,
    SubmissionApprovalUpdateResponse,
    SubmissionDraftCreateResponse,
    SubmissionDraftDetailResponse,
    SubmissionDraftListResponse,
    SubmissionTargetListResponse,
    UpdateSubmissionApprovalRequest,
)

from app.automation.service import AutomationService
from app.config import settings
from app.persistence.database import get_session
from app.submissions.errors import SubmissionDraftServiceError
from app.submissions.service import SubmissionDraftService

router = APIRouter(tags=["submission-drafts"])

_automation_service = AutomationService(
    runtime_base_url=settings.agent_runtime_url,
    timeout_seconds=settings.agent_runtime_timeout_seconds,
)


def _handle(exc: SubmissionDraftServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _get_service(session: Session = Depends(get_session)) -> SubmissionDraftService:
    return SubmissionDraftService(
        session,
        automation_capabilities_loader=_automation_service.get_capabilities,
    )


@router.get("/submission/targets", response_model=SubmissionTargetListResponse)
async def list_submission_targets(
    service: SubmissionDraftService = Depends(_get_service),
) -> SubmissionTargetListResponse:
    return service.list_targets()


@router.post("/cases/{case_id}/submission-drafts", response_model=SubmissionDraftCreateResponse)
async def create_submission_draft(
    case_id: str,
    body: CreateSubmissionDraftRequest,
    service: SubmissionDraftService = Depends(_get_service),
) -> SubmissionDraftCreateResponse:
    try:
        return service.create_draft(case_id, body)
    except SubmissionDraftServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/submission-drafts", response_model=SubmissionDraftListResponse)
async def list_submission_drafts(
    case_id: str,
    service: SubmissionDraftService = Depends(_get_service),
) -> SubmissionDraftListResponse:
    try:
        return service.list_drafts(case_id)
    except SubmissionDraftServiceError as exc:
        raise _handle(exc) from exc


@router.get("/submission-drafts/{draft_id}", response_model=SubmissionDraftDetailResponse)
async def get_submission_draft(
    draft_id: str,
    service: SubmissionDraftService = Depends(_get_service),
) -> SubmissionDraftDetailResponse:
    try:
        return service.get_draft(draft_id)
    except SubmissionDraftServiceError as exc:
        raise _handle(exc) from exc


@router.post("/submission-drafts/{draft_id}/plan", response_model=AutomationPlanGenerateResponse)
async def generate_submission_plan(
    draft_id: str,
    body: GenerateAutomationPlanRequest | None = None,
    service: SubmissionDraftService = Depends(_get_service),
) -> AutomationPlanGenerateResponse:
    try:
        return await service.generate_plan(draft_id, body or GenerateAutomationPlanRequest())
    except SubmissionDraftServiceError as exc:
        raise _handle(exc) from exc


@router.get("/submission-drafts/{draft_id}/plan", response_model=AutomationPlanResponse)
async def get_submission_plan(
    draft_id: str,
    service: SubmissionDraftService = Depends(_get_service),
) -> AutomationPlanResponse:
    try:
        return service.get_plan(draft_id)
    except SubmissionDraftServiceError as exc:
        raise _handle(exc) from exc


@router.patch("/submission-drafts/{draft_id}/approval", response_model=SubmissionApprovalUpdateResponse)
async def patch_submission_approval(
    draft_id: str,
    body: UpdateSubmissionApprovalRequest,
    service: SubmissionDraftService = Depends(_get_service),
) -> SubmissionApprovalUpdateResponse:
    try:
        return service.update_approval(draft_id, body)
    except SubmissionDraftServiceError as exc:
        raise _handle(exc) from exc