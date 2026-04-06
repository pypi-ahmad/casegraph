"""Shared human validation and review contracts.

These types define the human-in-the-loop validation layer that sits
between machine-generated outputs (extraction results, readiness
evaluations) and downstream consumption (packets, workflows).

Operators use this layer to explicitly accept, correct, reject, or flag
machine outputs. The original machine values are always preserved —
validation records are overlays, not destructive rewrites.

This layer does not implement autonomous adjudication, truth resolution,
multi-reviewer governance, or validation confidence scoring.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.extraction import ExtractionId, GroundingReference
from casegraph_agent_sdk.readiness import ChecklistId, ChecklistItemId

# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

FieldValidationId = str
RequirementReviewId = str

# ---------------------------------------------------------------------------
# Status literals
# ---------------------------------------------------------------------------

FieldValidationStatus = Literal[
    "unreviewed",
    "accepted",
    "corrected",
    "rejected",
    "needs_followup",
]

RequirementReviewStatus = Literal[
    "unreviewed",
    "confirmed_supported",
    "confirmed_missing",
    "requires_more_information",
    "manually_overridden",
]

# ---------------------------------------------------------------------------
# Reviewer metadata
# ---------------------------------------------------------------------------


class ReviewerMetadata(BaseModel):
    """Identity and context for the human reviewer.

    Actor identity is not yet bound to authenticated sessions;
    reviewer_id is an operator-provided identifier.
    """

    reviewer_id: str = ""
    display_name: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Field validation records
# ---------------------------------------------------------------------------


class OriginalValueReference(BaseModel):
    """Snapshot of the machine-generated value at validation time."""

    value: Any = None
    raw_value: str | None = None
    is_present: bool = False
    grounding: list[GroundingReference] = Field(default_factory=list)


class FieldValidationRecord(BaseModel):
    """Human validation decision for a single extracted field."""

    validation_id: FieldValidationId
    extraction_id: ExtractionId
    field_id: str
    case_id: str = ""
    status: FieldValidationStatus = "unreviewed"
    original: OriginalValueReference = Field(default_factory=OriginalValueReference)
    reviewed_value: Any = None
    reviewer: ReviewerMetadata = Field(default_factory=ReviewerMetadata)
    note: str = ""
    created_at: str = ""
    updated_at: str = ""


class ValidateFieldRequest(BaseModel):
    """Request to validate a single extracted field."""

    status: FieldValidationStatus
    reviewed_value: Any = None
    note: str = ""
    reviewer_id: str = ""
    reviewer_display_name: str = ""


# ---------------------------------------------------------------------------
# Requirement review records
# ---------------------------------------------------------------------------


class RequirementReviewRecord(BaseModel):
    """Human review decision for a single checklist requirement item."""

    review_id: RequirementReviewId
    case_id: str
    checklist_id: ChecklistId
    item_id: ChecklistItemId
    status: RequirementReviewStatus = "unreviewed"
    original_machine_status: str = ""
    reviewer: ReviewerMetadata = Field(default_factory=ReviewerMetadata)
    note: str = ""
    linked_document_ids: list[str] = Field(default_factory=list)
    linked_extraction_ids: list[str] = Field(default_factory=list)
    linked_evidence_notes: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class ReviewRequirementRequest(BaseModel):
    """Request to record a human review decision for a requirement item."""

    status: RequirementReviewStatus
    note: str = ""
    reviewer_id: str = ""
    reviewer_display_name: str = ""
    linked_document_ids: list[str] = Field(default_factory=list)
    linked_extraction_ids: list[str] = Field(default_factory=list)
    linked_evidence_notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Reviewed case state projection
# ---------------------------------------------------------------------------


class FieldValidationSummary(BaseModel):
    """Extraction validation summary for a case."""

    total_fields: int = 0
    reviewed_fields: int = 0
    accepted_fields: int = 0
    corrected_fields: int = 0
    rejected_fields: int = 0
    needs_followup_fields: int = 0
    extraction_count: int = 0


class RequirementReviewSummary(BaseModel):
    """Requirement review summary for a case."""

    total_items: int = 0
    reviewed_items: int = 0
    confirmed_supported: int = 0
    confirmed_missing: int = 0
    requires_more_information: int = 0
    manually_overridden: int = 0
    unresolved_count: int = 0


class UnresolvedReviewItem(BaseModel):
    """A single unresolved item requiring operator attention."""

    item_type: Literal["field_validation", "requirement_review"]
    entity_id: str
    display_label: str = ""
    current_status: str = ""
    note: str = ""


class ReviewedCaseState(BaseModel):
    """Projection of the reviewed case state from raw outputs + validations.

    This is a non-destructive view — original machine state is preserved.
    The reviewed state reflects explicit operator decisions only.
    """

    case_id: str
    field_validation: FieldValidationSummary = Field(default_factory=FieldValidationSummary)
    requirement_review: RequirementReviewSummary = Field(default_factory=RequirementReviewSummary)
    unresolved_items: list[UnresolvedReviewItem] = Field(default_factory=list)
    has_reviewed_state: bool = False
    reviewed_at: str = ""


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------


class ExtractionValidationsResponse(BaseModel):
    """All field validation records for a case."""

    case_id: str
    validations: list[FieldValidationRecord] = Field(default_factory=list)


class RequirementReviewsResponse(BaseModel):
    """All requirement review records for a case."""

    case_id: str
    reviews: list[RequirementReviewRecord] = Field(default_factory=list)


class ReviewedCaseStateResponse(BaseModel):
    """Full reviewed case state projection."""

    state: ReviewedCaseState


class FieldValidationResponse(BaseModel):
    """Response after validating a field."""

    validation: FieldValidationRecord


class RequirementReviewResponse(BaseModel):
    """Response after reviewing a requirement."""

    review: RequirementReviewRecord
