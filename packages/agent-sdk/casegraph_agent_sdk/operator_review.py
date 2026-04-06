"""Shared operator review, stage lifecycle, and queue contracts.

These types define the human review / operations layer that sits on top
of cases, readiness, linked documents, extraction results, and workflow
run metadata.

This layer is intentionally deterministic and operator-centric. It does
not implement automated approvals, denials, payer rules, filing logic,
or domain-specific decision engines.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.cases import CaseId, CaseStatus, NormalizedOperationError
from casegraph_agent_sdk.domains import CaseTypeTemplateId, DomainPackId
from casegraph_agent_sdk.ingestion import DocumentId
from casegraph_agent_sdk.readiness import ChecklistItemId, ReadinessStatus

StageTransitionId = str
ActionItemId = str
ReviewNoteId = str

CaseStage = Literal[
    "intake",
    "document_review",
    "readiness_review",
    "awaiting_documents",
    "ready_for_next_step",
    "closed_placeholder",
]

ActionItemCategory = Literal[
    "missing_document",
    "needs_review",
    "extraction_followup",
    "evidence_gap",
    "run_followup",
    "document_linking_needed",
]

ActionItemSource = Literal[
    "case",
    "checklist_item",
    "workflow_run",
    "extraction_run",
]

ActionItemPriority = Literal["normal", "high"]

ActionItemStatus = Literal["open", "resolved"]

ReviewDecision = Literal[
    "note_only",
    "follow_up_required",
    "ready_for_next_step",
    "hold",
    "close_placeholder",
]


class OperatorOperationResult(BaseModel):
    success: bool = True
    message: str = ""
    error: NormalizedOperationError | None = None


class StageTransitionMetadata(BaseModel):
    transition_type: Literal["manual"] = "manual"
    reason: str = ""
    note: str = ""


class CaseStageState(BaseModel):
    case_id: CaseId
    current_stage: CaseStage = "intake"
    allowed_transitions: list[CaseStage] = Field(default_factory=list)
    updated_at: str = ""


class StageTransitionRecord(BaseModel):
    transition_id: StageTransitionId
    case_id: CaseId
    from_stage: CaseStage
    to_stage: CaseStage
    metadata: StageTransitionMetadata
    created_at: str


class ActionItem(BaseModel):
    action_item_id: ActionItemId
    case_id: CaseId
    category: ActionItemCategory
    source: ActionItemSource
    priority: ActionItemPriority = "normal"
    status: ActionItemStatus = "open"
    title: str
    description: str = ""
    source_reason: str = ""
    checklist_item_id: ChecklistItemId | None = None
    document_id: DocumentId | None = None
    extraction_id: str | None = None
    run_id: str | None = None
    created_at: str
    updated_at: str
    resolved_at: str | None = None


class ReviewNote(BaseModel):
    note_id: ReviewNoteId
    case_id: CaseId
    body: str
    decision: ReviewDecision = "note_only"
    related_action_item_id: ActionItemId | None = None
    stage_snapshot: CaseStage = "intake"
    created_at: str


class OperatorActionSummary(BaseModel):
    case_id: CaseId
    detected_count: int = 0
    generated_count: int = 0
    reopened_count: int = 0
    resolved_count: int = 0
    open_count: int = 0


class QueueFilterMetadata(BaseModel):
    stage: CaseStage | None = None
    has_missing_items: bool | None = None
    has_open_actions: bool | None = None
    domain_pack_id: DomainPackId | None = None
    case_type_id: CaseTypeTemplateId | None = None
    limit: int = 100


class ReviewQueueItem(BaseModel):
    case_id: CaseId
    title: str
    case_status: CaseStatus
    current_stage: CaseStage
    domain_pack_id: DomainPackId | None = None
    case_type_id: CaseTypeTemplateId | None = None
    readiness_status: ReadinessStatus | None = None
    linked_document_count: int = 0
    open_action_count: int = 0
    detected_action_count: int = 0
    missing_required_count: int = 0
    needs_review_count: int = 0
    failed_run_count: int = 0
    has_open_actions: bool = False
    has_missing_items: bool = False
    attention_categories: list[ActionItemCategory] = Field(default_factory=list)
    last_activity_at: str = ""


class QueueStageCount(BaseModel):
    stage: CaseStage
    case_count: int = 0


class QueueSummary(BaseModel):
    total_cases: int = 0
    cases_with_open_actions: int = 0
    cases_with_missing_items: int = 0
    cases_needing_attention: int = 0
    stage_counts: list[QueueStageCount] = Field(default_factory=list)


class GenerateActionItemsRequest(BaseModel):
    pass


class UpdateCaseStageRequest(BaseModel):
    new_stage: CaseStage
    reason: str | None = None
    note: str | None = None


class CreateReviewNoteRequest(BaseModel):
    body: str
    decision: ReviewDecision = "note_only"
    related_action_item_id: ActionItemId | None = None


class ReviewQueueResponse(BaseModel):
    filters: QueueFilterMetadata
    items: list[ReviewQueueItem] = Field(default_factory=list)


class QueueSummaryResponse(BaseModel):
    filters: QueueFilterMetadata
    summary: QueueSummary


class CaseActionListResponse(BaseModel):
    actions: list[ActionItem] = Field(default_factory=list)


class ReviewNoteListResponse(BaseModel):
    notes: list[ReviewNote] = Field(default_factory=list)


class StageHistoryResponse(BaseModel):
    transitions: list[StageTransitionRecord] = Field(default_factory=list)


class CaseStageResponse(BaseModel):
    stage: CaseStageState


class ActionGenerationResponse(BaseModel):
    result: OperatorOperationResult
    summary: OperatorActionSummary
    actions: list[ActionItem] = Field(default_factory=list)


class StageTransitionResponse(BaseModel):
    result: OperatorOperationResult
    stage: CaseStageState
    transition: StageTransitionRecord


class ReviewNoteResponse(BaseModel):
    result: OperatorOperationResult
    note: ReviewNote