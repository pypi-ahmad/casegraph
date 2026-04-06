import type {
  FieldValidationStatus,
  OriginalValueReference,
  RequirementReviewStatus,
} from "./human-validation";
import type { ChecklistId, ChecklistItemId } from "./readiness";

export type ReviewedSnapshotId = string;
export type SignOffRecordId = string;
export type SignOffNote = string;

export type ReviewedSnapshotStatus =
  | "created"
  | "selected_for_handoff"
  | "archived_placeholder";

export type SignOffStatus =
  | "not_signed_off"
  | "signed_off"
  | "revoked_placeholder";

export type DownstreamSourceMode =
  | "live_case_state"
  | "reviewed_snapshot";

export type ReleaseGateStatus =
  | "eligible_with_current_rules"
  | "blocked_no_reviewed_snapshot"
  | "blocked_missing_signoff"
  | "blocked_unresolved_review_items"
  | "blocked_required_requirement_reviews_incomplete";

export type ReviewedHandoffIssueSeverity = "info" | "warning" | "error";

export interface ReviewedSnapshotSourceMetadata {
  case_id: string;
  linked_document_ids: string[];
  extraction_ids: string[];
  validation_record_ids: string[];
  checklist_id: ChecklistId | null;
  requirement_review_ids: string[];
  reviewed_state_timestamp: string;
}

export interface ReviewedSnapshotSummary {
  total_fields: number;
  included_fields: number;
  accepted_fields: number;
  corrected_fields: number;
  total_requirements: number;
  reviewed_requirements: number;
  required_requirement_reviews_complete: boolean;
  unresolved_item_count: number;
}

export interface ReviewedFieldEntry {
  extraction_id: string;
  document_id: string | null;
  field_id: string;
  field_type: string;
  validation_id: string;
  validation_status: FieldValidationStatus;
  original: OriginalValueReference;
  reviewed_value: unknown;
  snapshot_value: unknown;
  included_in_snapshot: boolean;
  note: string;
}

export interface ReviewedRequirementEntry {
  checklist_id: ChecklistId;
  item_id: ChecklistItemId;
  requirement_id: string;
  display_name: string;
  priority: string;
  machine_status: string;
  review_id: string;
  review_status: RequirementReviewStatus;
  included_in_snapshot: boolean;
  note: string;
  linked_document_ids: string[];
  linked_extraction_ids: string[];
}

export interface UnresolvedReviewItemSummary {
  item_type: "field_validation" | "requirement_review";
  entity_id: string;
  display_label: string;
  current_status: string;
  note: string;
}

export interface SignOffActorMetadata {
  actor_id: string;
  display_name: string;
  metadata: Record<string, unknown>;
}

export interface SnapshotSignOffRecord {
  signoff_id: SignOffRecordId;
  snapshot_id: ReviewedSnapshotId;
  case_id: string;
  status: SignOffStatus;
  actor: SignOffActorMetadata;
  note: SignOffNote;
  created_at: string;
}

export interface ReleaseGateReason {
  code: string;
  message: string;
  blocking: boolean;
}

export interface HandoffEligibilitySummary {
  case_id: string;
  snapshot_id: string;
  selected_snapshot_id: string;
  has_reviewed_snapshot: boolean;
  snapshot_status: ReviewedSnapshotStatus | null;
  signoff_status: SignOffStatus;
  unresolved_review_item_count: number;
  required_requirement_reviews_complete: boolean;
  release_gate_status: ReleaseGateStatus;
  eligible: boolean;
  reasons: ReleaseGateReason[];
}

export interface ReviewedHandoffIssue {
  severity: ReviewedHandoffIssueSeverity;
  code: string;
  message: string;
  related_entity_type: string | null;
  related_entity_id: string | null;
}

export interface ReviewedHandoffOperationResult {
  success: boolean;
  message: string;
  issues: ReviewedHandoffIssue[];
}

export interface ReviewedSnapshotRecord {
  snapshot_id: ReviewedSnapshotId;
  case_id: string;
  status: ReviewedSnapshotStatus;
  summary: ReviewedSnapshotSummary;
  source_metadata: ReviewedSnapshotSourceMetadata;
  fields: ReviewedFieldEntry[];
  requirements: ReviewedRequirementEntry[];
  unresolved_items: UnresolvedReviewItemSummary[];
  signoff_status: SignOffStatus;
  signoff: SnapshotSignOffRecord | null;
  note: string;
  created_at: string;
  selected_at: string;
}

export interface CreateReviewedSnapshotRequest {
  note?: string;
  operator_id?: string;
  operator_display_name?: string;
}

export interface SignOffReviewedSnapshotRequest {
  operator_id?: string;
  operator_display_name?: string;
  note?: SignOffNote;
}

export interface ReviewedSnapshotListResponse {
  case_id: string;
  snapshots: ReviewedSnapshotRecord[];
}

export interface ReviewedSnapshotResponse {
  snapshot: ReviewedSnapshotRecord;
}

export interface ReviewedSnapshotCreateResponse {
  result: ReviewedHandoffOperationResult;
  snapshot: ReviewedSnapshotRecord;
}

export interface ReviewedSnapshotSignOffResponse {
  result: ReviewedHandoffOperationResult;
  snapshot: ReviewedSnapshotRecord;
  signoff: SnapshotSignOffRecord;
}

export interface ReviewedSnapshotSelectResponse {
  result: ReviewedHandoffOperationResult;
  snapshot: ReviewedSnapshotRecord;
}

export interface HandoffEligibilityResponse {
  eligibility: HandoffEligibilitySummary;
}