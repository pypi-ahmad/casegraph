"""Route handlers for human validation — field validation, requirement review, and reviewed state."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from casegraph_agent_sdk.human_validation import (
    ExtractionValidationsResponse,
    FieldValidationResponse,
    RequirementReviewResponse,
    RequirementReviewsResponse,
    ReviewedCaseStateResponse,
    ReviewRequirementRequest,
    ValidateFieldRequest,
)

from app.human_validation.service import HumanValidationService, HumanValidationServiceError
from app.persistence.database import get_session

router = APIRouter(tags=["human-validation"])


def _get_service(session: Session = Depends(get_session)) -> HumanValidationService:
    return HumanValidationService(session)


def _handle(exc: HumanValidationServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/cases/{case_id}/review-state", response_model=ReviewedCaseStateResponse)
async def get_review_state(
    case_id: str,
    service: HumanValidationService = Depends(_get_service),
) -> ReviewedCaseStateResponse:
    try:
        return service.get_reviewed_state(case_id)
    except HumanValidationServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/extraction-validations", response_model=ExtractionValidationsResponse)
async def get_extraction_validations(
    case_id: str,
    service: HumanValidationService = Depends(_get_service),
) -> ExtractionValidationsResponse:
    try:
        return service.get_extraction_validations(case_id)
    except HumanValidationServiceError as exc:
        raise _handle(exc) from exc


@router.post(
    "/extractions/{extraction_id}/fields/{field_id}/validate",
    response_model=FieldValidationResponse,
)
async def validate_field(
    extraction_id: str,
    field_id: str,
    request: ValidateFieldRequest,
    service: HumanValidationService = Depends(_get_service),
) -> FieldValidationResponse:
    try:
        return service.validate_field(extraction_id, field_id, request)
    except HumanValidationServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/requirement-reviews", response_model=RequirementReviewsResponse)
async def get_requirement_reviews(
    case_id: str,
    service: HumanValidationService = Depends(_get_service),
) -> RequirementReviewsResponse:
    try:
        return service.get_requirement_reviews(case_id)
    except HumanValidationServiceError as exc:
        raise _handle(exc) from exc


@router.post(
    "/cases/{case_id}/checklist/items/{item_id}/review",
    response_model=RequirementReviewResponse,
)
async def review_requirement(
    case_id: str,
    item_id: str,
    request: ReviewRequirementRequest,
    service: HumanValidationService = Depends(_get_service),
) -> RequirementReviewResponse:
    try:
        return service.review_requirement(case_id, item_id, request)
    except HumanValidationServiceError as exc:
        raise _handle(exc) from exc
