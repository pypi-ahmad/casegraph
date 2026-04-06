/**
 * Shared human validation and review contracts.
 *
 * These types define the human-in-the-loop validation layer that sits
 * between machine-generated outputs (extraction results, readiness
 * evaluations) and downstream consumption (packets, workflows).
 *
 * Operators use this layer to explicitly accept, correct, reject, or flag
 * machine outputs. The original machine values are always preserved —
 * validation records are overlays, not destructive rewrites.
 *
 * This layer does not implement autonomous adjudication, truth resolution,
 * multi-reviewer governance, or validation confidence scoring.
 */

import type { ExtractionId, GroundingReference } from "./extraction";
import type { ChecklistId, ChecklistItemId } from "./readiness";

// ---------------------------------------------------------------------------
// Identifiers
// ---------------------------------------------------------------------------

export type FieldValidationId = string;
export type RequirementReviewId = string;

// ---------------------------------------------------------------------------
// Status literals
// ---------------------------------------------------------------------------

export type FieldValidationStatus =
  | "unreviewed"
  | "accepted"
  | "corrected"
  | "rejected"
  | "needs_followup";

export type RequirementReviewStatus =
  | "unreviewed"
  | "confirmed_supported"
  | "confirmed_missing"
  | "requires_more_information"
  | "manually_overridden";

// ---------------------------------------------------------------------------
// Reviewer metadata
// ---------------------------------------------------------------------------

export interface ReviewerMetadata {
  reviewer_id: string;
  display_name: string;
  metadata: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Field validation records
// ---------------------------------------------------------------------------

export interface OriginalValueReference {
  value: unknown;
  raw_value: string | null;
  is_present: boolean;
  grounding: GroundingReference[];
}

export interface FieldValidationRecord {
  validation_id: FieldValidationId;
  extraction_id: ExtractionId;
  field_id: string;
  case_id: string;
  status: FieldValidationStatus;
  original: OriginalValueReference;
  reviewed_value: unknown;
  reviewer: ReviewerMetadata;
  note: string;
  created_at: string;
  updated_at: string;
}

export interface ValidateFieldRequest {
  status: FieldValidationStatus;
  reviewed_value?: unknown;
  note?: string;
  reviewer_id?: string;
  reviewer_display_name?: string;
}

// ---------------------------------------------------------------------------
// Requirement review records
// ---------------------------------------------------------------------------

export interface RequirementReviewRecord {
  review_id: RequirementReviewId;
  case_id: string;
  checklist_id: ChecklistId;
  item_id: ChecklistItemId;
  status: RequirementReviewStatus;
  original_machine_status: string;
  reviewer: ReviewerMetadata;
  note: string;
  linked_document_ids: string[];
  linked_extraction_ids: string[];
  linked_evidence_notes: string[];
  created_at: string;
  updated_at: string;
}

export interface ReviewRequirementRequest {
  status: RequirementReviewStatus;
  note?: string;
  reviewer_id?: string;
  reviewer_display_name?: string;
  linked_document_ids?: string[];
  linked_extraction_ids?: string[];
  linked_evidence_notes?: string[];
}

// ---------------------------------------------------------------------------
// Reviewed case state projection
// ---------------------------------------------------------------------------

export interface FieldValidationSummary {
  total_fields: number;
  reviewed_fields: number;
  accepted_fields: number;
  corrected_fields: number;
  rejected_fields: number;
  needs_followup_fields: number;
  extraction_count: number;
}

export interface RequirementReviewSummary {
  total_items: number;
  reviewed_items: number;
  confirmed_supported: number;
  confirmed_missing: number;
  requires_more_information: number;
  manually_overridden: number;
  unresolved_count: number;
}

export type UnresolvedItemType = "field_validation" | "requirement_review";

export interface UnresolvedReviewItem {
  item_type: UnresolvedItemType;
  entity_id: string;
  display_label: string;
  current_status: string;
  note: string;
}

export interface ReviewedCaseState {
  case_id: string;
  field_validation: FieldValidationSummary;
  requirement_review: RequirementReviewSummary;
  unresolved_items: UnresolvedReviewItem[];
  has_reviewed_state: boolean;
  reviewed_at: string;
}

// ---------------------------------------------------------------------------
// API response models
// ---------------------------------------------------------------------------

export interface ExtractionValidationsResponse {
  case_id: string;
  validations: FieldValidationRecord[];
}

export interface RequirementReviewsResponse {
  case_id: string;
  reviews: RequirementReviewRecord[];
}

export interface ReviewedCaseStateResponse {
  state: ReviewedCaseState;
}

export interface FieldValidationResponse {
  validation: FieldValidationRecord;
}

export interface RequirementReviewResponse {
  review: RequirementReviewRecord;
}
