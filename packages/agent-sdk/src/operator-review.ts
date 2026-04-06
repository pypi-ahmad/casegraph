import type {
  CaseId,
  CaseStatus,
  NormalizedOperationError,
} from "./cases";
import type { CaseTypeTemplateId, DomainPackId } from "./domains";
import type { DocumentId } from "./ingestion";
import type { ChecklistItemId, ReadinessStatus } from "./readiness";

export type StageTransitionId = string;
export type ActionItemId = string;
export type ReviewNoteId = string;

export type CaseStage =
  | "intake"
  | "document_review"
  | "readiness_review"
  | "awaiting_documents"
  | "ready_for_next_step"
  | "closed_placeholder";

export type ActionItemCategory =
  | "missing_document"
  | "needs_review"
  | "extraction_followup"
  | "evidence_gap"
  | "run_followup"
  | "document_linking_needed";

export type ActionItemSource =
  | "case"
  | "checklist_item"
  | "workflow_run"
  | "extraction_run";

export type ActionItemPriority = "normal" | "high";

export type ActionItemStatus = "open" | "resolved";

export type ReviewDecision =
  | "note_only"
  | "follow_up_required"
  | "ready_for_next_step"
  | "hold"
  | "close_placeholder";

export interface OperatorOperationResult {
  success: boolean;
  message: string;
  error: NormalizedOperationError | null;
}

export interface StageTransitionMetadata {
  transition_type: "manual";
  reason: string;
  note: string;
}

export interface CaseStageState {
  case_id: CaseId;
  current_stage: CaseStage;
  allowed_transitions: CaseStage[];
  updated_at: string;
}

export interface StageTransitionRecord {
  transition_id: StageTransitionId;
  case_id: CaseId;
  from_stage: CaseStage;
  to_stage: CaseStage;
  metadata: StageTransitionMetadata;
  created_at: string;
}

export interface ActionItem {
  action_item_id: ActionItemId;
  case_id: CaseId;
  category: ActionItemCategory;
  source: ActionItemSource;
  priority: ActionItemPriority;
  status: ActionItemStatus;
  title: string;
  description: string;
  source_reason: string;
  checklist_item_id: ChecklistItemId | null;
  document_id: DocumentId | null;
  extraction_id: string | null;
  run_id: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface ReviewNote {
  note_id: ReviewNoteId;
  case_id: CaseId;
  body: string;
  decision: ReviewDecision;
  related_action_item_id: ActionItemId | null;
  stage_snapshot: CaseStage;
  created_at: string;
}

export interface OperatorActionSummary {
  case_id: CaseId;
  detected_count: number;
  generated_count: number;
  reopened_count: number;
  resolved_count: number;
  open_count: number;
}

export interface QueueFilterMetadata {
  stage: CaseStage | null;
  has_missing_items: boolean | null;
  has_open_actions: boolean | null;
  domain_pack_id: DomainPackId | null;
  case_type_id: CaseTypeTemplateId | null;
  limit: number;
}

export interface ReviewQueueItem {
  case_id: CaseId;
  title: string;
  case_status: CaseStatus;
  current_stage: CaseStage;
  domain_pack_id: DomainPackId | null;
  case_type_id: CaseTypeTemplateId | null;
  readiness_status: ReadinessStatus | null;
  linked_document_count: number;
  open_action_count: number;
  detected_action_count: number;
  missing_required_count: number;
  needs_review_count: number;
  failed_run_count: number;
  has_open_actions: boolean;
  has_missing_items: boolean;
  attention_categories: ActionItemCategory[];
  last_activity_at: string;
}

export interface QueueStageCount {
  stage: CaseStage;
  case_count: number;
}

export interface QueueSummary {
  total_cases: number;
  cases_with_open_actions: number;
  cases_with_missing_items: number;
  cases_needing_attention: number;
  stage_counts: QueueStageCount[];
}

export interface GenerateActionItemsRequest {}

export interface UpdateCaseStageRequest {
  new_stage: CaseStage;
  reason?: string | null;
  note?: string | null;
}

export interface CreateReviewNoteRequest {
  body: string;
  decision: ReviewDecision;
  related_action_item_id?: ActionItemId | null;
}

export interface ReviewQueueResponse {
  filters: QueueFilterMetadata;
  items: ReviewQueueItem[];
}

export interface QueueSummaryResponse {
  filters: QueueFilterMetadata;
  summary: QueueSummary;
}

export interface CaseActionListResponse {
  actions: ActionItem[];
}

export interface ReviewNoteListResponse {
  notes: ReviewNote[];
}

export interface StageHistoryResponse {
  transitions: StageTransitionRecord[];
}

export interface CaseStageResponse {
  stage: CaseStageState;
}

export interface ActionGenerationResponse {
  result: OperatorOperationResult;
  summary: OperatorActionSummary;
  actions: ActionItem[];
}

export interface StageTransitionResponse {
  result: OperatorOperationResult;
  stage: CaseStageState;
  transition: StageTransitionRecord;
}

export interface ReviewNoteResponse {
  result: OperatorOperationResult;
  note: ReviewNote;
}