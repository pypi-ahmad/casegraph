"""Tests for the operator review / action foundation."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.operator_review import (
    CreateReviewNoteRequest,
    QueueFilterMetadata,
    UpdateCaseStageRequest,
)

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel, WorkflowRunRecordModel
from app.extraction.models import ExtractionRunModel
from app.ingestion.models import DocumentRecord
from app.operator_review.actions import ActionItemService
from app.operator_review.errors import OperatorReviewServiceError
from app.operator_review.lifecycle import CaseLifecycleService
from app.operator_review.models import ActionItemModel
from app.operator_review.queue import ReviewQueueService
from app.operator_review.router import router as operator_review_router
from app.persistence.database import get_session
from app.readiness.service import ReadinessService


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _create_case(
    session: Session,
    *,
    domain: bool = False,
    workflow_id: str | None = None,
    current_stage: str = "intake",
) -> CaseRecordModel:
    case = CaseRecordModel(
        case_id=str(uuid4()),
        title="Operator Review Test Case",
        category="operations",
        selected_workflow_id=workflow_id,
        current_stage=current_stage,
        domain_pack_id="medical_us" if domain else None,
        case_type_id="medical_us:record_review" if domain else None,
        jurisdiction="us" if domain else None,
        domain_category="medical" if domain else None,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _add_document(
    session: Session,
    *,
    case_id: str,
    filename: str = "report.pdf",
) -> DocumentRecord:
    document = DocumentRecord(
        document_id=str(uuid4()),
        filename=filename,
        content_type="application/pdf",
        classification="document",
        requested_mode="auto",
        resolved_mode="auto",
        processing_status="completed",
    )
    session.add(document)
    session.add(CaseDocumentLinkModel(
        link_id=str(uuid4()),
        case_id=case_id,
        document_id=document.document_id,
    ))
    session.commit()
    return document


def _add_unlinked_document(session: Session, *, filename: str) -> DocumentRecord:
    document = DocumentRecord(
        document_id=str(uuid4()),
        filename=filename,
        content_type="application/pdf",
        classification="document",
        requested_mode="auto",
        resolved_mode="auto",
        processing_status="completed",
    )
    session.add(document)
    session.commit()
    return document


def _add_run(
    session: Session,
    *,
    case_id: str,
    status: str,
    workflow_id: str = "provider-task-execution",
) -> WorkflowRunRecordModel:
    run = WorkflowRunRecordModel(
        run_id=str(uuid4()),
        case_id=case_id,
        workflow_id=workflow_id,
        status=status,
    )
    session.add(run)
    session.commit()
    return run


def _add_extraction(
    session: Session,
    *,
    case_id: str,
    document_id: str,
    status: str = "completed",
    grounding_available: bool = True,
) -> ExtractionRunModel:
    run = ExtractionRunModel(
        extraction_id=str(uuid4()),
        document_id=document_id,
        template_id="tmpl-1",
        case_id=case_id,
        strategy_used="llm",
        status=status,
        fields_extracted=4,
        grounding_available=grounding_available,
    )
    session.add(run)
    session.commit()
    return run


class TestCaseLifecycleService:
    def test_default_stage_is_intake(self, session: Session) -> None:
        case = _create_case(session)
        service = CaseLifecycleService(session)

        result = service.get_stage(case.case_id)

        assert result.stage.current_stage == "intake"
        assert "document_review" in result.stage.allowed_transitions

    def test_transition_records_history(self, session: Session) -> None:
        case = _create_case(session)
        service = CaseLifecycleService(session)

        result = service.transition_stage(
            case.case_id,
            UpdateCaseStageRequest(
                new_stage="document_review",
                reason="Documents linked",
                note="Ready for initial document pass.",
            ),
        )
        history = service.list_stage_history(case.case_id)

        assert result.stage.current_stage == "document_review"
        assert history.transitions[0].from_stage == "intake"
        assert history.transitions[0].to_stage == "document_review"
        assert history.transitions[0].metadata.reason == "Documents linked"

    def test_invalid_transition_raises(self, session: Session) -> None:
        case = _create_case(session)
        service = CaseLifecycleService(session)

        with pytest.raises(OperatorReviewServiceError, match="not allowed"):
            service.transition_stage(
                case.case_id,
                UpdateCaseStageRequest(new_stage="ready_for_next_step"),
            )


class TestActionItemService:
    def test_generates_case_document_linking_action(self, session: Session) -> None:
        case = _create_case(session)
        service = ActionItemService(session)

        result = service.generate_actions(case.case_id)

        assert any(action.category == "document_linking_needed" for action in result.actions)

    def test_generates_checklist_generation_action_for_domain_case(self, session: Session) -> None:
        case = _create_case(session, domain=True)
        _add_document(session, case_id=case.case_id, filename="patient_identity_card.pdf")
        service = ActionItemService(session)

        result = service.generate_actions(case.case_id)

        assert any(
            action.category == "needs_review" and "checklist" in action.title.lower()
            for action in result.actions
        )

    def test_generates_checklist_evaluation_action_when_not_evaluated(self, session: Session) -> None:
        case = _create_case(session, domain=True)
        _add_document(session, case_id=case.case_id, filename="patient_identity_card.pdf")
        ReadinessService(session).generate_checklist(case.case_id)
        service = ActionItemService(session)

        result = service.generate_actions(case.case_id)

        assert any(
            action.category == "needs_review" and "evaluate checklist" in action.title.lower()
            for action in result.actions
        )

    def test_generates_missing_document_actions_from_evaluated_checklist(self, session: Session) -> None:
        case = _create_case(session, domain=True)
        readiness = ReadinessService(session)
        readiness.generate_checklist(case.case_id)
        readiness.evaluate(case.case_id)
        service = ActionItemService(session)

        result = service.generate_actions(case.case_id)

        assert any(action.category == "missing_document" for action in result.actions)

    def test_generates_extraction_followup_from_partially_supported_item(self, session: Session) -> None:
        case = _create_case(session, domain=True)
        _add_document(session, case_id=case.case_id, filename="patient_identity_card.pdf")
        readiness = ReadinessService(session)
        readiness.generate_checklist(case.case_id)
        readiness.evaluate(case.case_id)
        service = ActionItemService(session)

        result = service.generate_actions(case.case_id)

        assert any(action.category == "extraction_followup" for action in result.actions)

    def test_generates_document_linking_action_for_extraction_only_support(self, session: Session) -> None:
        case = _create_case(session, domain=True)
        document = _add_unlinked_document(session, filename="identity_form.pdf")
        _add_extraction(
            session,
            case_id=case.case_id,
            document_id=document.document_id,
            grounding_available=True,
        )
        readiness = ReadinessService(session)
        readiness.generate_checklist(case.case_id)
        readiness.evaluate(case.case_id)
        service = ActionItemService(session)

        result = service.generate_actions(case.case_id)

        assert any(
            action.category == "document_linking_needed" and action.checklist_item_id is not None
            for action in result.actions
        )

    def test_generates_run_followup_for_failed_run(self, session: Session) -> None:
        case = _create_case(session)
        _add_document(session, case_id=case.case_id, filename="supporting_packet.pdf")
        _add_run(session, case_id=case.case_id, status="failed")
        service = ActionItemService(session)

        result = service.generate_actions(case.case_id)

        assert any(action.category == "run_followup" for action in result.actions)

    def test_generates_evidence_gap_for_ungrounded_extraction(self, session: Session) -> None:
        case = _create_case(session)
        document = _add_document(session, case_id=case.case_id, filename="supporting_packet.pdf")
        _add_extraction(
            session,
            case_id=case.case_id,
            document_id=document.document_id,
            grounding_available=False,
        )
        service = ActionItemService(session)

        result = service.generate_actions(case.case_id)

        assert any(action.category == "evidence_gap" for action in result.actions)

    def test_resolves_stale_action_when_condition_clears(self, session: Session) -> None:
        case = _create_case(session)
        service = ActionItemService(session)

        first = service.generate_actions(case.case_id)
        assert any(action.status == "open" for action in first.actions)

        _add_document(session, case_id=case.case_id, filename="supporting_packet.pdf")
        second = service.generate_actions(case.case_id)

        assert all(action.status == "resolved" for action in second.actions)

    def test_create_review_note_uses_current_stage_snapshot(self, session: Session) -> None:
        case = _create_case(session, current_stage="document_review")
        service = ActionItemService(session)

        response = service.create_review_note(
            case.case_id,
            CreateReviewNoteRequest(
                body="Operator confirmed missing discharge summary.",
                decision="follow_up_required",
            ),
        )

        assert response.note.stage_snapshot == "document_review"
        assert response.note.decision == "follow_up_required"


class TestReviewQueueService:
    def test_queue_lists_only_cases_needing_attention(self, session: Session) -> None:
        needs_attention = _create_case(session)
        quiet_case = _create_case(session)
        _add_document(session, case_id=quiet_case.case_id, filename="supporting_packet.pdf")

        queue = ReviewQueueService(session).list_queue(QueueFilterMetadata())
        case_ids = {item.case_id for item in queue.items}

        assert needs_attention.case_id in case_ids
        assert quiet_case.case_id not in case_ids

    def test_queue_filter_by_stage(self, session: Session) -> None:
        case = _create_case(session)
        lifecycle = CaseLifecycleService(session)
        lifecycle.transition_stage(case.case_id, UpdateCaseStageRequest(new_stage="document_review"))

        queue = ReviewQueueService(session).list_queue(
            QueueFilterMetadata(stage="document_review"),
        )

        assert len(queue.items) == 1
        assert queue.items[0].current_stage == "document_review"

    def test_queue_filter_open_actions(self, session: Session) -> None:
        case = _create_case(session)
        ActionItemService(session).generate_actions(case.case_id)

        queue = ReviewQueueService(session).list_queue(
            QueueFilterMetadata(has_open_actions=True),
        )

        assert len(queue.items) == 1
        assert queue.items[0].has_open_actions is True

    def test_queue_limit_applies_after_filters(self, session: Session) -> None:
        older_matching_case = _create_case(session)
        newer_nonmatching_case = _create_case(session)
        lifecycle = CaseLifecycleService(session)
        lifecycle.transition_stage(
            older_matching_case.case_id,
            UpdateCaseStageRequest(new_stage="document_review"),
        )

        queue = ReviewQueueService(session).list_queue(
            QueueFilterMetadata(stage="document_review", limit=1),
        )

        assert len(queue.items) == 1
        assert queue.items[0].case_id == older_matching_case.case_id

    def test_queue_summary_ignores_limit_when_counting_matches(self, session: Session) -> None:
        first_case = _create_case(session)
        second_case = _create_case(session)
        lifecycle = CaseLifecycleService(session)
        lifecycle.transition_stage(first_case.case_id, UpdateCaseStageRequest(new_stage="document_review"))
        lifecycle.transition_stage(second_case.case_id, UpdateCaseStageRequest(new_stage="document_review"))

        summary = ReviewQueueService(session).get_summary(
            QueueFilterMetadata(stage="document_review", limit=1),
        )

        assert summary.summary.total_cases == 2


class TestOperatorReviewAPI:
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
        app.include_router(operator_review_router)
        app.dependency_overrides[get_session] = override_session

        with Session(engine) as seed:
            case = CaseRecordModel(
                case_id="operator-api-case",
                title="Operator API Test Case",
            )
            seed.add(case)
            seed.commit()

        with TestClient(app) as client:
            client.case_id = "operator-api-case"  # type: ignore[attr-defined]
            yield client

    def test_get_queue(self, client: TestClient) -> None:
        response = client.get("/queue")
        assert response.status_code == 200
        payload = response.json()
        assert payload["items"][0]["case_id"] == client.case_id  # type: ignore[attr-defined]

    def test_patch_stage_and_history(self, client: TestClient) -> None:
        response = client.patch(
            f"/cases/{client.case_id}/stage",  # type: ignore[attr-defined]
            json={"new_stage": "document_review", "reason": "Docs linked"},
        )
        assert response.status_code == 200
        assert response.json()["stage"]["current_stage"] == "document_review"

        history = client.get(f"/cases/{client.case_id}/stage-history")  # type: ignore[attr-defined]
        assert history.status_code == 200
        assert history.json()["transitions"][0]["to_stage"] == "document_review"

    def test_generate_actions_and_list_actions(self, client: TestClient) -> None:
        response = client.post(f"/cases/{client.case_id}/actions/generate")  # type: ignore[attr-defined]
        assert response.status_code == 200
        assert response.json()["summary"]["open_count"] >= 1

        actions = client.get(f"/cases/{client.case_id}/actions")  # type: ignore[attr-defined]
        assert actions.status_code == 200
        assert len(actions.json()["actions"]) >= 1

    def test_create_and_list_review_notes(self, client: TestClient) -> None:
        response = client.post(
            f"/cases/{client.case_id}/review-notes",  # type: ignore[attr-defined]
            json={"body": "Manual review note.", "decision": "note_only"},
        )
        assert response.status_code == 200
        assert response.json()["note"]["body"] == "Manual review note."

        notes = client.get(f"/cases/{client.case_id}/review-notes")  # type: ignore[attr-defined]
        assert notes.status_code == 200
        assert notes.json()["notes"][0]["body"] == "Manual review note."