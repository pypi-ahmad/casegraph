"""Base interface for vector store adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(slots=True)
class VectorSearchHit:
    """A single hit returned by the vector store."""

    chunk_id: str
    text: str
    score: float
    metadata: dict[str, object] = field(default_factory=dict)


class VectorStoreAdapter(ABC):
    """Abstract interface for vector databases."""

    @abstractmethod
    def store_name(self) -> str:
        """Human-readable identifier for the backing store."""

    @abstractmethod
    def ensure_collection(self, dimension: int) -> None:
        """Create the collection/index if it does not exist."""

    @abstractmethod
    def insert(
        self,
        *,
        ids: list[str],
        texts: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, object]],
    ) -> int:
        """Insert vectors with metadata.  Returns the number inserted."""

    @abstractmethod
    def search(
        self,
        *,
        vector: list[float],
        top_k: int,
        filters: dict[str, str] | None = None,
    ) -> list[VectorSearchHit]:
        """Return the closest hits for *vector*."""

    @abstractmethod
    def count(self) -> int:
        """Return the total number of stored vectors."""

    @abstractmethod
    def delete_by_document(self, document_id: str) -> int:
        """Delete all vectors for a given document.  Returns count deleted."""
