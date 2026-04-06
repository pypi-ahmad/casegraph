"""Explicit ingestion routing policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from casegraph_agent_sdk.ingestion import (
    IngestionError,
    IngestionMode,
    IngestionModePreference,
    IngestionRequest,
    SourceFileMetadata,
)

from app.ingestion.extractors.ocr import OcrExtractionAdapter
from app.ingestion.extractors.readable_pdf import ReadablePdfExtractor


@dataclass(slots=True)
class RoutingDecision:
    resolved_mode: IngestionMode
    errors: list[IngestionError] = field(default_factory=list)


class IngestionRouter:
    def __init__(
        self,
        readable_pdf_extractor: ReadablePdfExtractor,
        ocr_extractor: OcrExtractionAdapter,
    ) -> None:
        self._readable_pdf_extractor = readable_pdf_extractor
        self._ocr_extractor = ocr_extractor

    def route(
        self,
        source_file: SourceFileMetadata,
        request: IngestionRequest,
        file_path: Path,
    ) -> RoutingDecision:
        requested_mode = request.requested_mode

        if requested_mode == IngestionModePreference.READABLE_PDF:
            return self._route_readable_pdf(source_file, file_path)

        if requested_mode == IngestionModePreference.SCANNED_PDF:
            return self._route_scanned_pdf(source_file, request)

        if requested_mode == IngestionModePreference.IMAGE:
            return self._route_image(source_file, request)

        return self._route_auto(source_file, request, file_path)

    def _route_auto(
        self,
        source_file: SourceFileMetadata,
        request: IngestionRequest,
        file_path: Path,
    ) -> RoutingDecision:
        if source_file.classification.value == "image":
            if not request.ocr_enabled:
                return self._unsupported(
                    code="ocr_required_for_images",
                    message="Image ingestion requires OCR to be explicitly enabled.",
                    recoverable=True,
                )
            if not self._ocr_extractor.is_available_for_images():
                return self._unsupported(
                    code="ocr_engine_unavailable",
                    message="The OCR engine is not available for image ingestion.",
                    recoverable=True,
                )
            return RoutingDecision(resolved_mode=IngestionMode.IMAGE)

        if source_file.classification.value == "pdf":
            if not self._readable_pdf_extractor.is_available():
                return self._unsupported(
                    code="pdf_extractor_unavailable",
                    message="The readable PDF extractor is not available.",
                    recoverable=True,
                )

            if self._readable_pdf_extractor.has_readable_text_layer(file_path):
                return RoutingDecision(resolved_mode=IngestionMode.READABLE_PDF)

            if not request.ocr_enabled:
                return self._unsupported(
                    code="ocr_required_for_scanned_pdf",
                    message=(
                        "The PDF appears image-based. Enable OCR to ingest scanned PDFs."
                    ),
                    recoverable=True,
                )

            if not self._ocr_extractor.is_available_for_scanned_pdfs():
                return self._unsupported(
                    code="ocr_engine_unavailable",
                    message="The OCR engine is not available for scanned PDF ingestion.",
                    recoverable=True,
                )

            return RoutingDecision(resolved_mode=IngestionMode.SCANNED_PDF)

        return self._unsupported(
            code="unsupported_file_type",
            message="The uploaded file type is not currently supported.",
        )

    def _route_readable_pdf(
        self,
        source_file: SourceFileMetadata,
        file_path: Path,
    ) -> RoutingDecision:
        if source_file.classification.value != "pdf":
            return self._unsupported(
                code="invalid_mode_for_file_type",
                message="Readable PDF mode only accepts PDF files.",
                recoverable=True,
            )
        if not self._readable_pdf_extractor.is_available():
            return self._unsupported(
                code="pdf_extractor_unavailable",
                message="The readable PDF extractor is not available.",
                recoverable=True,
            )

        if not self._readable_pdf_extractor.has_readable_text_layer(file_path):
            return self._unsupported(
                code="readable_text_layer_not_detected",
                message=(
                    "Readable PDF mode requires a detectable text layer. "
                    "Use scanned_pdf with OCR enabled for image-based PDFs."
                ),
                recoverable=True,
            )

        return RoutingDecision(resolved_mode=IngestionMode.READABLE_PDF)

    def _route_scanned_pdf(
        self,
        source_file: SourceFileMetadata,
        request: IngestionRequest,
    ) -> RoutingDecision:
        if source_file.classification.value != "pdf":
            return self._unsupported(
                code="invalid_mode_for_file_type",
                message="Scanned PDF mode only accepts PDF files.",
                recoverable=True,
            )
        if not request.ocr_enabled:
            return self._unsupported(
                code="ocr_not_enabled",
                message="Scanned PDF mode requires OCR to be explicitly enabled.",
                recoverable=True,
            )
        if not self._ocr_extractor.is_available_for_scanned_pdfs():
            return self._unsupported(
                code="ocr_engine_unavailable",
                message="The OCR engine is not available for scanned PDF ingestion.",
                recoverable=True,
            )
        return RoutingDecision(resolved_mode=IngestionMode.SCANNED_PDF)

    def _route_image(
        self,
        source_file: SourceFileMetadata,
        request: IngestionRequest,
    ) -> RoutingDecision:
        if source_file.classification.value != "image":
            return self._unsupported(
                code="invalid_mode_for_file_type",
                message="Image mode only accepts image files.",
                recoverable=True,
            )
        if not request.ocr_enabled:
            return self._unsupported(
                code="ocr_not_enabled",
                message="Image mode requires OCR to be explicitly enabled.",
                recoverable=True,
            )
        if not self._ocr_extractor.is_available_for_images():
            return self._unsupported(
                code="ocr_engine_unavailable",
                message="The OCR engine is not available for image ingestion.",
                recoverable=True,
            )
        return RoutingDecision(resolved_mode=IngestionMode.IMAGE)

    def _unsupported(
        self,
        *,
        code: str,
        message: str,
        recoverable: bool = False,
    ) -> RoutingDecision:
        return RoutingDecision(
            resolved_mode=IngestionMode.UNSUPPORTED,
            errors=[IngestionError(code=code, message=message, recoverable=recoverable)],
        )
