"""Route handlers for knowledge retrieval."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from casegraph_agent_sdk.ingestion import NormalizedExtractionOutput
from casegraph_agent_sdk.retrieval import (
    IndexResult,
    SearchRequest,
    SearchResult,
)

from app.knowledge.dependencies import (
    _get_vector_store,
    embedding_available,
    get_indexing_service,
    get_search_service,
    vector_store_available,
)
from app.knowledge.embedding import SentenceTransformersAdapter
from app.knowledge.schemas import (
    KnowledgeCapabilitiesResponse,
    KnowledgeCapabilityStatus,
)

router = APIRouter(tags=["knowledge"])


@router.get("/knowledge/capabilities", response_model=KnowledgeCapabilitiesResponse)
async def knowledge_capabilities() -> KnowledgeCapabilitiesResponse:
    embedding_ok = embedding_available()
    store_ok = vector_store_available()

    embedding_info = None
    if embedding_ok:
        try:
            adapter = SentenceTransformersAdapter()
            embedding_info = adapter.info()
        except Exception:
            embedding_ok = False

    store_name: str | None = None
    store_notes: list[str] = ["No vector store is installed."]
    indexed_chunks = 0

    if store_ok:
        try:
            store = _get_vector_store()
            if store is not None:
                store_name = store.store_name()
                store.ensure_collection(embedding_info.dimension if embedding_info else 384)
                indexed_chunks = store.count()
                store_notes = [f"Using {store_name} for local persistent storage."]
        except Exception:
            pass

    return KnowledgeCapabilitiesResponse(
        embedding=KnowledgeCapabilityStatus(
            component="embedding",
            available=embedding_ok,
            name="sentence-transformers/all-MiniLM-L6-v2" if embedding_ok else None,
            notes=["Local open-source model, 384 dimensions."] if embedding_ok else ["sentence-transformers not installed."],
        ),
        vector_store=KnowledgeCapabilityStatus(
            component="vector_store",
            available=store_ok,
            name=store_name,
            notes=store_notes,
        ),
        embedding_model=embedding_info,
        indexed_chunks=indexed_chunks,
        limitations=[
            "Indexing runs synchronously inside the API process; there is no background job queue or separate indexing service.",
            "Chunking uses simple fixed-size overlapping windows, not semantic splitting.",
            "Search returns cosine similarity scores; no reranking or late interaction is implemented.",
            "Metadata filtering is limited to document_id, source_filename, page_number, and embedding_model.",
            "No multi-tenant isolation is implemented yet.",
        ],
    )


@router.post("/knowledge/index", response_model=IndexResult)
async def index_document(payload: NormalizedExtractionOutput) -> IndexResult:
    service = get_indexing_service()
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Knowledge indexing is not available. Ensure sentence-transformers and a vector store (chromadb or pymilvus) are installed.",
        )
    return service.index_document(payload)


@router.post("/knowledge/search", response_model=SearchResult)
async def search_knowledge(request: SearchRequest) -> SearchResult:
    service = get_search_service()
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Knowledge search is not available. Ensure sentence-transformers and a vector store (chromadb or pymilvus) are installed.",
        )
    return service.search(request)
