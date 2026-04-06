"""Shared domain pack contracts for the CaseGraph platform.

These types define jurisdiction-aware domain packs, case type templates,
workflow/extraction template bindings, and document requirement registries
for regulated/operational domains such as medical, insurance, and taxation.

This is a structured operational metadata layer — not a rules engine,
compliance engine, or decision-making system.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.extraction import ExtractionTemplateId


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

DomainPackId = str
CaseTypeTemplateId = str
DocumentRequirementId = str


# ---------------------------------------------------------------------------
# Enums and literals
# ---------------------------------------------------------------------------

Jurisdiction = Literal["us", "india"]

DomainCategory = Literal[
    "medical",
    "medical_insurance",
    "insurance",
    "taxation",
]

CaseTypeStatus = Literal[
    "open",
    "intake",
    "document_collection",
    "under_review",
    "pending_action",
    "escalated",
    "closed",
    "archived",
]

DocumentRequirementStatus = Literal[
    "not_submitted",
    "submitted",
    "accepted",
    "rejected",
    "waived",
]

DocumentRequirementPriority = Literal[
    "required",
    "recommended",
    "optional",
]

DocumentCategory = Literal[
    "identity",
    "referral_order",
    "prior_records",
    "insurer_payer_correspondence",
    "policy_document",
    "claim_form",
    "invoice_bill",
    "tax_notice",
    "income_document",
    "supporting_attachment",
    "clinical_notes",
    "diagnostic_report",
    "prescription",
    "proof_of_loss",
    "government_form",
    "other",
]


# ---------------------------------------------------------------------------
# Document requirement definition
# ---------------------------------------------------------------------------

class DocumentRequirementDefinition(BaseModel):
    """A single document requirement for a case type template.

    This is a metadata definition only — it does not enforce filing rules,
    payer policies, or regulatory compliance logic.
    """

    requirement_id: DocumentRequirementId
    display_name: str
    description: str = ""
    document_category: DocumentCategory
    priority: DocumentRequirementPriority = "required"
    accepted_extensions: list[str] = Field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Workflow and extraction bindings
# ---------------------------------------------------------------------------

class WorkflowBindingMetadata(BaseModel):
    """Reference to a workflow definition applicable to a case type."""

    workflow_id: str
    display_name: str
    description: str = ""
    binding_notes: str = ""


class ExtractionBindingMetadata(BaseModel):
    """Reference to an extraction template applicable to a case type."""

    extraction_template_id: ExtractionTemplateId
    display_name: str
    description: str = ""
    binding_notes: str = ""


# ---------------------------------------------------------------------------
# Case type template
# ---------------------------------------------------------------------------

class CaseTypeTemplateMetadata(BaseModel):
    """Metadata for a case type template within a domain pack.

    Case type templates define the operational shape of a case: what
    documents are needed, which workflows apply, what extraction templates
    are useful, and what stages the case may go through.
    """

    case_type_id: CaseTypeTemplateId
    display_name: str
    description: str = ""
    domain_pack_id: DomainPackId
    typical_stages: list[CaseTypeStatus] = Field(default_factory=list)
    workflow_bindings: list[WorkflowBindingMetadata] = Field(default_factory=list)
    extraction_bindings: list[ExtractionBindingMetadata] = Field(default_factory=list)
    document_requirements: list[DocumentRequirementDefinition] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Domain pack metadata
# ---------------------------------------------------------------------------

class DomainPackCapabilities(BaseModel):
    """Capability and limitation summary for a domain pack.

    Keeps the system honest about what is metadata vs what is executable.
    """

    has_case_types: bool = False
    has_workflow_bindings: bool = False
    has_extraction_bindings: bool = False
    has_document_requirements: bool = False
    limitations: list[str] = Field(default_factory=list)


class DomainPackMetadata(BaseModel):
    """Metadata for a registered domain pack."""

    pack_id: DomainPackId
    display_name: str
    description: str = ""
    domain_category: DomainCategory
    jurisdiction: Jurisdiction
    case_type_count: int = 0
    capabilities: DomainPackCapabilities = Field(default_factory=DomainPackCapabilities)


class DomainPackDetail(BaseModel):
    """Full domain pack with case type templates."""

    metadata: DomainPackMetadata
    case_types: list[CaseTypeTemplateMetadata] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Case domain context — stored on a case record
# ---------------------------------------------------------------------------

class CaseDomainContext(BaseModel):
    """Domain context attached to a case when created from a domain pack.

    Stored as part of case metadata. Optional — not all cases are domain-scoped.
    """

    domain_pack_id: DomainPackId
    jurisdiction: Jurisdiction
    case_type_id: CaseTypeTemplateId
    domain_category: DomainCategory


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------

class DomainPackListResponse(BaseModel):
    """Summary list of all registered domain packs."""

    packs: list[DomainPackMetadata] = Field(default_factory=list)


class DomainPackDetailResponse(BaseModel):
    """Full detail for a single domain pack."""

    pack: DomainPackDetail


class CaseTypeDetailResponse(BaseModel):
    """Full detail for a single case type template."""

    case_type: CaseTypeTemplateMetadata
    pack_metadata: DomainPackMetadata
