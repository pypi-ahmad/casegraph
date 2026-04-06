"""Shared target-pack contracts.

Target packs are versioned metadata definitions that connect a concrete
operational target shape to existing CaseGraph foundations such as domain packs,
submission targets, extraction templates, communication templates, and
workflow packs.

They do not implement official form logic, portal selectors, filing rules,
or external integration behavior.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.domains import (
    CaseTypeTemplateId,
    DocumentCategory,
    DocumentRequirementId,
    DocumentRequirementPriority,
    DomainPackId,
)


TargetPackId = str
TargetPackVersion = str
SubmissionTargetId = str
ExtractionTemplateId = str
CommunicationTemplateId = str
WorkflowPackId = str

TargetPackStatus = Literal[
    "draft_metadata",
    "active_metadata",
    "superseded",
]

TargetPackCategory = Literal[
    "payer_prior_auth_pack",
    "insurer_claim_pack",
    "insurance_correspondence_pack",
    "tax_notice_pack",
    "tax_intake_pack",
    "generic_form_pack",
]

TargetOrganizationType = Literal[
    "payer",
    "insurer",
    "tax_agency",
    "internal",
    "generic",
]

TargetFieldType = Literal[
    "text",
    "long_text",
    "identifier",
    "date",
    "document_list",
    "boolean",
]

TargetRequirementOverrideMode = Literal[
    "add_requirement",
    "refine_requirement",
]

TargetTemplateBindingType = Literal[
    "extraction_template",
    "communication_template",
]


class TargetOrganizationMetadata(BaseModel):
    organization_type: TargetOrganizationType = "generic"
    organization_id: str = ""
    display_name: str
    description: str = ""
    notes: list[str] = Field(default_factory=list)


class TargetPackMetadata(BaseModel):
    pack_id: TargetPackId
    version: TargetPackVersion = "1.0.0"
    status: TargetPackStatus = "draft_metadata"
    category: TargetPackCategory
    display_name: str
    description: str = ""
    organization: TargetOrganizationMetadata
    notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TargetPackCompatibilityRecord(BaseModel):
    compatible_domain_pack_ids: list[DomainPackId] = Field(default_factory=list)
    compatible_case_type_ids: list[CaseTypeTemplateId] = Field(default_factory=list)
    compatible_workflow_pack_ids: list[WorkflowPackId] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TargetFieldDefinition(BaseModel):
    field_id: str
    display_name: str
    field_type: TargetFieldType = "text"
    description: str = ""
    required: bool = False
    candidate_source_paths: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TargetFieldSection(BaseModel):
    section_id: str
    display_name: str
    description: str = ""
    fields: list[TargetFieldDefinition] = Field(default_factory=list)


class TargetFieldSchema(BaseModel):
    sections: list[TargetFieldSection] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TargetRequirementOverride(BaseModel):
    override_id: str
    mode: TargetRequirementOverrideMode = "refine_requirement"
    base_requirement_id: DocumentRequirementId | None = None
    display_name: str
    description: str = ""
    document_category: DocumentCategory = "other"
    priority: DocumentRequirementPriority = "required"
    requirement_group: str = ""
    notes: list[str] = Field(default_factory=list)


class TargetTemplateBinding(BaseModel):
    binding_type: TargetTemplateBindingType
    template_id: ExtractionTemplateId | CommunicationTemplateId
    display_name: str
    description: str = ""
    notes: list[str] = Field(default_factory=list)


class TargetSubmissionCompatibility(BaseModel):
    submission_target_ids: list[SubmissionTargetId] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TargetAutomationCompatibility(BaseModel):
    supported_backend_ids: list[str] = Field(default_factory=list)
    supports_dry_run_planning: bool = True
    supports_live_execution: bool = False
    notes: list[str] = Field(default_factory=list)


class CaseTargetPackSelection(BaseModel):
    pack_id: TargetPackId
    version: TargetPackVersion
    display_name: str
    category: TargetPackCategory
    selected_at: str = ""


class TargetPackSummary(BaseModel):
    metadata: TargetPackMetadata
    compatibility: TargetPackCompatibilityRecord
    field_section_count: int = 0
    field_count: int = 0
    requirement_override_count: int = 0
    template_binding_count: int = 0
    submission_target_count: int = 0


class TargetPackDetail(BaseModel):
    metadata: TargetPackMetadata
    compatibility: TargetPackCompatibilityRecord
    field_schema: TargetFieldSchema = Field(default_factory=TargetFieldSchema)
    requirement_overrides: list[TargetRequirementOverride] = Field(default_factory=list)
    template_bindings: list[TargetTemplateBinding] = Field(default_factory=list)
    submission_compatibility: TargetSubmissionCompatibility = Field(default_factory=TargetSubmissionCompatibility)
    automation_compatibility: TargetAutomationCompatibility = Field(default_factory=TargetAutomationCompatibility)


class TargetPackOperationError(BaseModel):
    error_code: str
    message: str
    recoverable: bool = False


class TargetPackOperationResult(BaseModel):
    success: bool = True
    message: str = ""
    error: TargetPackOperationError | None = None


class TargetPackListFilters(BaseModel):
    domain_pack_id: DomainPackId | None = None
    case_type_id: CaseTypeTemplateId | None = None
    category: TargetPackCategory | None = None
    status: TargetPackStatus | None = None


class UpdateCaseTargetPackRequest(BaseModel):
    pack_id: TargetPackId | None = None
    clear_selection: bool = False


class TargetPackListResponse(BaseModel):
    filters: TargetPackListFilters = Field(default_factory=TargetPackListFilters)
    packs: list[TargetPackSummary] = Field(default_factory=list)


class TargetPackDetailResponse(BaseModel):
    pack: TargetPackDetail


class TargetPackCompatibilityResponse(BaseModel):
    pack_id: TargetPackId
    compatibility: TargetPackCompatibilityRecord


class TargetPackFieldSchemaResponse(BaseModel):
    pack_id: TargetPackId
    field_schema: TargetFieldSchema


class TargetPackRequirementsResponse(BaseModel):
    pack_id: TargetPackId
    requirement_overrides: list[TargetRequirementOverride] = Field(default_factory=list)


class CaseTargetPackResponse(BaseModel):
    case_id: str
    selection: CaseTargetPackSelection | None = None


class CaseTargetPackUpdateResponse(BaseModel):
    result: TargetPackOperationResult
    case_id: str
    selection: CaseTargetPackSelection | None = None