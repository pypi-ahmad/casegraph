"""Tests for the reviewed handoff foundation."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.automation import (
    AutomationBackend,
    AutomationCapabilitiesResponse,
    ToolCapabilityFlags,
    ToolMetadata,
)
from casegraph_agent_sdk.extraction import ExtractedFieldResult
from casegraph_agent_sdk.human_validation import ReviewRequirementRequest, ValidateFieldRequest
from casegraph_agent_sdk.reviewed_handoff import (
    CreateReviewedSnapshotRequest,
    SignOffReviewedSnapshotRequest,
)
from casegraph_agent_sdk.submissions import CreateSubmissionDraftRequest, GenerateAutomationPlanRequest

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel
from app.extraction.models import ExtractionRunModel
from app.human_validation.service import HumanValidationService
from app.ingestion.models import DocumentRecord
from app.packets.errors import PacketServiceError
from app.packets.service import PacketAssemblyService
from app.persistence.database import get_session
from app.readiness.models import ChecklistItemModel, ChecklistModel
from app.reviewed_handoff.router import router as reviewed_handoff_router
from app.reviewed_handoff.service import ReviewedHandoffService, ReviewedHandoffServiceError
from app.submissions.service import SubmissionDraftService


async def _automation_caps_with_browser() -> AutomationCapabilitiesResponse:
    return AutomationCapabilitiesResponse(
        tools=[
            ToolMetadata(
                id="playwright.navigate",
                version="0.1.0",
                display_name="Playwright Navigate",
                description="Navigate to a URL.",
                category="browser_automation",
                safety_level="read_only",
                implementation_status="adapter_only",
                capability_flags=ToolCapabilityFlags(
                    read_only=True,
                    requires_approval=False,
                    requires_browser_session=True,
                    requires_computer_use_provider=False,
                ),
            )
        ],
        backends=[
            AutomationBackend(
                id="playwright_mcp",
                display_name="Playwright MCP",
                status="adapter_only",
                notes=["Configured locally."],
            )
        ],
    )


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _create_case(session: Session) -> CaseRecordModel:
    case = CaseRecordModel(
        case_id=str(uuid4()),
        title="Reviewed Handoff Case",
        category="operations",
        status="open",
        summary="Reviewed handoff test case",
        current_stage="document_review",
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _add_document(session: Session, *, case_id: str) -> DocumentRecord:
    document = DocumentRecord(
        document_id=str(uuid4()),
        filename="handoff-source.pdf",
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
            value="REF-100",
            raw_value="REF-100",
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
        document_category="authorization",
        priority="required",
        status="missing",
    )
    session.add(checklist)
    session.add(item)
    session.commit()
    return item


def _prepare_reviewed_case(session: Session) -> tuple[CaseRecordModel, ExtractionRunModel, ChecklistItemModel]:
    case = _create_case(session)
    document = _add_document(session, case_id=case.case_id)
    extraction = _add_extraction(session, case_id=case.case_id, document_id=document.document_id)
    checklist_item = _create_checklist(session, case_id=case.case_id)

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
        checklist_item.item_id,
        ReviewRequirementRequest(
            status="confirmed_supported",
            reviewer_id="reviewer-1",
            note="Confirmed by operator review.",
        ),
    )
    return case, extraction, checklist_item


class TestReviewedHandoffService:
    def test_create_snapshot_blocks_handoff_until_signoff(self, session: Session) -> None:
        case, extraction, checklist_item = _prepare_reviewed_case(session)
        service = ReviewedHandoffService(session)

        response = service.create_snapshot(
            case.case_id,
            CreateReviewedSnapshotRequest(
                note="Initial reviewed snapshot",
                operator_id="reviewer-1",
            ),
        )

        snapshot = response.snapshot
        assert snapshot.case_id == case.case_id
        assert snapshot.signoff_status == "not_signed_off"
        assert snapshot.summary.accepted_fields == 1
        assert snapshot.summary.corrected_fields == 1
        assert snapshot.summary.reviewed_requirements == 1
        assert snapshot.summary.unresolved_item_count == 0
        assert extraction.extraction_id in snapshot.source_metadata.extraction_ids
        assert checklist_item.item_id == snapshot.requirements[0].item_id

        eligibility = service.get_handoff_eligibility(case.case_id)
        assert eligibility.eligibility.eligible is False
        assert eligibility.eligibility.release_gate_status == "blocked_missing_signoff"

    def test_signoff_and_selection_make_snapshot_eligible(self, session: Session) -> None:
        case, _extraction, _item = _prepare_reviewed_case(session)
        service = ReviewedHandoffService(session)
        snapshot = service.create_snapshot(case.case_id, CreateReviewedSnapshotRequest()).snapshot

        signoff = service.signoff_snapshot(
            snapshot.snapshot_id,
            SignOffReviewedSnapshotRequest(
                operator_id="supervisor-1",
                operator_display_name="Supervisor One",
                note="Explicitly reviewed for downstream handoff.",
            ),
        )
        selected = service.select_snapshot(case.case_id, snapshot.snapshot_id)
        eligibility = service.get_handoff_eligibility(case.case_id)

        assert signoff.signoff.status == "signed_off"
        assert selected.snapshot.status == "selected_for_handoff"
        assert eligibility.eligibility.eligible is True
        assert eligibility.eligibility.selected_snapshot_id == snapshot.snapshot_id
        assert eligibility.eligibility.signoff_status == "signed_off"

    def test_selection_requires_current_handoff_eligibility(self, session: Session) -> None:
        case, _extraction, _item = _prepare_reviewed_case(session)
        service = ReviewedHandoffService(session)
        snapshot = service.create_snapshot(case.case_id, CreateReviewedSnapshotRequest()).snapshot

        with pytest.raises(ReviewedHandoffServiceError, match="signed off"):
            service.select_snapshot(case.case_id, snapshot.snapshot_id)

    def test_selecting_same_snapshot_twice_is_idempotent(self, session: Session) -> None:
        case, _extraction, _item = _prepare_reviewed_case(session)
        service = ReviewedHandoffService(session)
        snapshot = service.create_snapshot(case.case_id, CreateReviewedSnapshotRequest()).snapshot
        service.signoff_snapshot(
            snapshot.snapshot_id,
            SignOffReviewedSnapshotRequest(operator_id="supervisor-1"),
        )

        service.select_snapshot(case.case_id, snapshot.snapshot_id)
        repeated = service.select_snapshot(case.case_id, snapshot.snapshot_id)

        assert repeated.result.success is True
        assert repeated.result.message == "Reviewed snapshot is already selected for handoff."
        assert repeated.snapshot.status == "selected_for_handoff"

    def test_eligibility_reports_all_blocking_reasons(self, session: Session) -> None:
        """When multiple handoff conditions fail, all blocking reasons should appear."""
        case = _create_case(session)
        document = _add_document(session, case_id=case.case_id)
        _add_extraction(session, case_id=case.case_id, document_id=document.document_id)
        _create_checklist(session, case_id=case.case_id)

        service = ReviewedHandoffService(session)
        service.create_snapshot(case.case_id, CreateReviewedSnapshotRequest())

        eligibility = service.get_handoff_eligibility(case.case_id)
        blocking_codes = [reason.code for reason in eligibility.eligibility.reasons if reason.blocking]

        assert eligibility.eligibility.eligible is False
        assert "missing_signoff" in blocking_codes
        assert "required_requirement_reviews_incomplete" in blocking_codes
        assert len(blocking_codes) >= 2

    def test_reviewed_snapshot_packet_generation_requires_signoff_and_records_source(self, session: Session) -> None:
        case, _extraction, _item = _prepare_reviewed_case(session)
        handoff = ReviewedHandoffService(session)
        snapshot = handoff.create_snapshot(case.case_id, CreateReviewedSnapshotRequest()).snapshot
        packets = PacketAssemblyService(session)

        with pytest.raises(PacketServiceError, match="signed off"):
            packets.generate_packet(
                case.case_id,
                source_mode="reviewed_snapshot",
                reviewed_snapshot_id=snapshot.snapshot_id,
            )

        handoff.signoff_snapshot(
            snapshot.snapshot_id,
            SignOffReviewedSnapshotRequest(operator_id="supervisor-1"),
        )
        handoff.select_snapshot(case.case_id, snapshot.snapshot_id)

        result = packets.generate_packet(
            case.case_id,
            note="Reviewed handoff packet",
            source_mode="reviewed_snapshot",
            reviewed_snapshot_id=snapshot.snapshot_id,
        )

        assert result.packet is not None
        assert result.packet.source_mode == "reviewed_snapshot"
        assert result.packet.source_reviewed_snapshot_id == snapshot.snapshot_id

        detail = packets.get_packet(result.packet.packet_id)
        assert detail.manifest.source_mode == "reviewed_snapshot"
        assert detail.manifest.source_reviewed_snapshot_id == snapshot.snapshot_id
        assert detail.manifest.source_snapshot_signoff_status == "signed_off"
        reviewed_section = next(
            section for section in detail.manifest.sections if section.section_type == "reviewed_snapshot"
        )
        assert reviewed_section.data["summary"]["corrected_fields"] == 1

    def test_submission_draft_uses_reviewed_snapshot_values_and_propagates_source_mode(self, session: Session) -> None:
        case, _extraction, _item = _prepare_reviewed_case(session)
        handoff = ReviewedHandoffService(session)
        snapshot = handoff.create_snapshot(case.case_id, CreateReviewedSnapshotRequest()).snapshot
        handoff.signoff_snapshot(
            snapshot.snapshot_id,
            SignOffReviewedSnapshotRequest(operator_id="supervisor-1"),
        )
        handoff.select_snapshot(case.case_id, snapshot.snapshot_id)

        packet = PacketAssemblyService(session).generate_packet(
            case.case_id,
            source_mode="reviewed_snapshot",
            reviewed_snapshot_id=snapshot.snapshot_id,
        )
        assert packet.packet is not None

        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )
        draft = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(
                packet_id=packet.packet.packet_id,
                submission_target_id="portal_submission",
            ),
        )

        mappings = {mapping.target_field.field_name: mapping for mapping in draft.mappings}
        assert draft.draft.source_mode == "reviewed_snapshot"
        assert draft.source_metadata.source_mode == "reviewed_snapshot"
        assert draft.source_metadata.source_reviewed_snapshot_id == snapshot.snapshot_id
        assert mappings["full_name"].value_preview is not None
        assert mappings["full_name"].value_preview.text_value == "Jane Reviewed"
        assert mappings["full_name"].source_reference is not None
        assert mappings["full_name"].source_reference.source_entity_type == "reviewed_snapshot"

        plan = asyncio.run(
            service.generate_plan(
                draft.draft.draft_id,
                GenerateAutomationPlanRequest(dry_run=True),
            )
        )
        assert plan.plan.source_mode == "reviewed_snapshot"
        assert plan.plan.source_reviewed_snapshot_id == snapshot.snapshot_id


class TestReviewedHandoffAPI:
    @pytest.fixture()
    def client(self) -> TestClient:
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
        app.include_router(reviewed_handoff_router)
        app.dependency_overrides[get_session] = override_session

        with Session(engine) as seed:
            case, _extraction, _item = _prepare_reviewed_case(seed)
            case_id = case.case_id
            seed.commit()

        with TestClient(app) as client:
            client.case_id = case_id  # type: ignore[attr-defined]
            yield client

    def test_create_signoff_select_and_check_eligibility(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]

        created = client.post(
            f"/cases/{case_id}/reviewed-snapshots",
            json={"operator_id": "reviewer-1", "note": "API snapshot"},
        )
        assert created.status_code == 200
        snapshot_id = created.json()["snapshot"]["snapshot_id"]

        before = client.get(f"/cases/{case_id}/handoff-eligibility")
        assert before.status_code == 200
        assert before.json()["eligibility"]["release_gate_status"] == "blocked_missing_signoff"

        signoff = client.post(
            f"/reviewed-snapshots/{snapshot_id}/signoff",
            json={"operator_id": "supervisor-1", "note": "Signed for handoff"},
        )
        assert signoff.status_code == 200
        assert signoff.json()["signoff"]["status"] == "signed_off"

        selected = client.patch(
            f"/cases/{case_id}/reviewed-snapshots/{snapshot_id}/select-for-handoff"
        )
        assert selected.status_code == 200
        assert selected.json()["snapshot"]["status"] == "selected_for_handoff"

        after = client.get(f"/cases/{case_id}/handoff-eligibility")
        assert after.status_code == 200
        assert after.json()["eligibility"]["eligible"] is True
        assert after.json()["eligibility"]["selected_snapshot_id"] == snapshot_id

        listed = client.get(f"/cases/{case_id}/reviewed-snapshots")
        assert listed.status_code == 200
        assert len(listed.json()["snapshots"]) == 1

    def test_select_requires_snapshot_signoff(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]

        created = client.post(
            f"/cases/{case_id}/reviewed-snapshots",
            json={"operator_id": "reviewer-1", "note": "API snapshot"},
        )
        assert created.status_code == 200
        snapshot_id = created.json()["snapshot"]["snapshot_id"]

        selected = client.patch(
            f"/cases/{case_id}/reviewed-snapshots/{snapshot_id}/select-for-handoff"
        )
        assert selected.status_code == 400
        assert "signed off" in selected.json()["detail"]