"""Tests for the auditability foundation."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.automation import AutomationCapabilitiesResponse
from casegraph_agent_sdk.cases import CreateCaseRequest, LinkCaseDocumentRequest, UpdateCaseRequest
from casegraph_agent_sdk.communications import CommunicationDraftGenerateRequest
from casegraph_agent_sdk.execution import AutomationExecutionRequest, SkipCheckpointRequest
from casegraph_agent_sdk.extraction import ExtractionRequest
from casegraph_agent_sdk.operator_review import CreateReviewNoteRequest, UpdateCaseStageRequest
from casegraph_agent_sdk.submissions import CreateSubmissionDraftRequest, UpdateSubmissionApprovalRequest
from casegraph_agent_sdk.tasks import FinishReason, StructuredOutputResult, TaskExecutionResult

from app.audit.router import router as audit_router
from app.audit.service import AuditTrailService
from app.cases.service import CaseService
from app.communications.service import CommunicationDraftService
from app.execution.service import AutomationExecutionService
from app.extraction.service import ExtractionService
from app.ingestion.models import DocumentRecord
from app.operator_review.actions import ActionItemService
from app.operator_review.lifecycle import CaseLifecycleService
from app.packets.service import PacketAssemblyService
from app.persistence.database import get_session
from app.readiness.service import ReadinessService
from app.review.models import PageRecord
from app.submissions.service import SubmissionDraftService


async def _empty_automation_capabilities() -> AutomationCapabilitiesResponse:
    return AutomationCapabilitiesResponse()


class _FakeTaskExecutionService:
    async def execute_prepared_prompt(self, **_: Any) -> tuple[TaskExecutionResult, list[Any]]:
        return (
            TaskExecutionResult(
                task_id="extraction:contact_info",
                provider="openai",
                model_id="gpt-4o-mini",
                finish_reason=FinishReason.COMPLETED,
                output_text=(
                    '{"full_name": "John Doe", "email": "john.doe@example.com", '
                    '"phone": "555-0123", "address": null, "organization": null}'
                ),
                structured_output=StructuredOutputResult(
                    parsed={
                        "full_name": "John Doe",
                        "email": "john.doe@example.com",
                        "phone": "555-0123",
                        "address": None,
                        "organization": None,
                    },
                    raw_text='{"full_name": "John Doe"}',
                    schema_valid=True,
                    validation_errors=[],
                ),
                duration_ms=42,
            ),
            [],
        )


def _create_case(session: Session, *, title: str = "Audit Test Case"):
    return asyncio.run(
        CaseService(session).create_case(
            CreateCaseRequest(
                title=title,
                category="medical_insurance",
                summary="Case used to verify audit traceability.",
                metadata={"priority": "normal", "external_reference": "AUD-001"},
                domain_pack_id="medical_insurance_us",
                case_type_id="medical_insurance_us:prior_auth_review",
            )
        )
    )


def _add_document(session: Session, *, filename: str = "supporting.pdf") -> DocumentRecord:
    document = DocumentRecord(
        document_id=str(uuid4()),
        filename=filename,
        content_type="application/pdf",
        extension=".pdf",
        size_bytes=2048,
        sha256=uuid4().hex,
        classification="pdf",
        requested_mode="auto",
        resolved_mode="readable_pdf",
        processing_status="completed",
        extractor_name="pymupdf-readable-pdf",
        page_count=1,
        text_block_count=1,
        geometry_present=False,
        geometry_sources_json=["pdf_text"],
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def _add_page(session: Session, *, document_id: str, text: str) -> None:
    session.add(
        PageRecord(
            page_id=f"{document_id}:1",
            document_id=document_id,
            page_number=1,
            width=612.0,
            height=792.0,
            coordinate_space="pdf_points",
            geometry_source="pdf_text",
            text=text,
            text_blocks_json=[],
            has_page_image=False,
        )
    )
    session.commit()


def _link_document(session: Session, *, case_id: str, document_id: str) -> None:
    CaseService(session).link_document(
        case_id,
        LinkCaseDocumentRequest(document_id=document_id),
    )


def _build_client(session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(audit_router)

    def _get_session() -> Session:
        return session

    app.dependency_overrides[get_session] = _get_session
    return TestClient(app)


def test_audit_records_case_readiness_and_review_activity(session: Session) -> None:
    case = _create_case(session, title="Audit Timeline Case")
    document = _add_document(session, filename="timeline-source.pdf")

    asyncio.run(
        CaseService(session).update_case(
            case.case_id,
            UpdateCaseRequest(
                summary="Updated summary for audit verification.",
                metadata={"priority": "high", "external_reference": "AUD-002"},
            ),
        )
    )
    _link_document(session, case_id=case.case_id, document_id=document.document_id)

    readiness = ReadinessService(session)
    checklist = readiness.generate_checklist(case.case_id)
    readiness.evaluate(case.case_id)

    CaseLifecycleService(session).transition_stage(
        case.case_id,
        UpdateCaseStageRequest(
            new_stage="document_review",
            reason="Initial audit review.",
            note="Documents are ready for review.",
        ),
    )
    ActionItemService(session).create_review_note(
        case.case_id,
        CreateReviewNoteRequest(
            body="Operator identified one remaining supporting document gap.",
            decision="follow_up_required",
        ),
    )

    audit = AuditTrailService(session)
    timeline = audit.get_case_timeline(case.case_id)
    decisions = audit.get_case_decisions(case.case_id)
    lineage = audit.get_case_lineage(case.case_id)

    event_types = {event.event_type for event in timeline.events}
    assert {
        "case_created",
        "case_updated",
        "case_document_linked",
        "checklist_generated",
        "checklist_evaluated",
        "case_stage_transitioned",
        "review_note_added",
    }.issubset(event_types)

    decision_types = {decision.decision_type for decision in decisions.decisions}
    assert {"checklist_evaluated", "stage_transition", "review_note_added"}.issubset(decision_types)

    checklist_record = next(
        record for record in lineage.records if record.artifact.artifact_type == "checklist"
    )
    assert checklist_record.artifact.artifact_id == checklist.checklist.checklist_id
    assert {edge.relationship_type for edge in checklist_record.edges} == {"case_context"}


def test_audit_endpoints_expose_submission_execution_and_communication_traceability(
    session: Session,
) -> None:
    case = _create_case(session, title="Automation Audit Case")
    document = _add_document(session, filename="portal-support.pdf")
    _link_document(session, case_id=case.case_id, document_id=document.document_id)

    readiness = ReadinessService(session)
    readiness.generate_checklist(case.case_id)
    readiness.evaluate(case.case_id)

    packet = PacketAssemblyService(session).generate_packet(case.case_id, note="Packet prepared for audit test.")

    submissions = SubmissionDraftService(
        session,
        automation_capabilities_loader=_empty_automation_capabilities,
    )
    draft = submissions.create_draft(
        case.case_id,
        CreateSubmissionDraftRequest(
            packet_id=packet.packet.packet_id,
            submission_target_id="portal_submission",
            note="Create draft for traceability verification.",
        ),
    )
    assert draft.draft.status == "awaiting_operator_review"

    plan = asyncio.run(submissions.generate_plan(draft.draft.draft_id))
    approval = submissions.update_approval(
        draft.draft.draft_id,
        UpdateSubmissionApprovalRequest(
            approval_status="approved_for_future_execution",
            approved_by="operator@example.com",
            approval_note="Approved for audit coverage.",
        ),
    )
    assert approval.approval.approval_status == "approved_for_future_execution"

    execution = AutomationExecutionService(
        session,
        playwright_mcp_url="http://localhost:19999",
        automation_capabilities_loader=_empty_automation_capabilities,
    )
    run = asyncio.run(
        execution.execute(
            AutomationExecutionRequest(
                draft_id=draft.draft.draft_id,
                plan_id=plan.plan.plan_id,
                operator_id="operator-1",
            )
        )
    )
    checkpoint = execution.get_run_detail(run.run.run_id).checkpoints[0]
    execution.skip_checkpoint(
        run.run.run_id,
        checkpoint.checkpoint_id,
        SkipCheckpointRequest(
            operator_id="operator-1",
            decision_note="Handled manually outside automation.",
            skip_reason="Operator completed the portal transition manually.",
        ),
    )

    communication = asyncio.run(
        CommunicationDraftService(session).generate_draft(
            case.case_id,
            CommunicationDraftGenerateRequest(
                template_id="missing_document_request",
                operator_id="reviewer@example.com",
            ),
        )
    )
    assert communication.draft.template_id == "missing_document_request"

    with _build_client(session) as client:
        audit_response = client.get(f"/cases/{case.case_id}/audit", params={"category": "automation"})
        decisions_response = client.get(f"/cases/{case.case_id}/decisions")
        lineage_response = client.get(f"/cases/{case.case_id}/lineage")
        artifact_response = client.get(f"/artifacts/automation_run/{run.run.run_id}/lineage")

    assert audit_response.status_code == 200
    assert decisions_response.status_code == 200
    assert lineage_response.status_code == 200
    assert artifact_response.status_code == 200

    audit_payload = audit_response.json()
    assert audit_payload["events"]
    assert {event["category"] for event in audit_payload["events"]} == {"automation"}
    assert {
        "automation_plan_generated",
        "automation_run_created",
        "automation_checkpoint_decided",
    }.issubset({event["event_type"] for event in audit_payload["events"]})
    assert "communication" in audit_payload["filters"]["categories"]

    decision_types = {decision["decision_type"] for decision in decisions_response.json()["decisions"]}
    assert {
        "packet_generated",
        "automation_plan_generated",
        "draft_approval_updated",
        "checkpoint_skipped",
        "communication_draft_generated",
    }.issubset(decision_types)

    lineage_types = {
        record["artifact"]["artifact_type"] for record in lineage_response.json()["records"]
    }
    assert {
        "packet",
        "submission_draft",
        "automation_plan",
        "automation_run",
        "communication_draft",
    }.issubset(lineage_types)

    artifact_payload = artifact_response.json()["record"]
    assert artifact_payload["artifact"]["artifact_type"] == "automation_run"
    assert {
        edge["source"]["artifact_type"] for edge in artifact_payload["edges"]
    } == {"case", "submission_draft", "automation_plan", "packet"}


def test_extraction_audit_records_document_lineage(session: Session) -> None:
    case = _create_case(session, title="Extraction Audit Case")
    document = _add_document(session, filename="extraction-source.pdf")
    _add_page(
        session,
        document_id=document.document_id,
        text="John Doe\njohn.doe@example.com\n555-0123",
    )
    _link_document(session, case_id=case.case_id, document_id=document.document_id)

    result = asyncio.run(
        ExtractionService(
            session,
            task_execution_service=_FakeTaskExecutionService(),
        ).execute(
            ExtractionRequest(
                document_id=document.document_id,
                case_id=case.case_id,
                template_id="contact_info",
                strategy="provider_structured",
                provider="openai",
                model_id="gpt-4o-mini",
                api_key="test-key",
            )
        )
    )

    audit = AuditTrailService(session)
    timeline = audit.get_case_timeline(case.case_id, category="extraction")
    artifact_lineage = audit.get_artifact_lineage("extraction_run", result.run.extraction_id)

    assert {event.event_type for event in timeline.events} == {"extraction_completed"}
    assert artifact_lineage.record is not None
    assert artifact_lineage.record.artifact.artifact_type == "extraction_run"
    assert {
        edge.relationship_type for edge in artifact_lineage.record.edges
    } == {"case_context", "document_source"}


@pytest.fixture()
def session() -> Session:
    import app.audit.models  # noqa: F401
    import app.cases.models  # noqa: F401
    import app.communications.models  # noqa: F401
    import app.execution.models  # noqa: F401
    import app.extraction.models  # noqa: F401
    import app.ingestion.models  # noqa: F401
    import app.operator_review.models  # noqa: F401
    import app.packets.models  # noqa: F401
    import app.readiness.models  # noqa: F401
    import app.review.models  # noqa: F401
    import app.submissions.models  # noqa: F401
    import app.tasks.models  # noqa: F401
    import app.workflow_packs.models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session