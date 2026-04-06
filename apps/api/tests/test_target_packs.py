"""Tests for the target-pack foundation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.target_packs import TargetPackListFilters

from app.cases.models import CaseRecordModel
from app.persistence.database import get_session
from app.target_packs.context import get_case_target_pack_selection
from app.target_packs.packs import build_default_target_pack_registry, target_pack_registry
from app.target_packs.registry import TargetPackRegistry
from app.target_packs.router import router as target_packs_router


def _create_case(
    session: Session,
    *,
    domain_pack_id: str,
    case_type_id: str,
    jurisdiction: str,
    domain_category: str,
) -> CaseRecordModel:
    now = datetime.now(UTC)
    case = CaseRecordModel(
        case_id=str(uuid4()),
        title="Target Pack Test Case",
        category="operations",
        status="open",
        summary="Target-pack selection test case",
        current_stage="document_review",
        domain_pack_id=domain_pack_id,
        case_type_id=case_type_id,
        jurisdiction=jurisdiction,
        domain_category=domain_category,
        case_metadata_json={"external_reference": "TP-100"},
        created_at=now,
        updated_at=now,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


@pytest.fixture()
def session() -> Session:
    import app.audit.models  # noqa: F401
    import app.cases.models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client() -> TestClient:
    import app.audit.models  # noqa: F401
    import app.cases.models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app = FastAPI()
    app.include_router(target_packs_router)
    app.dependency_overrides[get_session] = override_session

    with TestClient(app) as test_client:
        test_client.engine = engine  # type: ignore[attr-defined]
        yield test_client


def test_default_registry_has_six_target_packs() -> None:
    registry = build_default_target_pack_registry()
    ids = {pack.metadata.pack_id for pack in registry.list_packs()}

    assert len(ids) == 6
    assert ids == {
        "generic_prior_auth_packet_v1",
        "generic_preclaim_packet_v1",
        "generic_insurance_claim_packet_v1",
        "generic_coverage_correspondence_packet_v1",
        "generic_tax_notice_packet_v1",
        "generic_tax_intake_packet_v1",
    }


def test_registry_filters_by_domain_context() -> None:
    response = target_pack_registry.list_summaries(
        TargetPackListFilters(domain_pack_id="medical_insurance_us")
    )

    assert len(response.packs) > 0
    assert all(
        "medical_insurance_us" in pack.compatibility.compatible_domain_pack_ids
        for pack in response.packs
    )


def test_registry_rejects_duplicate_pack_ids() -> None:
    registry = TargetPackRegistry()
    pack = target_pack_registry.get("generic_prior_auth_packet_v1")

    assert pack is not None
    registry.register(pack)

    with pytest.raises(ValueError):
        registry.register(pack.model_copy(deep=True))


def test_list_endpoint_filters_by_domain_pack(client: TestClient) -> None:
    response = client.get("/target-packs", params={"domain_pack_id": "tax_us"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["filters"]["domain_pack_id"] == "tax_us"
    assert len(payload["packs"]) > 0
    assert all(
        "tax_us" in pack["compatibility"]["compatible_domain_pack_ids"]
        for pack in payload["packs"]
    )


def test_case_target_pack_round_trip_via_api(client: TestClient) -> None:
    with Session(client.engine) as session:  # type: ignore[attr-defined]
        case = _create_case(
            session,
            domain_pack_id="medical_insurance_us",
            case_type_id="medical_insurance_us:prior_auth_review",
            jurisdiction="us",
            domain_category="medical_insurance",
        )
        case_id = case.case_id

    initial = client.get(f"/cases/{case_id}/target-pack")
    assert initial.status_code == 200
    assert initial.json()["selection"] is None

    update = client.patch(
        f"/cases/{case_id}/target-pack",
        json={"pack_id": "generic_prior_auth_packet_v1"},
    )
    assert update.status_code == 200
    assert update.json()["selection"]["pack_id"] == "generic_prior_auth_packet_v1"
    assert update.json()["selection"]["version"] == "1.0.0"

    persisted = client.get(f"/cases/{case_id}/target-pack")
    assert persisted.status_code == 200
    assert persisted.json()["selection"]["pack_id"] == "generic_prior_auth_packet_v1"

    with Session(client.engine) as session:  # type: ignore[attr-defined]
        record = session.get(CaseRecordModel, case_id)
        assert record is not None
        selection = get_case_target_pack_selection(record.case_metadata_json)
        assert selection is not None
        assert selection.pack_id == "generic_prior_auth_packet_v1"

    cleared = client.patch(
        f"/cases/{case_id}/target-pack",
        json={"clear_selection": True},
    )
    assert cleared.status_code == 200
    assert cleared.json()["selection"] is None


def test_case_target_pack_rejects_incompatible_selection(client: TestClient) -> None:
    with Session(client.engine) as session:  # type: ignore[attr-defined]
        case = _create_case(
            session,
            domain_pack_id="medical_insurance_us",
            case_type_id="medical_insurance_us:prior_auth_review",
            jurisdiction="us",
            domain_category="medical_insurance",
        )
        case_id = case.case_id

    response = client.patch(
        f"/cases/{case_id}/target-pack",
        json={"pack_id": "generic_tax_notice_packet_v1"},
    )

    assert response.status_code == 400
    assert "not compatible" in response.json()["detail"]