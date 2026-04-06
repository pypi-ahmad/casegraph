"""Shared retrieval / knowledge contracts for the CaseGraph platform.

These types define normalized structures for chunking, vector indexing,
and search over ingested document artifacts.  They are generic and do not
encode domain-specific business semantics.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

ChunkId = str
KnowledgeItemId = str


# ---------------------------------------------------------------------------
# Source references — lightweight back-pointers into ingestion artifacts
# ---------------------------------------------------------------------------

class SourceReference(BaseModel):
    """Points a chunk back to its originating document, page, and blocks."""

    document_id: str
    page_number: int | None = None
    block_ids: list[str] = Field(default_factory=list)
    geometry_source: str | None = None


# ---------------------------------------------------------------------------
# Chunk
# ---------------------------------------------------------------------------

class ChunkMetadata(BaseModel):
    """Structured metadata stored alongside each chunk in the vector index."""

    document_id: str
    page_number: int | None = None
    block_ids: list[str] = Field(default_factory=list)
    source_filename: str | None = None
    chunk_index: int = 0
    total_chunks: int = 0


class ChunkContent(BaseModel):
    """A single text chunk ready for embedding and indexing."""

    chunk_id: ChunkId
    text: str
    metadata: ChunkMetadata
    source_reference: SourceReference


# ---------------------------------------------------------------------------
# Embedding model metadata
# ---------------------------------------------------------------------------

class EmbeddingModelInfo(BaseModel):
    model_name: str
    dimension: int
    provider: str = "local"
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Index request / result
# ---------------------------------------------------------------------------

class IndexRequest(BaseModel):
    """Request to index chunks from a previously ingested document."""

    document_id: str
    chunks: list[ChunkContent] = Field(default_factory=list)


class IndexResultSummary(BaseModel):
    document_id: str
    chunks_indexed: int = 0
    embedding_model: str | None = None
    vector_store: str | None = None


class IndexResult(BaseModel):
    summary: IndexResultSummary
    errors: list[RetrievalError] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Search request / result
# ---------------------------------------------------------------------------

class MetadataFilter(BaseModel):
    field: str
    value: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=100)
    filters: list[MetadataFilter] = Field(default_factory=list)


class SearchScoreMetadata(BaseModel):
    raw_score: float
    normalized_score: float | None = None
    scoring_method: str = "cosine_similarity"


class SearchResultItem(BaseModel):
    chunk_id: ChunkId
    text: str
    score: SearchScoreMetadata
    metadata: ChunkMetadata
    source_reference: SourceReference


class SearchResult(BaseModel):
    query: str
    items: list[SearchResultItem] = Field(default_factory=list)
    total_results: int = 0
    embedding_model: str | None = None
    vector_store: str | None = None


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class RetrievalError(BaseModel):
    code: str
    message: str
    recoverable: bool = False


# ---------------------------------------------------------------------------
# Forward-reference fix — IndexResult references RetrievalError which is
# defined after it in the module; Pydantic v2 handles this via
# model_rebuild().
# ---------------------------------------------------------------------------

IndexResult.model_rebuild()


# ---------------------------------------------------------------------------
# Knowledge capability / status — shared between API and frontend
# ---------------------------------------------------------------------------


class KnowledgeCapabilityStatus(BaseModel):
    component: str
    available: bool
    name: str | None = None
    notes: list[str] = Field(default_factory=list)


class KnowledgeCapabilitiesResponse(BaseModel):
    embedding: KnowledgeCapabilityStatus
    vector_store: KnowledgeCapabilityStatus
    embedding_model: EmbeddingModelInfo | None = None
    indexed_chunks: int = 0
    limitations: list[str] = Field(default_factory=list)
