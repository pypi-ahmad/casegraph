"""Case work-management service.

Provides explicit case ownership, assignment history, due-date / SLA tracking,
workload segmentation, and descriptive escalation-readiness metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import ChangeSummary, FieldChangeRecord
from casegraph_agent_sdk.cases import NormalizedOperationError
from casegraph_agent_sdk.work_management import (
    AssignmentStatus,
    AssignmentHistoryEntry,
    AssignmentHistoryResponse,
    AssignmentReasonPlaceholder,
    AssigneeReference,
    CaseAssignmentResponse,
    CaseSLAResponse,
    CaseWorkStatusResponse,
    DueDateMetadata,
    EscalationAssessment,
    EscalationReadinessState,
    EscalationReason,
    OwnershipSummary,
    SLAState,
    SLATargetMetadata,
    UpdateCaseAssignmentRequest,
    UpdateCaseSLARequest,
    WorkManagementOperationResult,
    WorkQueueFilters,
    WorkQueueResponse,
    WorkStatusSummary,
    WorkSummaryResponse,
    WorkloadSegment,
    WorkloadSummary,
)

from app.audit.service import AuditTrailService, audit_actor, entity_ref
from app.cases.models import CaseRecordModel
from app.human_validation.service import HumanValidationService
from app.operator_review.models import ActionItemModel
from app.persistence.database import utcnow
from app.readiness.service import ReadinessService
from app.reviewed_handoff.models import ReviewedSnapshotModel
from app.reviewed_release.service import ReviewedReleaseService
from app.submissions.models import AutomationPlanModel, SubmissionDraftModel
from app.work_management.models import CaseAssignmentHistoryModel, CaseWorkStateModel
from app.work_management.users import LocalAssigneeRegistry


DEFAULT_DUE_SOON_WINDOW_HOURS = 24
DEFAULT_OPEN_ACTION_LINGER_HOURS = 24
ACTIVE_CASE_STATUSES = {"open", "active", "on_hold"}
ASSIGNED_STATUSES = {"assigned", "reassigned"}
SEGMENT_RANK = {
    "assigned": 0,
    "unassigned": 1,
    "attention_needed": 2,
    "due_soon": 3,
    "overdue": 4,
    "escalation_ready": 5,
}


@dataclass
class _EscalationInputs:
    open_action_count: int
    oldest_open_action_at: datetime | None
    unresolved_review_item_count: int
    release_blocked: bool
    submission_planning_blocked: bool


def isoformat_utc(value: datetime | None) -> str:
    if value is None:
        return ""
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parseisoformat_utc(value: str, *, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkManagementServiceError(
            f"{field_name} must be a valid ISO-8601 timestamp.",
            status_code=400,
        ) from exc
    normalized = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return normalized.astimezone(UTC)


class WorkManagementServiceError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class WorkManagementService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._readiness = ReadinessService(session)
        self._reviewed_state = HumanValidationService(session)
        self._reviewed_release = ReviewedReleaseService(session)
        self._assignees = LocalAssigneeRegistry()

    def list_queue(self, filters: WorkQueueFilters) -> WorkQueueResponse:
        items = self._collect_items(filters, apply_limit=True)
        return WorkQueueResponse(filters=filters, items=items)

    def get_summary(self, filters: WorkQueueFilters) -> WorkSummaryResponse:
        items = self._collect_items(filters, apply_limit=False)
        return WorkSummaryResponse(
            filters=filters,
            summary=WorkloadSummary(
                total_cases=len(items),
                assigned_cases=sum(1 for item in items if item.ownership.assignment_status in ASSIGNED_STATUSES),
                unassigned_cases=sum(1 for item in items if item.ownership.assignment_status == "unassigned"),
                due_soon_cases=sum(1 for item in items if item.sla_state == "due_soon"),
                overdue_cases=sum(1 for item in items if item.sla_state == "overdue"),
                attention_needed_cases=sum(1 for item in items if item.escalation.state == "attention_needed"),
                escalation_ready_cases=sum(1 for item in items if item.escalation.state == "escalation_ready"),
            ),
            available_assignees=self._assignees.list_assignees(),
        )

    def update_assignment(
        self,
        case_id: str,
        request: UpdateCaseAssignmentRequest,
    ) -> CaseAssignmentResponse:
        case = self._require_case(case_id)
        state = self._get_or_create_state(case_id)

        if request.clear_assignment and request.assignee_id:
            raise WorkManagementServiceError(
                "Provide either assignee_id or clear_assignment, not both.",
                status_code=400,
            )
        if not request.clear_assignment and not (request.assignee_id or "").strip():
            raise WorkManagementServiceError(
                "assignee_id is required unless clear_assignment is true.",
                status_code=400,
            )

        now = utcnow()
        previous_assignee_id = state.assignee_id
        previous_status = state.assignment_status
        previous_note = state.assignment_note
        previous_reason = state.assignment_reason

        if request.clear_assignment:
            if previous_assignee_id == "" and previous_status == "unassigned":
                return CaseAssignmentResponse(
                    result=WorkManagementOperationResult(success=True, message="Assignment already clear."),
                    ownership=self._build_ownership(case_id, state),
                    history_entry=None,
                )
            assignee = None
            new_status = "unassigned"
            reason = (request.reason or "manual_clear")
        else:
            assignee_id = (request.assignee_id or "").strip()
            assignee = self._assignees.get_assignee(assignee_id)
            if assignee is None:
                raise WorkManagementServiceError(
                    f"Assignee '{assignee_id}' is not available in the local user registry.",
                    status_code=400,
                )
            if previous_assignee_id == assignee.user_id and previous_status in ASSIGNED_STATUSES and previous_note == (request.note or "") and previous_reason == (request.reason or "manual_assignment"):
                return CaseAssignmentResponse(
                    result=WorkManagementOperationResult(success=True, message="Assignment unchanged."),
                    ownership=self._build_ownership(case_id, state),
                    history_entry=None,
                )
            new_status = "assigned" if previous_assignee_id == "" else "reassigned"
            reason = request.reason or ("manual_assignment" if previous_assignee_id == "" else "manual_reassignment")

        state.assignment_status = new_status
        state.assignee_id = assignee.user_id if assignee is not None else ""
        state.assignee_display_name = assignee.display_name if assignee is not None else ""
        state.assignee_email = assignee.email if assignee is not None else ""
        state.assignee_role = assignee.role if assignee is not None else "member"
        state.assignment_reason = reason
        state.assignment_note = (request.note or "").strip()
        state.assigned_at = now if assignee is not None else None
        state.assignment_changed_by_id = request.actor_id.strip()
        state.assignment_changed_by_display_name = request.actor_display_name.strip()
        state.updated_at = now
        self._session.add(state)

        history = CaseAssignmentHistoryModel(
            record_id=str(uuid4()),
            case_id=case_id,
            status=new_status,
            assignee_id=assignee.user_id if assignee is not None else "",
            assignee_display_name=assignee.display_name if assignee is not None else "",
            assignee_email=assignee.email if assignee is not None else "",
            assignee_role=assignee.role if assignee is not None else "member",
            reason=reason,
            note=(request.note or "").strip(),
            changed_by_id=request.actor_id.strip(),
            changed_by_display_name=request.actor_display_name.strip(),
            created_at=now,
        )
        self._session.add(history)

        actor = self._build_actor(request.actor_id, request.actor_display_name)
        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=case_id,
            category="work_management",
            event_type="case_assignment_updated",
            actor=actor,
            entity=entity_ref("case_assignment", case_id, case_id=case_id, display_label=case.title),
            change_summary=ChangeSummary(
                message="Case assignment updated.",
                field_changes=[
                    FieldChangeRecord(field_path="assignment_status", old_value=previous_status, new_value=new_status),
                    FieldChangeRecord(field_path="assignee_id", old_value=previous_assignee_id, new_value=state.assignee_id),
                    FieldChangeRecord(field_path="assignment_note", old_value=previous_note, new_value=state.assignment_note),
                ],
            ),
            metadata={"reason": reason},
        )
        decision = audit.append_decision(
            case_id=case_id,
            decision_type="case_assignment_updated",
            actor=actor,
            source_entity=entity_ref("case", case_id, case_id=case_id, display_label=case.title),
            outcome=new_status,
            reason=reason,
            note=state.assignment_note,
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)

        self._session.commit()
        return CaseAssignmentResponse(
            result=WorkManagementOperationResult(success=True, message="Case assignment updated."),
            ownership=self._build_ownership(case_id, state),
            history_entry=self._to_history_entry(history),
        )

    def list_assignment_history(self, case_id: str) -> AssignmentHistoryResponse:
        self._require_case(case_id)
        rows = list(self._session.exec(
            select(CaseAssignmentHistoryModel)
            .where(CaseAssignmentHistoryModel.case_id == case_id)
            .order_by(desc(CaseAssignmentHistoryModel.created_at), desc(CaseAssignmentHistoryModel.record_id))
        ).all())
        return AssignmentHistoryResponse(
            case_id=case_id,
            history=[self._to_history_entry(row) for row in rows],
        )

    def update_sla(
        self,
        case_id: str,
        request: UpdateCaseSLARequest,
    ) -> CaseSLAResponse:
        case = self._require_case(case_id)
        state = self._get_or_create_state(case_id)

        if request.clear_due_date and request.due_at:
            raise WorkManagementServiceError(
                "Provide either due_at or clear_due_date, not both.",
                status_code=400,
            )

        now = utcnow()
        previous_due_at = isoformat_utc(state.due_at)
        previous_policy_id = state.sla_policy_id
        previous_note = state.sla_note

        if request.clear_due_date:
            state.due_at = None
        elif request.due_at is not None:
            state.due_at = _parseisoformat_utc(request.due_at.strip(), field_name="due_at")

        if request.policy_id is not None:
            state.sla_policy_id = request.policy_id.strip()
        if request.due_soon_window_hours is not None:
            state.due_soon_window_hours = request.due_soon_window_hours

        state.sla_note = (request.note or "").strip()
        state.sla_updated_by_id = request.actor_id.strip()
        state.sla_updated_by_display_name = request.actor_display_name.strip()
        state.sla_updated_at = now
        state.updated_at = now
        self._session.add(state)

        actor = self._build_actor(request.actor_id, request.actor_display_name)
        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=case_id,
            category="work_management",
            event_type="case_sla_updated",
            actor=actor,
            entity=entity_ref("case_sla", case_id, case_id=case_id, display_label=case.title),
            change_summary=ChangeSummary(
                message="Case SLA metadata updated.",
                field_changes=[
                    FieldChangeRecord(field_path="due_at", old_value=previous_due_at, new_value=isoformat_utc(state.due_at)),
                    FieldChangeRecord(field_path="policy_id", old_value=previous_policy_id, new_value=state.sla_policy_id),
                    FieldChangeRecord(field_path="sla_note", old_value=previous_note, new_value=state.sla_note),
                ],
            ),
            metadata={"due_soon_window_hours": state.due_soon_window_hours},
        )
        decision = audit.append_decision(
            case_id=case_id,
            decision_type="case_sla_updated",
            actor=actor,
            source_entity=entity_ref("case", case_id, case_id=case_id, display_label=case.title),
            outcome=self._compute_sla_state(state),
            note=state.sla_note,
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)

        self._session.commit()
        return CaseSLAResponse(
            result=WorkManagementOperationResult(success=True, message="Case SLA metadata updated."),
            sla_target=self._build_sla_target(state),
            sla_state=self._compute_sla_state(state),
        )

    def get_work_status(self, case_id: str) -> CaseWorkStatusResponse:
        case = self._require_case(case_id)
        state = self._session.get(CaseWorkStateModel, case_id)
        return CaseWorkStatusResponse(
            work_status=self._build_work_status(case, state),
            available_assignees=self._assignees.list_assignees(),
        )

    def _collect_items(self, filters: WorkQueueFilters, *, apply_limit: bool) -> list[WorkStatusSummary]:
        limit = max(1, min(filters.limit, 200))
        cases = list(self._session.exec(
            select(CaseRecordModel).order_by(desc(CaseRecordModel.updated_at))
        ).all())

        items: list[WorkStatusSummary] = []
        for case in cases:
            state = self._session.get(CaseWorkStateModel, case.case_id)
            item = self._build_work_status(case, state)
            if filters.assignee_id and item.ownership.current_assignee is not None and item.ownership.current_assignee.user_id != filters.assignee_id:
                continue
            if filters.assignee_id and item.ownership.current_assignee is None:
                continue
            if filters.assignment_status and item.ownership.assignment_status != filters.assignment_status:
                continue
            if filters.sla_state and item.sla_state != filters.sla_state:
                continue
            if filters.escalation_state and item.escalation.state != filters.escalation_state:
                continue
            if filters.domain_pack_id and item.domain_pack_id != filters.domain_pack_id:
                continue
            if filters.case_type_id and item.case_type_id != filters.case_type_id:
                continue
            items.append(item)

        items.sort(
            key=lambda item: (
                SEGMENT_RANK[item.workload_segment],
                item.updated_at,
            ),
            reverse=True,
        )
        return items[:limit] if apply_limit else items

    def _build_work_status(
        self,
        case: CaseRecordModel,
        state: CaseWorkStateModel | None,
    ) -> WorkStatusSummary:
        ownership = self._build_ownership(case.case_id, state)
        sla_target = self._build_sla_target(state)
        sla_state = self._compute_sla_state(state)
        escalation_inputs = self._collect_escalation_inputs(case.case_id)
        assignment_expected = self._is_assignment_expected(case, escalation_inputs, sla_target)
        escalation = self._compute_escalation(case, ownership, assignment_expected, sla_state, escalation_inputs)
        workload_segment = self._determine_workload_segment(ownership.assignment_status, sla_state, escalation.state)
        readiness_status = None
        readiness = self._readiness.get_readiness(case.case_id)
        if readiness is not None:
            readiness_status = readiness.readiness.readiness_status
        updated_candidates = [case.updated_at]
        if state is not None:
            updated_candidates.append(state.updated_at)
        return WorkStatusSummary(
            case_id=case.case_id,
            title=case.title,
            case_status=case.status,
            current_stage=case.current_stage,
            domain_pack_id=case.domain_pack_id,
            case_type_id=case.case_type_id,
            readiness_status=readiness_status,
            ownership=ownership,
            assignment_expected=assignment_expected,
            sla_target=sla_target,
            sla_state=sla_state,
            workload_segment=workload_segment,
            escalation=escalation,
            open_action_count=escalation_inputs.open_action_count,
            unresolved_review_item_count=escalation_inputs.unresolved_review_item_count,
            release_blocked=escalation_inputs.release_blocked,
            submission_planning_blocked=escalation_inputs.submission_planning_blocked,
            updated_at=isoformat_utc(max(updated_candidates)),
        )

    def _collect_escalation_inputs(self, case_id: str) -> _EscalationInputs:
        open_actions = list(self._session.exec(
            select(ActionItemModel)
            .where(ActionItemModel.case_id == case_id)
            .where(ActionItemModel.status == "open")
            .order_by(ActionItemModel.created_at)
        ).all())
        oldest_open_action_at = open_actions[0].created_at if open_actions else None

        reviewed_state = self._reviewed_state.get_reviewed_state(case_id).state
        unresolved_review_item_count = len(reviewed_state.unresolved_items)

        reviewed_snapshot_count = len(list(self._session.exec(
            select(ReviewedSnapshotModel.snapshot_id).where(ReviewedSnapshotModel.case_id == case_id)
        ).all()))
        release_blocked = False
        if reviewed_snapshot_count > 0:
            release_blocked = not self._reviewed_release.get_release_eligibility(case_id).eligibility.eligible

        latest_draft = self._session.exec(
            select(SubmissionDraftModel)
            .where(SubmissionDraftModel.case_id == case_id)
            .order_by(desc(SubmissionDraftModel.updated_at), desc(SubmissionDraftModel.created_at))
        ).first()
        submission_planning_blocked = False
        if latest_draft is not None:
            if latest_draft.status == "blocked" or latest_draft.approval_status == "rejected":
                submission_planning_blocked = True
            latest_plan = self._session.exec(
                select(AutomationPlanModel)
                .where(AutomationPlanModel.draft_id == latest_draft.draft_id)
                .order_by(desc(AutomationPlanModel.updated_at), desc(AutomationPlanModel.created_at))
            ).first()
            if latest_plan is not None and latest_plan.status == "blocked":
                submission_planning_blocked = True

        return _EscalationInputs(
            open_action_count=len(open_actions),
            oldest_open_action_at=oldest_open_action_at,
            unresolved_review_item_count=unresolved_review_item_count,
            release_blocked=release_blocked,
            submission_planning_blocked=submission_planning_blocked,
        )

    def _build_ownership(self, case_id: str, state: CaseWorkStateModel | None) -> OwnershipSummary:
        if state is None:
            return OwnershipSummary(case_id=case_id)
        current_assignee = None
        if state.assignee_id:
            current_assignee = AssigneeReference(
                user_id=state.assignee_id,
                display_name=state.assignee_display_name,
                email=state.assignee_email,
                role=state.assignee_role,
            )
        return OwnershipSummary(
            case_id=case_id,
            assignment_status=state.assignment_status,
            current_assignee=current_assignee,
            assigned_at=isoformat_utc(state.assigned_at),
            changed_by_id=state.assignment_changed_by_id,
            changed_by_display_name=state.assignment_changed_by_display_name,
            note=state.assignment_note,
            reason=state.assignment_reason or None,
        )

    def _build_sla_target(self, state: CaseWorkStateModel | None) -> SLATargetMetadata:
        if state is None or (state.due_at is None and state.sla_policy_id == ""):
            return SLATargetMetadata()
        due_date = None
        if state.due_at is not None:
            due_date = DueDateMetadata(
                due_at=isoformat_utc(state.due_at),
                due_soon_window_hours=state.due_soon_window_hours,
                note=state.sla_note,
                updated_by_id=state.sla_updated_by_id,
                updated_by_display_name=state.sla_updated_by_display_name,
                updated_at=isoformat_utc(state.sla_updated_at),
            )
        return SLATargetMetadata(policy_id=state.sla_policy_id, due_date=due_date)

    def _compute_sla_state(self, state: CaseWorkStateModel | None) -> SLAState:
        if state is None or state.due_at is None:
            return "no_deadline"
        now = utcnow()
        due_at = state.due_at if state.due_at.tzinfo is not None else state.due_at.replace(tzinfo=UTC)
        if now >= due_at:
            return "overdue"
        due_soon_window = timedelta(hours=max(1, state.due_soon_window_hours or DEFAULT_DUE_SOON_WINDOW_HOURS))
        if due_at - now <= due_soon_window:
            return "due_soon"
        return "on_track"

    def _is_assignment_expected(
        self,
        case: CaseRecordModel,
        escalation_inputs: _EscalationInputs,
        sla_target: SLATargetMetadata,
    ) -> bool:
        return case.status in ACTIVE_CASE_STATUSES and (
            case.current_stage != "intake"
            or escalation_inputs.open_action_count > 0
            or escalation_inputs.unresolved_review_item_count > 0
            or escalation_inputs.release_blocked
            or escalation_inputs.submission_planning_blocked
            or sla_target.due_date is not None
        )

    def _compute_escalation(
        self,
        case: CaseRecordModel,
        ownership: OwnershipSummary,
        assignment_expected: bool,
        sla_state: SLAState,
        escalation_inputs: _EscalationInputs,
    ) -> EscalationAssessment:
        now = utcnow()
        reasons: list[EscalationReason] = []

        if sla_state == "overdue":
            reasons.append("overdue_case")
        if escalation_inputs.unresolved_review_item_count > 0:
            reasons.append("unresolved_review_items")
        if escalation_inputs.release_blocked:
            reasons.append("release_blocked")
        if escalation_inputs.submission_planning_blocked:
            reasons.append("submission_planning_blocked")
        if escalation_inputs.open_action_count > 0 and escalation_inputs.oldest_open_action_at is not None:
            linger_cutoff = now - timedelta(hours=DEFAULT_OPEN_ACTION_LINGER_HOURS)
            oldest_open_action_at = escalation_inputs.oldest_open_action_at
            if oldest_open_action_at.tzinfo is None:
                oldest_open_action_at = oldest_open_action_at.replace(tzinfo=UTC)
            if oldest_open_action_at <= linger_cutoff or sla_state in {"due_soon", "overdue"}:
                reasons.append("open_actions_lingering")
        if assignment_expected and ownership.assignment_status == "unassigned":
            reasons.append("assignment_missing")

        unique_reasons: list[EscalationReason] = []
        for reason in reasons:
            if reason not in unique_reasons:
                unique_reasons.append(reason)

        escalation_ready = (
            "overdue_case" in unique_reasons
            or "submission_planning_blocked" in unique_reasons
            or (
                "release_blocked" in unique_reasons
                and ("assignment_missing" in unique_reasons or "unresolved_review_items" in unique_reasons)
            )
        )

        if escalation_ready:
            return EscalationAssessment(
                state="escalation_ready",
                reasons=unique_reasons,
                note="Explicit case state indicates this work item may require escalation review.",
            )
        if unique_reasons:
            return EscalationAssessment(
                state="attention_needed",
                reasons=unique_reasons,
                note="Explicit case state indicates operator attention is needed before any escalation decision.",
            )
        return EscalationAssessment(state="not_applicable")

    @staticmethod
    def _determine_workload_segment(
        assignment_status: AssignmentStatus,
        sla_state: SLAState,
        escalation_state: EscalationReadinessState,
    ) -> WorkloadSegment:
        if escalation_state == "escalation_ready":
            return "escalation_ready"
        if sla_state == "overdue":
            return "overdue"
        if sla_state == "due_soon":
            return "due_soon"
        if escalation_state == "attention_needed":
            return "attention_needed"
        if assignment_status == "unassigned":
            return "unassigned"
        return "assigned"

    @staticmethod
    def _to_history_entry(row: CaseAssignmentHistoryModel) -> AssignmentHistoryEntry:
        assignee = None
        if row.assignee_id:
            assignee = AssigneeReference(
                user_id=row.assignee_id,
                display_name=row.assignee_display_name,
                email=row.assignee_email,
                role=row.assignee_role,
            )
        return AssignmentHistoryEntry(
            record_id=row.record_id,
            case_id=row.case_id,
            status=row.status,
            assignee=assignee,
            reason=row.reason,
            note=row.note,
            changed_by_id=row.changed_by_id,
            changed_by_display_name=row.changed_by_display_name,
            created_at=isoformat_utc(row.created_at),
        )

    def _get_or_create_state(self, case_id: str) -> CaseWorkStateModel:
        existing = self._session.get(CaseWorkStateModel, case_id)
        if existing is not None:
            return existing
        now = utcnow()
        return CaseWorkStateModel(case_id=case_id, created_at=now, updated_at=now)

    def _build_actor(self, actor_id: str, actor_display_name: str):
        if actor_id.strip():
            return audit_actor(
                "operator",
                actor_id=actor_id.strip(),
                display_name=actor_display_name.strip() or actor_id.strip(),
            )
        return audit_actor("service", actor_id="work_management.service", display_name="Work Management Service")

    def _require_case(self, case_id: str) -> CaseRecordModel:
        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise WorkManagementServiceError(f"Case '{case_id}' not found.", status_code=404)
        return case