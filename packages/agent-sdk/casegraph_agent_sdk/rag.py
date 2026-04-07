"""Shared contracts for retrieval-augmented task execution.

These types define normalized structures for evidence selection, citation
references, retrieval scope, and RAG-specific execution requests/results.
They are generic infrastructure contracts — no domain-specific fields.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from casegraph_agent_sdk.retrieval import SearchScoreMetadata, SourceReference
from casegraph_agent_sdk.tasks import (
    FinishReason,
    StructuredOutputResult,
    TaskExecutionError,
    TaskId,
    UsageMetadata,
)


# ---------------------------------------------------------------------------
# Evidence / citation references
# ---------------------------------------------------------------------------


class EvidenceChunkReference(BaseModel):
    """A single retrieved chunk used as evidence for a task."""

    chunk_id: str
    text: str
    score: SearchScoreMetadata
    source_reference: SourceReference
    source_filename: str | None = None
    page_number: int | None = None


class CitationReference(BaseModel):
    """A citation linking part of the output to retrieved evidence.

    This represents an honest chunk-level citation — the system does not
    claim fine-grained sentence-to-source mapping unless the provider
    truly supports it.
    """

    citation_index: int = Field(description="1-based citation index in the output.")
    chunk_id: str = Field(description="ID of the cited evidence chunk.")
    document_id: str | None = Field(default=None, description="Source document ID if available.")
    page_number: int | None = Field(default=None, description="Source page number if available.")
    source_filename: str | None = Field(default=None, description="Source filename if available.")


# ---------------------------------------------------------------------------
# Evidence selection summary
# ---------------------------------------------------------------------------


class EvidenceSelectionSummary(BaseModel):
    """Summary of the evidence selection step."""

    query: str = Field(description="The retrieval query used.")
    total_retrieved: int = Field(default=0, description="Total chunks returned by retrieval.")
    total_selected: int = Field(default=0, description="Chunks selected for context after filtering/truncation.")
    embedding_model: str | None = None
    vector_store: str | None = None


# ---------------------------------------------------------------------------
# Retrieval scope
# ---------------------------------------------------------------------------

RetrievalScopeKind = Literal["global", "case", "document"]


class RetrievalScope(BaseModel):
    """Defines the scope of retrieval for evidence selection."""

    kind: RetrievalScopeKind = Field(
        default="global",
        description="'global' searches all indexed knowledge; 'case' restricts to case-linked documents; 'document' restricts to specific document IDs.",
    )
    case_id: str | None = Field(
        default=None,
        description="Case ID for case-scoped retrieval. Required when kind='case'.",
    )
    document_ids: list[str] = Field(
        default_factory=list,
        description="Explicit document ID filter. Used when kind='document' or to further narrow within a case.",
    )

    @field_validator("case_id")
    @classmethod
    def normalize_case_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("document_ids")
    @classmethod
    def normalize_document_ids(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            trimmed = item.strip()
            if not trimmed or trimmed in seen:
                continue
            normalized.append(trimmed)
            seen.add(trimmed)
        return normalized

    @model_validator(mode="after")
    def validate_scope_requirements(self) -> "RetrievalScope":
        if self.kind == "case" and self.case_id is None:
            raise ValueError("case_id is required when retrieval_scope.kind='case'.")
        if self.kind == "document" and not self.document_ids:
            raise ValueError("document_ids must contain at least one ID when retrieval_scope.kind='document'.")
        return self


# ---------------------------------------------------------------------------
# RAG execution request / result
# ---------------------------------------------------------------------------


class RagTaskExecutionRequest(BaseModel):
    """Request to execute an evidence-backed task."""

    task_id: TaskId
    query: str = Field(description="User query or instruction for the task.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional task-specific parameters.",
    )
    provider_selection: "ProviderSelection"
    retrieval_scope: RetrievalScope = Field(default_factory=RetrievalScope)
    top_k: int = Field(default=5, ge=1, le=50, description="Number of evidence chunks to retrieve.")
    structured_output: "StructuredOutputSchema | None" = None
    max_tokens: int | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class ResultGroundingMetadata(BaseModel):
    """Metadata about how well the result is grounded in evidence."""

    evidence_provided: bool = Field(
        default=False,
        description="Whether any evidence was provided to the model.",
    )
    evidence_chunk_count: int = Field(
        default=0,
        description="Number of evidence chunks passed to the model.",
    )
    citation_count: int = Field(
        default=0,
        description="Number of citations returned in the output.",
    )
    grounding_method: str = Field(
        default="chunk_reference",
        description="Method used for grounding: 'chunk_reference' = honest chunk-level citations.",
    )


class RagTaskExecutionResult(BaseModel):
    """Normalized result from an evidence-backed task execution."""

    task_id: TaskId
    provider: str
    model_id: str
    finish_reason: FinishReason
    output_text: str | None = None
    structured_output: StructuredOutputResult | None = None
    citations: list[CitationReference] = Field(default_factory=list)
    evidence: list[EvidenceChunkReference] = Field(default_factory=list)
    evidence_summary: EvidenceSelectionSummary | None = None
    grounding: ResultGroundingMetadata | None = None
    usage: UsageMetadata | None = None
    error: TaskExecutionError | None = None
    duration_ms: int | None = None
    provider_request_id: str | None = None


# ---------------------------------------------------------------------------
# RAG task registry response
# ---------------------------------------------------------------------------


class RagTaskDefinitionMeta(BaseModel):
    """Metadata describing a registered evidence-backed task."""

    task_id: TaskId
    display_name: str
    category: str
    description: str
    requires_evidence: bool = Field(
        default=True,
        description="Whether this task requires retrieved evidence to function.",
    )
    returns_citations: bool = Field(
        default=True,
        description="Whether this task attempts to return citation references.",
    )
    supports_structured_output: bool = False
    output_schema: dict[str, Any] = Field(default_factory=dict)


class RagTaskRegistryResponse(BaseModel):
    """Response listing all registered evidence-backed tasks."""

    tasks: list[RagTaskDefinitionMeta] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# RAG-specific event kinds
# ---------------------------------------------------------------------------

RagEventKind = Literal[
    "retrieval_started",
    "retrieval_completed",
    "evidence_selected",
    "context_assembled",
    "provider_resolved",
    "model_invoked",
    "model_completed",
    "structured_output_validated",
    "citations_attached",
    "model_failed",
    "retrieval_failed",
]


# ---------------------------------------------------------------------------
# Forward-reference imports (avoid circular at module level)
# ---------------------------------------------------------------------------

from casegraph_agent_sdk.tasks import ProviderSelection, StructuredOutputSchema  # noqa: E402

RagTaskExecutionRequest.model_rebuild()
