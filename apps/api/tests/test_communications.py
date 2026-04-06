"""Tests for the communication draft foundation."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.communications import CommunicationDraftGenerateRequest
from casegraph_agent_sdk.tasks import (
    FinishReason,
    ProviderSelection,
    StructuredOutputResult,
    TaskExecutionError,
    TaskExecutionResult,
)
from casegraph_agent_sdk.workflow_packs import OperatorReviewRecommendation

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel
from app.audit.service import AuditTrailService
from app.communications.errors import CommunicationDraftServiceError
from app.communications.models import CommunicationDraftModel
from app.communications.router import router as communications_router
from app.communications.service import CommunicationDraftService
from app.ingestion.models import DocumentRecord
from app.operator_review.models import ActionItemModel
from app.packets.service import PacketAssemblyService
from app.persistence.database import get_session
from app.readiness.service import ReadinessService
from app.workflow_packs.models import WorkflowPackRunModel


@pytest.fixture()
def session() -> Session:
    import app.cases.models  # noqa: F401
    import app.communications.models  # noqa: F401
    import app.extraction.models  # noqa: F401
    import app.ingestion.models  # noqa: F401
    import app.operator_review.models  # noqa: F401
    import app.packets.models  # noqa: F401
    import app.readiness.models  # noqa: F401
    import app.workflow_packs.models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture()
def client(session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(communications_router)

    def _get_session() -> Session:
        return session

    app.dependency_overrides[get_session] = _get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_case(
    session: Session,
    *,
    title: str = "Communication Draft Case",
    domain_pack_id: str = "medical_insurance_us",
    case_type_id: str = "medical_insurance_us:prior_auth_review",
) -> CaseRecordModel:
    case = CaseRecordModel(
        case_id=str(uuid4()),
        title=title,
        category="operations",
        status="open",
        summary="Case used for communication draft tests.",
        current_stage="intake",
        domain_pack_id=domain_pack_id,
        case_type_id=case_type_id,
        jurisdiction="us",
        domain_category="medical_insurance",
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _add_document(session: Session, *, case_id: str, filename: str = "packet.pdf") -> DocumentRecord:
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
    session.refresh(document)
    return document


def _add_workflow_pack_run(session: Session, *, case_id: str) -> WorkflowPackRunModel:
    run = WorkflowPackRunModel(
        run_id=str(uuid4()),
        case_id=case_id,
        workflow_pack_id="prior_auth_preclaim_packet_review",
        status="completed_partial",
        review_recommendation_json=OperatorReviewRecommendation(
            has_missing_required_documents=True,
            readiness_status="incomplete",
            suggested_next_stage="awaiting_documents",
            notes=["Required document categories are missing."],
        ).model_dump(mode="json"),
        notes_json=["Workflow pack completed with missing required documents."],
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def test_generate_missing_document_request_uses_checklist_state(session: Session) -> None:
    case = _create_case(session)
    ReadinessService(session).generate_checklist(case.case_id)
    service = CommunicationDraftService(session)

    response = asyncio.run(service.generate_draft(
        case.case_id,
        CommunicationDraftGenerateRequest(template_id="missing_document_request"),
    ))

    assert response.draft.draft_type == "missing_document_request"
    assert response.draft.source_metadata.missing_required_item_count > 0
    assert response.draft.review.requires_human_review is True
    assert any(
        reference.source_entity_type == "checklist_item"
        for reference in response.draft.evidence_references
    )


def test_packet_cover_note_requires_real_packet(session: Session) -> None:
    case = _create_case(session)
    service = CommunicationDraftService(session)

    with pytest.raises(CommunicationDraftServiceError) as exc_info:
        asyncio.run(service.generate_draft(
            case.case_id,
            CommunicationDraftGenerateRequest(template_id="packet_cover_note"),
        ))

    assert exc_info.value.status_code == 400
    assert "requires a real generated packet" in exc_info.value.detail


def test_provider_assisted_fallback_preserves_deterministic_draft(session: Session) -> None:
    case = _create_case(session)
    ReadinessService(session).generate_checklist(case.case_id)
    service = CommunicationDraftService(session)
    service._task_service.execute_prepared_prompt = AsyncMock(
        return_value=(
            TaskExecutionResult(
                task_id="communication-draft-rewrite",
                provider="openai",
                model_id="gpt-test",
                finish_reason=FinishReason.ERROR,
                error=TaskExecutionError(
                    error_code="upstream_timeout",
                    message="Provider timed out.",
                    provider="openai",
                    model_id="gpt-test",
                    recoverable=True,
                ),
                duration_ms=123,
            ),
            [],
        )
    )

    response = asyncio.run(service.generate_draft(
        case.case_id,
        CommunicationDraftGenerateRequest(
            template_id="missing_document_request",
            strategy="provider_assisted_draft",
            provider_selection=ProviderSelection(
                provider="openai",
                model_id="gpt-test",
                api_key="test-key",
            ),
        ),
    ))

    assert response.draft.strategy == "deterministic_template_only"
    assert response.draft.generation.error is not None
    assert any(issue.code == "provider_assist_failed" for issue in response.result.issues)


def test_provider_assisted_rewrite_records_preserved_sections(session: Session) -> None:
    case = _create_case(session)
    ReadinessService(session).generate_checklist(case.case_id)

    deterministic_service = CommunicationDraftService(session)
    deterministic_response = asyncio.run(deterministic_service.generate_draft(
        case.case_id,
        CommunicationDraftGenerateRequest(template_id="missing_document_request"),
    ))
    deterministic_sections = {
        section.section_type: section
        for section in deterministic_response.draft.sections
    }

    service = CommunicationDraftService(session)
    service._task_service.execute_prepared_prompt = AsyncMock(
        return_value=(
            TaskExecutionResult(
                task_id="communication-draft-rewrite",
                provider="openai",
                model_id="gpt-test",
                finish_reason=FinishReason.COMPLETED,
                structured_output=StructuredOutputResult(
                    parsed={
                        "title": "Missing document request draft - rewritten",
                        "subject": deterministic_response.draft.subject,
                        "sections": [
                            {
                                "section_type": "summary",
                                "title": "Current State",
                                "body": "Rewritten summary from provider assistance.",
                                "bullet_items": [],
                            }
                        ],
                    },
                    raw_text="{}",
                    schema_valid=True,
                ),
                duration_ms=123,
                provider_request_id="req-123",
            ),
            [],
        )
    )

    response = asyncio.run(service.generate_draft(
        case.case_id,
        CommunicationDraftGenerateRequest(
            template_id="missing_document_request",
            strategy="provider_assisted_draft",
            provider_selection=ProviderSelection(
                provider="openai",
                model_id="gpt-test",
                api_key="test-key",
            ),
        ),
    ))
    response_sections = {
        section.section_type: section
        for section in response.draft.sections
    }

    assert response.draft.strategy == "provider_assisted_draft"
    assert response_sections["summary"].body == "Rewritten summary from provider assistance."
    assert response_sections["request_items"].bullet_items == deterministic_sections["request_items"].bullet_items
    assert any(
        "Provider-assisted rewrite returned structured wording for 1/4 section(s)." == note
        for note in response.draft.generation.notes
    )
    assert any(
        "request_items" in note and "closing" in note
        for note in response.draft.generation.notes
    )


def test_packet_cover_note_with_real_packet(session: Session) -> None:
    case = _create_case(session)
    _add_document(session, case_id=case.case_id)
    ReadinessService(session).generate_checklist(case.case_id)
    PacketAssemblyService(session).generate_packet(case.case_id)
    service = CommunicationDraftService(session)

    response = asyncio.run(service.generate_draft(
        case.case_id,
        CommunicationDraftGenerateRequest(template_id="packet_cover_note"),
    ))

    assert response.draft.draft_type == "packet_cover_note"
    assert response.draft.packet_id is not None
    assert any(
        reference.source_entity_type == "packet"
        for reference in response.draft.evidence_references
    )
    assert any(
        section.section_type == "packet_context"
        for section in response.draft.sections
    )


def test_internal_handoff_note_includes_actions(session: Session) -> None:
    case = _create_case(session)
    ReadinessService(session).generate_checklist(case.case_id)
    action = ActionItemModel(
        action_item_id=str(uuid4()),
        case_id=case.case_id,
        fingerprint="test-missing-labs-fingerprint",
        category="document_gap",
        title="Follow up on missing labs",
        description="Lab results are missing from case documents.",
        priority="high",
        status="open",
        source="readiness",
        source_reason="Checklist gap identified",
    )
    session.add(action)
    session.commit()

    service = CommunicationDraftService(session)
    response = asyncio.run(service.generate_draft(
        case.case_id,
        CommunicationDraftGenerateRequest(template_id="internal_handoff_note"),
    ))

    assert response.draft.draft_type == "internal_handoff_note"
    assert response.draft.source_metadata.open_action_count >= 1
    assert any(
        reference.source_entity_type == "action_item"
        for reference in response.draft.evidence_references
    )
    assert any(
        section.section_type == "follow_up_items"
        for section in response.draft.sections
    )


def test_missing_document_request_can_use_workflow_pack_run_context(session: Session) -> None:
    case = _create_case(session)
    ReadinessService(session).generate_checklist(case.case_id)
    workflow_pack_run = _add_workflow_pack_run(session, case_id=case.case_id)

    service = CommunicationDraftService(session)
    response = asyncio.run(service.generate_draft(
        case.case_id,
        CommunicationDraftGenerateRequest(
            template_id="missing_document_request",
            workflow_pack_run_id=workflow_pack_run.run_id,
        ),
    ))

    assert response.draft.source_metadata.workflow_pack_run_id == workflow_pack_run.run_id
    assert any(
        reference.source_entity_type == "workflow_pack_run"
        for reference in response.draft.evidence_references
    )


def test_invalid_persisted_draft_data_returns_clean_error(session: Session) -> None:
    case = _create_case(session)
    ReadinessService(session).generate_checklist(case.case_id)
    service = CommunicationDraftService(session)
    response = asyncio.run(service.generate_draft(
        case.case_id,
        CommunicationDraftGenerateRequest(template_id="missing_document_request"),
    ))

    draft_model = session.get(CommunicationDraftModel, response.draft.draft_id)
    assert draft_model is not None
    draft_model.sections_json = [{"section_type": "summary"}]
    session.add(draft_model)
    session.commit()

    with pytest.raises(CommunicationDraftServiceError) as exc_info:
        service.get_draft(response.draft.draft_id)

    assert exc_info.value.status_code == 500
    assert "contains invalid persisted data" in exc_info.value.detail


def test_communication_routes_list_templates_create_and_review(
    client: TestClient,
    session: Session,
) -> None:
    # List templates
    templates_resp = client.get("/communication/templates")
    assert templates_resp.status_code == 200
    templates = templates_resp.json()["templates"]
    assert len(templates) >= 3
    assert any(t["template_id"] == "missing_document_request" for t in templates)

    # Create a case with a checklist so missing-document draft can generate
    case = _create_case(session)
    ReadinessService(session).generate_checklist(case.case_id)

    # Generate a draft via route
    gen_resp = client.post(
        f"/cases/{case.case_id}/communication-drafts",
        json={"template_id": "missing_document_request"},
    )
    assert gen_resp.status_code == 200
    draft = gen_resp.json()["draft"]
    draft_id = draft["draft_id"]
    assert draft["status"] == "needs_human_review"
    assert draft["draft_type"] == "missing_document_request"

    # List drafts for the case
    list_resp = client.get(f"/cases/{case.case_id}/communication-drafts")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["drafts"]) == 1

    # Get draft detail
    detail_resp = client.get(f"/communication-drafts/{draft_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["draft"]["draft_id"] == draft_id

    # Get draft sources
    sources_resp = client.get(f"/communication-drafts/{draft_id}/sources")
    assert sources_resp.status_code == 200
    assert sources_resp.json()["draft_id"] == draft_id

    # Update review
    review_resp = client.patch(
        f"/communication-drafts/{draft_id}/review",
        json={"status": "approved_placeholder", "reviewed_by": "test-operator"},
    )
    assert review_resp.status_code == 200
    updated_draft = review_resp.json()["draft"]
    assert updated_draft["status"] == "approved_placeholder"
    assert updated_draft["review"]["reviewed_by"] == "test-operator"

    decisions = AuditTrailService(session).get_case_decisions(case.case_id)
    assert any(
        decision.decision_type == "communication_draft_review_updated"
        and decision.source_entity.entity_id == draft_id
        and decision.actor.actor_id == "test-operator"
        for decision in decisions.decisions
    )