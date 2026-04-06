import type { CaseId, CaseStatus } from "./cases";
import type { CaseTypeTemplateId, DomainPackId } from "./domains";
import type { PacketId } from "./packets";
import type { ReadinessStatus } from "./readiness";
import type { SourceReference } from "./retrieval";
import type { NormalizedOperationResult } from "./submissions";
import type {
	FinishReason,
	ProviderSelection,
	TaskExecutionError,
	UsageMetadata,
} from "./tasks";

export type CommunicationDraftId = string;
export type CommunicationTemplateId = string;
export type CommunicationWorkflowRunId = string;

export type CommunicationDraftType =
	| "missing_document_request"
	| "internal_handoff_note"
	| "packet_cover_note";

export type CommunicationDraftStatus =
	| "needs_human_review"
	| "revised_placeholder"
	| "approved_placeholder"
	| "archived_placeholder";

export type CommunicationDraftStrategy =
	| "deterministic_template_only"
	| "provider_assisted_draft";

export type CommunicationAudienceType =
	| "external_party"
	| "internal_operator"
	| "packet_consumer";

export type CommunicationTemplateSourceInput =
	| "case"
	| "readiness"
	| "checklist_missing_items"
	| "open_actions"
	| "linked_documents"
	| "extraction_summary"
	| "packet"
	| "workflow_pack_run"
	| "document_evidence";

export type CommunicationDraftSectionType =
	| "summary"
	| "request_items"
	| "follow_up_items"
	| "packet_context"
	| "evidence_snippets"
	| "closing"
	| "operator_review_note";

export type CommunicationDraftSourceEntityType =
	| "case"
	| "case_metadata"
	| "workflow_run"
	| "workflow_pack_run"
	| "review_note"
	| "checklist"
	| "checklist_item"
	| "action_item"
	| "document"
	| "extraction_run"
	| "packet"
	| "packet_section"
	| "readiness_summary";

export type CommunicationEvidenceKind =
	| "state_summary"
	| "retrieved_document_chunk";

export type CommunicationCopyExportFormat =
	| "plain_text"
	| "markdown_text";

export interface CommunicationTemplateInputRequirement {
	input_id: CommunicationTemplateSourceInput;
	display_name: string;
	description: string;
	required: boolean;
}

export interface CommunicationTemplateMetadata {
	template_id: CommunicationTemplateId;
	draft_type: CommunicationDraftType;
	display_name: string;
	audience_type: CommunicationAudienceType;
	description: string;
	required_source_inputs: CommunicationTemplateInputRequirement[];
	provider_assisted_available: boolean;
	uses_deterministic_sections: boolean;
	supported_domain_pack_ids: DomainPackId[];
	supported_case_type_ids: CaseTypeTemplateId[];
	notes: string[];
}

export interface CommunicationDraftSourceMetadata {
	case_id: CaseId;
	case_title: string;
	case_status: CaseStatus;
	domain_pack_id: DomainPackId | null;
	case_type_id: CaseTypeTemplateId | null;
	readiness_status: ReadinessStatus;
	linked_document_count: number;
	extraction_run_count: number;
	missing_required_item_count: number;
	open_action_count: number;
	latest_packet_id: PacketId | null;
	workflow_run_id: CommunicationWorkflowRunId | null;
	workflow_pack_run_id: CommunicationWorkflowRunId | null;
	includes_document_evidence: boolean;
	notes: string[];
}

export interface CommunicationDraftSourceEntityReference {
	source_entity_type: CommunicationDraftSourceEntityType;
	source_entity_id: string;
	display_label: string;
	source_path: string;
	notes: string[];
}

export interface CommunicationDraftEvidenceReference {
	evidence_id: string;
	label: string;
	kind: CommunicationEvidenceKind;
	snippet_text: string;
	source_entity_type: CommunicationDraftSourceEntityType;
	source_entity_id: string;
	source_reference: SourceReference | null;
	notes: string[];
}

export interface CommunicationDraftSection {
	section_type: CommunicationDraftSectionType;
	title: string;
	body: string;
	bullet_items: string[];
	evidence_reference_ids: string[];
	notes: string[];
}

