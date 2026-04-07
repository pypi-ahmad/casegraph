"""Readable PDF extraction using PyMuPDF."""

from __future__ import annotations

from pathlib import Path

from casegraph_agent_sdk.ingestion import (
    BoundingBoxArtifact,
    CoordinateSpace,
    DocumentId,
    DocumentProcessingStatus,
    GeometrySource,
    IngestionMode,
    IngestionRequest,
    NormalizedExtractionOutput,
    PageArtifact,
    SourceFileMetadata,
    TextBlockArtifact,
)

from app.ingestion.extractors.base import (
    ExtractionAdapter,
    ExtractorDependencyError,
    ExtractorExecutionError,
)

try:
    import pymupdf
except ImportError:  # pragma: no cover - exercised via capability checks
    pymupdf = None


def readable_pdf_runtime_available() -> bool:
    return pymupdf is not None


class ReadablePdfExtractor(ExtractionAdapter):
    extractor_name = "pymupdf-readable-pdf"

    def is_available(self) -> bool:
        return readable_pdf_runtime_available()

    def has_readable_text_layer(self, file_path: Path) -> bool:
        if pymupdf is None:
            return False

        try:
            with pymupdf.open(file_path) as document:
                for page in document:
                    words = page.get_text("words", sort=True)
                    if any(str(word[4]).strip() for word in words if len(word) > 4):
                        return True
        except Exception as exc:  # pragma: no cover - defensive guard
            raise ExtractorExecutionError(
                code="pdf_text_layer_check_failed",
                message=f"Unable to inspect the PDF text layer: {exc}",
                recoverable=True,
            ) from exc

        return False

    def extract(
        self,
        *,
        document_id: DocumentId,
        source_file: SourceFileMetadata,
        request: IngestionRequest,
        file_path: Path,
    ) -> NormalizedExtractionOutput:
        if pymupdf is None:
            raise ExtractorDependencyError(
                code="pymupdf_missing",
                message="PyMuPDF is required for readable PDF extraction.",
                recoverable=True,
            )

        pages: list[PageArtifact] = []
        extracted_text_chunks: list[str] = []

        try:
            with pymupdf.open(file_path) as document:
                for page_index, page in enumerate(document, start=1):
                    blocks = page.get_text("blocks", sort=True)
                    page_blocks: list[TextBlockArtifact] = []
                    page_text_chunks: list[str] = []

                    for block_index, block in enumerate(blocks, start=1):
                        if len(block) < 5:
                            continue

                        text = str(block[4]).strip()
                        block_type = int(block[6]) if len(block) > 6 else 0
                        if block_type != 0 or not text:
                            continue

                        bbox = BoundingBoxArtifact(
                            x0=float(block[0]),
                            y0=float(block[1]),
                            x1=float(block[2]),
                            y1=float(block[3]),
                            coordinate_space=CoordinateSpace.PDF_POINTS,
                        )
                        page_blocks.append(
                            TextBlockArtifact(
                                block_id=f"page-{page_index}-block-{block_index}",
                                page_number=page_index,
                                text=text,
                                bbox=bbox,
                                polygon=None,
                                confidence=None,
                                geometry_source=GeometrySource.PDF_TEXT,
                            )
                        )
                        page_text_chunks.append(text)

                    page_text = "\n".join(page_text_chunks).strip()
                    if not page_text:
                        page_text = page.get_text("text", sort=True).strip()

                    if page_text:
                        extracted_text_chunks.append(page_text)

                    pages.append(
                        PageArtifact(
                            page_number=page_index,
                            width=float(page.rect.width),
                            height=float(page.rect.height),
                            coordinate_space=CoordinateSpace.PDF_POINTS,
                            text=page_text,
                            text_blocks=page_blocks,
                            geometry_source=(GeometrySource.PDF_TEXT if page_blocks else None),
                        )
                    )
        except ExtractorExecutionError:
            raise
        except Exception as exc:
            raise ExtractorExecutionError(
                code="readable_pdf_extraction_failed",
                message=f"Readable PDF extraction failed: {exc}",
            ) from exc

        return NormalizedExtractionOutput(
            document_id=document_id,
            source_file=source_file,
            requested_mode=request.requested_mode,
            resolved_mode=IngestionMode.READABLE_PDF,
            status=DocumentProcessingStatus.COMPLETED,
            extractor_name=self.extractor_name,
            extracted_text="\n\n".join(chunk for chunk in extracted_text_chunks if chunk).strip(),
            pages=pages,
        )
