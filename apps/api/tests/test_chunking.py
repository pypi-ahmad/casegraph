"""Unit tests for the chunking pipeline."""

from casegraph_agent_sdk.ingestion import (
    DocumentProcessingStatus,
    FileTypeClassification,
    GeometrySource,
    IngestionMode,
    IngestionModePreference,
    NormalizedExtractionOutput,
    PageArtifact,
    SourceFileMetadata,
    TextBlockArtifact,
)

from app.knowledge.chunking import chunk_extraction_output


def _make_output(pages: list[PageArtifact]) -> NormalizedExtractionOutput:
    return NormalizedExtractionOutput(
        document_id="doc-001",
        source_file=SourceFileMetadata(
            filename="test.pdf",
            content_type="application/pdf",
            extension=".pdf",
            size_bytes=1024,
            sha256="abc",
            classification=FileTypeClassification.PDF,
        ),
        requested_mode=IngestionModePreference.AUTO,
        resolved_mode=IngestionMode.READABLE_PDF,
        status=DocumentProcessingStatus.COMPLETED,
        extractor_name="test",
        extracted_text="hello world",
        pages=pages,
    )


def test_single_page_single_chunk() -> None:
    output = _make_output(
        [
            PageArtifact(
                page_number=1,
                text="This is a test document with enough text to form one chunk.",
                text_blocks=[],
                geometry_source=None,
            ),
        ]
    )
    chunks = chunk_extraction_output(output, chunk_size=1024)
    assert len(chunks) == 1
    assert chunks[0].metadata.document_id == "doc-001"
    assert chunks[0].metadata.page_number == 1
    assert chunks[0].metadata.chunk_index == 0
    assert chunks[0].metadata.total_chunks == 1


def test_multipage_produces_multiple_chunks() -> None:
    pages = [
        PageArtifact(
            page_number=i,
            text=f"Page {i} content with enough length to be a valid chunk text block.",
            text_blocks=[],
            geometry_source=None,
        )
        for i in range(1, 4)
    ]
    output = _make_output(pages)
    chunks = chunk_extraction_output(output, chunk_size=1024)
    assert len(chunks) == 3
    assert chunks[0].source_reference.page_number == 1
    assert chunks[2].source_reference.page_number == 3
    assert all(c.metadata.total_chunks == 3 for c in chunks)


def test_block_ids_are_preserved() -> None:
    output = _make_output(
        [
            PageArtifact(
                page_number=1,
                text="",
                text_blocks=[
                    TextBlockArtifact(
                        block_id="page-1-block-1",
                        page_number=1,
                        text="First block of text for testing purposes.",
                        bbox=None,
                        polygon=None,
                        confidence=None,
                        geometry_source=GeometrySource.PDF_TEXT,
                    ),
                    TextBlockArtifact(
                        block_id="page-1-block-2",
                        page_number=1,
                        text="Second block of text for testing purposes.",
                        bbox=None,
                        polygon=None,
                        confidence=None,
                        geometry_source=GeometrySource.PDF_TEXT,
                    ),
                ],
                geometry_source=GeometrySource.PDF_TEXT,
            ),
        ]
    )
    chunks = chunk_extraction_output(output, chunk_size=2048)
    assert len(chunks) == 1
    assert "page-1-block-1" in chunks[0].metadata.block_ids
    assert "page-1-block-2" in chunks[0].metadata.block_ids
    assert chunks[0].source_reference.geometry_source == "pdf_text"


def test_long_page_splits_into_windows() -> None:
    long_text = "word " * 200
    output = _make_output(
        [
            PageArtifact(
                page_number=1,
                text=long_text,
                text_blocks=[],
                geometry_source=None,
            ),
        ]
    )
    chunks = chunk_extraction_output(output, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    assert all(c.metadata.document_id == "doc-001" for c in chunks)


def test_empty_pages_are_skipped() -> None:
    output = _make_output(
        [
            PageArtifact(
                page_number=1,
                text="",
                text_blocks=[],
                geometry_source=None,
            ),
        ]
    )
    chunks = chunk_extraction_output(output)
    assert len(chunks) == 0
