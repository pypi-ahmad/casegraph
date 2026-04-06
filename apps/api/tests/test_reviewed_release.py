"""Tests for the reviewed release foundation."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.extraction import ExtractedFieldResult
from casegraph_agent_sdk.human_validation import ReviewRequirementRequest, ValidateFieldRequest
from casegraph_agent_sdk.reviewed_handoff import (
    CreateReviewedSnapshotRequest,
    SignOffReviewedSnapshotRequest,
)

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel
from app.extraction.models import ExtractionRunModel
from app.human_validation.service import HumanValidationService
from app.ingestion.models import DocumentRecord
from app.persistence.database import get_session
from app.readiness.models import ChecklistItemModel, ChecklistModel
from app.reviewed_handoff.service import ReviewedHandoffService
from app.reviewed_release.router import router as reviewed_release_router
from app.reviewed_release.service import ReviewedReleaseService, ReviewedReleaseServiceError
from app.target_packs.context import build_case_target_pack_selection, set_case_target_pack_selection
from app.target_packs.packs import target_pack_registry


@pytest.fixture()
def session() -> Session:
    # Import all models so SQLModel.metadata.create_all creates all tables
    import app.audit.models  # noqa: F401
    import app.cases.models  # noqa: F401
    import app.ingestion.models  # noqa: F401
    import app.review.models  # noqa: F401
    import app.extraction.models  # noqa: F401
    import app.tasks.models  # noqa: F401
    import app.readiness.models  # noqa: F401
    import app.operator_review.models  # noqa: F401
    import app.packets.models  # noqa: F401
    import app.submissions.models  # noqa: F401
    import app.communications.models  # noqa: F401
    import app.execution.models  # noqa: F401
    import app.workflow_packs.models  # noqa: F401
    import app.human_validation.models  # noqa: F401
    import app.reviewed_handoff.models  # noqa: F401
    import app.reviewed_release.models  # noqa: F401

    engine = create_engine("sqlite://", echo=False, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _create_case(session: Session) -> CaseRecordModel:
    case = CaseRecordModel(
        case_id=str(uuid4()),
        title="Release Test Case",
        category="operations",
        status="open",
        summary="Release foundation test case",
        current_stage="document_review",
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _add_document(session: Session, *, case_id: str) -> DocumentRecord:
    document = DocumentRecord(
        document_id=str(uuid4()),
        filename="release-source.pdf",
        content_type="application/pdf",
        classification="document",
        requested_mode="auto",
        resolved_mode="auto",
        processing_status="completed",
        page_count=2,
    )
    session.add(document)
    session.add(
        CaseDocumentLinkModel(
            link_id=str(uuid4()),
            case_id=case_id,
            document_id=document.document_id,
        )
    )
    session.commit()
    return document


def _add_extraction(session: Session, *, case_id: str, document_id: str) -> ExtractionRunModel:
    fields = [
        ExtractedFieldResult(
            field_id="full_name",
            field_type="string",
            value="Jane Doe",
            raw_value="Jane Doe",
            is_present=True,
        ),
        ExtractedFieldResult(
            field_id="reference_number",
            field_type="string",
            value="REF-200",
            raw_value="REF-200",
            is_present=True,
        ),
    ]
    extraction = ExtractionRunModel(
        extraction_id=str(uuid4()),
        document_id=document_id,
        template_id="contact_info",
        case_id=case_id,
        strategy_used="provider_structured",
        provider="openai",
        model_id="gpt-4.1",
        status="completed",
        field_count=len(fields),
        fields_extracted=len(fields),
        grounding_available=False,
        fields_json=[field.model_dump(mode="json") for field in fields],
    )
    session.add(extraction)
    session.commit()
    return extraction


def _create_checklist(session: Session, *, case_id: str) -> ChecklistItemModel:
    checklist = ChecklistModel(
        checklist_id=f"chk-{case_id}",
        case_id=case_id,
        domain_pack_id="test-pack",
        case_type_id="test-case-type",
        requirement_count=1,
    )
    item = ChecklistItemModel(
        item_id=f"item-{case_id}",
        checklist_id=checklist.checklist_id,
        requirement_id="req-1",
        display_name="Signed authorization",
        description="Authorization record available",
        document_category="supporting_attachment",
        priority="required",
        status="missing",
    )
    session.add(checklist)
    session.add(item)
    session.commit()
    return item


def _prepare_signed_off_case(session: Session) -> tuple[CaseRecordModel, str]:
    """Create a case with a signed-off reviewed snapshot, ready for release."""
    case = _create_case(session)
    document = _add_document(session, case_id=case.case_id)
    extraction = _add_extraction(session, case_id=case.case_id, document_id=document.document_id)
    item = _create_checklist(session, case_id=case.case_id)

    validation = HumanValidationService(session)
    validation.validate_field(
        extraction.extraction_id,
        "full_name",
        ValidateFieldRequest(
            status="corrected",
            reviewed_value="Jane Reviewed",
            reviewer_id="reviewer-1",
        ),
    )
    validation.validate_field(
        extraction.extraction_id,
        "reference_number",
        ValidateFieldRequest(
            status="accepted",
            reviewer_id="reviewer-1",
        ),
    )
    validation.review_requirement(
        case.case_id,
        item.item_id,
        ReviewRequirementRequest(
            requirement_id="req-1",
            status="confirmed_supported",
            reviewer_id="reviewer-1",
            note="Authorization verified",
        ),
    )

    handoff = ReviewedHandoffService(session)
    snapshot_resp = handoff.create_snapshot(case.case_id, CreateReviewedSnapshotRequest())
    snapshot_id = snapshot_resp.snapshot.snapshot_id

    handoff.signoff_snapshot(
        snapshot_id,
        SignOffReviewedSnapshotRequest(
            operator_id="senior-reviewer",
            operator_display_name="Senior Reviewer",
            status="signed_off",
            note="Ready for release.",
        ),
    )

    return case, snapshot_id


# ---------------------------------------------------------------------------
# Unit tests for the service
# ---------------------------------------------------------------------------


class TestReleaseEligibility:
    def test_eligible_with_signed_off_snapshot(self, session: Session) -> None:
        case, snapshot_id = _prepare_signed_off_case(session)
        service = ReviewedReleaseService(session)
        resp = service.get_release_eligibility(case.case_id)
        assert resp.eligibility.eligible is True
        assert resp.eligibility.snapshot_id == snapshot_id

    def test_ineligible_without_snapshot(self, session: Session) -> None:
        case = _create_case(session)
        service = ReviewedReleaseService(session)
        resp = service.get_release_eligibility(case.case_id)
        assert resp.eligibility.eligible is False
        assert len(resp.eligibility.reasons) > 0

    def test_ineligible_case_not_found(self, session: Session) -> None:
        service = ReviewedReleaseService(session)
        with pytest.raises(ReviewedReleaseServiceError) as exc_info:
            service.get_release_eligibility("nonexistent-case-id")
        assert exc_info.value.status_code == 404

    def test_eligible_with_specific_snapshot(self, session: Session) -> None:
        case, snapshot_id = _prepare_signed_off_case(session)
        service = ReviewedReleaseService(session)
        resp = service.get_release_eligibility(case.case_id, snapshot_id=snapshot_id)
        assert resp.eligibility.eligible is True
        assert resp.eligibility.snapshot_id == snapshot_id


class TestReleaseCreation:
    def test_create_release_bundle(self, session: Session) -> None:
        from casegraph_agent_sdk.reviewed_release import CreateReleaseBundleRequest

        case, snapshot_id = _prepare_signed_off_case(session)
        service = ReviewedReleaseService(session)
        resp = asyncio.run(
            service.create_release(
                case.case_id,
                CreateReleaseBundleRequest(
                    operator_id="release-operator",
                    operator_display_name="Release Operator",
                    note="Test release",
                    generate_packet=True,
                    generate_submission_draft=True,
                    generate_communication_draft=False,
                    include_automation_plan_metadata=False,
                ),
            )
        )
        assert resp.result.success is True
        assert resp.release is not None
        assert resp.release.status in ("created", "incomplete")
        assert resp.release.source.snapshot_id == snapshot_id
        assert resp.release.source.signoff_status == "signed_off"

    def test_create_release_persists_and_lists(self, session: Session) -> None:
        from casegraph_agent_sdk.reviewed_release import CreateReleaseBundleRequest
        from app.reviewed_release.models import ReleaseBundleModel

        case, _ = _prepare_signed_off_case(session)
        service = ReviewedReleaseService(session)
        create_resp = asyncio.run(
            service.create_release(
                case.case_id,
                CreateReleaseBundleRequest(
                    operator_id="op1",
                    generate_packet=True,
                    generate_communication_draft=False,
                ),
            )
        )
        release_id = create_resp.release.release_id

        list_resp = service.list_releases(case.case_id)
        assert len(list_resp.releases) == 1
        assert list_resp.releases[0].release_id == release_id

        get_resp = service.get_release(release_id)
        assert get_resp.release.release_id == release_id
        assert get_resp.release.source.signoff_status == "signed_off"

        persisted = session.get(ReleaseBundleModel, release_id)
        assert persisted is not None
        assert persisted.signoff_id == get_resp.release.source.signoff_id

    def test_create_release_records_artifacts(self, session: Session) -> None:
        from casegraph_agent_sdk.reviewed_release import CreateReleaseBundleRequest

        case, _ = _prepare_signed_off_case(session)
        service = ReviewedReleaseService(session)
        resp = asyncio.run(
            service.create_release(
                case.case_id,
                CreateReleaseBundleRequest(
                    operator_id="op1",
                    generate_packet=True,
                    generate_communication_draft=False,
                    include_automation_plan_metadata=True,
                ),
            )
        )
        assert resp.release.summary.total_artifacts >= 1
        artifact_types = [a.artifact_type for a in resp.release.artifacts]
        assert "reviewed_packet" in artifact_types
        assert "reviewed_automation_plan" in artifact_types
        assert all(a.release_bundle_id == resp.release.release_id for a in resp.release.artifacts)
        plan_artifacts = [a for a in resp.release.artifacts if a.artifact_type == "reviewed_automation_plan"]
        assert plan_artifacts[0].status == "skipped_missing_data"

    def test_create_release_requires_valid_case(self, session: Session) -> None:
        from casegraph_agent_sdk.reviewed_release import CreateReleaseBundleRequest

        service = ReviewedReleaseService(session)
        with pytest.raises(ReviewedReleaseServiceError) as exc_info:
            asyncio.run(
                service.create_release(
                    "nonexistent",
                    CreateReleaseBundleRequest(operator_id="op1"),
                )
            )
        assert exc_info.value.status_code == 404

    def test_get_release_artifacts_endpoint(self, session: Session) -> None:
        from casegraph_agent_sdk.reviewed_release import CreateReleaseBundleRequest

        case, _ = _prepare_signed_off_case(session)
        service = ReviewedReleaseService(session)
        resp = asyncio.run(
            service.create_release(
                case.case_id,
                CreateReleaseBundleRequest(
                    operator_id="op1",
                    generate_packet=True,
                    generate_communication_draft=False,
                ),
            )
        )
        artifacts_resp = service.get_release_artifacts(resp.release.release_id)
        assert artifacts_resp.release_id == resp.release.release_id
        assert len(artifacts_resp.artifacts) == resp.release.summary.total_artifacts


class TestReleaseSourceProvenance:
    def test_source_metadata_captures_snapshot_details(self, session: Session) -> None:
        from casegraph_agent_sdk.reviewed_release import CreateReleaseBundleRequest

        case, snapshot_id = _prepare_signed_off_case(session)
        service = ReviewedReleaseService(session)
        resp = asyncio.run(
            service.create_release(
                case.case_id,
                CreateReleaseBundleRequest(
                    operator_id="op1",
                    generate_packet=True,
                    generate_communication_draft=False,
                ),
            )
        )
        source = resp.release.source
        assert source.case_id == case.case_id
        assert source.snapshot_id == snapshot_id
        assert source.signoff_id != ""
        assert source.signoff_status == "signed_off"
        assert source.signed_off_by != ""
        assert source.signed_off_at != ""

    def test_source_metadata_captures_target_pack_selection(self, session: Session) -> None:
        from casegraph_agent_sdk.reviewed_release import CreateReleaseBundleRequest

        case, _ = _prepare_signed_off_case(session)
        pack = target_pack_registry.get("generic_prior_auth_packet_v1")
        assert pack is not None
        case.domain_pack_id = "medical_insurance_us"
        case.case_type_id = "medical_insurance_us:prior_auth_review"
        case.jurisdiction = "us"
        case.domain_category = "medical_insurance"
        case.case_metadata_json = set_case_target_pack_selection(
            case.case_metadata_json,
            build_case_target_pack_selection(pack, selected_at="2024-01-02T03:04:05Z"),
        )
        session.add(case)
        session.commit()

        service = ReviewedReleaseService(session)
        resp = asyncio.run(
            service.create_release(
                case.case_id,
                CreateReleaseBundleRequest(
                    operator_id="op1",
                    generate_packet=True,
                    generate_communication_draft=False,
                ),
            )
        )

        assert resp.release.source.target_pack_selection is not None
        assert resp.release.source.target_pack_selection.pack_id == "generic_prior_auth_packet_v1"
        assert resp.release.source.target_pack_selection.version == "1.0.0"

    def test_packet_artifact_records_source_mode(self, session: Session) -> None:
        from casegraph_agent_sdk.reviewed_release import CreateReleaseBundleRequest

        case, snapshot_id = _prepare_signed_off_case(session)
        service = ReviewedReleaseService(session)
        resp = asyncio.run(
            service.create_release(
                case.case_id,
                CreateReleaseBundleRequest(
                    operator_id="op1",
                    generate_packet=True,
                    generate_communication_draft=False,
                ),
            )
        )
        packet_artifacts = [a for a in resp.release.artifacts if a.artifact_type == "reviewed_packet"]
        assert len(packet_artifacts) == 1
        assert packet_artifacts[0].source_mode == "reviewed_snapshot"
        assert packet_artifacts[0].source_snapshot_id == snapshot_id


class TestReleaseSkippedArtifacts:
    def test_submission_draft_skipped_without_packet(self, session: Session) -> None:
        from casegraph_agent_sdk.reviewed_release import CreateReleaseBundleRequest

        case, _ = _prepare_signed_off_case(session)
        service = ReviewedReleaseService(session)
        resp = asyncio.run(
            service.create_release(
                case.case_id,
                CreateReleaseBundleRequest(
                    operator_id="op1",
                    generate_packet=False,
                    generate_submission_draft=True,
                ),
            )
        )
        sub_artifacts = [a for a in resp.release.artifacts if a.artifact_type == "reviewed_submission_draft"]
        assert len(sub_artifacts) == 1
        assert sub_artifacts[0].status == "skipped_missing_data"

    def test_communication_draft_skipped_without_packet(self, session: Session) -> None:
        from casegraph_agent_sdk.reviewed_release import CreateReleaseBundleRequest

        case, _ = _prepare_signed_off_case(session)
        service = ReviewedReleaseService(session)
        resp = asyncio.run(
            service.create_release(
                case.case_id,
                CreateReleaseBundleRequest(
                    operator_id="op1",
                    generate_packet=False,
                    generate_communication_draft=True,
                ),
            )
        )
        comm_artifacts = [a for a in resp.release.artifacts if a.artifact_type == "reviewed_communication_draft"]
        assert len(comm_artifacts) == 1
        assert comm_artifacts[0].status == "skipped_missing_data"


# ---------------------------------------------------------------------------
# Integration tests via FastAPI TestClient
# ---------------------------------------------------------------------------

from sqlalchemy.pool import StaticPool


class TestReleaseEndpoints:
    @pytest.fixture()
    def client(self) -> TestClient:
        # Import all models
        import app.audit.models  # noqa: F401
        import app.cases.models  # noqa: F401
        import app.ingestion.models  # noqa: F401
        import app.review.models  # noqa: F401
        import app.extraction.models  # noqa: F401
        import app.tasks.models  # noqa: F401
        import app.readiness.models  # noqa: F401
        import app.operator_review.models  # noqa: F401
        import app.packets.models  # noqa: F401
        import app.submissions.models  # noqa: F401
        import app.communications.models  # noqa: F401
        import app.execution.models  # noqa: F401
        import app.workflow_packs.models  # noqa: F401
        import app.human_validation.models  # noqa: F401
        import app.reviewed_handoff.models  # noqa: F401
        import app.reviewed_release.models  # noqa: F401

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
        app.include_router(reviewed_release_router)
        app.dependency_overrides[get_session] = override_session

        with Session(engine) as seed:
            case, snapshot_id = _prepare_signed_off_case(seed)
            case_id = case.case_id
            seed.commit()

        with TestClient(app) as client:
            client.case_id = case_id  # type: ignore[attr-defined]
            yield client

    def test_list_releases_empty(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]
        resp = client.get(f"/cases/{case_id}/releases")
        assert resp.status_code == 200
        data = resp.json()
        assert data["releases"] == []

    def test_create_release_via_api(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]
        resp = client.post(
            f"/cases/{case_id}/releases",
            json={
                "operator_id": "api-operator",
                "note": "API release test",
                "generate_packet": True,
                "generate_communication_draft": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["success"] is True
        assert data["release"]["status"] in ("created", "incomplete")

    def test_get_release_via_api(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]
        create_resp = client.post(
            f"/cases/{case_id}/releases",
            json={"operator_id": "api-op", "generate_packet": True, "generate_communication_draft": False},
        )
        release_id = create_resp.json()["release"]["release_id"]

        get_resp = client.get(f"/releases/{release_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["release"]["release_id"] == release_id

    def test_get_release_artifacts_via_api(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]
        create_resp = client.post(
            f"/cases/{case_id}/releases",
            json={"operator_id": "api-op", "generate_packet": True, "generate_communication_draft": False},
        )
        release_id = create_resp.json()["release"]["release_id"]

        art_resp = client.get(f"/releases/{release_id}/artifacts")
        assert art_resp.status_code == 200
        assert art_resp.json()["release_id"] == release_id

    def test_release_eligibility_via_api(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]
        resp = client.get(f"/cases/{case_id}/release-eligibility")
        assert resp.status_code == 200
        assert resp.json()["eligibility"]["eligible"] is True

    def test_release_not_found(self, client: TestClient) -> None:
        resp = client.get("/releases/nonexistent-release-id")
        assert resp.status_code == 404

    def test_create_release_case_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/cases/nonexistent/releases",
            json={"operator_id": "op1", "generate_communication_draft": False},
        )
        assert resp.status_code == 404
