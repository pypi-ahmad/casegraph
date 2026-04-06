/**
 * Shared domain pack contracts for the CaseGraph platform.
 *
 * These types define jurisdiction-aware domain packs, case type templates,
 * workflow/extraction template bindings, and document requirement registries
 * for regulated/operational domains such as medical, insurance, and taxation.
 *
 * This is a structured operational metadata layer — not a rules engine,
 * compliance engine, or decision-making system.
 */

import type { ExtractionTemplateId } from "./extraction";

// ---------------------------------------------------------------------------
// Identifiers
// ---------------------------------------------------------------------------

export type DomainPackId = string;
export type CaseTypeTemplateId = string;
export type DocumentRequirementId = string;

// ---------------------------------------------------------------------------
// Enums and literals
// ---------------------------------------------------------------------------

export type Jurisdiction = "us" | "india";

export type DomainCategory =
  | "medical"
  | "medical_insurance"
  | "insurance"
  | "taxation";

export type CaseTypeStatus =
  | "open"
  | "intake"
  | "document_collection"
  | "under_review"
  | "pending_action"
  | "escalated"
  | "closed"
  | "archived";

export type DocumentRequirementStatus =
  | "not_submitted"
  | "submitted"
  | "accepted"
  | "rejected"
  | "waived";

export type DocumentRequirementPriority =
  | "required"
  | "recommended"
  | "optional";

export type DocumentCategory =
  | "identity"
  | "referral_order"
  | "prior_records"
  | "insurer_payer_correspondence"
  | "policy_document"
  | "claim_form"
  | "invoice_bill"
  | "tax_notice"
  | "income_document"
  | "supporting_attachment"
  | "clinical_notes"
  | "diagnostic_report"
  | "prescription"
  | "proof_of_loss"
  | "government_form"
  | "other";

// ---------------------------------------------------------------------------
// Document requirement definition
// ---------------------------------------------------------------------------

export interface DocumentRequirementDefinition {
  requirement_id: DocumentRequirementId;
  display_name: string;
  description: string;
  document_category: DocumentCategory;
  priority: DocumentRequirementPriority;
  accepted_extensions: string[];
  notes: string;
}

// ---------------------------------------------------------------------------
// Workflow and extraction bindings
// ---------------------------------------------------------------------------

export interface WorkflowBindingMetadata {
  workflow_id: string;
  display_name: string;
  description: string;
  binding_notes: string;
}

export interface ExtractionBindingMetadata {
  extraction_template_id: ExtractionTemplateId;
  display_name: string;
  description: string;
  binding_notes: string;
}

// ---------------------------------------------------------------------------
// Case type template
// ---------------------------------------------------------------------------

export interface CaseTypeTemplateMetadata {
  case_type_id: CaseTypeTemplateId;
  display_name: string;
  description: string;
  domain_pack_id: DomainPackId;
  typical_stages: CaseTypeStatus[];
  workflow_bindings: WorkflowBindingMetadata[];
  extraction_bindings: ExtractionBindingMetadata[];
  document_requirements: DocumentRequirementDefinition[];
}

// ---------------------------------------------------------------------------
// Domain pack metadata
// ---------------------------------------------------------------------------

export interface DomainPackCapabilities {
  has_case_types: boolean;
  has_workflow_bindings: boolean;
  has_extraction_bindings: boolean;
  has_document_requirements: boolean;
  limitations: string[];
}

export interface DomainPackMetadata {
  pack_id: DomainPackId;
  display_name: string;
  description: string;
  domain_category: DomainCategory;
  jurisdiction: Jurisdiction;
  case_type_count: number;
  capabilities: DomainPackCapabilities;
}

export interface DomainPackDetail {
  metadata: DomainPackMetadata;
  case_types: CaseTypeTemplateMetadata[];
}

// ---------------------------------------------------------------------------
// Case domain context
// ---------------------------------------------------------------------------

export interface CaseDomainContext {
  domain_pack_id: DomainPackId;
  jurisdiction: Jurisdiction;
  case_type_id: CaseTypeTemplateId;
  domain_category: DomainCategory;
}

// ---------------------------------------------------------------------------
// API response models
// ---------------------------------------------------------------------------

export interface DomainPackListResponse {
  packs: DomainPackMetadata[];
}

export interface DomainPackDetailResponse {
  pack: DomainPackDetail;
}

export interface CaseTypeDetailResponse {
  case_type: CaseTypeTemplateMetadata;
  pack_metadata: DomainPackMetadata;
}
