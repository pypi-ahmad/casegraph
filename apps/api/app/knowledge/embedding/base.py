"""Base interface for embedding adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from casegraph_agent_sdk.retrieval import EmbeddingModelInfo


class EmbeddingAdapter(ABC):
    """Abstract interface for embedding providers.

    Implementations must be stateless per-call.  Model loading may be
    deferred until the first ``embed`` call.
    """

    @abstractmethod
    def info(self) -> EmbeddingModelInfo:
        """Return metadata about the underlying model."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for each input text."""

    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension for collection schema creation."""
