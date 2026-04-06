import type { CaseId } from "./cases";
import type { CaseTypeTemplateId, DomainPackId } from "./domains";
import type { PacketId, PacketSectionType } from "./packets";
import type { ReadinessStatus } from "./readiness";
import type { DownstreamSourceMode, SignOffStatus } from "./reviewed-handoff";
import type {
  CaseTargetPackSelection,
  TargetAutomationCompatibility,
} from "./target-packs";

export type SubmissionTargetId = string;
export type SubmissionDraftId = string;
export type SubmissionMappingId = string;
export type AutomationPlanId = string;

export type AutomationExecutionMode =
  | "playwright_mcp"
  | "computer_use_fallback"
  | "manual_only"
  | "blocked";

export type SubmissionTargetCategory =
  | "portal_submission"
  | "form_packet_export"
  | "internal_handoff_packet";

export type SubmissionDraftStatus =
  | "draft_created"
  | "mapping_incomplete"
  | "awaiting_operator_review"
  | "approved_for_future_execution"
  | "blocked"
  | "superseded_placeholder";

export type SubmissionSourceEntityType =
  | "case"
  | "case_metadata"
  | "packet_manifest"
  | "packet_section"
  | "document"
  | "extraction"
  | "readiness"
  | "reviewed_snapshot";

export type SubmissionMappingStatus =
  | "unresolved"
  | "candidate_available"
  | "mapped_preview"
  | "requires_human_input";

export type AutomationPlanStepType =
  | "open_target"
  | "navigate_section"
  | "populate_field_placeholder"
  | "attach_document_placeholder"
  | "review_before_submit"
  | "submit_blocked_placeholder";

export type AutomationPlanStatus =
  | "draft"
  | "partial"
  | "awaiting_operator_review"
  | "approved_for_future_execution"
  | "blocked";

export type AutomationPlanStepStatus =
  | "informational"
  | "future_automation_placeholder"
  | "requires_human_input"
  | "blocked";

export type ApprovalStatus =
  | "not_requested"
  | "awaiting_operator_review"
  | "approved_for_future_execution"
  | "rejected";

export type ResultIssueSeverity = "info" | "warning" | "error";

export interface SubmissionMappingSourceReference {
  source_entity_type: SubmissionSourceEntityType;
  source_entity_id: string;
  source_path: string;
  display_label: string;
}

export interface SubmissionMappingTargetField {
  field_name: string;
  target_section: string;
  display_label: string;
  field_type: string;
  required: boolean;
  candidate_source_paths: string[];
  notes: string[];
}

export interface SubmissionFieldValuePreview {
  value_present: boolean;
  text_value: string;
  raw_value: unknown;
  source_reference: SubmissionMappingSourceReference | null;
  notes: string[];
}

export interface SubmissionMappingFieldDefinition {
  mapping_id: SubmissionMappingId;
  target_field: SubmissionMappingTargetField;
  status: SubmissionMappingStatus;
  source_reference: SubmissionMappingSourceReference | null;
  value_preview: SubmissionFieldValuePreview | null;
  notes: string[];
}

export interface SubmissionTargetMetadata {
  target_id: SubmissionTargetId;
  category: SubmissionTargetCategory;
  display_name: string;
  description: string;
  notes: string[];
  supported_domain_pack_ids: DomainPackId[];
  supported_case_type_ids: CaseTypeTemplateId[];
  supports_field_mapping: boolean;
  supports_file_attachments: boolean;
  supports_dry_run_preview: boolean;
  supports_live_submission: boolean;
  default_backend_ids: string[];
  default_target_fields: SubmissionMappingTargetField[];
}

export interface SubmissionTargetListResponse {
  targets: SubmissionTargetMetadata[];
}

export interface SubmissionDraftSourceMetadata {
  packet_id: PacketId;
  source_mode: DownstreamSourceMode;
  source_reviewed_snapshot_id: string;
  source_snapshot_signoff_status: SignOffStatus;
  source_snapshot_signed_off_at: string;
  source_snapshot_signed_off_by: string;
  packet_generated_at: string;
  domain_pack_id: DomainPackId | null;
  case_type_id: CaseTypeTemplateId | null;
  readiness_status: ReadinessStatus | null;
  linked_document_count: number;
  extraction_count: number;
  candidate_source_count: number;
  source_sections: PacketSectionType[];
  target_pack_selection: CaseTargetPackSelection | null;
}

export interface ApprovalRequirementMetadata {
  requires_operator_approval: boolean;
  approval_status: ApprovalStatus;
  approved_by: string;
  approved_at: string;
  approval_note: string;
  scope: string;
}

