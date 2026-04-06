"""Shared communication draft contracts.

This layer defines reviewable communication drafts grounded in explicit
case, readiness, action, document, extraction, packet, and workflow state.
It does not implement outbound delivery, recipient resolution, legal or
regulatory review, or autonomous communication.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.cases import CaseId, CaseStatus
from casegraph_agent_sdk.domains import CaseTypeTemplateId, DomainPackId
from casegraph_agent_sdk.packets import PacketId
from casegraph_agent_sdk.readiness import ReadinessStatus
from casegraph_agent_sdk.retrieval import SourceReference
from casegraph_agent_sdk.submissions import NormalizedOperationResult
from casegraph_agent_sdk.tasks import (
	FinishReason,
	ProviderSelection,
	TaskExecutionError,
	UsageMetadata,
)

CommunicationDraftId = str
CommunicationTemplateId = str
CommunicationWorkflowRunId = str

CommunicationDraftType = Literal[
	"missing_document_request",
	"internal_handoff_note",
	"packet_cover_note",
]

CommunicationDraftStatus = Literal[
	"needs_human_review",
	"revised_placeholder",
	"approved_placeholder",
	"archived_placeholder",
]

CommunicationDraftStrategy = Literal[
	"deterministic_template_only",
	"provider_assisted_draft",
]

CommunicationAudienceType = Literal[
	"external_party",
	"internal_operator",
	"packet_consumer",
]

CommunicationTemplateSourceInput = Literal[
	"case",
	"readiness",
	"checklist_missing_items",
	"open_actions",
	"linked_documents",
	"extraction_summary",
	"packet",
	"workflow_pack_run",
	"document_evidence",
]

CommunicationDraftSectionType = Literal[
	"summary",
	"request_items",
	"follow_up_items",
	"packet_context",
	"evidence_snippets",
	"closing",
	"operator_review_note",
]

CommunicationDraftSourceEntityType = Literal[
	"case",
	"case_metadata",
	"workflow_run",
	"workflow_pack_run",
	"review_note",
	"checklist",
	"checklist_item",
	"action_item",
	"document",
	"extraction_run",
	"packet",
	"packet_section",
	"readiness_summary",
]

CommunicationEvidenceKind = Literal[
	"state_summary",
	"retrieved_document_chunk",
]

CommunicationCopyExportFormat = Literal[
	"plain_text",
	"markdown_text",
]


class CommunicationTemplateInputRequirement(BaseModel):
	input_id: CommunicationTemplateSourceInput
	display_name: str
	description: str = ""
	required: bool = False


class CommunicationTemplateMetadata(BaseModel):
	template_id: CommunicationTemplateId
	draft_type: CommunicationDraftType
	display_name: str
	audience_type: CommunicationAudienceType
	description: str = ""
	required_source_inputs: list[CommunicationTemplateInputRequirement] = Field(default_factory=list)
	provider_assisted_available: bool = False
	uses_deterministic_sections: bool = True
	supported_domain_pack_ids: list[DomainPackId] = Field(default_factory=list)
	supported_case_type_ids: list[CaseTypeTemplateId] = Field(default_factory=list)
	notes: list[str] = Field(default_factory=list)


class CommunicationDraftSourceMetadata(BaseModel):
	case_id: CaseId
	case_title: str = ""
	case_status: CaseStatus = "open"
	domain_pack_id: DomainPackId | None = None
	case_type_id: CaseTypeTemplateId | None = None
	readiness_status: ReadinessStatus = "not_evaluated"
	linked_document_count: int = 0
	extraction_run_count: int = 0
	missing_required_item_count: int = 0
	open_action_count: int = 0
	latest_packet_id: PacketId | None = None
	workflow_run_id: CommunicationWorkflowRunId | None = None
	workflow_pack_run_id: CommunicationWorkflowRunId | None = None
	includes_document_evidence: bool = False
	notes: list[str] = Field(default_factory=list)


class CommunicationDraftSourceEntityReference(BaseModel):
	source_entity_type: CommunicationDraftSourceEntityType
	source_entity_id: str = ""
	display_label: str = ""
	source_path: str = ""
	notes: list[str] = Field(default_factory=list)


class CommunicationDraftEvidenceReference(BaseModel):
	evidence_id: str
	label: str
	kind: CommunicationEvidenceKind = "state_summary"
	snippet_text: str = ""
	source_entity_type: CommunicationDraftSourceEntityType
	source_entity_id: str = ""
	source_reference: SourceReference | None = None
	notes: list[str] = Field(default_factory=list)


class CommunicationDraftSection(BaseModel):
	section_type: CommunicationDraftSectionType
	title: str
	body: str = ""
	bullet_items: list[str] = Field(default_factory=list)
	evidence_reference_ids: list[str] = Field(default_factory=list)
	notes: list[str] = Field(default_factory=list)


class CommunicationDraftReviewMetadata(BaseModel):
	requires_human_review: bool = True
	reviewed_by: str = ""
	reviewed_at: str = ""
	review_notes: str = ""
	last_updated_by: str = ""
	last_updated_at: str = ""


class CommunicationDraftGenerationMetadata(BaseModel):
	strategy: CommunicationDraftStrategy
	provider: str = ""
	model_id: str = ""
	finish_reason: FinishReason | None = None
	duration_ms: int | None = None
	provider_request_id: str = ""
	usage: UsageMetadata | None = None
	error: TaskExecutionError | None = None
	used_document_evidence: bool = False
	notes: list[str] = Field(default_factory=list)


class CommunicationCopyExportArtifact(BaseModel):
	format: CommunicationCopyExportFormat
	filename: str = ""
	content_text: str = ""
	generated_at: str = ""


class CommunicationDraftGenerateRequest(BaseModel):
	template_id: CommunicationTemplateId
	strategy: CommunicationDraftStrategy = "deterministic_template_only"
	operator_id: str = ""
	packet_id: PacketId | None = None
	workflow_run_id: CommunicationWorkflowRunId | None = None
	workflow_pack_run_id: CommunicationWorkflowRunId | None = None
	include_document_evidence: bool = False
	provider_selection: ProviderSelection | None = None
	note: str = ""


class CommunicationDraftReviewUpdateRequest(BaseModel):
	status: CommunicationDraftStatus | None = None
	reviewed_by: str = ""
	review_notes: str = ""


class CommunicationDraftSummary(BaseModel):
	draft_id: CommunicationDraftId
	case_id: CaseId
	template_id: CommunicationTemplateId
	draft_type: CommunicationDraftType
	status: CommunicationDraftStatus = "needs_human_review"
	audience_type: CommunicationAudienceType
	strategy: CommunicationDraftStrategy
	packet_id: PacketId | None = None
	workflow_run_id: CommunicationWorkflowRunId | None = None
	workflow_pack_run_id: CommunicationWorkflowRunId | None = None
	title: str = ""
	subject: str = ""
	created_at: str = ""
	updated_at: str = ""


class CommunicationDraftRecord(BaseModel):
	draft_id: CommunicationDraftId
	case_id: CaseId
	template_id: CommunicationTemplateId
	draft_type: CommunicationDraftType
	status: CommunicationDraftStatus = "needs_human_review"
	audience_type: CommunicationAudienceType
	strategy: CommunicationDraftStrategy
	packet_id: PacketId | None = None
	workflow_run_id: CommunicationWorkflowRunId | None = None
	workflow_pack_run_id: CommunicationWorkflowRunId | None = None
	title: str = ""
	subject: str = ""
	sections: list[CommunicationDraftSection] = Field(default_factory=list)
	source_metadata: CommunicationDraftSourceMetadata
	source_entities: list[CommunicationDraftSourceEntityReference] = Field(default_factory=list)
	evidence_references: list[CommunicationDraftEvidenceReference] = Field(default_factory=list)
	review: CommunicationDraftReviewMetadata = Field(default_factory=CommunicationDraftReviewMetadata)
	generation: CommunicationDraftGenerationMetadata
	created_at: str = ""
	updated_at: str = ""


class CommunicationTemplateListResponse(BaseModel):
	templates: list[CommunicationTemplateMetadata] = Field(default_factory=list)


class CommunicationDraftListResponse(BaseModel):
	drafts: list[CommunicationDraftSummary] = Field(default_factory=list)


class CommunicationDraftGenerateResponse(BaseModel):
	result: NormalizedOperationResult
	draft: CommunicationDraftRecord
	template: CommunicationTemplateMetadata | None = None
	copy_artifacts: list[CommunicationCopyExportArtifact] = Field(default_factory=list)


class CommunicationDraftDetailResponse(BaseModel):
	draft: CommunicationDraftRecord
	template: CommunicationTemplateMetadata | None = None
	copy_artifacts: list[CommunicationCopyExportArtifact] = Field(default_factory=list)


class CommunicationDraftSourceResponse(BaseModel):
	draft_id: CommunicationDraftId
	source_metadata: CommunicationDraftSourceMetadata
	source_entities: list[CommunicationDraftSourceEntityReference] = Field(default_factory=list)
	evidence_references: list[CommunicationDraftEvidenceReference] = Field(default_factory=list)


class CommunicationDraftReviewUpdateResponse(BaseModel):
	result: NormalizedOperationResult
	draft: CommunicationDraftRecord