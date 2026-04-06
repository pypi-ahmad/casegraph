import type {
  CaseTypeTemplateId,
  DocumentCategory,
  DocumentRequirementId,
  DocumentRequirementPriority,
  DomainPackId,
} from "./domains";
import type { ExtractionTemplateId } from "./extraction";
import type { CommunicationTemplateId } from "./communications";
import type { WorkflowPackId } from "./workflow-packs";

export type TargetPackId = string;
export type TargetPackVersion = string;
export type SubmissionTargetId = string;

export type TargetPackStatus =
  | "draft_metadata"
  | "active_metadata"
  | "superseded";

export type TargetPackCategory =
  | "payer_prior_auth_pack"
  | "insurer_claim_pack"
  | "insurance_correspondence_pack"
  | "tax_notice_pack"
  | "tax_intake_pack"
  | "generic_form_pack";

export type TargetOrganizationType =
  | "payer"
  | "insurer"
  | "tax_agency"
  | "internal"
  | "generic";

export type TargetFieldType =
  | "text"
  | "long_text"
  | "identifier"
  | "date"
  | "document_list"
  | "boolean";

export type TargetRequirementOverrideMode =
  | "add_requirement"
  | "refine_requirement";

export type TargetTemplateBindingType =
  | "extraction_template"
  | "communication_template";

export interface TargetOrganizationMetadata {
  organization_type: TargetOrganizationType;
  organization_id: string;
  display_name: string;
  description: string;
  notes: string[];
}

export interface TargetPackMetadata {
  pack_id: TargetPackId;
  version: TargetPackVersion;
  status: TargetPackStatus;
  category: TargetPackCategory;
  display_name: string;
  description: string;
  organization: TargetOrganizationMetadata;
  notes: string[];
  limitations: string[];
}

export interface TargetPackCompatibilityRecord {
  compatible_domain_pack_ids: DomainPackId[];
  compatible_case_type_ids: CaseTypeTemplateId[];
  compatible_workflow_pack_ids: WorkflowPackId[];
  notes: string[];
}

export interface TargetFieldDefinition {
  field_id: string;
  display_name: string;
  field_type: TargetFieldType;
  description: string;
  required: boolean;
  candidate_source_paths: string[];
  notes: string[];
}

export interface TargetFieldSection {
  section_id: string;
  display_name: string;
  description: string;
  fields: TargetFieldDefinition[];
}

export interface TargetFieldSchema {
  sections: TargetFieldSection[];
  notes: string[];
}

export interface TargetRequirementOverride {
  override_id: string;
  mode: TargetRequirementOverrideMode;
  base_requirement_id: DocumentRequirementId | null;
  display_name: string;
  description: string;
  document_category: DocumentCategory;
  priority: DocumentRequirementPriority;
  requirement_group: string;
  notes: string[];
}

export interface TargetTemplateBinding {
  binding_type: TargetTemplateBindingType;
  template_id: ExtractionTemplateId | CommunicationTemplateId;
  display_name: string;
  description: string;
  notes: string[];
}

export interface TargetSubmissionCompatibility {
  submission_target_ids: SubmissionTargetId[];
  notes: string[];
}

export interface TargetAutomationCompatibility {
  supported_backend_ids: string[];
  supports_dry_run_planning: boolean;
  supports_live_execution: boolean;
  notes: string[];
}

export interface CaseTargetPackSelection {
  pack_id: TargetPackId;
  version: TargetPackVersion;
  display_name: string;
  category: TargetPackCategory;
  selected_at: string;
}

export interface TargetPackSummary {
  metadata: TargetPackMetadata;
  compatibility: TargetPackCompatibilityRecord;
  field_section_count: number;
  field_count: number;
  requirement_override_count: number;
  template_binding_count: number;
  submission_target_count: number;
}

export interface TargetPackDetail {
  metadata: TargetPackMetadata;
  compatibility: TargetPackCompatibilityRecord;
  field_schema: TargetFieldSchema;
  requirement_overrides: TargetRequirementOverride[];
  template_bindings: TargetTemplateBinding[];
  submission_compatibility: TargetSubmissionCompatibility;
  automation_compatibility: TargetAutomationCompatibility;
}

export interface TargetPackOperationError {
  error_code: string;
  message: string;
  recoverable: boolean;
}

export interface TargetPackOperationResult {
  success: boolean;
  message: string;
  error: TargetPackOperationError | null;
}

export interface TargetPackListFilters {
  domain_pack_id?: DomainPackId | null;
  case_type_id?: CaseTypeTemplateId | null;
  category?: TargetPackCategory | null;
  status?: TargetPackStatus | null;
}

export interface UpdateCaseTargetPackRequest {
  pack_id?: TargetPackId | null;
  clear_selection?: boolean;
}

export interface TargetPackListResponse {
  filters: TargetPackListFilters;
  packs: TargetPackSummary[];
}

export interface TargetPackDetailResponse {
  pack: TargetPackDetail;
}

export interface TargetPackCompatibilityResponse {
  pack_id: TargetPackId;
  compatibility: TargetPackCompatibilityRecord;
}

export interface TargetPackFieldSchemaResponse {
  pack_id: TargetPackId;
  field_schema: TargetFieldSchema;
}

export interface TargetPackRequirementsResponse {
  pack_id: TargetPackId;
  requirement_overrides: TargetRequirementOverride[];
}

export interface CaseTargetPackResponse {
  case_id: string;
  selection: CaseTargetPackSelection | null;
}

export interface CaseTargetPackUpdateResponse {
  result: TargetPackOperationResult;
  case_id: string;
  selection: CaseTargetPackSelection | null;
}