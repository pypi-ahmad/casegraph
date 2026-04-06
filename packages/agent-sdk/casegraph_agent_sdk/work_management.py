"""Shared work-management contracts.

This layer defines explicit case ownership, assignment history, due-date / SLA
tracking, workload segmentation, and descriptive escalation-readiness metadata.

It does not implement org management, invitations, notifications, automatic
escalation, productivity analytics, or enterprise governance workflows.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.cases import CaseId, CaseStatus, NormalizedOperationError
from casegraph_agent_sdk.domains import CaseTypeTemplateId, DomainPackId
from casegraph_agent_sdk.operator_review import CaseStage
from casegraph_agent_sdk.readiness import ReadinessStatus


AssignmentRecordId = str
SLAPolicyId = str

WorkUserRole = Literal["admin", "member"]

AssignmentStatus = Literal[
    "unassigned",
    "assigned",
    "reassigned",
    "released_placeholder",
]

AssignmentReasonPlaceholder = Literal[
    "manual_assignment",
    "manual_reassignment",
    "manual_clear",
    "workload_balancing_placeholder",
]

WorkloadSegment = Literal[
    "assigned",
    "unassigned",
    "attention_needed",
    "due_soon",
    "overdue",
    "escalation_ready",
]

SLAState = Literal[
    "no_deadline",
    "on_track",
    "due_soon",
    "overdue",
]

EscalationReadinessState = Literal[
    "not_applicable",
    "attention_needed",
    "escalation_ready",
]

EscalationReason = Literal[
    "overdue_case",
    "unresolved_review_items",
    "release_blocked",
    "submission_planning_blocked",
    "open_actions_lingering",
    "assignment_missing",
]


class AssigneeReference(BaseModel):
    user_id: str
    display_name: str
    email: str = ""
    role: WorkUserRole = "member"


class AssignmentHistoryEntry(BaseModel):
    record_id: AssignmentRecordId
    case_id: CaseId
    status: AssignmentStatus = "unassigned"
    assignee: AssigneeReference | None = None
    reason: AssignmentReasonPlaceholder = "manual_assignment"
    note: str = ""
    changed_by_id: str = ""
    changed_by_display_name: str = ""
    created_at: str = ""


class OwnershipSummary(BaseModel):
    case_id: CaseId
    assignment_status: AssignmentStatus = "unassigned"
    current_assignee: AssigneeReference | None = None
    assigned_at: str = ""
    changed_by_id: str = ""
    changed_by_display_name: str = ""
    note: str = ""
    reason: AssignmentReasonPlaceholder | None = None


class DueDateMetadata(BaseModel):
    due_at: str = ""
    due_soon_window_hours: int = 24
    note: str = ""
    updated_by_id: str = ""
    updated_by_display_name: str = ""
    updated_at: str = ""


class SLATargetMetadata(BaseModel):
    policy_id: SLAPolicyId = ""
    due_date: DueDateMetadata | None = None


class EscalationAssessment(BaseModel):
    state: EscalationReadinessState = "not_applicable"
    reasons: list[EscalationReason] = Field(default_factory=list)
    note: str = ""


class WorkStatusSummary(BaseModel):
    case_id: CaseId
    title: str
    case_status: CaseStatus
    current_stage: CaseStage = "intake"
    domain_pack_id: DomainPackId | None = None
    case_type_id: CaseTypeTemplateId | None = None
    readiness_status: ReadinessStatus | None = None
    ownership: OwnershipSummary
    assignment_expected: bool = False
    sla_target: SLATargetMetadata = Field(default_factory=SLATargetMetadata)
    sla_state: SLAState = "no_deadline"
    workload_segment: WorkloadSegment = "unassigned"
    escalation: EscalationAssessment = Field(default_factory=EscalationAssessment)
    open_action_count: int = 0
    unresolved_review_item_count: int = 0
    release_blocked: bool = False
    submission_planning_blocked: bool = False
    updated_at: str = ""


class WorkloadSummary(BaseModel):
    total_cases: int = 0
    assigned_cases: int = 0
    unassigned_cases: int = 0
    due_soon_cases: int = 0
    overdue_cases: int = 0
    attention_needed_cases: int = 0
    escalation_ready_cases: int = 0


class WorkManagementOperationResult(BaseModel):
    success: bool = True
    message: str = ""
    error: NormalizedOperationError | None = None


class WorkQueueFilters(BaseModel):
    assignee_id: str | None = None
    assignment_status: AssignmentStatus | None = None
    sla_state: SLAState | None = None
    escalation_state: EscalationReadinessState | None = None
    domain_pack_id: DomainPackId | None = None
    case_type_id: CaseTypeTemplateId | None = None
    limit: int = 100


class UpdateCaseAssignmentRequest(BaseModel):
    assignee_id: str | None = None
    clear_assignment: bool = False
    reason: AssignmentReasonPlaceholder | None = None
    note: str | None = None
    actor_id: str = ""
    actor_display_name: str = ""


class UpdateCaseSLARequest(BaseModel):
    due_at: str | None = None
    clear_due_date: bool = False
    policy_id: SLAPolicyId | None = None
    due_soon_window_hours: int | None = Field(default=None, ge=1, le=168)
    note: str | None = None
    actor_id: str = ""
    actor_display_name: str = ""


class WorkQueueResponse(BaseModel):
    filters: WorkQueueFilters
    items: list[WorkStatusSummary] = Field(default_factory=list)


class WorkSummaryResponse(BaseModel):
    filters: WorkQueueFilters
    summary: WorkloadSummary
    available_assignees: list[AssigneeReference] = Field(default_factory=list)


class CaseAssignmentResponse(BaseModel):
    result: WorkManagementOperationResult
    ownership: OwnershipSummary
    history_entry: AssignmentHistoryEntry | None = None


class AssignmentHistoryResponse(BaseModel):
    case_id: CaseId
    history: list[AssignmentHistoryEntry] = Field(default_factory=list)


class CaseSLAResponse(BaseModel):
    result: WorkManagementOperationResult
    sla_target: SLATargetMetadata
    sla_state: SLAState


class CaseWorkStatusResponse(BaseModel):
    work_status: WorkStatusSummary
    available_assignees: list[AssigneeReference] = Field(default_factory=list)