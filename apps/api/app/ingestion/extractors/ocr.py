"""OCR extraction adapter backed by RapidOCR.

This is the current minimal real OCR path. The schema remains compatible with
future docTR-style polygon and overlay workflows.
"""

from __future__ import annotations

from functools import lru_cache
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
    PolygonArtifact,
    PolygonPoint,
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

try:
    from rapidocr import RapidOCR
except ImportError:  # pragma: no cover - exercised via capability checks
    RapidOCR = None


@lru_cache(maxsize=1)
def _get_rapidocr_engine() -> object:
    if RapidOCR is None:
        raise ExtractorDependencyError(
            code="rapidocr_missing",
            message="RapidOCR is required for OCR ingestion.",
            recoverable=True,
        )
    return RapidOCR()


def ocr_runtime_available() -> bool:
    return RapidOCR is not None


def scanned_pdf_ocr_runtime_available() -> bool:
    return RapidOCR is not None and pymupdf is not None


class OcrExtractionAdapter(ExtractionAdapter):
    extractor_name = "rapidocr-onnxruntime"

    def is_available_for_images(self) -> bool:
        return ocr_runtime_available()

    def is_available_for_scanned_pdfs(self) -> bool:
        return scanned_pdf_ocr_runtime_available()

    def extract_image(
        self,
        *,
        document_id: DocumentId,
        source_file: SourceFileMetadata,
        request: IngestionRequest,
        file_path: Path,
    ) -> NormalizedExtractionOutput:
        if not self.is_available_for_images():
            raise ExtractorDependencyError(
                code="ocr_engine_unavailable",
                message="RapidOCR is not available for image ingestion.",
                recoverable=True,
            )

        width, height = self._get_image_dimensions(file_path)
        page = self._extract_page_from_image(
            image_path=file_path,
            page_number=1,
            width=width,
            height=height,
        )
        return NormalizedExtractionOutput(
            document_id=document_id,
            source_file=source_file,
            requested_mode=request.requested_mode,
            resolved_mode=IngestionMode.IMAGE,
            status=DocumentProcessingStatus.COMPLETED,
            extractor_name=self.extractor_name,
            extracted_text=page.text,
            pages=[page],
        )

    def extract_scanned_pdf(
        self,
        *,
        document_id: DocumentId,
        source_file: SourceFileMetadata,
        request: IngestionRequest,
        file_path: Path,
    ) -> NormalizedExtractionOutput:
        if not self.is_available_for_scanned_pdfs():
            raise ExtractorDependencyError(
                code="ocr_engine_unavailable",
                message="RapidOCR and PyMuPDF are required for scanned PDF ingestion.",
                recoverable=True,
            )

        if pymupdf is None:
            raise ExtractorDependencyError(
                code="pymupdf_missing",
                message="PyMuPDF is required to rasterize scanned PDFs.",
                recoverable=True,
            )

        pages: list[PageArtifact] = []
        extracted_text_chunks: list[str] = []

        try:
            with pymupdf.open(file_path) as document:
                for page_index, pdf_page in enumerate(document, start=1):
                    image_path = file_path.parent / f"ocr-page-{page_index}.png"
                    pixmap = pdf_page.get_pixmap(dpi=180, alpha=False)
                    pixmap.save(image_path)

                    page = self._extract_page_from_image(
                        image_path=image_path,
                        page_number=page_index,
                        width=float(pixmap.width),
                        height=float(pixmap.height),
                    )
                    pages.append(page)
                    if page.text:
                        extracted_text_chunks.append(page.text)
        except ExtractorDependencyError:
            raise
        except Exception as exc:
            raise ExtractorExecutionError(
                code="scanned_pdf_ocr_failed",
                message=f"Scanned PDF OCR failed: {exc}",
            ) from exc

        return NormalizedExtractionOutput(
            document_id=document_id,
            source_file=source_file,
            requested_mode=request.requested_mode,
            resolved_mode=IngestionMode.SCANNED_PDF,
            status=DocumentProcessingStatus.COMPLETED,
            extractor_name=self.extractor_name,
            extracted_text="\n\n".join(chunk for chunk in extracted_text_chunks if chunk).strip(),
            pages=pages,
        )

    def _extract_page_from_image(
        self,
        *,
        image_path: Path,
        page_number: int,
        width: float | None,
        height: float | None,
    ) -> PageArtifact:
        engine = _get_rapidocr_engine()

        try:
            result = engine(str(image_path))
        except ExtractorDependencyError:
            raise
        except Exception as exc:
            raise ExtractorExecutionError(
                code="ocr_execution_failed",
                message=f"RapidOCR failed to process the image: {exc}",
            ) from exc

        boxes = getattr(result, "boxes", None) if result is not None else None
        texts = getattr(result, "txts", None) if result is not None else None
        scores = getattr(result, "scores", None) if result is not None else None

        polygon_list = self._to_list(boxes)
        text_list = list(texts or [])
        score_list = list(scores or [])

        text_blocks: list[TextBlockArtifact] = []
        page_text_chunks: list[str] = []

        for index, raw_polygon in enumerate(polygon_list, start=1):
            text = str(text_list[index - 1]).strip() if index - 1 < len(text_list) else ""
            if not text:
                continue

            polygon_points = [
                PolygonPoint(x=float(point[0]), y=float(point[1]))
                for point in raw_polygon
                if isinstance(point, (list, tuple)) and len(point) >= 2
            ]
            if not polygon_points:
                continue

            xs = [point.x for point in polygon_points]
            ys = [point.y for point in polygon_points]
            confidence = (
                float(score_list[index - 1])
                if index - 1 < len(score_list) and score_list[index - 1] is not None
                else None
            )

            text_blocks.append(
                TextBlockArtifact(
                    block_id=f"page-{page_number}-block-{index}",
                    page_number=page_number,
                    text=text,
                    bbox=BoundingBoxArtifact(
                        x0=min(xs),
                        y0=min(ys),
                        x1=max(xs),
                        y1=max(ys),
                        coordinate_space=CoordinateSpace.PIXELS,
                    ),
                    polygon=PolygonArtifact(
                        points=polygon_points,
                        coordinate_space=CoordinateSpace.PIXELS,
                    ),
                    confidence=confidence,
                    geometry_source=GeometrySource.OCR,
                )
            )
            page_text_chunks.append(text)

        return PageArtifact(
            page_number=page_number,
            width=width,
            height=height,
            coordinate_space=CoordinateSpace.PIXELS,
            text="\n".join(page_text_chunks).strip(),
            text_blocks=text_blocks,
            geometry_source=GeometrySource.OCR if text_blocks else None,
        )

    def _get_image_dimensions(self, image_path: Path) -> tuple[float | None, float | None]:
        if pymupdf is None:
            return None, None

        try:
            pixmap = pymupdf.Pixmap(str(image_path))
            return float(pixmap.width), float(pixmap.height)
        except Exception:
            return None, None

    def _to_list(self, value: object) -> list[list[list[float]]]:
        if value is None:
            return []
        if hasattr(value, "tolist"):
            converted = value.tolist()
            if isinstance(converted, list):
                return converted
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return []
