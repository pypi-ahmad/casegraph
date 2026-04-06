"""Indexing service — chunks, embeds, and stores document content."""

from __future__ import annotations

import logging

from casegraph_agent_sdk.ingestion import NormalizedExtractionOutput
from casegraph_agent_sdk.retrieval import (
    IndexResult,
    IndexResultSummary,
    RetrievalError,
)

from app.knowledge.chunking import chunk_extraction_output
from app.knowledge.embedding.base import EmbeddingAdapter
from app.knowledge.vectorstore.base import VectorStoreAdapter

logger = logging.getLogger(__name__)

# Maximum texts to embed in a single batch.
_EMBED_BATCH_SIZE = 64


class IndexingService:
    """Orchestrates: ingestion output → chunks → embeddings → vector store."""

    def __init__(
        self,
        embedding: EmbeddingAdapter,
        store: VectorStoreAdapter,
    ) -> None:
        self._embedding = embedding
        self._store = store

    def index_document(
        self,
        output: NormalizedExtractionOutput,
    ) -> IndexResult:
        errors: list[RetrievalError] = []
        document_id = output.document_id
        model_info = self._embedding.info()

        # 1. Ensure collection exists.
        try:
            self._store.ensure_collection(self._embedding.dimension())
        except Exception as exc:
            return IndexResult(
                summary=IndexResultSummary(
                    document_id=document_id,
                    chunks_indexed=0,
                    embedding_model=model_info.model_name,
                    vector_store=self._store.store_name(),
                ),
                errors=[
                    RetrievalError(
                        code="collection_setup_failed",
                        message=str(exc),
                        recoverable=True,
                    )
                ],
            )

        # 2. Chunk the extraction output.
        chunks = chunk_extraction_output(output)
        if not chunks:
            return IndexResult(
                summary=IndexResultSummary(
                    document_id=document_id,
                    chunks_indexed=0,
                    embedding_model=model_info.model_name,
                    vector_store=self._store.store_name(),
                ),
                errors=[
                    RetrievalError(
                        code="no_chunks_produced",
                        message="The document produced no indexable chunks.",
                        recoverable=True,
                    )
                ],
            )

        # 3. Embed in batches.
        texts = [c.text for c in chunks]
        all_vectors: list[list[float]] = []
        try:
            for i in range(0, len(texts), _EMBED_BATCH_SIZE):
                batch = texts[i : i + _EMBED_BATCH_SIZE]
                all_vectors.extend(self._embedding.embed(batch))
        except Exception as exc:
            return IndexResult(
                summary=IndexResultSummary(
                    document_id=document_id,
                    chunks_indexed=0,
                    embedding_model=model_info.model_name,
                    vector_store=self._store.store_name(),
                ),
                errors=[
                    RetrievalError(
                        code="embedding_failed",
                        message=str(exc),
                        recoverable=True,
                    )
                ],
            )

        # 4. Insert into the vector store.
        ids = [c.chunk_id for c in chunks]
        metadatas = [
            {
                "document_id": c.metadata.document_id,
                "page_number": c.metadata.page_number,
                "block_ids": c.metadata.block_ids,
                "source_filename": c.metadata.source_filename or "",
                "embedding_model": model_info.model_name,
            }
            for c in chunks
        ]

        try:
            inserted = self._store.insert(
                ids=ids,
                texts=texts,
                vectors=all_vectors,
                metadatas=metadatas,
            )
        except Exception as exc:
            errors.append(
                RetrievalError(
                    code="vector_insert_failed",
                    message=str(exc),
                    recoverable=True,
                )
            )
            inserted = 0

        return IndexResult(
            summary=IndexResultSummary(
                document_id=document_id,
                chunks_indexed=inserted,
                embedding_model=model_info.model_name,
                vector_store=self._store.store_name(),
            ),
            errors=errors,
        )
