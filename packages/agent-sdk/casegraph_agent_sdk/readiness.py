"""Shared case readiness and requirement checklist contracts.

These types define the structured readiness/checklist layer — how cases
derive requirement checklists from domain pack case type templates, how
documents and extraction results link to checklist items, and how
readiness is evaluated.

This is a structured operational metadata layer. It does not implement
rules engines, compliance validators, adjudication logic, or filing
decision systems.
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
from casegraph_agent_sdk.ingestion import DocumentId

# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

ChecklistId = str
ChecklistItemId = str

# ---------------------------------------------------------------------------
# Status literals
# ---------------------------------------------------------------------------

ChecklistItemStatus = Literal[
    "missing",
    "partially_supported",
    "supported",
    "needs_human_review",
    "optional_unfilled",
    "waived",
]

ReadinessStatus = Literal[
    "not_evaluated",
    "incomplete",
    "needs_review",
    "ready",
]


# ---------------------------------------------------------------------------
# Evidence / linkage references
# ---------------------------------------------------------------------------

class LinkedDocumentReference(BaseModel):
    """A case document linked as support for a checklist item."""

    document_id: DocumentId
    filename: str = ""
    content_type: str = ""
    linked_at: str = ""


class LinkedExtractionReference(BaseModel):
    """An extraction run result linked as support for a checklist item."""

    extraction_id: str
    template_id: str
    document_id: DocumentId
    field_count: int = 0
    grounding_available: bool = False


class LinkedEvidenceReference(BaseModel):
    """A retrieval/evidence chunk linked as support for a checklist item."""

    source_document_id: DocumentId
    chunk_summary: str = ""
    page_number: int | None = None


# ---------------------------------------------------------------------------
# Checklist item
# ---------------------------------------------------------------------------

class ChecklistItem(BaseModel):
    """A single requirement item within a case checklist.

    Each item corresponds to a DocumentRequirementDefinition from the
    domain pack case type template.
    """

    item_id: ChecklistItemId
    checklist_id: ChecklistId
    requirement_id: DocumentRequirementId
    display_name: str
    description: str = ""
    document_category: DocumentCategory
    priority: DocumentRequirementPriority
    status: ChecklistItemStatus = "missing"
    operator_notes: str = ""
    linked_documents: list[LinkedDocumentReference] = Field(default_factory=list)
    linked_extractions: list[LinkedExtractionReference] = Field(default_factory=list)
    linked_evidence: list[LinkedEvidenceReference] = Field(default_factory=list)
    last_evaluated_at: str | None = None


# ---------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------

class ChecklistGenerationMetadata(BaseModel):
    """How and when the checklist was generated."""

    generated_at: str
    domain_pack_id: DomainPackId
    case_type_id: CaseTypeTemplateId
    requirement_count: int = 0


class CaseChecklist(BaseModel):
    """Full checklist for a case, derived from its domain pack case type."""

    checklist_id: ChecklistId
    case_id: str
    generation: ChecklistGenerationMetadata
    items: list[ChecklistItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Readiness summary
# ---------------------------------------------------------------------------

class MissingItemSummary(BaseModel):
    """Summary of a single missing or unsupported requirement."""

    item_id: ChecklistItemId
    requirement_id: DocumentRequirementId
    display_name: str
    priority: DocumentRequirementPriority
    status: ChecklistItemStatus


class ReadinessSummary(BaseModel):
    """Honest readiness evaluation for a case checklist.

    Counts are derived from explicit linked artifacts only.
    No fabricated confidence or completeness scores.
    """

    case_id: str
    checklist_id: ChecklistId
    readiness_status: ReadinessStatus = "not_evaluated"
    total_items: int = 0
    required_items: int = 0
    supported_items: int = 0
    partially_supported_items: int = 0
    missing_items: int = 0
    needs_review_items: int = 0
    optional_unfilled_items: int = 0
    waived_items: int = 0
    missing_required: list[MissingItemSummary] = Field(default_factory=list)
    evaluated_at: str = ""


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------

class GenerateChecklistRequest(BaseModel):
    """Request to generate (or regenerate) a checklist for a case."""

    force: bool = False


class EvaluateChecklistRequest(BaseModel):
    """Request to evaluate checklist coverage for a case."""
    pass


class UpdateChecklistItemRequest(BaseModel):
    """Operator note or manual override for a checklist item."""

    operator_notes: str | None = None
    status_override: ChecklistItemStatus | None = None


class ChecklistResponse(BaseModel):
    """Full checklist with items."""

    checklist: CaseChecklist


class ReadinessResponse(BaseModel):
    """Readiness evaluation result."""

    readiness: ReadinessSummary
