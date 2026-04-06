"""Route handlers for domain pack discovery and case type metadata."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from casegraph_agent_sdk.domains import (
    CaseTypeDetailResponse,
    CaseTypeTemplateMetadata,
    DocumentRequirementDefinition,
    DomainPackDetailResponse,
    DomainPackListResponse,
)

from app.domains.packs import domain_pack_registry

router = APIRouter(tags=["domain-packs"])


@router.get(
    "/domain-packs",
    response_model=DomainPackListResponse,
)
async def list_domain_packs() -> DomainPackListResponse:
    return domain_pack_registry.list_metadata()


@router.get(
    "/domain-packs/{pack_id}",
    response_model=DomainPackDetailResponse,
)
async def get_domain_pack(pack_id: str) -> DomainPackDetailResponse:
    pack = domain_pack_registry.get(pack_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="Domain pack not found.")
    return DomainPackDetailResponse(pack=pack)


@router.get(
    "/domain-packs/{pack_id}/case-types",
    response_model=list[CaseTypeTemplateMetadata],
)
async def list_pack_case_types(pack_id: str) -> list[CaseTypeTemplateMetadata]:
    pack = domain_pack_registry.get(pack_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="Domain pack not found.")
    return pack.case_types


@router.get(
    "/case-types/{case_type_id}",
    response_model=CaseTypeDetailResponse,
)
async def get_case_type(case_type_id: str) -> CaseTypeDetailResponse:
    result = domain_pack_registry.get_case_type(case_type_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Case type not found.")
    case_type, pack_metadata = result
    return CaseTypeDetailResponse(
        case_type=case_type,
        pack_metadata=pack_metadata,
    )


@router.get(
    "/case-types/{case_type_id}/requirements",
    response_model=list[DocumentRequirementDefinition],
)
async def list_case_type_requirements(
    case_type_id: str,
) -> list[DocumentRequirementDefinition]:
    result = domain_pack_registry.get_case_type(case_type_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Case type not found.")
    case_type, _pack = result
    return case_type.document_requirements
