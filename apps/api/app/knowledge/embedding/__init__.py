"""Embedding adapters for knowledge retrieval."""

from app.knowledge.embedding.base import EmbeddingAdapter
from app.knowledge.embedding.sentence_transformers import (
    SentenceTransformersAdapter,
    sentence_transformers_available,
)

__all__ = [
    "EmbeddingAdapter",
    "SentenceTransformersAdapter",
    "sentence_transformers_available",
]
