"""Chunking pipeline — converts normalized ingestion outputs to indexed chunks.

Operates exclusively on NormalizedExtractionOutput from the ingestion
foundation.  Does NOT re-parse raw files.
"""

from __future__ import annotations

from uuid import uuid4

from casegraph_agent_sdk.ingestion import NormalizedExtractionOutput
from casegraph_agent_sdk.retrieval import (
    ChunkContent,
    ChunkMetadata,
    SourceReference,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64
MIN_CHUNK_LENGTH = 20


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chunk_extraction_output(
    output: NormalizedExtractionOutput,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[ChunkContent]:
    """Produce chunks from a completed ingestion output.

    Strategy
    --------
    1. Iterate pages in order.
    2. For each page, collect block-level texts (preserving block IDs) or fall
       back to the page-level ``text`` field.
    3. Split page text into fixed-size overlapping windows.
    4. Each chunk carries a ``SourceReference`` linking it back to the document,
       page, and contributing block IDs.
    """

    all_chunks: list[ChunkContent] = []

    for page in output.pages:
        page_text, block_ids = _page_text_and_block_ids(page)
        if not page_text or len(page_text.strip()) < MIN_CHUNK_LENGTH:
            continue

        windows = _split_text(page_text.strip(), chunk_size, chunk_overlap)

        for window_text in windows:
            all_chunks.append(
                ChunkContent(
                    chunk_id=str(uuid4()),
                    text=window_text,
                    metadata=ChunkMetadata(
                        document_id=output.document_id,
                        page_number=page.page_number,
                        block_ids=block_ids,
                        source_filename=output.source_file.filename,
                        chunk_index=0,
                        total_chunks=0,
                    ),
                    source_reference=SourceReference(
                        document_id=output.document_id,
                        page_number=page.page_number,
                        block_ids=block_ids,
                        geometry_source=(
                            page.geometry_source.value
                            if page.geometry_source is not None
                            else None
                        ),
                    ),
                )
            )

    # Back-fill chunk_index / total_chunks now that we know the total.
    total = len(all_chunks)
    for idx, chunk in enumerate(all_chunks):
        chunk.metadata.chunk_index = idx
        chunk.metadata.total_chunks = total

    return all_chunks


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _page_text_and_block_ids(
    page: object,
) -> tuple[str, list[str]]:
    """Extract concatenated text and block IDs from a PageArtifact."""

    blocks = getattr(page, "text_blocks", []) or []
    if blocks:
        texts: list[str] = []
        ids: list[str] = []
        for block in blocks:
            text = getattr(block, "text", "").strip()
            if text:
                texts.append(text)
                ids.append(getattr(block, "block_id", ""))
        if texts:
            return "\n".join(texts), ids

    # Fallback to page-level text.
    return getattr(page, "text", "") or "", []


def _split_text(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """Split *text* into character-level windows of *chunk_size* with *overlap*.

    Returns at least one chunk even if the text is shorter than chunk_size.
    """

    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        window = text[start:end].strip()
        if window and len(window) >= MIN_CHUNK_LENGTH:
            chunks.append(window)
        if end >= len(text):
            break
        start += chunk_size - overlap

    return chunks if chunks else [text]
