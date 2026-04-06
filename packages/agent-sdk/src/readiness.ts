/**
 * Shared case readiness and requirement checklist contracts.
 *
 * These types define the structured readiness/checklist layer — how cases
 * derive requirement checklists from domain pack case type templates, how
 * documents and extraction results link to checklist items, and how
 * readiness is evaluated.
 *
 * This is a structured operational metadata layer. It does not implement
 * rules engines, compliance validators, adjudication logic, or filing
 * decision systems.
 */

import type {
  CaseTypeTemplateId,
  DocumentCategory,
  DocumentRequirementId,
  DocumentRequirementPriority,
  DomainPackId,
} from "./domains";
import type { DocumentId } from "./ingestion";

// ---------------------------------------------------------------------------
// Identifiers
// ---------------------------------------------------------------------------

export type ChecklistId = string;
export type ChecklistItemId = string;

// ---------------------------------------------------------------------------
// Status literals
// ---------------------------------------------------------------------------

export type ChecklistItemStatus =
  | "missing"
  | "partially_supported"
  | "supported"
  | "needs_human_review"
  | "optional_unfilled"
  | "waived";

export type ReadinessStatus =
  | "not_evaluated"
  | "incomplete"
  | "needs_review"
  | "ready";

// ---------------------------------------------------------------------------
// Evidence / linkage references
// ---------------------------------------------------------------------------

export interface LinkedDocumentReference {
  document_id: DocumentId;
  filename: string;
  content_type: string;
  linked_at: string;
}

export interface LinkedExtractionReference {
  extraction_id: string;
  template_id: string;
  document_id: DocumentId;
  field_count: number;
  grounding_available: boolean;
}

export interface LinkedEvidenceReference {
  source_document_id: DocumentId;
  chunk_summary: string;
  page_number: number | null;
}

// ---------------------------------------------------------------------------
// Checklist item
// ---------------------------------------------------------------------------

export interface ChecklistItem {
  item_id: ChecklistItemId;
  checklist_id: ChecklistId;
  requirement_id: DocumentRequirementId;
  display_name: string;
  description: string;
  document_category: DocumentCategory;
  priority: DocumentRequirementPriority;
  status: ChecklistItemStatus;
  operator_notes: string;
  linked_documents: LinkedDocumentReference[];
  linked_extractions: LinkedExtractionReference[];
  linked_evidence: LinkedEvidenceReference[];
  last_evaluated_at: string | null;
}

// ---------------------------------------------------------------------------
// Checklist
// ---------------------------------------------------------------------------

export interface ChecklistGenerationMetadata {
  generated_at: string;
  domain_pack_id: DomainPackId;
  case_type_id: CaseTypeTemplateId;
  requirement_count: number;
}

export interface CaseChecklist {
  checklist_id: ChecklistId;
  case_id: string;
  generation: ChecklistGenerationMetadata;
  items: ChecklistItem[];
}

// ---------------------------------------------------------------------------
// Readiness summary
// ---------------------------------------------------------------------------

export interface MissingItemSummary {
  item_id: ChecklistItemId;
  requirement_id: DocumentRequirementId;
  display_name: string;
  priority: DocumentRequirementPriority;
  status: ChecklistItemStatus;
}

export interface ReadinessSummary {
  case_id: string;
  checklist_id: ChecklistId;
  readiness_status: ReadinessStatus;
  total_items: number;
  required_items: number;
  supported_items: number;
  partially_supported_items: number;
  missing_items: number;
  needs_review_items: number;
  optional_unfilled_items: number;
  waived_items: number;
  missing_required: MissingItemSummary[];
  evaluated_at: string;
}

// ---------------------------------------------------------------------------
// API request / response models
// ---------------------------------------------------------------------------

export interface GenerateChecklistRequest {
  force: boolean;
}

export interface EvaluateChecklistRequest {}

export interface UpdateChecklistItemRequest {
  operator_notes?: string;
  status_override?: ChecklistItemStatus;
}

export interface ChecklistResponse {
  checklist: CaseChecklist;
}

export interface ReadinessResponse {
  readiness: ReadinessSummary;
}
