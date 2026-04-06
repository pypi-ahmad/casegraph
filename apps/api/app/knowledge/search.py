"""Search service — query the vector store and return normalised results."""

from __future__ import annotations

import logging

from casegraph_agent_sdk.retrieval import (
    ChunkMetadata,
    SearchRequest,
    SearchResult,
    SearchResultItem,
    SearchScoreMetadata,
    SourceReference,
)

from app.knowledge.embedding.base import EmbeddingAdapter
from app.knowledge.vectorstore.base import VectorStoreAdapter
from app.observability.tracing import trace_span

logger = logging.getLogger(__name__)


class SearchService:
    """Embeds a query and searches the vector store."""

    def __init__(
        self,
        embedding: EmbeddingAdapter,
        store: VectorStoreAdapter,
    ) -> None:
        self._embedding = embedding
        self._store = store

    def search(self, request: SearchRequest) -> SearchResult:
        with trace_span(
            name="knowledge.search",
            metadata={"query_length": len(request.query), "top_k": request.top_k},
            input_data={"query": request.query},
        ) as ctx:
            result = self._search_impl(request)
            ctx["output"] = {"total_results": result.total_results}
            return result

    def _search_impl(self, request: SearchRequest) -> SearchResult:
        model_info = self._embedding.info()
        store_name = self._store.store_name()

        # 1. Embed the query.
        try:
            vectors = self._embedding.embed([request.query])
        except Exception as exc:
            logger.warning("Query embedding failed: %s", exc)
            return SearchResult(
                query=request.query,
                items=[],
                total_results=0,
                embedding_model=model_info.model_name,
                vector_store=store_name,
            )

        if not vectors or not vectors[0]:
            return SearchResult(
                query=request.query,
                items=[],
                total_results=0,
                embedding_model=model_info.model_name,
                vector_store=store_name,
            )

        query_vector = vectors[0]

        # 2. Build filter dict.
        filter_dict: dict[str, str] | None = None
        if request.filters:
            filter_dict = {f.field: f.value for f in request.filters}

        # 3. Search.
        try:
            hits = self._store.search(
                vector=query_vector,
                top_k=request.top_k,
                filters=filter_dict,
            )
        except Exception as exc:
            logger.warning("Vector search failed: %s", exc)
            return SearchResult(
                query=request.query,
                items=[],
                total_results=0,
                embedding_model=model_info.model_name,
                vector_store=store_name,
            )

        # 4. Normalise hits into typed results.
        items: list[SearchResultItem] = []
        for hit in hits:
            meta = hit.metadata
            block_ids = meta.get("block_ids", [])
            if isinstance(block_ids, str):
                import json

                try:
                    block_ids = json.loads(block_ids)
                except (json.JSONDecodeError, TypeError):
                    block_ids = []

            page_number = meta.get("page_number")
            if page_number == -1:
                page_number = None

            items.append(
                SearchResultItem(
                    chunk_id=hit.chunk_id,
                    text=hit.text,
                    score=SearchScoreMetadata(
                        raw_score=hit.score,
                        normalized_score=hit.score,
                        scoring_method="cosine_similarity",
                    ),
                    metadata=ChunkMetadata(
                        document_id=str(meta.get("document_id", "")),
                        page_number=page_number,
                        block_ids=block_ids if isinstance(block_ids, list) else [],
                        source_filename=str(meta.get("source_filename", "")) or None,
                        chunk_index=0,
                        total_chunks=0,
                    ),
                    source_reference=SourceReference(
                        document_id=str(meta.get("document_id", "")),
                        page_number=page_number,
                        block_ids=block_ids if isinstance(block_ids, list) else [],
                        geometry_source=None,
                    ),
                )
            )

        return SearchResult(
            query=request.query,
            items=items,
            total_results=len(items),
            embedding_model=model_info.model_name,
            vector_store=store_name,
        )
