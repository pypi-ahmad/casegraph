"""Tests for the work-management foundation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.work_management import (
    UpdateCaseAssignmentRequest,
    UpdateCaseSLARequest,
    WorkQueueFilters,
)

from app.audit.service import AuditTrailService
from app.cases.models import CaseRecordModel
from app.operator_review.models import ActionItemModel
from app.persistence.database import get_session, utcnow
from app.work_management.models import CaseWorkStateModel
from app.work_management.router import router as work_management_router
from app.work_management.service import WorkManagementService, WorkManagementServiceError


@pytest.fixture()
def session() -> Session:
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
    import app.work_management.models  # noqa: F401

    engine = create_engine("sqlite://", echo=False, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed_local_users(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_USER_1_EMAIL", "owner.one@local.dev")
    monkeypatch.setenv("AUTH_USER_1_PASSWORD_HASH", "hash-1")
    monkeypatch.setenv("AUTH_USER_1_NAME", "Owner One")
    monkeypatch.setenv("AUTH_USER_1_ROLE", "member")
    monkeypatch.setenv("AUTH_USER_2_EMAIL", "lead.two@local.dev")
    monkeypatch.setenv("AUTH_USER_2_PASSWORD_HASH", "hash-2")
    monkeypatch.setenv("AUTH_USER_2_NAME", "Lead Two")
    monkeypatch.setenv("AUTH_USER_2_ROLE", "admin")


def _create_case(session: Session, *, stage: str = "document_review") -> CaseRecordModel:
    now = utcnow()
    case = CaseRecordModel(
        case_id=str(uuid4()),
        title="Work Management Case",
        category="operations",
        status="open",
        summary="Case used for work-management tests.",
        current_stage=stage,
        created_at=now,
        updated_at=now,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def _add_open_action(session: Session, *, case_id: str, created_at: datetime | None = None) -> None:
    now = created_at or utcnow()
    session.add(
        ActionItemModel(
            action_item_id=str(uuid4()),
            case_id=case_id,
            fingerprint=str(uuid4()),
            category="needs_review",
            source="case",
            priority="normal",
            status="open",
            title="Follow up on missing review",
            description="Operator attention is required.",
            source_reason="Test action",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()


class TestWorkManagementService:
    def test_assignment_requires_known_local_user(self, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_local_users(monkeypatch)
        case = _create_case(session)
        service = WorkManagementService(session)

        with pytest.raises(WorkManagementServiceError) as exc_info:
            service.update_assignment(
                case.case_id,
                UpdateCaseAssignmentRequest(
                    assignee_id="missing-user",
                    actor_id="local-2",
                    actor_display_name="Lead Two",
                ),
            )
        assert exc_info.value.status_code == 400

    def test_assign_reassign_and_clear_case_persists_history(
        self,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_local_users(monkeypatch)
        case = _create_case(session)
        service = WorkManagementService(session)

        assigned = service.update_assignment(
            case.case_id,
            UpdateCaseAssignmentRequest(
                assignee_id="local-1",
                actor_id="local-2",
                actor_display_name="Lead Two",
                note="Initial assignment.",
            ),
        )
        assert assigned.ownership.assignment_status == "assigned"
        assert assigned.ownership.current_assignee is not None
        assert assigned.ownership.current_assignee.user_id == "local-1"

        reassigned = service.update_assignment(
            case.case_id,
            UpdateCaseAssignmentRequest(
                assignee_id="local-2",
                actor_id="local-2",
                actor_display_name="Lead Two",
                note="Escalated to lead.",
            ),
        )
        assert reassigned.ownership.assignment_status == "reassigned"
        assert reassigned.ownership.current_assignee is not None
        assert reassigned.ownership.current_assignee.user_id == "local-2"

        cleared = service.update_assignment(
            case.case_id,
            UpdateCaseAssignmentRequest(
                clear_assignment=True,
                actor_id="local-2",
                actor_display_name="Lead Two",
                note="Returned to unassigned pool.",
            ),
        )
        assert cleared.ownership.assignment_status == "unassigned"
        assert cleared.ownership.current_assignee is None
        assert cleared.ownership.note == "Returned to unassigned pool."
        assert cleared.ownership.changed_by_id == "local-2"

        history = service.list_assignment_history(case.case_id)
        assert len(history.history) == 3
        assert [entry.status for entry in history.history] == ["unassigned", "reassigned", "assigned"]

        persisted = session.get(CaseWorkStateModel, case.case_id)
        assert persisted is not None
        assert persisted.assignment_status == "unassigned"
        assert persisted.assignee_id == ""

    def test_sla_updates_compute_due_states_and_escalation(self, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        _seed_local_users(monkeypatch)
        case = _create_case(session)
        _add_open_action(session, case_id=case.case_id, created_at=utcnow() - timedelta(hours=26))
        service = WorkManagementService(session)

        due_soon = service.update_sla(
            case.case_id,
            UpdateCaseSLARequest(
                due_at=(datetime.now(UTC) + timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
                actor_id="local-2",
                actor_display_name="Lead Two",
            ),
        )
        assert due_soon.sla_state == "due_soon"

        overdue = service.update_sla(
            case.case_id,
            UpdateCaseSLARequest(
                due_at=(datetime.now(UTC) - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
                actor_id="local-2",
                actor_display_name="Lead Two",
            ),
        )
        assert overdue.sla_state == "overdue"

        status = service.get_work_status(case.case_id)
        assert status.work_status.escalation.state == "escalation_ready"
        assert "overdue_case" in status.work_status.escalation.reasons
        assert "assignment_missing" in status.work_status.escalation.reasons

    def test_work_queue_and_summary_use_real_assignment_and_sla_state(
        self,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_local_users(monkeypatch)
        case_one = _create_case(session, stage="document_review")
        case_two = _create_case(session, stage="readiness_review")
        service = WorkManagementService(session)

        service.update_assignment(
            case_one.case_id,
            UpdateCaseAssignmentRequest(
                assignee_id="local-1",
                actor_id="local-2",
                actor_display_name="Lead Two",
            ),
        )
        service.update_sla(
            case_two.case_id,
            UpdateCaseSLARequest(
                due_at=(datetime.now(UTC) + timedelta(hours=4)).isoformat().replace("+00:00", "Z"),
                actor_id="local-2",
                actor_display_name="Lead Two",
            ),
        )

        queue = service.list_queue(WorkQueueFilters(limit=20))
        assert len(queue.items) == 2

        owned = service.list_queue(WorkQueueFilters(assignee_id="local-1", limit=20))
        assert len(owned.items) == 1
        assert owned.items[0].case_id == case_one.case_id

        due_soon = service.list_queue(WorkQueueFilters(sla_state="due_soon", limit=20))
        assert len(due_soon.items) == 1
        assert due_soon.items[0].case_id == case_two.case_id

        summary = service.get_summary(WorkQueueFilters(limit=20))
        assert summary.summary.total_cases == 2
        assert summary.summary.assigned_cases == 1
        assert summary.summary.due_soon_cases == 1
        assert len(summary.available_assignees) == 2

    def test_assignment_and_sla_changes_emit_audit_events(
        self,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _seed_local_users(monkeypatch)
        case = _create_case(session)
        service = WorkManagementService(session)

        service.update_assignment(
            case.case_id,
            UpdateCaseAssignmentRequest(
                assignee_id="local-1",
                actor_id="local-2",
                actor_display_name="Lead Two",
            ),
        )
        service.update_sla(
            case.case_id,
            UpdateCaseSLARequest(
                due_at=(datetime.now(UTC) + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                actor_id="local-2",
                actor_display_name="Lead Two",
            ),
        )

        audit = AuditTrailService(session)
        timeline = audit.get_case_timeline(case.case_id)
        decisions = audit.get_case_decisions(case.case_id)
        event_types = {event.event_type for event in timeline.events}
        decision_types = {decision.decision_type for decision in decisions.decisions}

        assert "case_assignment_updated" in event_types
        assert "case_sla_updated" in event_types
        assert "case_assignment_updated" in decision_types
        assert "case_sla_updated" in decision_types


class TestWorkManagementAPI:
    @pytest.fixture()
    def client(self, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        _seed_local_users(monkeypatch)
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
        import app.work_management.models  # noqa: F401

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
        app.include_router(work_management_router)
        app.dependency_overrides[get_session] = override_session

        with Session(engine) as seed:
            case = _create_case(seed)
            _add_open_action(seed, case_id=case.case_id)
            case_id = case.case_id
            seed.commit()

        with TestClient(app) as client:
            client.case_id = case_id  # type: ignore[attr-defined]
            yield client

    def test_assignment_sla_history_and_work_status_routes(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]

        assigned = client.patch(
            f"/cases/{case_id}/assignment",
            json={
                "assignee_id": "local-1",
                "actor_id": "local-2",
                "actor_display_name": "Lead Two",
                "note": "API assignment",
            },
        )
        assert assigned.status_code == 200
        assert assigned.json()["ownership"]["current_assignee"]["user_id"] == "local-1"

        history = client.get(f"/cases/{case_id}/assignment-history")
        assert history.status_code == 200
        assert len(history.json()["history"]) == 1

        sla = client.patch(
            f"/cases/{case_id}/sla",
            json={
                "due_at": (datetime.now(UTC) + timedelta(hours=8)).isoformat().replace("+00:00", "Z"),
                "actor_id": "local-2",
                "actor_display_name": "Lead Two",
            },
        )
        assert sla.status_code == 200
        assert sla.json()["sla_state"] == "due_soon"

        work_status = client.get(f"/cases/{case_id}/work-status")
        assert work_status.status_code == 200
        assert work_status.json()["work_status"]["ownership"]["current_assignee"]["user_id"] == "local-1"
        assert len(work_status.json()["available_assignees"]) == 2

    def test_work_queue_and_summary_routes(self, client: TestClient) -> None:
        case_id = client.case_id  # type: ignore[attr-defined]

        assign = client.patch(
            f"/cases/{case_id}/assignment",
            json={
                "assignee_id": "local-1",
                "actor_id": "local-2",
                "actor_display_name": "Lead Two",
            },
        )
        assert assign.status_code == 200

        queue = client.get("/work/queue?assignee_id=local-1")
        assert queue.status_code == 200
        assert len(queue.json()["items"]) == 1

        summary = client.get("/work/summary")
        assert summary.status_code == 200
        assert summary.json()["summary"]["assigned_cases"] == 1
        assert len(summary.json()["available_assignees"]) == 2

    def test_case_not_found_routes(self, client: TestClient) -> None:
        missing_assignment = client.patch(
            "/cases/missing-case/assignment",
            json={"assignee_id": "local-1", "actor_id": "local-2"},
        )
        assert missing_assignment.status_code == 404

        missing_status = client.get("/cases/missing-case/work-status")
        assert missing_status.status_code == 404