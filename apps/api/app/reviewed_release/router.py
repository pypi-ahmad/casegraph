"""Route handlers for reviewed release bundles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from casegraph_agent_sdk.reviewed_release import (
    CreateReleaseBundleRequest,
    ReleaseArtifactListResponse,
    ReleaseBundleCreateResponse,
    ReleaseBundleListResponse,
    ReleaseBundleResponse,
    ReleaseEligibilityResponse,
)

from app.persistence.database import get_session
from app.reviewed_release.service import ReviewedReleaseService, ReviewedReleaseServiceError

router = APIRouter(tags=["reviewed-release"])


def _get_service(session: Session = Depends(get_session)) -> ReviewedReleaseService:
    return ReviewedReleaseService(session)


def _handle(exc: ReviewedReleaseServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/cases/{case_id}/releases", response_model=ReleaseBundleListResponse)
async def list_releases(
    case_id: str,
    service: ReviewedReleaseService = Depends(_get_service),
) -> ReleaseBundleListResponse:
    try:
        return service.list_releases(case_id)
    except ReviewedReleaseServiceError as exc:
        raise _handle(exc) from exc


@router.post("/cases/{case_id}/releases", response_model=ReleaseBundleCreateResponse)
async def create_release(
    case_id: str,
    body: CreateReleaseBundleRequest | None = None,
    service: ReviewedReleaseService = Depends(_get_service),
) -> ReleaseBundleCreateResponse:
    try:
        return await service.create_release(case_id, body or CreateReleaseBundleRequest())
    except ReviewedReleaseServiceError as exc:
        raise _handle(exc) from exc


@router.get("/releases/{release_id}", response_model=ReleaseBundleResponse)
async def get_release(
    release_id: str,
    service: ReviewedReleaseService = Depends(_get_service),
) -> ReleaseBundleResponse:
    try:
        return service.get_release(release_id)
    except ReviewedReleaseServiceError as exc:
        raise _handle(exc) from exc


@router.get("/releases/{release_id}/artifacts", response_model=ReleaseArtifactListResponse)
async def get_release_artifacts(
    release_id: str,
    service: ReviewedReleaseService = Depends(_get_service),
) -> ReleaseArtifactListResponse:
    try:
        return service.get_release_artifacts(release_id)
    except ReviewedReleaseServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/release-eligibility", response_model=ReleaseEligibilityResponse)
async def get_release_eligibility(
    case_id: str,
    snapshot_id: str = Query("", description="Optional snapshot ID to check eligibility for"),
    service: ReviewedReleaseService = Depends(_get_service),
) -> ReleaseEligibilityResponse:
    try:
        return service.get_release_eligibility(case_id, snapshot_id=snapshot_id)
    except ReviewedReleaseServiceError as exc:
        raise _handle(exc) from exc
