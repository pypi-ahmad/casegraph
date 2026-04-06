"""Reviewed snapshot, sign-off, and release-gate contracts.

These contracts define the explicit reviewed handoff layer between
human validation and downstream packet / submission / automation
consumption. A reviewed snapshot is an immutable, persisted checkpoint
of current reviewed field and requirement state.

This layer does not implement compliance certification, multi-party
approvals, authoritative release governance, or external readiness
guarantees.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.human_validation import (
    FieldValidationStatus,
    OriginalValueReference,
    RequirementReviewStatus,
)
from casegraph_agent_sdk.readiness import ChecklistId, ChecklistItemId


ReviewedSnapshotId = str
SignOffRecordId = str
SignOffNote = str


ReviewedSnapshotStatus = Literal[
    "created",
    "selected_for_handoff",
    "archived_placeholder",
]

SignOffStatus = Literal[
    "not_signed_off",
    "signed_off",
    "revoked_placeholder",
]

DownstreamSourceMode = Literal[
    "live_case_state",
    "reviewed_snapshot",
]

ReleaseGateStatus = Literal[
    "eligible_with_current_rules",
    "blocked_no_reviewed_snapshot",
    "blocked_missing_signoff",
    "blocked_unresolved_review_items",
    "blocked_required_requirement_reviews_incomplete",
]

ReviewedHandoffIssueSeverity = Literal["info", "warning", "error"]


class ReviewedSnapshotSourceMetadata(BaseModel):
    """Source references used to build a reviewed snapshot."""

    case_id: str
    linked_document_ids: list[str] = Field(default_factory=list)
    extraction_ids: list[str] = Field(default_factory=list)
    validation_record_ids: list[str] = Field(default_factory=list)
    checklist_id: ChecklistId | None = None
    requirement_review_ids: list[str] = Field(default_factory=list)
    reviewed_state_timestamp: str = ""


class ReviewedSnapshotSummary(BaseModel):
    """Summary counts for an immutable reviewed snapshot."""

    total_fields: int = 0
    included_fields: int = 0
    accepted_fields: int = 0
    corrected_fields: int = 0
    total_requirements: int = 0
    reviewed_requirements: int = 0
    required_requirement_reviews_complete: bool = False
    unresolved_item_count: int = 0


class ReviewedFieldEntry(BaseModel):
    """Single reviewed field entry preserved inside a snapshot."""

    extraction_id: str
    document_id: str | None = None
    field_id: str
    field_type: str
    validation_id: str = ""
    validation_status: FieldValidationStatus = "unreviewed"
    original: OriginalValueReference = Field(default_factory=OriginalValueReference)
    reviewed_value: Any = None
    snapshot_value: Any = None
    included_in_snapshot: bool = False
    note: str = ""


class ReviewedRequirementEntry(BaseModel):
    """Single reviewed requirement entry preserved inside a snapshot."""

    checklist_id: ChecklistId
    item_id: ChecklistItemId
    requirement_id: str = ""
    display_name: str = ""
    priority: str = ""
    machine_status: str = ""
    review_id: str = ""
    review_status: RequirementReviewStatus = "unreviewed"
    included_in_snapshot: bool = False
    note: str = ""
    linked_document_ids: list[str] = Field(default_factory=list)
    linked_extraction_ids: list[str] = Field(default_factory=list)


class UnresolvedReviewItemSummary(BaseModel):
    """Snapshot-preserved unresolved item summary."""

    item_type: Literal["field_validation", "requirement_review"]
    entity_id: str
    display_label: str = ""
    current_status: str = ""
    note: str = ""


class SignOffActorMetadata(BaseModel):
    """Operator metadata recorded at snapshot sign-off time."""

    actor_id: str = ""
    display_name: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SnapshotSignOffRecord(BaseModel):
    """Explicit operator sign-off record for a reviewed snapshot."""

    signoff_id: SignOffRecordId
    snapshot_id: ReviewedSnapshotId
    case_id: str
    status: SignOffStatus = "signed_off"
    actor: SignOffActorMetadata = Field(default_factory=SignOffActorMetadata)
    note: SignOffNote = ""
    created_at: str = ""


class ReleaseGateReason(BaseModel):
    """Single descriptive handoff gate reason."""

    code: str
    message: str
    blocking: bool = True


class HandoffEligibilitySummary(BaseModel):
    """Current descriptive release / handoff eligibility view."""

    case_id: str
    snapshot_id: str = ""
    selected_snapshot_id: str = ""
    has_reviewed_snapshot: bool = False
    snapshot_status: ReviewedSnapshotStatus | None = None
    signoff_status: SignOffStatus = "not_signed_off"
    unresolved_review_item_count: int = 0
    required_requirement_reviews_complete: bool = False
    release_gate_status: ReleaseGateStatus = "blocked_no_reviewed_snapshot"
    eligible: bool = False
    reasons: list[ReleaseGateReason] = Field(default_factory=list)


class ReviewedHandoffIssue(BaseModel):
    severity: ReviewedHandoffIssueSeverity = "info"
    code: str
    message: str
    related_entity_type: str | None = None
    related_entity_id: str | None = None


class ReviewedHandoffOperationResult(BaseModel):
    success: bool = True
    message: str = ""
    issues: list[ReviewedHandoffIssue] = Field(default_factory=list)


class ReviewedSnapshotRecord(BaseModel):
    """Immutable reviewed snapshot artifact."""

    snapshot_id: ReviewedSnapshotId
    case_id: str
    status: ReviewedSnapshotStatus = "created"
    summary: ReviewedSnapshotSummary = Field(default_factory=ReviewedSnapshotSummary)
    source_metadata: ReviewedSnapshotSourceMetadata
    fields: list[ReviewedFieldEntry] = Field(default_factory=list)
    requirements: list[ReviewedRequirementEntry] = Field(default_factory=list)
    unresolved_items: list[UnresolvedReviewItemSummary] = Field(default_factory=list)
    signoff_status: SignOffStatus = "not_signed_off"
    signoff: SnapshotSignOffRecord | None = None
    note: str = ""
    created_at: str = ""
    selected_at: str = ""


class CreateReviewedSnapshotRequest(BaseModel):
    note: str = ""
    operator_id: str = ""
    operator_display_name: str = ""


class SignOffReviewedSnapshotRequest(BaseModel):
    operator_id: str = ""
    operator_display_name: str = ""
    note: SignOffNote = ""


class ReviewedSnapshotListResponse(BaseModel):
    case_id: str
    snapshots: list[ReviewedSnapshotRecord] = Field(default_factory=list)


class ReviewedSnapshotResponse(BaseModel):
    snapshot: ReviewedSnapshotRecord


class ReviewedSnapshotCreateResponse(BaseModel):
    result: ReviewedHandoffOperationResult
    snapshot: ReviewedSnapshotRecord


class ReviewedSnapshotSignOffResponse(BaseModel):
    result: ReviewedHandoffOperationResult
    snapshot: ReviewedSnapshotRecord
    signoff: SnapshotSignOffRecord


class ReviewedSnapshotSelectResponse(BaseModel):
    result: ReviewedHandoffOperationResult
    snapshot: ReviewedSnapshotRecord


class HandoffEligibilityResponse(BaseModel):
    eligibility: HandoffEligibilitySummary