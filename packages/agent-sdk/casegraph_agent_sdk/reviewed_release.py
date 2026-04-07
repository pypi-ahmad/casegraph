"""Reviewed release bundle contracts.

These contracts define the explicit release/handoff packaging layer
that turns signed-off reviewed snapshots into stable downstream
artifact bundles.

A release bundle is a frozen collection of downstream artifacts
(packets, submission drafts, communication drafts, automation plan
metadata) derived from a specific reviewed snapshot at a specific
point in time. Once a bundle is created, its content does not change
even if the underlying case state evolves.

This layer does not implement compliance certification, external
delivery, regulatory filing, authoritative approval workflows,
or autonomous release decisions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.reviewed_handoff import (
    DownstreamSourceMode,
    ReviewedSnapshotId,
    SignOffRecordId,
    SignOffStatus,
)
from casegraph_agent_sdk.target_packs import CaseTargetPackSelection

ReleaseBundleId = str
ReleaseArtifactId = str

ReleaseBundleStatus = Literal[
    "created",
    "incomplete",
    "superseded_placeholder",
    "archived_placeholder",
]

ReleaseArtifactType = Literal[
    "reviewed_packet",
    "reviewed_submission_draft",
    "reviewed_communication_draft",
    "reviewed_automation_plan",
]

ReleaseArtifactStatus = Literal[
    "generated",
    "skipped_missing_data",
    "blocked",
    "failed",
]

ReleaseBlockingReasonCode = Literal[
    "no_reviewed_snapshot",
    "missing_signoff",
    "unresolved_review_items",
    "required_requirement_reviews_incomplete",
]

ReleaseIssueSeverity = Literal["info", "warning", "error"]


class ReleaseBundleSourceMetadata(BaseModel):
    """Provenance metadata linking a release bundle to its source."""

    case_id: str
    snapshot_id: ReviewedSnapshotId
    signoff_id: SignOffRecordId = ""
    signoff_status: SignOffStatus = "not_signed_off"
    signed_off_by: str = ""
    signed_off_at: str = ""
    snapshot_created_at: str = ""
    snapshot_included_fields: int = 0
    snapshot_corrected_fields: int = 0
    snapshot_reviewed_requirements: int = 0
    snapshot_unresolved_item_count: int = 0
    target_pack_selection: CaseTargetPackSelection | None = None


class ReleaseArtifactEntry(BaseModel):
    """Reference to a downstream artifact included in a release bundle."""

    artifact_ref_id: ReleaseArtifactId
    artifact_type: ReleaseArtifactType
    downstream_artifact_id: str = ""
    status: ReleaseArtifactStatus = "generated"
    display_label: str = ""
    source_mode: DownstreamSourceMode = "reviewed_snapshot"
    source_snapshot_id: ReviewedSnapshotId = ""
    release_bundle_id: ReleaseBundleId = ""
    notes: list[str] = Field(default_factory=list)
    created_at: str = ""


class ReleaseBundleSummary(BaseModel):
    """Summary counts for a release bundle."""

    total_artifacts: int = 0
    generated_artifacts: int = 0
    skipped_artifacts: int = 0
    blocked_artifacts: int = 0
    failed_artifacts: int = 0


class ReleaseBlockingReason(BaseModel):
    """Single blocking reason preventing release creation."""

    code: ReleaseBlockingReasonCode
    message: str
    blocking: bool = True


class ReleaseEligibilitySummary(BaseModel):
    """Current descriptive release eligibility view."""

    case_id: str
    snapshot_id: str = ""
    signoff_status: SignOffStatus = "not_signed_off"
    eligible: bool = False
    reasons: list[ReleaseBlockingReason] = Field(default_factory=list)


class ReleaseIssue(BaseModel):
    severity: ReleaseIssueSeverity = "info"
    code: str
    message: str
    related_artifact_type: ReleaseArtifactType | None = None
    related_artifact_id: str | None = None


class ReleaseOperationResult(BaseModel):
    success: bool = True
    message: str = ""
    issues: list[ReleaseIssue] = Field(default_factory=list)


class ReleaseBundleRecord(BaseModel):
    """Persisted release bundle artifact."""

    release_id: ReleaseBundleId
    case_id: str
    status: ReleaseBundleStatus = "created"
    source: ReleaseBundleSourceMetadata
    summary: ReleaseBundleSummary = Field(default_factory=ReleaseBundleSummary)
    artifacts: list[ReleaseArtifactEntry] = Field(default_factory=list)
    note: str = ""
    created_by: str = ""
    created_at: str = ""


class CreateReleaseBundleRequest(BaseModel):
    snapshot_id: ReviewedSnapshotId = ""
    note: str = ""
    operator_id: str = ""
    operator_display_name: str = ""
    generate_packet: bool = True
    generate_submission_draft: bool = True
    generate_communication_draft: bool = True
    include_automation_plan_metadata: bool = True


class ReleaseBundleCreateResponse(BaseModel):
    result: ReleaseOperationResult
    release: ReleaseBundleRecord


class ReleaseBundleResponse(BaseModel):
    release: ReleaseBundleRecord


class ReleaseBundleListResponse(BaseModel):
    case_id: str
    releases: list[ReleaseBundleRecord] = Field(default_factory=list)


class ReleaseArtifactListResponse(BaseModel):
    release_id: ReleaseBundleId
    artifacts: list[ReleaseArtifactEntry] = Field(default_factory=list)


class ReleaseEligibilityResponse(BaseModel):
    eligibility: ReleaseEligibilitySummary
