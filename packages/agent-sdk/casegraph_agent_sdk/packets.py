"""Shared packet assembly and export contracts.

These types define the reviewable case packet layer: structured packaging
of case metadata, linked documents, extraction results, readiness state,
action items, review notes, and run summaries into an export-ready artifact.

This layer is an operational handoff preparation tool. It does not implement
external filing, portal submission, form filling, or regulatory compliance
verification. Packet contents are deterministic reflections of explicit
persisted case state.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.cases import CaseId, CaseStatus
from casegraph_agent_sdk.domains import CaseTypeTemplateId, DomainPackId
from casegraph_agent_sdk.ingestion import DocumentId
from casegraph_agent_sdk.operator_review import (
    ActionItemCategory,
    ActionItemPriority,
    ActionItemStatus,
    CaseStage,
    ReviewDecision,
)
from casegraph_agent_sdk.readiness import ChecklistItemId, ChecklistItemStatus, ReadinessStatus
from casegraph_agent_sdk.reviewed_handoff import DownstreamSourceMode, SignOffStatus

PacketId = str
ExportArtifactId = str

PacketStatus = Literal[
    "generated",
    "stale",
]

PacketSectionType = Literal[
    "case_summary",
    "domain_metadata",
    "linked_documents",
    "extraction_results",
    "readiness_summary",
    "open_actions",
    "review_notes",
    "run_history",
    "human_review_state",
    "reviewed_snapshot",
]

ExportArtifactFormat = Literal[
    "json_manifest",
    "markdown_summary",
]


class PacketGenerateRequest(BaseModel):
    note: str = ""
    source_mode: DownstreamSourceMode = "live_case_state"
    reviewed_snapshot_id: str = ""


class PacketDocumentEntry(BaseModel):
    document_id: DocumentId
    filename: str
    content_type: str | None = None
    page_count: int = 0
    linked_at: str = ""


class PacketExtractionEntry(BaseModel):
    extraction_id: str
    document_id: DocumentId | None = None
    template_id: str | None = None
    strategy_used: str | None = None
    status: str = ""
    field_count: int = 0
    fields_extracted: int = 0
    grounding_available: bool = False
    created_at: str = ""


class PacketReadinessEntry(BaseModel):
    checklist_item_id: ChecklistItemId
    requirement_id: str
    display_name: str
    priority: str = ""
    status: ChecklistItemStatus = "missing"
    linked_document_count: int = 0
    linked_extraction_count: int = 0


class PacketActionEntry(BaseModel):
    action_item_id: str
    category: ActionItemCategory
    priority: ActionItemPriority = "normal"
    status: ActionItemStatus = "open"
    title: str
    source_reason: str = ""


class PacketReviewNoteEntry(BaseModel):
    note_id: str
    body: str
    decision: ReviewDecision = "note_only"
    stage_snapshot: CaseStage = "intake"
    created_at: str = ""


class PacketRunSummaryEntry(BaseModel):
    run_id: str
    workflow_id: str
    status: str = ""
    created_at: str = ""
    updated_at: str = ""


class PacketSection(BaseModel):
    section_type: PacketSectionType
    title: str
    item_count: int = 0
    data: dict[str, Any] = Field(default_factory=dict)
    empty: bool = False


class PacketManifest(BaseModel):
    packet_id: PacketId
    case_id: CaseId
    source_mode: DownstreamSourceMode = "live_case_state"
    source_reviewed_snapshot_id: str = ""
    source_snapshot_signoff_status: SignOffStatus = "not_signed_off"
    source_snapshot_signed_off_at: str = ""
    source_snapshot_signed_off_by: str = ""
    case_title: str = ""
    case_status: CaseStatus = "open"
    current_stage: CaseStage = "intake"
    domain_pack_id: DomainPackId | None = None
    case_type_id: CaseTypeTemplateId | None = None
    readiness_status: ReadinessStatus | None = None
    linked_document_count: int = 0
    extraction_count: int = 0
    open_action_count: int = 0
    review_note_count: int = 0
    run_count: int = 0
    sections: list[PacketSection] = Field(default_factory=list)
    generated_at: str = ""
    note: str = ""


class ExportArtifact(BaseModel):
    artifact_id: ExportArtifactId
    packet_id: PacketId
    format: ExportArtifactFormat
    filename: str
    size_bytes: int = 0
    content_type: str = ""
    created_at: str = ""


class PacketSummary(BaseModel):
    packet_id: PacketId
    case_id: CaseId
    source_mode: DownstreamSourceMode = "live_case_state"
    source_reviewed_snapshot_id: str = ""
    case_title: str = ""
    current_stage: CaseStage = "intake"
    readiness_status: ReadinessStatus | None = None
    section_count: int = 0
    artifact_count: int = 0
    generated_at: str = ""
    note: str = ""


class PacketGenerationResult(BaseModel):
    success: bool = True
    message: str = ""
    packet: PacketSummary | None = None


class PacketListResponse(BaseModel):
    packets: list[PacketSummary] = Field(default_factory=list)


class PacketDetailResponse(BaseModel):
    packet: PacketSummary
    manifest: PacketManifest


class PacketManifestResponse(BaseModel):
    manifest: PacketManifest


class PacketArtifactListResponse(BaseModel):
    artifacts: list[ExportArtifact] = Field(default_factory=list)


class PacketGenerateResponse(BaseModel):
    result: PacketGenerationResult
    packet: PacketSummary | None = None
    artifacts: list[ExportArtifact] = Field(default_factory=list)