export interface ExecutionGuardrailMetadata {
  requires_operator_approval: boolean;
  approval_status: ApprovalStatus;
  browser_write_actions_blocked: boolean;
  live_submission_blocked: boolean;
  allowed_backend_ids: string[];
  allowed_tool_ids: string[];
  blocked_actions: string[];
  notes: string[];
}

export interface AutomationFallbackRoutingHint {
  recommended_mode: AutomationExecutionMode;
  reason: string;
  supported_provider_ids: string[];
  notes: string[];
}

export interface NormalizedResultIssue {
  severity: ResultIssueSeverity;
  code: string;
  message: string;
  related_entity_type: string | null;
  related_entity_id: string | null;
}

export interface NormalizedOperationResult {
  success: boolean;
  message: string;
  issues: NormalizedResultIssue[];
}

export interface AutomationPlanStep {
  step_id: string;
  step_index: number;
  step_type: AutomationPlanStepType;
  status: AutomationPlanStepStatus;
  title: string;
  description: string;
  target_reference: string;
  tool_id: string | null;
  backend_id: string | null;
  execution_mode: AutomationExecutionMode;
  checkpoint_required: boolean;
  checkpoint_reason: string;
  fallback_hint: AutomationFallbackRoutingHint | null;
  mapping_id: SubmissionMappingId | null;
  related_document_id: string | null;
  notes: string[];
}

export interface DryRunResultSummary {
  plan_status: AutomationPlanStatus;
  total_steps: number;
  informational_steps: number;
  future_automation_steps: number;
  requires_human_input_steps: number;
  blocked_steps: number;
  missing_required_mapping_count: number;
  attachment_count: number;
  referenced_tool_count: number;
  referenced_backend_count: number;
  notes: string[];
}

export interface AutomationPlan {
  plan_id: AutomationPlanId;
  draft_id: SubmissionDraftId;
  target_id: SubmissionTargetId;
  target_pack_selection: CaseTargetPackSelection | null;
  target_pack_automation_compatibility: TargetAutomationCompatibility | null;
  source_mode: DownstreamSourceMode;
  source_reviewed_snapshot_id: string;
  status: AutomationPlanStatus;
  dry_run: boolean;
  generated_at: string;
  guardrails: ExecutionGuardrailMetadata;
  dry_run_summary: DryRunResultSummary;
  steps: AutomationPlanStep[];
}

export interface SubmissionDraftSummary {
  draft_id: SubmissionDraftId;
  case_id: CaseId;
  case_title: string;
  packet_id: PacketId;
  source_mode: DownstreamSourceMode;
  source_reviewed_snapshot_id: string;
  submission_target_id: SubmissionTargetId;
  submission_target_category: SubmissionTargetCategory;
  target_pack_selection: CaseTargetPackSelection | null;
  status: SubmissionDraftStatus;
  approval_status: ApprovalStatus;
  mapping_count: number;
  unresolved_mapping_count: number;
  created_at: string;
  updated_at: string;
  note: string;
}

export interface SubmissionDraftListResponse {
  drafts: SubmissionDraftSummary[];
}

export interface CreateSubmissionDraftRequest {
  packet_id: PacketId;
  submission_target_id: SubmissionTargetId;
  note?: string;
}

export interface SubmissionDraftCreateResponse {
  result: NormalizedOperationResult;
  draft: SubmissionDraftSummary;
  target: SubmissionTargetMetadata;
  source_metadata: SubmissionDraftSourceMetadata;
  mappings: SubmissionMappingFieldDefinition[];
  approval: ApprovalRequirementMetadata;
}

export interface SubmissionDraftDetailResponse {
  draft: SubmissionDraftSummary;
  target: SubmissionTargetMetadata;
  source_metadata: SubmissionDraftSourceMetadata;
  mappings: SubmissionMappingFieldDefinition[];
  approval: ApprovalRequirementMetadata;
  plan: AutomationPlan | null;
}

export interface GenerateAutomationPlanRequest {
  dry_run?: boolean;
}

export interface AutomationPlanGenerateResponse {
  result: NormalizedOperationResult;
  draft: SubmissionDraftSummary;
  plan: AutomationPlan;
}

export interface AutomationPlanResponse {
  plan: AutomationPlan;
}

export interface UpdateSubmissionApprovalRequest {
  approval_status: ApprovalStatus;
  approved_by?: string;
  approval_note?: string;
}

export interface SubmissionApprovalUpdateResponse {
  result: NormalizedOperationResult;
  draft: SubmissionDraftSummary;
  approval: ApprovalRequirementMetadata;
}