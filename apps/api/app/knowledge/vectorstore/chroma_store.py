"""ChromaDB vector store adapter — local-first, works on all platforms.

Uses ChromaDB in persistent local mode.  Data is stored on disk in a local
directory, no external server required.  This is the default vector store
on platforms where Milvus Lite is not available (e.g. Windows, Python 3.13+).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.knowledge.vectorstore.base import VectorSearchHit, VectorStoreAdapter

try:
    import chromadb
except ImportError:  # pragma: no cover
    chromadb = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

COLLECTION_NAME = "casegraph_chunks"
DEFAULT_DB_PATH = "./.chroma"


def chromadb_available() -> bool:
    return chromadb is not None


class ChromaDBStore(VectorStoreAdapter):
    """Local-first ChromaDB vector store (persistent on disk)."""

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        if chromadb is None:
            raise RuntimeError(
                "chromadb is not installed.  Run: pip install chromadb"
            )

        self._collection_name = collection_name
        self._db_path = db_path

        Path(db_path).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=db_path)
        self._collection: object | None = None

    # ------------------------------------------------------------------
    # VectorStoreAdapter interface
    # ------------------------------------------------------------------

    def store_name(self) -> str:
        return "chromadb-local"

    def ensure_collection(self, dimension: int) -> None:
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={
                "hnsw:space": "cosine",
                "dimension": dimension,
            },
        )

    def insert(
        self,
        *,
        ids: list[str],
        texts: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, object]],
    ) -> int:
        if self._collection is None:
            raise RuntimeError("Collection not initialized.  Call ensure_collection() first.")

        # ChromaDB requires metadata values to be str, int, float, or bool.
        clean_metadatas: list[dict[str, str | int | float | bool]] = []
        for meta in metadatas:
            clean: dict[str, str | int | float | bool] = {}
            for k, v in meta.items():
                if isinstance(v, (list, tuple)):
                    clean[k] = json.dumps(v)
                elif isinstance(v, (str, int, float, bool)):
                    clean[k] = v
                elif v is None:
                    clean[k] = ""
                else:
                    clean[k] = str(v)
            clean_metadatas.append(clean)

        self._collection.add(
            ids=ids,
            documents=texts,
            embeddings=vectors,
            metadatas=clean_metadatas,
        )
        return len(ids)

    def search(
        self,
        *,
        vector: list[float],
        top_k: int,
        filters: dict[str, str] | None = None,
    ) -> list[VectorSearchHit]:
        if self._collection is None:
            return []

        where_filter = self._build_where_filter(filters) if filters else None

        results = self._collection.query(
            query_embeddings=[vector],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        hits: list[VectorSearchHit] = []
        result_ids = results.get("ids", [[]])[0]
        result_docs = results.get("documents", [[]])[0]
        result_metas = results.get("metadatas", [[]])[0]
        result_distances = results.get("distances", [[]])[0]

        for i, chunk_id in enumerate(result_ids):
            text = result_docs[i] if i < len(result_docs) else ""
            meta_raw = result_metas[i] if i < len(result_metas) else {}
            distance = result_distances[i] if i < len(result_distances) else 0.0

            # ChromaDB cosine distance: 0 = identical.  Convert to similarity.
            similarity = 1.0 - float(distance)

            meta: dict[str, object] = dict(meta_raw) if meta_raw else {}
            # Deserialize block_ids from JSON.
            block_ids_raw = meta.get("block_ids", "[]")
            if isinstance(block_ids_raw, str):
                try:
                    meta["block_ids"] = json.loads(block_ids_raw)
                except (json.JSONDecodeError, TypeError):
                    meta["block_ids"] = []

            hits.append(
                VectorSearchHit(
                    chunk_id=str(chunk_id),
                    text=str(text),
                    score=similarity,
                    metadata=meta,
                )
            )

        return hits

    def count(self) -> int:
        if self._collection is None:
            return 0
        return self._collection.count()

    def delete_by_document(self, document_id: str) -> int:
        if self._collection is None:
            return 0
        # Get IDs matching the document, then delete them.
        results = self._collection.get(
            where={"document_id": document_id},
            include=[],
        )
        ids_to_delete = results.get("ids", [])
        if ids_to_delete:
            self._collection.delete(ids=ids_to_delete)
        return len(ids_to_delete)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _build_where_filter(filters: dict[str, str]) -> dict[str, object] | None:
        allowed_string_fields = {"document_id", "source_filename", "embedding_model"}
        conditions: list[dict[str, object]] = []

        for field, value in filters.items():
            if field in allowed_string_fields:
                conditions.append({field: {"$eq": value}})
            elif field == "page_number":
                try:
                    conditions.append({"page_number": {"$eq": int(value)}})
                except ValueError:
                    pass

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
