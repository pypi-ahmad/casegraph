"""Shared submission draft and automation planning contracts.

This layer defines reviewable, approval-gated metadata between packet assembly
and any future live submission automation. It does not implement real portal
posting, payer-specific rules, regulatory filing logic, browser writes, or
 autonomous submission execution.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.cases import CaseId
from casegraph_agent_sdk.domains import CaseTypeTemplateId, DomainPackId
from casegraph_agent_sdk.packets import PacketId, PacketSectionType
from casegraph_agent_sdk.readiness import ReadinessStatus
from casegraph_agent_sdk.reviewed_handoff import DownstreamSourceMode, SignOffStatus
from casegraph_agent_sdk.target_packs import CaseTargetPackSelection, TargetAutomationCompatibility

SubmissionTargetId = str
SubmissionDraftId = str
SubmissionMappingId = str
AutomationPlanId = str

AutomationExecutionMode = Literal[
    "playwright_mcp",
    "computer_use_fallback",
    "manual_only",
    "blocked",
]

SubmissionTargetCategory = Literal[
    "portal_submission",
    "form_packet_export",
    "internal_handoff_packet",
]

SubmissionDraftStatus = Literal[
    "draft_created",
    "mapping_incomplete",
    "awaiting_operator_review",
    "approved_for_future_execution",
    "blocked",
    "superseded_placeholder",
]

SubmissionSourceEntityType = Literal[
    "case",
    "case_metadata",
    "packet_manifest",
    "packet_section",
    "document",
    "extraction",
    "readiness",
    "reviewed_snapshot",
]

SubmissionMappingStatus = Literal[
    "unresolved",
    "candidate_available",
    "mapped_preview",
    "requires_human_input",
]

AutomationPlanStepType = Literal[
    "open_target",
    "navigate_section",
    "populate_field_placeholder",
    "attach_document_placeholder",
    "review_before_submit",
    "submit_blocked_placeholder",
]

AutomationPlanStatus = Literal[
    "draft",
    "partial",
    "awaiting_operator_review",
    "approved_for_future_execution",
    "blocked",
]

AutomationPlanStepStatus = Literal[
    "informational",
    "future_automation_placeholder",
    "requires_human_input",
    "blocked",
]

ApprovalStatus = Literal[
    "not_requested",
    "awaiting_operator_review",
    "approved_for_future_execution",
    "rejected",
]

ResultIssueSeverity = Literal["info", "warning", "error"]


class SubmissionMappingSourceReference(BaseModel):
    source_entity_type: SubmissionSourceEntityType
    source_entity_id: str = ""
    source_path: str = ""
    display_label: str = ""


class SubmissionMappingTargetField(BaseModel):
    field_name: str
    target_section: str = ""
    display_label: str = ""
    field_type: str = "text"
    required: bool = False
    candidate_source_paths: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SubmissionFieldValuePreview(BaseModel):
    value_present: bool = False
    text_value: str = ""
    raw_value: Any = None
    source_reference: SubmissionMappingSourceReference | None = None
    notes: list[str] = Field(default_factory=list)


class SubmissionMappingFieldDefinition(BaseModel):
    mapping_id: SubmissionMappingId
    target_field: SubmissionMappingTargetField
    status: SubmissionMappingStatus = "unresolved"
    source_reference: SubmissionMappingSourceReference | None = None
    value_preview: SubmissionFieldValuePreview | None = None
    notes: list[str] = Field(default_factory=list)


class SubmissionTargetMetadata(BaseModel):
    target_id: SubmissionTargetId
    category: SubmissionTargetCategory
    display_name: str
    description: str = ""
    notes: list[str] = Field(default_factory=list)
    supported_domain_pack_ids: list[DomainPackId] = Field(default_factory=list)
    supported_case_type_ids: list[CaseTypeTemplateId] = Field(default_factory=list)
    supports_field_mapping: bool = True
    supports_file_attachments: bool = True
    supports_dry_run_preview: bool = True
    supports_live_submission: bool = False
    default_backend_ids: list[str] = Field(default_factory=list)
    default_target_fields: list[SubmissionMappingTargetField] = Field(default_factory=list)


class SubmissionTargetListResponse(BaseModel):
    targets: list[SubmissionTargetMetadata] = Field(default_factory=list)


class SubmissionDraftSourceMetadata(BaseModel):
    packet_id: PacketId
    source_mode: DownstreamSourceMode = "live_case_state"
    source_reviewed_snapshot_id: str = ""
    source_snapshot_signoff_status: SignOffStatus = "not_signed_off"
    source_snapshot_signed_off_at: str = ""
    source_snapshot_signed_off_by: str = ""
    packet_generated_at: str = ""
    domain_pack_id: DomainPackId | None = None
    case_type_id: CaseTypeTemplateId | None = None
    readiness_status: ReadinessStatus | None = None
    linked_document_count: int = 0
    extraction_count: int = 0
    candidate_source_count: int = 0
    source_sections: list[PacketSectionType] = Field(default_factory=list)
    target_pack_selection: CaseTargetPackSelection | None = None


class ApprovalRequirementMetadata(BaseModel):
    requires_operator_approval: bool = True
    approval_status: ApprovalStatus = "not_requested"
    approved_by: str = ""
    approved_at: str = ""
    approval_note: str = ""
    scope: str = "future_execution"


class ExecutionGuardrailMetadata(BaseModel):
    requires_operator_approval: bool = True
    approval_status: ApprovalStatus = "not_requested"
    browser_write_actions_blocked: bool = True
    live_submission_blocked: bool = True
    allowed_backend_ids: list[str] = Field(default_factory=list)
    allowed_tool_ids: list[str] = Field(default_factory=list)
    blocked_actions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AutomationFallbackRoutingHint(BaseModel):
    recommended_mode: AutomationExecutionMode = "blocked"
    reason: str = ""
    supported_provider_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class NormalizedResultIssue(BaseModel):
    severity: ResultIssueSeverity = "info"
    code: str
    message: str
    related_entity_type: str | None = None
    related_entity_id: str | None = None


class NormalizedOperationResult(BaseModel):
    success: bool = True
    message: str = ""
    issues: list[NormalizedResultIssue] = Field(default_factory=list)


class AutomationPlanStep(BaseModel):
    step_id: str
    step_index: int = 0
    step_type: AutomationPlanStepType
    status: AutomationPlanStepStatus = "informational"
    title: str
    description: str = ""
    target_reference: str = ""
    tool_id: str | None = None
    backend_id: str | None = None
    execution_mode: AutomationExecutionMode = "blocked"
    checkpoint_required: bool = False
    checkpoint_reason: str = ""
    fallback_hint: AutomationFallbackRoutingHint | None = None
    mapping_id: SubmissionMappingId | None = None
    related_document_id: str | None = None
    notes: list[str] = Field(default_factory=list)


class DryRunResultSummary(BaseModel):
    plan_status: AutomationPlanStatus = "draft"
    total_steps: int = 0
    informational_steps: int = 0
    future_automation_steps: int = 0
    requires_human_input_steps: int = 0
    blocked_steps: int = 0
    missing_required_mapping_count: int = 0
    attachment_count: int = 0
    referenced_tool_count: int = 0
    referenced_backend_count: int = 0
    notes: list[str] = Field(default_factory=list)


class AutomationPlan(BaseModel):
    plan_id: AutomationPlanId
    draft_id: SubmissionDraftId
    target_id: SubmissionTargetId
    target_pack_selection: CaseTargetPackSelection | None = None
    target_pack_automation_compatibility: TargetAutomationCompatibility | None = None
    source_mode: DownstreamSourceMode = "live_case_state"
    source_reviewed_snapshot_id: str = ""
    status: AutomationPlanStatus = "draft"
    dry_run: bool = True
    generated_at: str = ""
    guardrails: ExecutionGuardrailMetadata
    dry_run_summary: DryRunResultSummary
    steps: list[AutomationPlanStep] = Field(default_factory=list)


class SubmissionDraftSummary(BaseModel):
    draft_id: SubmissionDraftId
    case_id: CaseId
    case_title: str = ""
    packet_id: PacketId
    source_mode: DownstreamSourceMode = "live_case_state"
    source_reviewed_snapshot_id: str = ""
    submission_target_id: SubmissionTargetId
    submission_target_category: SubmissionTargetCategory
    target_pack_selection: CaseTargetPackSelection | None = None
    status: SubmissionDraftStatus = "draft_created"
    approval_status: ApprovalStatus = "not_requested"
    mapping_count: int = 0
    unresolved_mapping_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    note: str = ""


class SubmissionDraftListResponse(BaseModel):
    drafts: list[SubmissionDraftSummary] = Field(default_factory=list)


class CreateSubmissionDraftRequest(BaseModel):
    packet_id: PacketId
    submission_target_id: SubmissionTargetId
    note: str = ""


class SubmissionDraftCreateResponse(BaseModel):
    result: NormalizedOperationResult
    draft: SubmissionDraftSummary
    target: SubmissionTargetMetadata
    source_metadata: SubmissionDraftSourceMetadata
    mappings: list[SubmissionMappingFieldDefinition] = Field(default_factory=list)
    approval: ApprovalRequirementMetadata


class SubmissionDraftDetailResponse(BaseModel):
    draft: SubmissionDraftSummary
    target: SubmissionTargetMetadata
    source_metadata: SubmissionDraftSourceMetadata
    mappings: list[SubmissionMappingFieldDefinition] = Field(default_factory=list)
    approval: ApprovalRequirementMetadata
    plan: AutomationPlan | None = None


class GenerateAutomationPlanRequest(BaseModel):
    dry_run: bool = True


class AutomationPlanGenerateResponse(BaseModel):
    result: NormalizedOperationResult
    draft: SubmissionDraftSummary
    plan: AutomationPlan


class AutomationPlanResponse(BaseModel):
    plan: AutomationPlan


class UpdateSubmissionApprovalRequest(BaseModel):
    approval_status: ApprovalStatus
    approved_by: str = ""
    approval_note: str = ""


class SubmissionApprovalUpdateResponse(BaseModel):
    result: NormalizedOperationResult
    draft: SubmissionDraftSummary
    approval: ApprovalRequirementMetadata