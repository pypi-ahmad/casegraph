"""Audit, decision ledger, and artifact lineage contracts.

These contracts describe local-first operational traceability. They do
not claim compliance archiving, WORM storage, notarization, or formal
immutability guarantees.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


AuditEventId = str
DecisionLedgerEntryId = str
LineageRecordId = str
LineageEdgeId = str


AuditEventCategory = Literal[
    "case",
    "work_management",
    "checklist",
    "review",
    "extraction",
    "packet",
    "submission_draft",
    "automation",
    "workflow_run",
    "communication",
    "human_validation",
    "reviewed_handoff",
    "reviewed_release",
]

AuditEventType = Literal[
    "case_created",
    "case_updated",
    "case_assignment_updated",
    "case_sla_updated",
    "case_document_linked",
    "case_stage_transitioned",
    "checklist_generated",
    "checklist_evaluated",
    "review_note_added",
    "extraction_completed",
    "packet_generated",
    "submission_draft_created",
    "submission_approval_updated",
    "automation_plan_generated",
    "automation_run_created",
    "automation_checkpoint_decided",
    "communication_draft_generated",
    "communication_draft_review_updated",
    "workflow_pack_run_completed",
    "field_validation_recorded",
    "requirement_review_recorded",
    "reviewed_snapshot_created",
    "reviewed_snapshot_signed_off",
    "reviewed_snapshot_selected_for_handoff",
    "release_bundle_created",
]

AuditActorType = Literal[
    "operator",
    "service",
    "system",
    "workflow_pack",
    "automation",
]

DecisionType = Literal[
    "stage_transition",
    "review_note_added",
    "case_assignment_updated",
    "case_sla_updated",
    "checklist_evaluated",
    "packet_generated",
    "draft_approval_updated",
    "checkpoint_approved",
    "checkpoint_skipped",
    "checkpoint_blocked",
    "workflow_pack_completed",
    "communication_draft_generated",
    "communication_draft_review_updated",
    "automation_plan_generated",
    "field_validated",
    "requirement_reviewed",
    "reviewed_snapshot_signed_off",
    "release_bundle_created",
]

ArtifactType = Literal[
    "case",
    "document",
    "checklist",
    "workflow_run",
    "workflow_pack_run",
    "extraction_run",
    "packet",
    "submission_draft",
    "automation_plan",
    "automation_run",
    "communication_draft",
    "reviewed_snapshot",
    "release_bundle",
]

LineageRelationshipType = Literal[
    "case_context",
    "document_source",
    "checklist_reference",
    "workflow_reference",
    "workflow_pack_reference",
    "extraction_source",
    "packet_source",
    "snapshot_source",
    "draft_source",
    "plan_source",
    "run_source",
    "release_bundle_source",
]


class AuditActorMetadata(BaseModel):
    actor_type: AuditActorType
    actor_id: str = ""
    display_name: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditableEntityReference(BaseModel):
    entity_type: str
    entity_id: str
    case_id: str = ""
    display_label: str = ""
    source_path: str = ""


class FieldChangeRecord(BaseModel):
    field_path: str
    old_value: Any = None
    new_value: Any = None


class ChangeSummary(BaseModel):
    message: str = ""
    field_changes: list[FieldChangeRecord] = Field(default_factory=list)


class SourceArtifactReference(BaseModel):
    artifact_type: ArtifactType
    artifact_id: str
    case_id: str = ""
    display_label: str = ""
    source_path: str = ""


class DerivedArtifactReference(BaseModel):
    artifact_type: ArtifactType
    artifact_id: str
    case_id: str = ""
    display_label: str = ""


class AuditEventRecord(BaseModel):
    event_id: AuditEventId
    case_id: str
    category: AuditEventCategory
    event_type: AuditEventType
    actor: AuditActorMetadata
    entity: AuditableEntityReference
    change_summary: ChangeSummary = Field(default_factory=ChangeSummary)
    decision_ids: list[DecisionLedgerEntryId] = Field(default_factory=list)
    related_entities: list[AuditableEntityReference] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class DecisionLedgerEntry(BaseModel):
    decision_id: DecisionLedgerEntryId
    case_id: str
    decision_type: DecisionType
    actor: AuditActorMetadata
    source_entity: AuditableEntityReference
    outcome: str = ""
    reason: str = ""
    note: str = ""
    related_event_id: AuditEventId = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class LineageEdge(BaseModel):
    edge_id: LineageEdgeId
    relationship_type: LineageRelationshipType
    source: SourceArtifactReference
    derived: DerivedArtifactReference
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class LineageRecord(BaseModel):
    record_id: LineageRecordId
    case_id: str
    artifact: DerivedArtifactReference
    edges: list[LineageEdge] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class AuditFilterMetadata(BaseModel):
    categories: list[AuditEventCategory] = Field(default_factory=list)
    event_types: list[AuditEventType] = Field(default_factory=list)
    actor_types: list[AuditActorType] = Field(default_factory=list)


class AuditErrorInfo(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class AuditOperationResult(BaseModel):
    success: bool = False
    message: str = ""
    error: AuditErrorInfo | None = None


class AuditTimelineResponse(BaseModel):
    case_id: str
    events: list[AuditEventRecord] = Field(default_factory=list)
    filters: AuditFilterMetadata = Field(default_factory=AuditFilterMetadata)


class DecisionLedgerResponse(BaseModel):
    case_id: str
    decisions: list[DecisionLedgerEntry] = Field(default_factory=list)


class LineageResponse(BaseModel):
    case_id: str
    records: list[LineageRecord] = Field(default_factory=list)


class ArtifactLineageResponse(BaseModel):
    artifact_type: ArtifactType
    artifact_id: str
    record: LineageRecord | None = None