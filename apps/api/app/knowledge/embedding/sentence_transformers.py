"""Sentence-transformers embedding adapter — local, open-source default.

Uses ``all-MiniLM-L6-v2`` (384-dimensional, ~80 MB) as the baseline model.
The model is loaded lazily on first use and cached for the process lifetime.
"""

from __future__ import annotations

from functools import lru_cache

from casegraph_agent_sdk.retrieval import EmbeddingModelInfo

from app.knowledge.embedding.base import EmbeddingAdapter

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None  # type: ignore[assignment,misc]

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_DIMENSION = 384


def sentence_transformers_available() -> bool:
    return SentenceTransformer is not None


@lru_cache(maxsize=1)
def _load_model(model_name: str) -> object:
    if SentenceTransformer is None:
        raise RuntimeError(
            "sentence-transformers is not installed.  "
            "Run: pip install sentence-transformers"
        )
    return SentenceTransformer(model_name)


class SentenceTransformersAdapter(EmbeddingAdapter):
    """Local embedding via sentence-transformers."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self._model_name = model_name

    def info(self) -> EmbeddingModelInfo:
        return EmbeddingModelInfo(
            model_name=self._model_name,
            dimension=self.dimension(),
            provider="local/sentence-transformers",
            notes=[
                f"Model: {self._model_name}",
                f"Dimension: {self.dimension()}",
                "Loaded lazily on first embed() call.",
            ],
        )

    def dimension(self) -> int:
        return DEFAULT_DIMENSION

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = _load_model(self._model_name)
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return [vec.tolist() for vec in embeddings]
