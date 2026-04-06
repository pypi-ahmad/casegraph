"""Evidence selection — retrieves and prepares context chunks for RAG tasks.

This service bridges the existing knowledge/search foundation and the
task execution layer.  It does NOT duplicate retrieval logic — it delegates
to ``SearchService`` and applies filtering, truncation, and formatting.
"""

from __future__ import annotations

import logging
from casegraph_agent_sdk.rag import (
    EvidenceChunkReference,
    EvidenceSelectionSummary,
    RetrievalScope,
)
from casegraph_agent_sdk.retrieval import MetadataFilter, SearchRequest, SearchResultItem

from app.knowledge.search import SearchService

logger = logging.getLogger(__name__)

# Maximum total characters of evidence text to include in prompt context.
MAX_EVIDENCE_CHARS = 12_000


class EvidenceSelectionResult:
    """Container for selected evidence and metadata."""

    __slots__ = ("chunks", "summary")

    def __init__(
        self,
        chunks: list[EvidenceChunkReference],
        summary: EvidenceSelectionSummary,
    ) -> None:
        self.chunks = chunks
        self.summary = summary


class EvidenceSelector:
    """Selects and prepares evidence chunks for a RAG task."""

    def __init__(self, search_service: SearchService) -> None:
        self._search = search_service

    def select(
        self,
        query: str,
        *,
        top_k: int = 5,
        scope: RetrievalScope | None = None,
        document_ids: list[str] | None = None,
    ) -> EvidenceSelectionResult:
        """Retrieve chunks and select the best evidence.

        Parameters
        ----------
        query:
            The user query / instruction.
        top_k:
            Maximum chunks to retrieve from the vector store.
        scope:
            Retrieval scope (global, case, document).
        document_ids:
            Explicit document IDs from case-scoped resolution.
            These override scope.document_ids when provided.
        """
        resolved_document_ids = self._resolve_document_ids(scope, document_ids)
        if resolved_document_ids == []:
            return EvidenceSelectionResult(
                chunks=[],
                summary=EvidenceSelectionSummary(
                    query=query,
                    total_retrieved=0,
                    total_selected=0,
                ),
            )

        filters = self._build_filters(resolved_document_ids)
        request = SearchRequest(query=query, top_k=top_k, filters=filters)
        result = self._search.search(request)

        # Select and truncate
        selected = self._select_and_truncate(result.items)

        chunks = [self._to_evidence_ref(item) for item in selected]

        summary = EvidenceSelectionSummary(
            query=query,
            total_retrieved=result.total_results,
            total_selected=len(chunks),
            embedding_model=result.embedding_model,
            vector_store=result.vector_store,
        )

        return EvidenceSelectionResult(chunks=chunks, summary=summary)

    def _resolve_document_ids(
        self,
        scope: RetrievalScope | None,
        case_document_ids: list[str] | None,
    ) -> list[str] | None:
        """Resolve the document IDs that retrieval is actually allowed to search."""
        if scope is None or scope.kind == "global":
            return None

        requested_document_ids = list(scope.document_ids)

        if scope.kind == "case":
            if case_document_ids is None:
                return []
            if requested_document_ids:
                allowed_ids = set(case_document_ids)
                return [doc_id for doc_id in requested_document_ids if doc_id in allowed_ids]
            return list(case_document_ids)

        return requested_document_ids

    def _build_filters(
        self,
        document_ids: list[str] | None,
    ) -> list[MetadataFilter]:
        """Build metadata filters from already-resolved document IDs."""
        filters: list[MetadataFilter] = []

        # The existing vector store only supports single-value document_id filter.
        # If multiple document IDs are provided, use the first one. This is a
        # known limitation — multi-doc OR filtering requires future vector store
        # work.
        if document_ids:
            filters.append(MetadataFilter(field="document_id", value=document_ids[0]))

        return filters

    def _select_and_truncate(
        self,
        items: list[SearchResultItem],
    ) -> list[SearchResultItem]:
        """Keep the highest-scoring items that fit within context budget."""
        selected: list[SearchResultItem] = []
        total_chars = 0

        for item in items:
            chars = len(item.text)
            if total_chars + chars > MAX_EVIDENCE_CHARS and selected:
                break
            selected.append(item)
            total_chars += chars

        return selected

    @staticmethod
    def _to_evidence_ref(item: SearchResultItem) -> EvidenceChunkReference:
        return EvidenceChunkReference(
            chunk_id=item.chunk_id,
            text=item.text,
            score=item.score,
            source_reference=item.source_reference,
            source_filename=item.metadata.source_filename,
            page_number=item.metadata.page_number,
        )


def format_evidence_context(chunks: list[EvidenceChunkReference]) -> str:
    """Format evidence chunks into a prompt-ready context block.

    Each chunk is numbered [1], [2], ... so the model can reference them.
    """
    if not chunks:
        return ""

    parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        source_label = ""
        if chunk.source_filename:
            source_label = f" (source: {chunk.source_filename}"
            if chunk.page_number is not None:
                source_label += f", page {chunk.page_number}"
            source_label += ")"
        parts.append(f"[{i}]{source_label}\n{chunk.text}")

    return "\n\n".join(parts)
