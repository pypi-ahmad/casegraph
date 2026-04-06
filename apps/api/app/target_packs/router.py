"""Route handlers for target-pack registry discovery and case selection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from casegraph_agent_sdk.domains import CaseTypeTemplateId, DomainPackId
from casegraph_agent_sdk.target_packs import (
    CaseTargetPackResponse,
    CaseTargetPackUpdateResponse,
    TargetPackCategory,
    TargetPackCompatibilityResponse,
    TargetPackDetailResponse,
    TargetPackFieldSchemaResponse,
    TargetPackListFilters,
    TargetPackListResponse,
    TargetPackRequirementsResponse,
    TargetPackStatus,
    UpdateCaseTargetPackRequest,
)

from app.persistence.database import get_session
from app.target_packs.service import TargetPackService, TargetPackServiceError

router = APIRouter(tags=["target-packs"])


def _handle(exc: TargetPackServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _get_service(session: Session = Depends(get_session)) -> TargetPackService:
    return TargetPackService(session)


def _filters(
    domain_pack_id: DomainPackId | None = Query(default=None),
    case_type_id: CaseTypeTemplateId | None = Query(default=None),
    category: TargetPackCategory | None = Query(default=None),
    status: TargetPackStatus | None = Query(default=None),
) -> TargetPackListFilters:
    return TargetPackListFilters(
        domain_pack_id=domain_pack_id,
        case_type_id=case_type_id,
        category=category,
        status=status,
    )


@router.get("/target-packs", response_model=TargetPackListResponse)
async def list_target_packs(
    filters: TargetPackListFilters = Depends(_filters),
    service: TargetPackService = Depends(_get_service),
) -> TargetPackListResponse:
    return service.list_packs(filters)


@router.get("/target-packs/{pack_id}", response_model=TargetPackDetailResponse)
async def get_target_pack(
    pack_id: str,
    service: TargetPackService = Depends(_get_service),
) -> TargetPackDetailResponse:
    try:
        return service.get_pack(pack_id)
    except TargetPackServiceError as exc:
        raise _handle(exc) from exc


@router.get("/target-packs/{pack_id}/compatibility", response_model=TargetPackCompatibilityResponse)
async def get_target_pack_compatibility(
    pack_id: str,
    service: TargetPackService = Depends(_get_service),
) -> TargetPackCompatibilityResponse:
    try:
        return service.get_compatibility(pack_id)
    except TargetPackServiceError as exc:
        raise _handle(exc) from exc


@router.get("/target-packs/{pack_id}/field-schema", response_model=TargetPackFieldSchemaResponse)
async def get_target_pack_field_schema(
    pack_id: str,
    service: TargetPackService = Depends(_get_service),
) -> TargetPackFieldSchemaResponse:
    try:
        return service.get_field_schema(pack_id)
    except TargetPackServiceError as exc:
        raise _handle(exc) from exc


@router.get("/target-packs/{pack_id}/requirements", response_model=TargetPackRequirementsResponse)
async def get_target_pack_requirements(
    pack_id: str,
    service: TargetPackService = Depends(_get_service),
) -> TargetPackRequirementsResponse:
    try:
        return service.get_requirements(pack_id)
    except TargetPackServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/target-pack", response_model=CaseTargetPackResponse)
async def get_case_target_pack(
    case_id: str,
    service: TargetPackService = Depends(_get_service),
) -> CaseTargetPackResponse:
    try:
        return service.get_case_target_pack(case_id)
    except TargetPackServiceError as exc:
        raise _handle(exc) from exc


@router.patch("/cases/{case_id}/target-pack", response_model=CaseTargetPackUpdateResponse)
async def patch_case_target_pack(
    case_id: str,
    body: UpdateCaseTargetPackRequest,
    service: TargetPackService = Depends(_get_service),
) -> CaseTargetPackUpdateResponse:
    try:
        return service.update_case_target_pack(case_id, body)
    except TargetPackServiceError as exc:
        raise _handle(exc) from exc