export interface CommunicationDraftReviewMetadata {
	requires_human_review: boolean;
	reviewed_by: string;
	reviewed_at: string;
	review_notes: string;
	last_updated_by: string;
	last_updated_at: string;
}

export interface CommunicationDraftGenerationMetadata {
	strategy: CommunicationDraftStrategy;
	provider: string;
	model_id: string;
	finish_reason: FinishReason | null;
	duration_ms: number | null;
	provider_request_id: string;
	usage: UsageMetadata | null;
	error: TaskExecutionError | null;
	used_document_evidence: boolean;
	notes: string[];
}

export interface CommunicationCopyExportArtifact {
	format: CommunicationCopyExportFormat;
	filename: string;
	content_text: string;
	generated_at: string;
}

export interface CommunicationDraftGenerateRequest {
	template_id: CommunicationTemplateId;
	strategy?: CommunicationDraftStrategy;
	operator_id?: string;
	packet_id?: PacketId | null;
	workflow_run_id?: CommunicationWorkflowRunId | null;
	workflow_pack_run_id?: CommunicationWorkflowRunId | null;
	include_document_evidence?: boolean;
	provider_selection?: ProviderSelection | null;
	note?: string;
}

export interface CommunicationDraftReviewUpdateRequest {
	status?: CommunicationDraftStatus | null;
	reviewed_by?: string;
	review_notes?: string;
}

export interface CommunicationDraftSummary {
	draft_id: CommunicationDraftId;
	case_id: CaseId;
	template_id: CommunicationTemplateId;
	draft_type: CommunicationDraftType;
	status: CommunicationDraftStatus;
	audience_type: CommunicationAudienceType;
	strategy: CommunicationDraftStrategy;
	packet_id: PacketId | null;
	workflow_run_id: CommunicationWorkflowRunId | null;
	workflow_pack_run_id: CommunicationWorkflowRunId | null;
	title: string;
	subject: string;
	created_at: string;
	updated_at: string;
}

export interface CommunicationDraftRecord {
	draft_id: CommunicationDraftId;
	case_id: CaseId;
	template_id: CommunicationTemplateId;
	draft_type: CommunicationDraftType;
	status: CommunicationDraftStatus;
	audience_type: CommunicationAudienceType;
	strategy: CommunicationDraftStrategy;
	packet_id: PacketId | null;
	workflow_run_id: CommunicationWorkflowRunId | null;
	workflow_pack_run_id: CommunicationWorkflowRunId | null;
	title: string;
	subject: string;
	sections: CommunicationDraftSection[];
	source_metadata: CommunicationDraftSourceMetadata;
	source_entities: CommunicationDraftSourceEntityReference[];
	evidence_references: CommunicationDraftEvidenceReference[];
	review: CommunicationDraftReviewMetadata;
	generation: CommunicationDraftGenerationMetadata;
	created_at: string;
	updated_at: string;
}

export interface CommunicationTemplateListResponse {
	templates: CommunicationTemplateMetadata[];
}

export interface CommunicationDraftListResponse {
	drafts: CommunicationDraftSummary[];
}

export interface CommunicationDraftGenerateResponse {
	result: NormalizedOperationResult;
	draft: CommunicationDraftRecord;
	template: CommunicationTemplateMetadata | null;
	copy_artifacts: CommunicationCopyExportArtifact[];
}

export interface CommunicationDraftDetailResponse {
	draft: CommunicationDraftRecord;
	template: CommunicationTemplateMetadata | null;
	copy_artifacts: CommunicationCopyExportArtifact[];
}

export interface CommunicationDraftSourceResponse {
	draft_id: CommunicationDraftId;
	source_metadata: CommunicationDraftSourceMetadata;
	source_entities: CommunicationDraftSourceEntityReference[];
	evidence_references: CommunicationDraftEvidenceReference[];
}

export interface CommunicationDraftReviewUpdateResponse {
	result: NormalizedOperationResult;
	draft: CommunicationDraftRecord;
}