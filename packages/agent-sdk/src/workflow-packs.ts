/**
 * Shared workflow pack contracts — TypeScript mirror.
 *
 * Domain-specific orchestrated workflows that compose existing case,
 * document, extraction, readiness, packet, and submission-draft
 * foundations into reviewable end-to-end operational workflows.
 */

import type {
  CaseTypeTemplateId,
  DomainCategory,
  DomainPackId,
  Jurisdiction,
} from "./domains";
import type { CaseStage } from "./operator-review";
import type { ReadinessStatus } from "./readiness";

// ---------------------------------------------------------------------------
// Identifiers
// ---------------------------------------------------------------------------

export type WorkflowPackId = string;
export type WorkflowPackRunId = string;

// ---------------------------------------------------------------------------
// Status literals
// ---------------------------------------------------------------------------

export type WorkflowPackStageStatus =
  | "not_started"
  | "completed"
  | "completed_partial"
  | "skipped"
  | "blocked"
  | "failed";

export type WorkflowPackRunStatus =
  | "created"
  | "running"
  | "completed"
  | "completed_partial"
  | "blocked"
  | "failed";

// ---------------------------------------------------------------------------
// Stage definitions
// ---------------------------------------------------------------------------

export type WorkflowPackStageId =
  | "intake_document_check"
  | "extraction_pass"
  | "checklist_refresh"
  | "readiness_evaluation"
  | "action_generation"
  | "packet_assembly"
  | "submission_draft_preparation"
  | "human_review_check";

export interface WorkflowPackStageDefinition {
  stage_id: WorkflowPackStageId;
  display_name: string;
  description: string;
  optional: boolean;
  depends_on: WorkflowPackStageId[];
}

// ---------------------------------------------------------------------------
// Stage result summaries
// ---------------------------------------------------------------------------

export interface IntakeDocumentCheckSummary {
  linked_document_count: number;
  required_document_count: number;
  missing_categories: string[];
  notes: string[];
}

export interface ExtractionPassSummary {
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  skipped_runs: number;
  extracted_field_count: number;
  extraction_run_ids: string[];
  notes: string[];
}

export interface ChecklistRefreshSummary {
  checklist_generated: boolean;
  checklist_id: string;
  total_items: number;
  notes: string[];
}

export interface ReadinessEvaluationSummary {
  readiness_status: string;
  total_items: number;
  supported_items: number;
  missing_items: number;
  partially_supported_items: number;
  missing_required_names: string[];
  notes: string[];
}

export interface ActionGenerationSummary {
  total_actions: number;
  open_actions: number;
  high_priority_actions: number;
  action_categories: string[];
  notes: string[];
}

export interface PacketAssemblySummary {
  packet_generated: boolean;
  packet_id: string;
  artifact_count: number;
  skipped_reason: string;
  notes: string[];
}

export interface SubmissionDraftPreparationSummary {
  draft_generated: boolean;
  draft_id: string;
  plan_generated: boolean;
  plan_id: string;
  skipped_reason: string;
  notes: string[];
}

export interface HumanReviewCheckSummary {
  has_reviewed_state: boolean;
  reviewed_fields: number;
  total_fields: number;
  reviewed_requirements: number;
  total_requirements: number;
  unresolved_count: number;
  notes: string[];
}

// ---------------------------------------------------------------------------
// Stage result
// ---------------------------------------------------------------------------

export interface WorkflowPackStageResult {
  stage_id: WorkflowPackStageId;
  status: WorkflowPackStageStatus;
  display_name: string;
  started_at: string;
  completed_at: string;
  summary: Record<string, unknown>;
  error_message: string;
  notes: string[];
}

// ---------------------------------------------------------------------------
// Operator review recommendation
// ---------------------------------------------------------------------------

export interface OperatorReviewRecommendation {
  has_missing_required_documents: boolean;
  has_open_high_priority_actions: boolean;
  has_failed_stages: boolean;
  readiness_status: ReadinessStatus;
  suggested_next_stage: CaseStage;
  notes: string[];
}

// ---------------------------------------------------------------------------
// Workflow pack metadata and definition
// ---------------------------------------------------------------------------

export interface WorkflowPackMetadata {
  workflow_pack_id: WorkflowPackId;
  display_name: string;
  description: string;
  version: string;
  domain_pack_id: DomainPackId;
  domain_category: DomainCategory;
  jurisdiction: Jurisdiction;
  compatible_case_type_ids: CaseTypeTemplateId[];
  stage_count: number;
  limitations: string[];
}

export interface WorkflowPackDefinition {
  metadata: WorkflowPackMetadata;
  stages: WorkflowPackStageDefinition[];
}

// ---------------------------------------------------------------------------
// Execution request and result
// ---------------------------------------------------------------------------

export interface WorkflowPackExecutionRequest {
  case_id: string;
  workflow_pack_id: WorkflowPackId;
  operator_id?: string;
  skip_optional_stages?: boolean;
  notes?: string[];
}

export interface WorkflowPackRunRecord {
  run_id: WorkflowPackRunId;
  case_id: string;
  workflow_pack_id: WorkflowPackId;
  status: WorkflowPackRunStatus;
  operator_id: string;
  stage_results: WorkflowPackStageResult[];
  review_recommendation: OperatorReviewRecommendation;
  created_at: string;
  started_at: string;
  completed_at: string;
  notes: string[];
}

// ---------------------------------------------------------------------------
// API responses
// ---------------------------------------------------------------------------

export interface WorkflowPackListResponse {
  packs: WorkflowPackMetadata[];
}

export interface WorkflowPackDetailResponse {
  definition: WorkflowPackDefinition;
}

export interface WorkflowPackRunResponse {
  success: boolean;
  message: string;
  run: WorkflowPackRunRecord;
}

export interface WorkflowPackRunSummaryResponse {
  run: WorkflowPackRunRecord;
  case_title: string;
  domain_pack_display_name: string;
}
