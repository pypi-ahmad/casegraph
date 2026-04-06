"""Route handlers for operator queue, action items, lifecycle, and review notes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from casegraph_agent_sdk.operator_review import (
    ActionGenerationResponse,
    CaseActionListResponse,
    CaseStage,
    CaseStageResponse,
    CreateReviewNoteRequest,
    QueueFilterMetadata,
    QueueSummaryResponse,
    ReviewNoteListResponse,
    ReviewNoteResponse,
    ReviewQueueResponse,
    StageHistoryResponse,
    StageTransitionResponse,
    UpdateCaseStageRequest,
)

from app.operator_review.actions import ActionItemService
from app.operator_review.errors import OperatorReviewServiceError
from app.operator_review.lifecycle import CaseLifecycleService
from app.operator_review.queue import ReviewQueueService
from app.persistence.database import get_session

router = APIRouter(tags=["operator-review"])


def _handle(exc: OperatorReviewServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _queue_filters(
    stage: CaseStage | None = Query(default=None),
    has_missing_items: bool | None = Query(default=None),
    has_open_actions: bool | None = Query(default=None),
    domain_pack_id: str | None = Query(default=None),
    case_type_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> QueueFilterMetadata:
    return QueueFilterMetadata(
        stage=stage,
        has_missing_items=has_missing_items,
        has_open_actions=has_open_actions,
        domain_pack_id=domain_pack_id,
        case_type_id=case_type_id,
        limit=limit,
    )


def _get_action_service(session: Session = Depends(get_session)) -> ActionItemService:
    return ActionItemService(session)


def _get_lifecycle_service(session: Session = Depends(get_session)) -> CaseLifecycleService:
    return CaseLifecycleService(session)


def _get_queue_service(session: Session = Depends(get_session)) -> ReviewQueueService:
    return ReviewQueueService(session)


@router.get("/queue", response_model=ReviewQueueResponse)
async def get_queue(
    filters: QueueFilterMetadata = Depends(_queue_filters),
    service: ReviewQueueService = Depends(_get_queue_service),
) -> ReviewQueueResponse:
    try:
        return service.list_queue(filters)
    except OperatorReviewServiceError as exc:
        raise _handle(exc) from exc


@router.get("/queue/summary", response_model=QueueSummaryResponse)
async def get_queue_summary(
    filters: QueueFilterMetadata = Depends(_queue_filters),
    service: ReviewQueueService = Depends(_get_queue_service),
) -> QueueSummaryResponse:
    try:
        return service.get_summary(filters)
    except OperatorReviewServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/stage", response_model=CaseStageResponse)
async def get_case_stage(
    case_id: str,
    service: CaseLifecycleService = Depends(_get_lifecycle_service),
) -> CaseStageResponse:
    try:
        return service.get_stage(case_id)
    except OperatorReviewServiceError as exc:
        raise _handle(exc) from exc


@router.patch("/cases/{case_id}/stage", response_model=StageTransitionResponse)
async def update_case_stage(
    case_id: str,
    body: UpdateCaseStageRequest,
    service: CaseLifecycleService = Depends(_get_lifecycle_service),
) -> StageTransitionResponse:
    try:
        return service.transition_stage(case_id, body)
    except OperatorReviewServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/stage-history", response_model=StageHistoryResponse)
async def get_stage_history(
    case_id: str,
    service: CaseLifecycleService = Depends(_get_lifecycle_service),
) -> StageHistoryResponse:
    try:
        return service.list_stage_history(case_id)
    except OperatorReviewServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/actions", response_model=CaseActionListResponse)
async def get_case_actions(
    case_id: str,
    service: ActionItemService = Depends(_get_action_service),
) -> CaseActionListResponse:
    try:
        return service.list_actions(case_id)
    except OperatorReviewServiceError as exc:
        raise _handle(exc) from exc


@router.post("/cases/{case_id}/actions/generate", response_model=ActionGenerationResponse)
async def generate_case_actions(
    case_id: str,
    service: ActionItemService = Depends(_get_action_service),
) -> ActionGenerationResponse:
    try:
        return service.generate_actions(case_id)
    except OperatorReviewServiceError as exc:
        raise _handle(exc) from exc


@router.post("/cases/{case_id}/review-notes", response_model=ReviewNoteResponse)
async def create_review_note(
    case_id: str,
    body: CreateReviewNoteRequest,
    service: ActionItemService = Depends(_get_action_service),
) -> ReviewNoteResponse:
    try:
        return service.create_review_note(case_id, body)
    except OperatorReviewServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/review-notes", response_model=ReviewNoteListResponse)
async def get_review_notes(
    case_id: str,
    service: ActionItemService = Depends(_get_action_service),
) -> ReviewNoteListResponse:
    try:
        return service.list_review_notes(case_id)
    except OperatorReviewServiceError as exc:
        raise _handle(exc) from exc