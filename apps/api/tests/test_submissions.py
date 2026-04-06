"""Tests for submission drafting and dry-run automation planning."""

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
from casegraph_agent_sdk.submissions import (
    CreateSubmissionDraftRequest,
    GenerateAutomationPlanRequest,
    UpdateSubmissionApprovalRequest,
)
from casegraph_agent_sdk.target_packs import CaseTargetPackSelection

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel
from app.extraction.models import ExtractionRunModel
from app.ingestion.models import DocumentRecord
from app.packets.service import PacketAssemblyService
from app.persistence.database import get_session
from app.submissions import router as submissions_router_module
from app.submissions.errors import SubmissionDraftServiceError
from app.submissions.models import SubmissionDraftModel
from app.submissions.router import router as submissions_router
from app.submissions.service import SubmissionDraftService
from app.target_packs.context import build_case_target_pack_selection, set_case_target_pack_selection
from app.target_packs.packs import target_pack_registry


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
        limitations=["Execution is not wired."],
    )


async def _automation_caps_empty() -> AutomationCapabilitiesResponse:
    return AutomationCapabilitiesResponse()


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _create_case(
    session: Session,
    *,
    domain_pack_id: str | None = None,
    case_type_id: str | None = None,
) -> CaseRecordModel:
    case = CaseRecordModel(
        case_id=str(uuid4()),
        title="Submission Draft Case",
        category="operations",
        status="open",
        summary="Case summary text",
        current_stage="document_review",
        domain_pack_id=domain_pack_id,
        case_type_id=case_type_id,
        jurisdiction="us" if domain_pack_id else None,
        domain_category="medical" if domain_pack_id else None,
        case_metadata_json={
            "external_reference": "REF-123",
            "priority": "normal",
        },
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _add_document(
    session: Session,
    *,
    case_id: str,
    filename: str = "submission.pdf",
) -> DocumentRecord:
    document = DocumentRecord(
        document_id=str(uuid4()),
        filename=filename,
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


def _add_extraction(
    session: Session,
    *,
    case_id: str,
    document_id: str,
    template_id: str = "contact_info",
    fields: list[ExtractedFieldResult] | None = None,
) -> ExtractionRunModel:
    values = fields or []
    extraction = ExtractionRunModel(
        extraction_id=str(uuid4()),
        document_id=document_id,
        template_id=template_id,
        case_id=case_id,
        strategy_used="provider_structured",
        provider="openai",
        model_id="gpt-4.1",
        status="completed",
        field_count=len(values),
        fields_extracted=sum(1 for field in values if field.is_present),
        grounding_available=False,
        fields_json=[field.model_dump(mode="json") for field in values],
    )
    session.add(extraction)
    session.commit()
    return extraction


def _create_packet(session: Session, case_id: str, *, note: str = "") -> str:
    packet = PacketAssemblyService(session).generate_packet(case_id, note=note)
    assert packet.packet is not None
    return packet.packet.packet_id


class TestSubmissionDraftService:
    def test_list_targets_returns_registry_profiles(self, session: Session) -> None:
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )

        response = service.list_targets()
        ids = {target.target_id for target in response.targets}
        assert ids == {
            "portal_submission",
            "insurer_portal_placeholder",
            "tax_portal_placeholder",
            "form_packet_export",
            "internal_handoff_packet",
        }

    def test_create_draft_from_packet_and_case_state(self, session: Session) -> None:
        case = _create_case(session)
        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )

        response = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(
                packet_id=packet_id,
                submission_target_id="portal_submission",
                note="Initial draft",
            ),
        )

        assert response.draft.case_id == case.case_id
        assert response.draft.packet_id == packet_id
        assert response.draft.status == "awaiting_operator_review"
        assert response.approval.approval_status == "awaiting_operator_review"
        assert response.draft.mapping_count == len(response.mappings)

    def test_create_draft_maps_case_and_extraction_values(self, session: Session) -> None:
        case = _create_case(session)
        document = _add_document(session, case_id=case.case_id)
        _add_extraction(
            session,
            case_id=case.case_id,
            document_id=document.document_id,
            fields=[
                ExtractedFieldResult(
                    field_id="full_name",
                    field_type="string",
                    value="Jane Doe",
                    is_present=True,
                ),
                ExtractedFieldResult(
                    field_id="email",
                    field_type="string",
                    value="jane@example.com",
                    is_present=True,
                ),
            ],
        )
        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )

        response = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(
                packet_id=packet_id,
                submission_target_id="portal_submission",
            ),
        )

        mappings = {mapping.target_field.field_name: mapping for mapping in response.mappings}
        assert mappings["full_name"].status == "mapped_preview"
        assert mappings["full_name"].value_preview is not None
        assert mappings["full_name"].value_preview.text_value == "Jane Doe"
        assert mappings["full_name"].source_reference is not None
        assert mappings["full_name"].source_reference.source_path == "extraction.full_name"
        assert mappings["email"].value_preview is not None
        assert mappings["email"].value_preview.text_value == "jane@example.com"

    def test_create_draft_carries_selected_target_pack_context(self, session: Session) -> None:
        case = _create_case(
            session,
            domain_pack_id="medical_insurance_us",
            case_type_id="medical_insurance_us:prior_auth_review",
        )
        pack = target_pack_registry.get("generic_prior_auth_packet_v1")
        assert pack is not None
        case.case_metadata_json = set_case_target_pack_selection(
            case.case_metadata_json,
            build_case_target_pack_selection(pack, selected_at="2024-01-02T03:04:05Z"),
        )
        session.add(case)
        session.commit()

        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )

        response = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(
                packet_id=packet_id,
                submission_target_id="portal_submission",
            ),
        )

        assert response.source_metadata.target_pack_selection is not None
        assert response.source_metadata.target_pack_selection.pack_id == "generic_prior_auth_packet_v1"
        assert response.draft.target_pack_selection is not None
        assert response.draft.target_pack_selection.pack_id == "generic_prior_auth_packet_v1"
        field_names = {field.field_name for field in response.target.default_target_fields}
        assert "requester_name" in field_names
        assert "supporting_documents" in field_names

    def test_get_draft_restores_target_field_hints_from_registry(self, session: Session) -> None:
        case = _create_case(session)
        packet_id = _create_packet(session, case.case_id, note="Packet note differs from case summary")
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )

        created = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(
                packet_id=packet_id,
                submission_target_id="portal_submission",
            ),
        )
        detail = service.get_draft(created.draft.draft_id)

        mappings = {mapping.target_field.field_name: mapping for mapping in detail.mappings}
        case_summary = mappings["case_summary"]
        assert case_summary.target_field.candidate_source_paths == [
            "case.summary",
            "packet.note",
            "packet.case_summary.summary",
        ]
        assert case_summary.target_field.notes == [
            "Preview only. No narrative generation is added in this step.",
        ]

    def test_generate_plan_preserves_candidate_warning_notes(self, session: Session) -> None:
        case = _create_case(session)
        packet_id = _create_packet(session, case.case_id, note="Packet note differs from case summary")
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )
        draft = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(packet_id=packet_id, submission_target_id="portal_submission"),
        )

        plan_response = asyncio.run(service.generate_plan(draft.draft.draft_id, GenerateAutomationPlanRequest()))
        case_summary_step = next(
            step for step in plan_response.plan.steps if step.target_reference == "case_context.case_summary"
        )

        assert any("candidate sources matched" in note for note in case_summary_step.notes)

    def test_generate_plan_includes_target_pack_automation_metadata(self, session: Session) -> None:
        case = _create_case(
            session,
            domain_pack_id="medical_insurance_us",
            case_type_id="medical_insurance_us:prior_auth_review",
        )
        pack = target_pack_registry.get("generic_prior_auth_packet_v1")
        assert pack is not None
        case.case_metadata_json = set_case_target_pack_selection(
            case.case_metadata_json,
            build_case_target_pack_selection(pack, selected_at="2024-01-02T03:04:05Z"),
        )
        session.add(case)
        session.commit()

        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )
        draft = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(
                packet_id=packet_id,
                submission_target_id="portal_submission",
            ),
        )

        plan_response = asyncio.run(
            service.generate_plan(draft.draft.draft_id, GenerateAutomationPlanRequest())
        )

        assert plan_response.plan.target_pack_selection is not None
        assert plan_response.plan.target_pack_selection.pack_id == "generic_prior_auth_packet_v1"
        assert plan_response.plan.target_pack_automation_compatibility is not None
        assert plan_response.plan.target_pack_automation_compatibility.supported_backend_ids == [
            "playwright_mcp"
        ]

    def test_create_draft_warns_when_selected_target_pack_version_mismatches(self, session: Session) -> None:
        case = _create_case(
            session,
            domain_pack_id="medical_insurance_us",
            case_type_id="medical_insurance_us:prior_auth_review",
        )
        case.case_metadata_json = set_case_target_pack_selection(
            case.case_metadata_json,
            CaseTargetPackSelection(
                pack_id="generic_prior_auth_packet_v1",
                version="9.9.9",
                display_name="Generic Prior Authorization Packet",
                category="payer_prior_auth_pack",
                selected_at="2024-01-02T03:04:05Z",
            ),
        )
        session.add(case)
        session.commit()

        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )

        response = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(
                packet_id=packet_id,
                submission_target_id="portal_submission",
            ),
        )

        assert any(
            issue.code == "selected_target_pack_version_mismatch"
            for issue in response.result.issues
        )
        field_names = {field.field_name for field in response.target.default_target_fields}
        assert "requester_name" not in field_names
        assert response.source_metadata.target_pack_selection is not None
        assert response.source_metadata.target_pack_selection.version == "9.9.9"

        plan_response = asyncio.run(
            service.generate_plan(response.draft.draft_id, GenerateAutomationPlanRequest())
        )

        assert plan_response.plan.target_pack_selection is not None
        assert plan_response.plan.target_pack_selection.version == "9.9.9"
        assert plan_response.plan.target_pack_automation_compatibility is None

    def test_create_draft_blocks_incompatible_target_profile(self, session: Session) -> None:
        case = _create_case(session)
        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )

        response = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(
                packet_id=packet_id,
                submission_target_id="insurer_portal_placeholder",
            ),
        )

        assert response.draft.status == "blocked"
        assert any(issue.code == "missing_domain_pack_context" for issue in response.result.issues)

    def test_create_draft_supersedes_previous_same_target_and_packet(self, session: Session) -> None:
        case = _create_case(session)
        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )

        first = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(
                packet_id=packet_id,
                submission_target_id="portal_submission",
            ),
        )
        second = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(
                packet_id=packet_id,
                submission_target_id="portal_submission",
            ),
        )

        first_record = session.get(SubmissionDraftModel, first.draft.draft_id)
        assert first_record is not None
        assert first_record.status == "superseded_placeholder"
        assert second.draft.status == "awaiting_operator_review"

    def test_list_drafts_orders_latest_first(self, session: Session) -> None:
        case = _create_case(session)
        packet_1 = _create_packet(session, case.case_id, note="Packet one")
        packet_2 = _create_packet(session, case.case_id, note="Packet two")
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )
        service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(packet_id=packet_1, submission_target_id="portal_submission", note="First"),
        )
        latest = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(packet_id=packet_2, submission_target_id="portal_submission", note="Second"),
        )

        drafts = service.list_drafts(case.case_id)
        assert drafts.drafts[0].draft_id == latest.draft.draft_id
        assert len(drafts.drafts) == 2

    def test_generate_plan_includes_attachment_and_blocked_submit_steps(self, session: Session) -> None:
        case = _create_case(session)
        _add_document(session, case_id=case.case_id, filename="claim.pdf")
        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )
        draft = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(packet_id=packet_id, submission_target_id="portal_submission"),
        )

        plan_response = asyncio.run(service.generate_plan(draft.draft.draft_id, GenerateAutomationPlanRequest()))
        step_types = [step.step_type for step in plan_response.plan.steps]

        assert plan_response.plan.status == "awaiting_operator_review"
        assert "attach_document_placeholder" in step_types
        assert step_types[-1] == "submit_blocked_placeholder"
        assert plan_response.plan.steps[-1].status == "blocked"
        open_step = next(step for step in plan_response.plan.steps if step.step_type == "open_target")
        assert open_step.tool_id == "playwright.navigate"

    def test_generate_plan_is_partial_without_browser_metadata(self, session: Session) -> None:
        case = _create_case(session)
        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_empty,
        )
        draft = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(packet_id=packet_id, submission_target_id="portal_submission"),
        )

        plan_response = asyncio.run(service.generate_plan(draft.draft.draft_id, GenerateAutomationPlanRequest()))
        codes = {issue.code for issue in plan_response.result.issues}

        assert plan_response.plan.status == "partial"
        assert "browser_tool_metadata_missing" in codes
        assert "browser_backend_missing" in codes

    def test_get_plan_raises_when_missing(self, session: Session) -> None:
        case = _create_case(session)
        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )
        draft = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(packet_id=packet_id, submission_target_id="portal_submission"),
        )

        with pytest.raises(SubmissionDraftServiceError, match="Automation plan not found"):
            service.get_plan(draft.draft.draft_id)

    def test_update_approval_requires_generated_plan(self, session: Session) -> None:
        case = _create_case(session)
        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )
        draft = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(packet_id=packet_id, submission_target_id="portal_submission"),
        )

        with pytest.raises(SubmissionDraftServiceError, match="Generate a dry-run automation plan"):
            service.update_approval(
                draft.draft.draft_id,
                UpdateSubmissionApprovalRequest(
                    approval_status="approved_for_future_execution",
                    approved_by="operator@example.com",
                ),
            )

    def test_update_approval_awaiting_review_clears_approved_fields(self, session: Session) -> None:
        case = _create_case(session)
        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )
        draft = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(packet_id=packet_id, submission_target_id="portal_submission"),
        )

        approval = service.update_approval(
            draft.draft.draft_id,
            UpdateSubmissionApprovalRequest(
                approval_status="awaiting_operator_review",
                approved_by="operator@example.com",
                approval_note="Needs more manual review.",
            ),
        )

        assert approval.approval.approval_status == "awaiting_operator_review"
        assert approval.approval.approved_by == ""
        assert approval.approval.approved_at == ""
        assert approval.draft.status == "awaiting_operator_review"

    def test_update_approval_marks_draft_and_plan_approved(self, session: Session) -> None:
        case = _create_case(session)
        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )
        draft = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(packet_id=packet_id, submission_target_id="portal_submission"),
        )
        asyncio.run(service.generate_plan(draft.draft.draft_id, GenerateAutomationPlanRequest()))

        approval = service.update_approval(
            draft.draft.draft_id,
            UpdateSubmissionApprovalRequest(
                approval_status="approved_for_future_execution",
                approved_by="operator@example.com",
                approval_note="Ready for future controlled execution.",
            ),
        )

        assert approval.draft.status == "approved_for_future_execution"
        assert approval.approval.approval_status == "approved_for_future_execution"
        plan = service.get_plan(draft.draft.draft_id)
        assert plan.plan.status == "approved_for_future_execution"

    def test_rejected_approval_blocks_draft_and_plan(self, session: Session) -> None:
        case = _create_case(session)
        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )
        draft = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(packet_id=packet_id, submission_target_id="portal_submission"),
        )
        asyncio.run(service.generate_plan(draft.draft.draft_id, GenerateAutomationPlanRequest()))

        approval = service.update_approval(
            draft.draft.draft_id,
            UpdateSubmissionApprovalRequest(
                approval_status="rejected",
                approved_by="operator@example.com",
                approval_note="Do not proceed with this draft.",
            ),
        )

        assert approval.draft.status == "blocked"
        assert approval.approval.approval_status == "rejected"
        plan = service.get_plan(draft.draft.draft_id)
        assert plan.plan.status == "blocked"

    def test_generate_plan_rejects_non_dry_run_requests(self, session: Session) -> None:
        case = _create_case(session)
        packet_id = _create_packet(session, case.case_id)
        service = SubmissionDraftService(
            session,
            automation_capabilities_loader=_automation_caps_with_browser,
        )
        draft = service.create_draft(
            case.case_id,
            CreateSubmissionDraftRequest(packet_id=packet_id, submission_target_id="portal_submission"),
        )

        with pytest.raises(SubmissionDraftServiceError, match="Only dry-run automation planning"):
            asyncio.run(
                service.generate_plan(
                    draft.draft.draft_id,
                    GenerateAutomationPlanRequest(dry_run=False),
                )
            )


