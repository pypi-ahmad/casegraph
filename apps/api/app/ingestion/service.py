"""Service layer for document ingestion."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from casegraph_agent_sdk.ingestion import (
    DocumentProcessingStatus,
    GeometrySource,
    IngestionError,
    IngestionMode,
    IngestionRequest,
    IngestionResult,
    IngestionResultSummary,
    NormalizedExtractionOutput,
    PageArtifact,
    SourceFileMetadata,
)

from app.config import settings
from app.ingestion.extractors.base import ExtractorError
from app.ingestion.extractors.ocr import OcrExtractionAdapter
from app.ingestion.extractors.readable_pdf import ReadablePdfExtractor
from app.ingestion.file_utils import PersistedUpload, cleanup_upload, persist_upload
from app.ingestion.registry import DocumentRegistryService
from app.ingestion.routing import IngestionRouter
from app.ingestion.schemas import DocumentsCapabilitiesResponse, IngestionModeCapability
from app.review.models import PageRecord

try:
    import pymupdf as _pymupdf
except ImportError:
    _pymupdf = None


class DocumentIngestionService:
    def __init__(self, *, document_registry: DocumentRegistryService | None = None) -> None:
        self._readable_pdf_extractor = ReadablePdfExtractor()
        self._ocr_extractor = OcrExtractionAdapter()
        self._router = IngestionRouter(self._readable_pdf_extractor, self._ocr_extractor)
        self._document_registry = document_registry

    async def ingest_upload(
        self,
        *,
        upload_file: UploadFile,
        request: IngestionRequest,
    ) -> IngestionResult:
        persisted = await persist_upload(upload_file)
        document_id = str(uuid4())
        resolved_mode = IngestionMode.UNSUPPORTED

        try:
            decision = self._router.route(persisted.metadata, request, persisted.path)
            resolved_mode = decision.resolved_mode
            if decision.errors:
                result = self._build_error_result(
                    document_id=document_id,
                    source_file=persisted.metadata,
                    request=request,
                    resolved_mode=decision.resolved_mode,
                    status=DocumentProcessingStatus.UNSUPPORTED,
                    errors=decision.errors,
                )
                self._persist_summary(result.summary)
                return result

            output = self._extract(
                document_id=document_id,
                source_file=persisted.metadata,
                request=request,
                resolved_mode=decision.resolved_mode,
                file_path=persisted.path,
            )
            page_images = self._save_page_images(output, persisted)
            source_file_path = self._persist_source_file(output.document_id, persisted)
            result = self._build_success_result(output)
            self._persist_summary(
                result.summary,
                extraction_output=output,
                source_file_path=source_file_path,
            )
            self._persist_page_artifacts(output, page_images)
            return result
        except ExtractorError as exc:
            result = self._build_error_result(
                document_id=document_id,
                source_file=persisted.metadata,
                request=request,
                resolved_mode=resolved_mode,
                status=DocumentProcessingStatus.FAILED,
                extractor_name=self._extractor_name_for_mode(resolved_mode),
                errors=[
                    IngestionError(
                        code=exc.code,
                        message=exc.message,
                        recoverable=exc.recoverable,
                    )
                ],
            )
            self._persist_summary(result.summary)
            return result
        except Exception as exc:  # pragma: no cover - defensive guard
            result = self._build_error_result(
                document_id=document_id,
                source_file=persisted.metadata,
                request=request,
                resolved_mode=resolved_mode,
                status=DocumentProcessingStatus.FAILED,
                extractor_name=self._extractor_name_for_mode(resolved_mode),
                errors=[
                    IngestionError(
                        code="unexpected_ingestion_error",
                        message=f"Unexpected ingestion failure: {exc}",
                        recoverable=False,
                    )
                ],
            )
            self._persist_summary(result.summary)
            return result
        finally:
            cleanup_upload(persisted)

    def capabilities(self) -> DocumentsCapabilitiesResponse:
        return DocumentsCapabilitiesResponse(
            modes=[
                IngestionModeCapability(
                    mode=IngestionMode.READABLE_PDF,
                    supported=self._readable_pdf_extractor.is_available(),
                    requires_ocr=False,
                    extractor_name=self._readable_pdf_extractor.extractor_name,
                    notes=[
                        "Uses PyMuPDF text extraction and preserves page/block bounding boxes when available.",
                        "Optimized for born-digital PDFs with a readable text layer.",
                    ],
                ),
                IngestionModeCapability(
                    mode=IngestionMode.SCANNED_PDF,
                    supported=self._ocr_extractor.is_available_for_scanned_pdfs(),
                    requires_ocr=True,
                    extractor_name=self._ocr_extractor.extractor_name,
                    notes=[
                        "Rasterizes each PDF page, then applies OCR.",
                        "Coordinates are returned in pixel space from the OCR path.",
                    ],
                ),
                IngestionModeCapability(
                    mode=IngestionMode.IMAGE,
                    supported=self._ocr_extractor.is_available_for_images(),
                    requires_ocr=True,
                    extractor_name=self._ocr_extractor.extractor_name,
                    notes=[
                        "Runs OCR directly on uploaded image files.",
                        "Polygon and bounding-box artifacts come from the OCR engine output.",
                    ],
                ),
                IngestionModeCapability(
                    mode=IngestionMode.UNSUPPORTED,
                    supported=False,
                    requires_ocr=False,
                    extractor_name=None,
                    notes=["Unsupported files are rejected without attempting OCR fallback."],
                ),
            ],
            limitations=[
                "OCR is explicit: auto mode will not use OCR unless the request enables it.",
                "Readable PDF extraction does not attempt table reconstruction or semantic parsing.",
                "OCR currently uses RapidOCR behind a clean adapter. Review overlays are available only for geometry that the extractor actually produced; docTR-specific extraction is not implemented.",
                "The API persists uploaded source files, document summaries, full extraction output, and page-level review artifacts (text, geometry, and page-image references).",
            ],
        )

    def _extract(
        self,
        *,
        document_id: str,
        source_file: SourceFileMetadata,
        request: IngestionRequest,
        resolved_mode: IngestionMode,
        file_path: Path,
    ) -> NormalizedExtractionOutput:
        if resolved_mode == IngestionMode.READABLE_PDF:
            return self._readable_pdf_extractor.extract(
                document_id=document_id,
                source_file=source_file,
                request=request,
                file_path=file_path,
            )

        if resolved_mode == IngestionMode.SCANNED_PDF:
            return self._ocr_extractor.extract_scanned_pdf(
                document_id=document_id,
                source_file=source_file,
                request=request,
                file_path=file_path,
            )

        if resolved_mode == IngestionMode.IMAGE:
            return self._ocr_extractor.extract_image(
                document_id=document_id,
                source_file=source_file,
                request=request,
                file_path=file_path,
            )

        raise ExtractorError(
            code="unsupported_ingestion_mode",
            message=f"Unsupported ingestion mode: {resolved_mode.value}",
            recoverable=False,
        )

    def _build_success_result(self, output: NormalizedExtractionOutput) -> IngestionResult:
        text_block_count = sum(len(page.text_blocks) for page in output.pages)
        geometry_sources = self._collect_geometry_sources(output)
        summary = IngestionResultSummary(
            document_id=output.document_id,
            source_file=output.source_file,
            status=output.status,
            requested_mode=output.requested_mode,
            resolved_mode=output.resolved_mode,
            extractor_name=output.extractor_name,
            page_count=len(output.pages),
            text_block_count=text_block_count,
            geometry_present=bool(geometry_sources),
            geometry_sources=geometry_sources,
        )
        return IngestionResult(summary=summary, output=output, errors=[])

    def _build_error_result(
        self,
        *,
        document_id: str,
        source_file: SourceFileMetadata,
        request: IngestionRequest,
        resolved_mode: IngestionMode,
        status: DocumentProcessingStatus,
        extractor_name: str | None = None,
        errors: list[IngestionError],
    ) -> IngestionResult:
        summary = IngestionResultSummary(
            document_id=document_id,
            source_file=source_file,
            status=status,
            requested_mode=request.requested_mode,
            resolved_mode=resolved_mode,
            extractor_name=extractor_name,
            page_count=0,
            text_block_count=0,
            geometry_present=False,
            geometry_sources=[],
        )
        return IngestionResult(summary=summary, output=None, errors=errors)

    def _extractor_name_for_mode(self, resolved_mode: IngestionMode) -> str | None:
        if resolved_mode == IngestionMode.READABLE_PDF:
            return self._readable_pdf_extractor.extractor_name
        if resolved_mode in {IngestionMode.SCANNED_PDF, IngestionMode.IMAGE}:
            return self._ocr_extractor.extractor_name
        return None

    def _collect_geometry_sources(
        self,
        output: NormalizedExtractionOutput,
    ) -> list[GeometrySource]:
        values = {
            block.geometry_source
            for page in output.pages
            for block in page.text_blocks
            if block.bbox is not None or block.polygon is not None
        }
        values.update(
            page.geometry_source for page in output.pages if page.geometry_source is not None
        )
        return sorted(values, key=lambda item: item.value)

    def _persist_summary(
        self,
        summary: IngestionResultSummary,
        *,
        extraction_output: NormalizedExtractionOutput | None = None,
        source_file_path: str | None = None,
    ) -> None:
        if self._document_registry is not None:
            self._document_registry.record_summary(
                summary,
                extraction_output=extraction_output,
                source_file_path=source_file_path,
            )

    def _persist_source_file(
        self,
        document_id: str,
        persisted: PersistedUpload,
    ) -> str | None:
        """Copy the original uploaded file into the persistent artifacts directory.

        Returns the artifact-relative path, or *None* when the registry is
        not available (unit-test fast-path).
        """
        if self._document_registry is None:
            return None

        base = Path(settings.artifacts_dir)
        doc_dir = base / "documents" / document_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        suffix = persisted.path.suffix or ""
        dest = doc_dir / f"source{suffix}"
        shutil.copy2(persisted.path, dest)
        return f"documents/{document_id}/source{suffix}"

    def _save_page_images(
        self,
        output: NormalizedExtractionOutput,
        persisted: PersistedUpload,
    ) -> dict[int, str]:
        """Save page images to the artifacts directory.

        Returns a mapping of page_number → relative path from artifacts_dir.
        For readable PDFs, rasterizes each page via PyMuPDF.
        For scanned PDFs, copies the OCR rasterized images.
        For images, copies the uploaded file.
        """
        if self._document_registry is None:
            return {}

        base = Path(settings.artifacts_dir)
        page_dir = base / "documents" / output.document_id / "pages"
        page_dir.mkdir(parents=True, exist_ok=True)

        result: dict[int, str] = {}

        if output.resolved_mode == IngestionMode.READABLE_PDF:
            result = self._rasterize_pdf_pages(persisted.path, page_dir, output.document_id)
        elif output.resolved_mode == IngestionMode.SCANNED_PDF:
            for page in output.pages:
                src = persisted.temp_dir / f"ocr-page-{page.page_number}.png"
                if src.exists():
                    dest = page_dir / f"page-{page.page_number}.png"
                    shutil.copy2(src, dest)
                    rel = f"documents/{output.document_id}/pages/page-{page.page_number}.png"
                    result[page.page_number] = rel
        elif output.resolved_mode == IngestionMode.IMAGE:
            suffix = persisted.path.suffix or ".png"
            dest = page_dir / f"page-1{suffix}"
            shutil.copy2(persisted.path, dest)
            result[1] = f"documents/{output.document_id}/pages/page-1{suffix}"

        return result

    def _rasterize_pdf_pages(
        self,
        file_path: Path,
        page_dir: Path,
        document_id: str,
    ) -> dict[int, str]:
        if _pymupdf is None:
            return {}
        try:
            result: dict[int, str] = {}
            with _pymupdf.open(file_path) as doc:
                for page_index, page in enumerate(doc, start=1):
                    pixmap = page.get_pixmap(dpi=150, alpha=False)
                    dest = page_dir / f"page-{page_index}.png"
                    pixmap.save(str(dest))
                    result[page_index] = f"documents/{document_id}/pages/page-{page_index}.png"
            return result
        except Exception:
            return {}

    def _persist_page_artifacts(
        self,
        output: NormalizedExtractionOutput,
        page_images: dict[int, str],
    ) -> None:
        if self._document_registry is None:
            return

        records: list[PageRecord] = []
        for page in output.pages:
            image_rel = page_images.get(page.page_number)
            records.append(
                PageRecord(
                    page_id=f"{output.document_id}:{page.page_number}",
                    document_id=output.document_id,
                    page_number=page.page_number,
                    width=page.width,
                    height=page.height,
                    coordinate_space=(
                        page.coordinate_space.value if page.coordinate_space else None
                    ),
                    geometry_source=(
                        page.geometry_source.value if page.geometry_source else None
                    ),
                    text=page.text,
                    text_blocks_json=[
                        block.model_dump(mode="json") for block in page.text_blocks
                    ],
                    has_page_image=image_rel is not None,
                    page_image_path=image_rel,
                )
            )

        self._document_registry.persist_page_records(records)
