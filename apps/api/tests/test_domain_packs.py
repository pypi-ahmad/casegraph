"""Tests for the domain pack foundation."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.domains import (
    DomainPackDetail,
    DomainPackListResponse,
    DomainPackMetadata,
)
from casegraph_agent_sdk.cases import CreateCaseRequest

from app.cases.models import CaseRecordModel
from app.cases.service import CaseService, CaseServiceError
from app.domains.packs import build_default_domain_pack_registry, domain_pack_registry
from app.domains.registry import DomainPackRegistry
from app.domains.router import router as domains_router


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def domain_client() -> TestClient:
    app = FastAPI()
    app.include_router(domains_router)
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

def test_default_registry_has_eight_packs() -> None:
    registry = build_default_domain_pack_registry()
    packs = registry.list_packs()
    ids = [p.metadata.pack_id for p in packs]
    assert len(ids) == 8
    assert "medical_us" in ids
    assert "medical_india" in ids
    assert "medical_insurance_us" in ids
    assert "medical_insurance_india" in ids
    assert "insurance_us" in ids
    assert "insurance_india" in ids
    assert "tax_us" in ids
    assert "tax_india" in ids


def test_singleton_registry_matches_default() -> None:
    assert len(domain_pack_registry.list_packs()) == 8


def test_pack_metadata_structure() -> None:
    pack = domain_pack_registry.get("medical_us")
    assert pack is not None
    meta = pack.metadata
    assert meta.pack_id == "medical_us"
    assert meta.domain_category == "medical"
    assert meta.jurisdiction == "us"
    assert meta.case_type_count > 0
    assert meta.capabilities.has_case_types is True
    assert meta.capabilities.has_workflow_bindings is True
    assert meta.capabilities.has_extraction_bindings is True
    assert meta.capabilities.has_document_requirements is True
    assert len(meta.capabilities.limitations) > 0


def test_list_metadata_returns_response() -> None:
    resp = domain_pack_registry.list_metadata()
    assert isinstance(resp, DomainPackListResponse)
    assert len(resp.packs) == 8
    assert all(isinstance(p, DomainPackMetadata) for p in resp.packs)


def test_get_unknown_pack_returns_none() -> None:
    assert domain_pack_registry.get("nonexistent") is None


# ---------------------------------------------------------------------------
# Case type tests
# ---------------------------------------------------------------------------

def test_each_pack_has_case_types() -> None:
    for pack in domain_pack_registry.list_packs():
        assert len(pack.case_types) > 0, f"{pack.metadata.pack_id} has no case types"


def test_case_type_ids_are_unique() -> None:
    all_ids: list[str] = []
    for pack in domain_pack_registry.list_packs():
        for ct in pack.case_types:
            all_ids.append(ct.case_type_id)
    assert len(all_ids) == len(set(all_ids)), "Duplicate case type IDs found"


def test_get_case_type_cross_pack_lookup() -> None:
    result = domain_pack_registry.get_case_type("medical_us:record_review")
    assert result is not None
    case_type, pack_meta = result
    assert case_type.case_type_id == "medical_us:record_review"
    assert pack_meta.pack_id == "medical_us"


def test_get_case_type_missing_returns_none() -> None:
    assert domain_pack_registry.get_case_type("nonexistent") is None


def test_case_types_have_typical_stages() -> None:
    for pack in domain_pack_registry.list_packs():
        for ct in pack.case_types:
            assert len(ct.typical_stages) > 0, f"{ct.case_type_id} has no stages"


def test_case_types_have_document_requirements() -> None:
    for pack in domain_pack_registry.list_packs():
        for ct in pack.case_types:
            assert len(ct.document_requirements) > 0, f"{ct.case_type_id} has no document requirements"


def test_case_types_have_workflow_bindings() -> None:
    for pack in domain_pack_registry.list_packs():
        for ct in pack.case_types:
            assert len(ct.workflow_bindings) > 0, f"{ct.case_type_id} has no workflow bindings"


def test_case_types_reference_real_workflow_ids() -> None:
    from app.workflow_packs.registry import get_workflow_pack_registry
    workflow_registry = get_workflow_pack_registry()
    allowed_ids = {
        "provider-task-execution",
        "rag-task-execution",
    } | {pack.metadata.workflow_pack_id for pack in workflow_registry.list_packs()}
    for pack in domain_pack_registry.list_packs():
        for ct in pack.case_types:
            for wb in ct.workflow_bindings:
                assert wb.workflow_id in allowed_ids, (
                    f"{ct.case_type_id} references unknown workflow: {wb.workflow_id}"
                )


def test_domain_workflow_bindings_match_case_type_compatibility() -> None:
    from app.workflow_packs.registry import get_workflow_pack_registry

    workflow_registry = get_workflow_pack_registry()
    generic_ids = {"provider-task-execution", "rag-task-execution"}

    for pack in domain_pack_registry.list_packs():
        for ct in pack.case_types:
            for wb in ct.workflow_bindings:
                if wb.workflow_id in generic_ids:
                    continue
                definition = workflow_registry.get(wb.workflow_id)
                assert definition is not None, f"Missing workflow definition for {wb.workflow_id}"
                assert ct.case_type_id in definition.metadata.compatible_case_type_ids, (
                    f"{ct.case_type_id} is bound to incompatible workflow {wb.workflow_id}"
                )


def test_case_types_reference_real_extraction_ids() -> None:
    allowed_ids = {"contact_info", "document_header", "key_value_packet"}
    for pack in domain_pack_registry.list_packs():
        for ct in pack.case_types:
            for eb in ct.extraction_bindings:
                assert eb.extraction_template_id in allowed_ids, (
                    f"{ct.case_type_id} references unknown extraction: {eb.extraction_template_id}"
                )


def test_document_requirements_have_valid_priorities() -> None:
    valid = {"required", "recommended", "optional"}
    for pack in domain_pack_registry.list_packs():
        for ct in pack.case_types:
            for req in ct.document_requirements:
                assert req.priority in valid, f"{ct.case_type_id}:{req.requirement_id} bad priority"


# ---------------------------------------------------------------------------
# Jurisdiction and category tests
# ---------------------------------------------------------------------------

def test_jurisdictions_covered() -> None:
    jurisdictions = {p.metadata.jurisdiction for p in domain_pack_registry.list_packs()}
    assert "us" in jurisdictions
    assert "india" in jurisdictions


def test_domain_categories_covered() -> None:
    categories = {p.metadata.domain_category for p in domain_pack_registry.list_packs()}
    assert "medical" in categories
    assert "medical_insurance" in categories
    assert "insurance" in categories
    assert "taxation" in categories


# ---------------------------------------------------------------------------
# Case integration tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_create_case_with_domain_context(session: Session) -> None:
    service = CaseService(session)
    request = CreateCaseRequest(
        title="PA Review — Test Patient",
        category="medical_insurance",
        domain_pack_id="medical_insurance_us",
        case_type_id="medical_insurance_us:prior_auth_review",
    )
    case = await service.create_case(request)

    assert case.domain_context is not None
    assert case.domain_context.domain_pack_id == "medical_insurance_us"
    assert case.domain_context.jurisdiction == "us"
    assert case.domain_context.case_type_id == "medical_insurance_us:prior_auth_review"
    assert case.domain_context.domain_category == "medical_insurance"


@pytest.mark.anyio
async def test_create_case_without_domain_context(session: Session) -> None:
    service = CaseService(session)
    request = CreateCaseRequest(
        title="Generic Case",
    )
    case = await service.create_case(request)
    assert case.domain_context is None


@pytest.mark.anyio
async def test_create_case_rejects_invalid_case_type(session: Session) -> None:
    service = CaseService(session)
    request = CreateCaseRequest(
        title="Bad Case",
        domain_pack_id="medical_us",
        case_type_id="nonexistent:type",
    )
    with pytest.raises(CaseServiceError) as exc:
        await service.create_case(request)
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_create_case_rejects_mismatched_pack(session: Session) -> None:
    service = CaseService(session)
    request = CreateCaseRequest(
        title="Bad Case",
        domain_pack_id="tax_us",
        case_type_id="medical_us:record_review",
    )
    with pytest.raises(CaseServiceError) as exc:
        await service.create_case(request)
    assert exc.value.status_code == 400
    assert "does not belong to pack" in exc.value.detail


@pytest.mark.anyio
async def test_domain_context_persists_in_database(session: Session) -> None:
    service = CaseService(session)
    request = CreateCaseRequest(
        title="Tax Notice — Test",
        domain_pack_id="tax_india",
        case_type_id="tax_india:notice_review",
    )
    case = await service.create_case(request)

    record = session.get(CaseRecordModel, case.case_id)
    assert record is not None
    assert record.domain_pack_id == "tax_india"
    assert record.jurisdiction == "india"
    assert record.case_type_id == "tax_india:notice_review"
    assert record.domain_category == "taxation"


@pytest.mark.anyio
async def test_case_detail_includes_domain_context(session: Session) -> None:
    service = CaseService(session)
    case = await service.create_case(
        CreateCaseRequest(
            title="Insurance Review — Test",
            domain_pack_id="insurance_us",
            case_type_id="insurance_us:policy_review",
        )
    )
    detail = await service.get_case_detail(case.case_id)
    assert detail.case.domain_context is not None
    assert detail.case.domain_context.domain_pack_id == "insurance_us"


@pytest.mark.anyio
async def test_case_record_derives_missing_domain_metadata_from_registry(
    session: Session,
) -> None:
    now = datetime.now(UTC)
    session.add(
        CaseRecordModel(
            case_id="legacy-domain-case",
            title="Legacy Domain Case",
            status="open",
            case_metadata_json={},
            domain_pack_id="tax_india",
            case_type_id="tax_india:notice_review",
            jurisdiction=None,
            domain_category=None,
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()

    service = CaseService(session)
    detail = await service.get_case_detail("legacy-domain-case")

    assert detail.case.domain_context is not None
    assert detail.case.domain_context.jurisdiction == "india"
    assert detail.case.domain_context.domain_category == "taxation"


# ---------------------------------------------------------------------------
# Custom registry tests
# ---------------------------------------------------------------------------

def test_custom_registry_register_and_get() -> None:
    registry = DomainPackRegistry()
    pack = DomainPackDetail(
        metadata=DomainPackMetadata(
            pack_id="custom_pack",
            display_name="Custom Pack",
            domain_category="medical",
            jurisdiction="us",
        ),
        case_types=[],
    )
    registry.register(pack)
    found = registry.get("custom_pack")
    assert found is not None
    assert found.metadata.pack_id == "custom_pack"


def test_list_case_types_for_pack() -> None:
    types = domain_pack_registry.list_case_types_for_pack("medical_us")
    assert len(types) >= 2
    assert all(ct.domain_pack_id == "medical_us" for ct in types)


def test_list_case_types_for_unknown_pack() -> None:
    types = domain_pack_registry.list_case_types_for_pack("nonexistent")
    assert types == []


def test_list_domain_packs_endpoint_returns_registry_data(
    domain_client: TestClient,
) -> None:
    response = domain_client.get("/domain-packs")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["packs"]) == 8
    assert any(pack["pack_id"] == "medical_us" for pack in payload["packs"])


def test_domain_pack_detail_endpoint_returns_case_types(
    domain_client: TestClient,
) -> None:
    response = domain_client.get("/domain-packs/medical_us")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pack"]["metadata"]["pack_id"] == "medical_us"
    assert any(
        case_type["case_type_id"] == "medical_us:record_review"
        for case_type in payload["pack"]["case_types"]
    )


def test_case_type_endpoints_return_metadata_and_requirements(
    domain_client: TestClient,
) -> None:
    detail_response = domain_client.get("/case-types/medical_us:record_review")
    requirements_response = domain_client.get(
        "/case-types/medical_us:record_review/requirements"
    )

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["pack_metadata"]["pack_id"] == "medical_us"
    assert detail_payload["case_type"]["case_type_id"] == "medical_us:record_review"

    assert requirements_response.status_code == 200
    requirements_payload = requirements_response.json()
    assert any(
        requirement["requirement_id"] == "clinical_notes"
        for requirement in requirements_payload
    )


def test_domain_endpoints_return_404_for_unknown_resources(
    domain_client: TestClient,
) -> None:
    assert domain_client.get("/domain-packs/unknown-pack").status_code == 404
    assert domain_client.get("/case-types/unknown-type").status_code == 404
    assert domain_client.get("/case-types/unknown-type/requirements").status_code == 404
