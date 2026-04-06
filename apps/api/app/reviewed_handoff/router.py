"""Route handlers for reviewed snapshots, sign-off, and handoff eligibility."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from casegraph_agent_sdk.reviewed_handoff import (
    CreateReviewedSnapshotRequest,
    HandoffEligibilityResponse,
    ReviewedSnapshotCreateResponse,
    ReviewedSnapshotListResponse,
    ReviewedSnapshotResponse,
    ReviewedSnapshotSelectResponse,
    ReviewedSnapshotSignOffResponse,
    SignOffReviewedSnapshotRequest,
)

from app.persistence.database import get_session
from app.reviewed_handoff.service import ReviewedHandoffService, ReviewedHandoffServiceError

router = APIRouter(tags=["reviewed-handoff"])


def _get_service(session: Session = Depends(get_session)) -> ReviewedHandoffService:
    return ReviewedHandoffService(session)


def _handle(exc: ReviewedHandoffServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/cases/{case_id}/reviewed-snapshots", response_model=ReviewedSnapshotListResponse)
async def list_reviewed_snapshots(
    case_id: str,
    service: ReviewedHandoffService = Depends(_get_service),
) -> ReviewedSnapshotListResponse:
    try:
        return service.list_snapshots(case_id)
    except ReviewedHandoffServiceError as exc:
        raise _handle(exc) from exc


@router.post("/cases/{case_id}/reviewed-snapshots", response_model=ReviewedSnapshotCreateResponse)
async def create_reviewed_snapshot(
    case_id: str,
    body: CreateReviewedSnapshotRequest | None = None,
    service: ReviewedHandoffService = Depends(_get_service),
) -> ReviewedSnapshotCreateResponse:
    try:
        return service.create_snapshot(case_id, body or CreateReviewedSnapshotRequest())
    except ReviewedHandoffServiceError as exc:
        raise _handle(exc) from exc


@router.get("/reviewed-snapshots/{snapshot_id}", response_model=ReviewedSnapshotResponse)
async def get_reviewed_snapshot(
    snapshot_id: str,
    service: ReviewedHandoffService = Depends(_get_service),
) -> ReviewedSnapshotResponse:
    try:
        return service.get_snapshot(snapshot_id)
    except ReviewedHandoffServiceError as exc:
        raise _handle(exc) from exc


@router.post("/reviewed-snapshots/{snapshot_id}/signoff", response_model=ReviewedSnapshotSignOffResponse)
async def signoff_reviewed_snapshot(
    snapshot_id: str,
    body: SignOffReviewedSnapshotRequest,
    service: ReviewedHandoffService = Depends(_get_service),
) -> ReviewedSnapshotSignOffResponse:
    try:
        return service.signoff_snapshot(snapshot_id, body)
    except ReviewedHandoffServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/handoff-eligibility", response_model=HandoffEligibilityResponse)
async def get_handoff_eligibility(
    case_id: str,
    service: ReviewedHandoffService = Depends(_get_service),
) -> HandoffEligibilityResponse:
    try:
        return service.get_handoff_eligibility(case_id)
    except ReviewedHandoffServiceError as exc:
        raise _handle(exc) from exc


@router.patch("/cases/{case_id}/reviewed-snapshots/{snapshot_id}/select-for-handoff", response_model=ReviewedSnapshotSelectResponse)
async def select_reviewed_snapshot_for_handoff(
    case_id: str,
    snapshot_id: str,
    service: ReviewedHandoffService = Depends(_get_service),
) -> ReviewedSnapshotSelectResponse:
    try:
        return service.select_snapshot(case_id, snapshot_id)
    except ReviewedHandoffServiceError as exc:
        raise _handle(exc) from exc