class _FakeAutomationService:
    async def get_capabilities(self) -> AutomationCapabilitiesResponse:
        return await _automation_caps_with_browser()


class TestSubmissionDraftAPI:
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
        app.include_router(submissions_router)
        app.dependency_overrides[get_session] = override_session

        original_automation_service = submissions_router_module._automation_service
        submissions_router_module._automation_service = _FakeAutomationService()

        with Session(engine) as seed:
            case = _create_case(seed)
            _add_document(seed, case_id=case.case_id, filename="api-doc.pdf")
            packet_id = _create_packet(seed, case.case_id)
            case_id = case.case_id
            seed.commit()

        try:
            with TestClient(app) as client:
                client.case_id = case_id  # type: ignore[attr-defined]
                client.packet_id = packet_id  # type: ignore[attr-defined]
                yield client
        finally:
            submissions_router_module._automation_service = original_automation_service

    def test_list_targets(self, client: TestClient) -> None:
        response = client.get("/submission/targets")
        assert response.status_code == 200
        ids = {target["target_id"] for target in response.json()["targets"]}
        assert "portal_submission" in ids
        assert "internal_handoff_packet" in ids

    def test_create_and_list_drafts(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]
        packet_id = client.packet_id  # type: ignore[attr-defined]

        create = client.post(
            f"/cases/{case_id}/submission-drafts",
            json={
                "packet_id": packet_id,
                "submission_target_id": "portal_submission",
            },
        )
        assert create.status_code == 200
        assert create.json()["draft"]["case_id"] == case_id

        drafts = client.get(f"/cases/{case_id}/submission-drafts")
        assert drafts.status_code == 200
        assert len(drafts.json()["drafts"]) == 1

    def test_get_detail_and_plan(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]
        packet_id = client.packet_id  # type: ignore[attr-defined]

        create = client.post(
            f"/cases/{case_id}/submission-drafts",
            json={
                "packet_id": packet_id,
                "submission_target_id": "portal_submission",
            },
        )
        draft_id = create.json()["draft"]["draft_id"]

        detail = client.get(f"/submission-drafts/{draft_id}")
        assert detail.status_code == 200
        assert detail.json()["draft"]["draft_id"] == draft_id

        plan = client.post(f"/submission-drafts/{draft_id}/plan", json={"dry_run": True})
        assert plan.status_code == 200
        assert plan.json()["plan"]["draft_id"] == draft_id

        get_plan = client.get(f"/submission-drafts/{draft_id}/plan")
        assert get_plan.status_code == 200
        assert get_plan.json()["plan"]["status"] in {"awaiting_operator_review", "partial"}

    def test_patch_approval(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]
        packet_id = client.packet_id  # type: ignore[attr-defined]

        create = client.post(
            f"/cases/{case_id}/submission-drafts",
            json={
                "packet_id": packet_id,
                "submission_target_id": "portal_submission",
            },
        )
        draft_id = create.json()["draft"]["draft_id"]
        client.post(f"/submission-drafts/{draft_id}/plan", json={"dry_run": True})

        approval = client.patch(
            f"/submission-drafts/{draft_id}/approval",
            json={
                "approval_status": "approved_for_future_execution",
                "approved_by": "operator@example.com",
                "approval_note": "Reviewed.",
            },
        )
        assert approval.status_code == 200
        assert approval.json()["draft"]["status"] == "approved_for_future_execution"

    def test_create_draft_404_for_missing_case(self, client: TestClient) -> None:
        packet_id = client.packet_id  # type: ignore[attr-defined]
        response = client.post(
            "/cases/missing/submission-drafts",
            json={
                "packet_id": packet_id,
                "submission_target_id": "portal_submission",
            },
        )
        assert response.status_code == 404