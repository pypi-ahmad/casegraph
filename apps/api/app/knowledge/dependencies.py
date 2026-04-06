"""Facade that wires together embedding, vector store, indexing, and search."""

from __future__ import annotations

from functools import lru_cache

from app.knowledge.embedding import SentenceTransformersAdapter, sentence_transformers_available
from app.knowledge.embedding.base import EmbeddingAdapter
from app.knowledge.indexing import IndexingService
from app.knowledge.search import SearchService
from app.knowledge.vectorstore import ChromaDBStore, MilvusLiteStore, chromadb_available, milvus_available
from app.knowledge.vectorstore.base import VectorStoreAdapter


@lru_cache(maxsize=1)
def _get_embedding_adapter() -> EmbeddingAdapter | None:
    if not sentence_transformers_available():
        return None
    return SentenceTransformersAdapter()


@lru_cache(maxsize=1)
def _get_vector_store() -> VectorStoreAdapter | None:
    """Return the best available vector store.

    Prefers Milvus Lite (Linux only) → falls back to ChromaDB (all platforms).
    """
    if milvus_available():
        try:
            return MilvusLiteStore()
        except Exception:
            pass

    if chromadb_available():
        return ChromaDBStore()

    return None


def get_indexing_service() -> IndexingService | None:
    embedding = _get_embedding_adapter()
    store = _get_vector_store()
    if embedding is None or store is None:
        return None
    return IndexingService(embedding=embedding, store=store)


def get_search_service() -> SearchService | None:
    embedding = _get_embedding_adapter()
    store = _get_vector_store()
    if embedding is None or store is None:
        return None
    return SearchService(embedding=embedding, store=store)


def embedding_available() -> bool:
    return sentence_transformers_available()


def vector_store_available() -> bool:
    return milvus_available() or chromadb_available()
