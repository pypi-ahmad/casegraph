"""Milvus Lite vector store adapter — local-first, file-based.

Uses ``pymilvus`` with MilvusLite mode which stores data in a local SQLite-
backed file.  No external server is required for development.

Collection schema
-----------------
- chunk_id       VARCHAR(128)  — primary key
- document_id    VARCHAR(128)  — partition key candidate (metadata filter)
- text           VARCHAR(8192) — original chunk text
- page_number    INT64         — source page number (-1 when unknown)
- block_ids      VARCHAR(4096) — JSON-serialised list of contributing block IDs
- source_filename VARCHAR(512) — original source filename
- embedding_model VARCHAR(256) — model name used for the vector
- vector         FLOAT_VECTOR  — embedding vector
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.knowledge.vectorstore.base import VectorSearchHit, VectorStoreAdapter

try:
    from pymilvus import (
        CollectionSchema,
        DataType,
        FieldSchema,
        MilvusClient,
    )
except ImportError:  # pragma: no cover
    MilvusClient = None  # type: ignore[assignment,misc]
    CollectionSchema = None  # type: ignore[assignment,misc]
    DataType = None  # type: ignore[assignment,misc]
    FieldSchema = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

COLLECTION_NAME = "casegraph_chunks"
DEFAULT_DB_PATH = "./.milvus/casegraph.db"


def milvus_available() -> bool:
    return MilvusClient is not None


class MilvusLiteStore(VectorStoreAdapter):
    """Local-first Milvus Lite vector store."""

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        if MilvusClient is None:
            raise RuntimeError(
                "pymilvus is not installed.  Run: pip install 'pymilvus[lite]'"
            )

        self._collection_name = collection_name
        self._db_path = db_path

        # Ensure parent directory exists.
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._client: object = MilvusClient(uri=db_path)

    # ------------------------------------------------------------------
    # VectorStoreAdapter interface
    # ------------------------------------------------------------------

    def store_name(self) -> str:
        return "milvus-lite"

    def ensure_collection(self, dimension: int) -> None:
        if self._client.has_collection(self._collection_name):
            return

        schema = self._build_schema(dimension)
        self._client.create_collection(
            collection_name=self._collection_name,
            schema=schema,
        )

        # Create a vector index for search.
        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="FLAT",
            metric_type="COSINE",
        )
        self._client.create_index(
            collection_name=self._collection_name,
            index_params=index_params,
        )
        self._client.load_collection(self._collection_name)

        logger.info(
            "Created Milvus collection %s (dim=%d)", self._collection_name, dimension
        )

    def insert(
        self,
        *,
        ids: list[str],
        texts: list[str],
        vectors: list[list[float]],
        metadatas: list[dict[str, object]],
    ) -> int:
        rows: list[dict[str, object]] = []
        for i, chunk_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            rows.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": str(meta.get("document_id", "")),
                    "text": texts[i],
                    "page_number": int(meta.get("page_number", -1) or -1),
                    "block_ids": json.dumps(meta.get("block_ids", [])),
                    "source_filename": str(meta.get("source_filename", "")),
                    "embedding_model": str(meta.get("embedding_model", "")),
                    "vector": vectors[i],
                }
            )

        result = self._client.insert(
            collection_name=self._collection_name,
            data=rows,
        )
        return result.get("insert_count", len(rows)) if isinstance(result, dict) else len(rows)

    def search(
        self,
        *,
        vector: list[float],
        top_k: int,
        filters: dict[str, str] | None = None,
    ) -> list[VectorSearchHit]:
        filter_expr = self._build_filter_expr(filters) if filters else ""

        results = self._client.search(
            collection_name=self._collection_name,
            data=[vector],
            limit=top_k,
            output_fields=[
                "chunk_id",
                "document_id",
                "text",
                "page_number",
                "block_ids",
                "source_filename",
                "embedding_model",
            ],
            filter=filter_expr or "",
        )

        hits: list[VectorSearchHit] = []
        for result_list in results:
            for hit in result_list:
                entity = hit.get("entity", {}) if isinstance(hit, dict) else {}
                block_ids_raw = entity.get("block_ids", "[]")
                try:
                    block_ids = json.loads(block_ids_raw) if isinstance(block_ids_raw, str) else block_ids_raw
                except (json.JSONDecodeError, TypeError):
                    block_ids = []

                hits.append(
                    VectorSearchHit(
                        chunk_id=entity.get("chunk_id", hit.get("id", "")),
                        text=entity.get("text", ""),
                        score=float(hit.get("distance", 0.0)),
                        metadata={
                            "document_id": entity.get("document_id", ""),
                            "page_number": entity.get("page_number", -1),
                            "block_ids": block_ids,
                            "source_filename": entity.get("source_filename", ""),
                            "embedding_model": entity.get("embedding_model", ""),
                        },
                    )
                )

        return hits

    def count(self) -> int:
        if not self._client.has_collection(self._collection_name):
            return 0
        stats = self._client.get_collection_stats(self._collection_name)
        return int(stats.get("row_count", 0)) if isinstance(stats, dict) else 0

    def delete_by_document(self, document_id: str) -> int:
        if not self._client.has_collection(self._collection_name):
            return 0
        result = self._client.delete(
            collection_name=self._collection_name,
            filter=f'document_id == "{document_id}"',
        )
        return int(result) if result else 0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_schema(self, dimension: int) -> object:
        fields = [
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128, is_primary=True),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
            FieldSchema(name="page_number", dtype=DataType.INT64),
            FieldSchema(name="block_ids", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="source_filename", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="embedding_model", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
        ]
        return CollectionSchema(fields=fields, enable_dynamic_field=False)

    @staticmethod
    def _build_filter_expr(filters: dict[str, str]) -> str:
        parts: list[str] = []
        allowed_fields = {"document_id", "source_filename", "embedding_model"}
        for field, value in filters.items():
            if field in allowed_fields:
                safe_value = value.replace('"', '\\"')
                parts.append(f'{field} == "{safe_value}"')
            elif field == "page_number":
                try:
                    parts.append(f"page_number == {int(value)}")
                except ValueError:
                    pass
        return " and ".join(parts)
