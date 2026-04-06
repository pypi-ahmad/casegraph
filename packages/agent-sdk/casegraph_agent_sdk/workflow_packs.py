"""Shared workflow pack contracts for domain-specific orchestrated workflows.

A workflow pack is a structured, multi-stage orchestration that composes
existing case, document, extraction, readiness, packet, and submission-draft
foundations into a reviewable end-to-end operational workflow for a specific
domain case type.

Workflow packs are not rules engines, clinical decision support systems,
payer adjudication tools, or autonomous submission pipelines. They are
explicit, operator-centric sequences that surface structured state for
human review and decision-making.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.domains import (
    CaseTypeTemplateId,
    DomainCategory,
    DomainPackId,
    Jurisdiction,
)
from casegraph_agent_sdk.operator_review import CaseStage
from casegraph_agent_sdk.readiness import ReadinessStatus

# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

WorkflowPackId = str
WorkflowPackRunId = str

# ---------------------------------------------------------------------------
# Status literals
# ---------------------------------------------------------------------------

WorkflowPackStageStatus = Literal[
    "not_started",
    "completed",
    "completed_partial",
    "skipped",
    "blocked",
    "failed",
]

WorkflowPackRunStatus = Literal[
    "created",
    "running",
    "completed",
    "completed_partial",
    "blocked",
    "failed",
]

# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------

WorkflowPackStageId = Literal[
    "intake_document_check",
    "extraction_pass",
    "checklist_refresh",
    "readiness_evaluation",
    "action_generation",
    "packet_assembly",
    "submission_draft_preparation",
    "human_review_check",
]


class WorkflowPackStageDefinition(BaseModel):
    """Definition of a single stage in a workflow pack."""

    stage_id: WorkflowPackStageId
    display_name: str
    description: str = ""
    optional: bool = False
    depends_on: list[WorkflowPackStageId] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage result summaries
# ---------------------------------------------------------------------------


class IntakeDocumentCheckSummary(BaseModel):
    """Summary of the intake document linkage check."""

    linked_document_count: int = 0
    required_document_count: int = 0
    missing_categories: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ExtractionPassSummary(BaseModel):
    """Summary of persisted extraction runs linked to the case documents."""

    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    skipped_runs: int = 0
    extracted_field_count: int = 0
    extraction_run_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ChecklistRefreshSummary(BaseModel):
    """Summary of checklist generation or refresh."""

    checklist_generated: bool = False
    checklist_id: str = ""
    total_items: int = 0
    notes: list[str] = Field(default_factory=list)


class ReadinessEvaluationSummary(BaseModel):
    """Summary of readiness evaluation results."""

    readiness_status: str = "not_evaluated"
    total_items: int = 0
    supported_items: int = 0
    missing_items: int = 0
    partially_supported_items: int = 0
    missing_required_names: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ActionGenerationSummary(BaseModel):
    """Summary of follow-up action generation."""

    total_actions: int = 0
    open_actions: int = 0
    high_priority_actions: int = 0
    action_categories: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PacketAssemblySummary(BaseModel):
    """Summary of packet assembly results."""

    packet_generated: bool = False
    packet_id: str = ""
    artifact_count: int = 0
    skipped_reason: str = ""
    notes: list[str] = Field(default_factory=list)


class SubmissionDraftPreparationSummary(BaseModel):
    """Summary of submission draft preparation results."""

    draft_generated: bool = False
    draft_id: str = ""
    plan_generated: bool = False
    plan_id: str = ""
    skipped_reason: str = ""
    notes: list[str] = Field(default_factory=list)


class HumanReviewCheckSummary(BaseModel):
    """Summary of the human review state check."""

    has_reviewed_state: bool = False
    reviewed_fields: int = 0
    total_fields: int = 0
    reviewed_requirements: int = 0
    total_requirements: int = 0
    unresolved_count: int = 0
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage result
# ---------------------------------------------------------------------------


class WorkflowPackStageResult(BaseModel):
    """Result of executing a single stage in a workflow pack run."""

    stage_id: WorkflowPackStageId
    status: WorkflowPackStageStatus = "not_started"
    display_name: str = ""
    started_at: str = ""
    completed_at: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Operator review recommendation
# ---------------------------------------------------------------------------


class OperatorReviewRecommendation(BaseModel):
    """Structured recommendation for the human operator after a workflow run.

    This is a deterministic summary of explicit state, not a clinical
    or regulatory recommendation.
    """

    has_missing_required_documents: bool = False
    has_open_high_priority_actions: bool = False
    has_failed_stages: bool = False
    readiness_status: ReadinessStatus = "not_evaluated"
    suggested_next_stage: CaseStage = "document_review"
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Workflow pack metadata and definition
# ---------------------------------------------------------------------------


class WorkflowPackMetadata(BaseModel):
    """Metadata for a registered workflow pack."""

    workflow_pack_id: WorkflowPackId
    display_name: str
    description: str = ""
    version: str = "0.1.0"
    domain_pack_id: DomainPackId
    domain_category: DomainCategory
    jurisdiction: Jurisdiction
    compatible_case_type_ids: list[CaseTypeTemplateId] = Field(default_factory=list)
    stage_count: int = 0
    limitations: list[str] = Field(default_factory=list)


class WorkflowPackDefinition(BaseModel):
    """Full workflow pack definition including stage sequence."""

    metadata: WorkflowPackMetadata
    stages: list[WorkflowPackStageDefinition] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Execution request and result
# ---------------------------------------------------------------------------


class WorkflowPackExecutionRequest(BaseModel):
    """Request to execute a workflow pack against a case."""

    case_id: str
    workflow_pack_id: WorkflowPackId
    operator_id: str = ""
    skip_optional_stages: bool = False
    notes: list[str] = Field(default_factory=list)


class WorkflowPackRunRecord(BaseModel):
    """Full record of a workflow pack run."""

    run_id: WorkflowPackRunId
    case_id: str
    workflow_pack_id: WorkflowPackId
    status: WorkflowPackRunStatus = "created"
    operator_id: str = ""
    stage_results: list[WorkflowPackStageResult] = Field(default_factory=list)
    review_recommendation: OperatorReviewRecommendation = Field(
        default_factory=OperatorReviewRecommendation
    )
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API responses
# ---------------------------------------------------------------------------


class WorkflowPackListResponse(BaseModel):
    """Response listing available workflow packs."""

    packs: list[WorkflowPackMetadata] = Field(default_factory=list)


class WorkflowPackDetailResponse(BaseModel):
    """Detailed response for a single workflow pack."""

    definition: WorkflowPackDefinition


class WorkflowPackRunResponse(BaseModel):
    """Response after executing a workflow pack."""

    success: bool = False
    message: str = ""
    run: WorkflowPackRunRecord


class WorkflowPackRunSummaryResponse(BaseModel):
    """Summary of a completed or in-progress workflow pack run."""

    run: WorkflowPackRunRecord
    case_title: str = ""
    domain_pack_display_name: str = ""
