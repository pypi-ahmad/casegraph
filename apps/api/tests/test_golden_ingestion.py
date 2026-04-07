"""Golden-response tests for normalized ingestion output shapes.

These tests pin the exact schema, field names, coordinate spaces, and
geometry metadata that extraction outputs MUST produce.  If the shape
changes, a downstream consumer (SDK, frontend overlay, packet assembly)
will break — so the test should break first.

Golden fixtures are checked in at ``tests/fixtures/golden_extraction_outputs.json``
so changes to the expected shape are version-controlled and reviewable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from casegraph_agent_sdk.ingestion import (
    BoundingBoxArtifact,
    CoordinateSpace,
    DocumentProcessingStatus,
    GeometrySource,
    IngestionMode,
    IngestionModePreference,
    IngestionResult,
    IngestionResultSummary,
    NormalizedExtractionOutput,
    PageArtifact,
    SourceFileMetadata,
    TextBlockArtifact,
)


# ═══════════════════════════════════════════════════════════════════════════
# Load golden fixtures from checked-in JSON
# ═══════════════════════════════════════════════════════════════════════════

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

def _load_golden_fixtures() -> dict:
    with open(_FIXTURES_DIR / "golden_extraction_outputs.json", encoding="utf-8") as f:
        return json.load(f)

_FIXTURES = _load_golden_fixtures()
GOLDEN_READABLE_PDF = NormalizedExtractionOutput.model_validate(_FIXTURES["readable_pdf"])
GOLDEN_OCR_IMAGE = NormalizedExtractionOutput.model_validate(_FIXTURES["ocr_image"])


# ═══════════════════════════════════════════════════════════════════════════
# Fixture round-trip: JSON file must parse to valid SDK types
# ═══════════════════════════════════════════════════════════════════════════


class TestFixtureIntegrity:
    """The checked-in JSON fixture must stay valid against the SDK schema."""

    def test_readable_pdf_fixture_parses(self) -> None:
        assert GOLDEN_READABLE_PDF.resolved_mode == IngestionMode.READABLE_PDF

    def test_ocr_image_fixture_parses(self) -> None:
        assert GOLDEN_OCR_IMAGE.resolved_mode == IngestionMode.IMAGE

    def test_fixture_file_is_valid_json(self) -> None:
        raw = (_FIXTURES_DIR / "golden_extraction_outputs.json").read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert "readable_pdf" in parsed
        assert "ocr_image" in parsed


# ═══════════════════════════════════════════════════════════════════════════
# Schema shape tests — field existence and types
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalizedOutputSchema:
    """Pin the exact fields on NormalizedExtractionOutput so removal is caught."""

    REQUIRED_TOP_FIELDS = {
        "document_id", "source_file", "requested_mode", "resolved_mode",
        "status", "extractor_name", "extracted_text", "pages",
    }
    REQUIRED_PAGE_FIELDS = {
        "page_number", "width", "height", "coordinate_space",
        "text", "text_blocks", "geometry_source",
    }
    REQUIRED_BLOCK_FIELDS = {
        "block_id", "page_number", "text", "bbox", "polygon",
        "confidence", "geometry_source",
    }
    REQUIRED_BBOX_FIELDS = {"x0", "y0", "x1", "y1", "coordinate_space"}
    REQUIRED_SOURCE_FIELDS = {
        "filename", "content_type", "extension", "size_bytes",
        "sha256", "classification",
    }

    def test_top_level_fields(self) -> None:
        actual = set(NormalizedExtractionOutput.model_fields.keys())
        assert self.REQUIRED_TOP_FIELDS <= actual, (
            f"Missing top-level fields: {self.REQUIRED_TOP_FIELDS - actual}"
        )

    def test_page_artifact_fields(self) -> None:
        actual = set(PageArtifact.model_fields.keys())
        assert self.REQUIRED_PAGE_FIELDS <= actual, (
            f"Missing PageArtifact fields: {self.REQUIRED_PAGE_FIELDS - actual}"
        )

    def test_text_block_artifact_fields(self) -> None:
        actual = set(TextBlockArtifact.model_fields.keys())
        assert self.REQUIRED_BLOCK_FIELDS <= actual, (
            f"Missing TextBlockArtifact fields: {self.REQUIRED_BLOCK_FIELDS - actual}"
        )

    def test_bounding_box_artifact_fields(self) -> None:
        actual = set(BoundingBoxArtifact.model_fields.keys())
        assert self.REQUIRED_BBOX_FIELDS <= actual, (
            f"Missing BoundingBoxArtifact fields: {self.REQUIRED_BBOX_FIELDS - actual}"
        )

    def test_source_file_metadata_fields(self) -> None:
        actual = set(SourceFileMetadata.model_fields.keys())
        assert self.REQUIRED_SOURCE_FIELDS <= actual, (
            f"Missing SourceFileMetadata fields: {self.REQUIRED_SOURCE_FIELDS - actual}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Golden readable-PDF assertions
# ═══════════════════════════════════════════════════════════════════════════


class TestGoldenReadablePdf:
    """Pin exact shape of readable-PDF extraction output."""

    def test_resolved_mode(self) -> None:
        assert GOLDEN_READABLE_PDF.resolved_mode == IngestionMode.READABLE_PDF

    def test_status_completed(self) -> None:
        assert GOLDEN_READABLE_PDF.status == DocumentProcessingStatus.COMPLETED

    def test_extractor_name(self) -> None:
        assert GOLDEN_READABLE_PDF.extractor_name == "pymupdf-readable-pdf"

    def test_page_count(self) -> None:
        assert len(GOLDEN_READABLE_PDF.pages) == 1

    def test_coordinate_space_pdf_points(self) -> None:
        page = GOLDEN_READABLE_PDF.pages[0]
        assert page.coordinate_space == CoordinateSpace.PDF_POINTS
        for block in page.text_blocks:
            assert block.bbox is not None
            assert block.bbox.coordinate_space == CoordinateSpace.PDF_POINTS

    def test_geometry_source_pdf_text(self) -> None:
        page = GOLDEN_READABLE_PDF.pages[0]
        assert page.geometry_source == GeometrySource.PDF_TEXT
        for block in page.text_blocks:
            assert block.geometry_source == GeometrySource.PDF_TEXT

    def test_no_polygon_on_readable_pdf(self) -> None:
        for page in GOLDEN_READABLE_PDF.pages:
            for block in page.text_blocks:
                assert block.polygon is None, (
                    "Readable PDF blocks must NOT have polygon data"
                )

    def test_no_confidence_on_readable_pdf(self) -> None:
        for page in GOLDEN_READABLE_PDF.pages:
            for block in page.text_blocks:
                assert block.confidence is None, (
                    "Readable PDF blocks must NOT have confidence scores"
                )

    def test_block_id_format(self) -> None:
        for page in GOLDEN_READABLE_PDF.pages:
            for block in page.text_blocks:
                assert block.block_id.startswith("page-"), (
                    f"Block ID must start with 'page-': {block.block_id}"
                )

    def test_page_dimensions_present(self) -> None:
        page = GOLDEN_READABLE_PDF.pages[0]
        assert page.width is not None and page.width > 0
        assert page.height is not None and page.height > 0

    def test_bbox_coordinates_valid(self) -> None:
        for page in GOLDEN_READABLE_PDF.pages:
            for block in page.text_blocks:
                assert block.bbox is not None
                assert block.bbox.x0 < block.bbox.x1
                assert block.bbox.y0 < block.bbox.y1

    def test_round_trip_serialization(self) -> None:
        dumped = GOLDEN_READABLE_PDF.model_dump(mode="json")
        restored = NormalizedExtractionOutput.model_validate(dumped)
        assert restored == GOLDEN_READABLE_PDF


# ═══════════════════════════════════════════════════════════════════════════
# Golden OCR/image assertions
# ═══════════════════════════════════════════════════════════════════════════


class TestGoldenOcrImage:
    """Pin exact shape of OCR image extraction output."""

    def test_resolved_mode(self) -> None:
        assert GOLDEN_OCR_IMAGE.resolved_mode == IngestionMode.IMAGE

    def test_coordinate_space_pixels(self) -> None:
        page = GOLDEN_OCR_IMAGE.pages[0]
        assert page.coordinate_space == CoordinateSpace.PIXELS
        for block in page.text_blocks:
            assert block.bbox is not None
            assert block.bbox.coordinate_space == CoordinateSpace.PIXELS

    def test_geometry_source_ocr(self) -> None:
        page = GOLDEN_OCR_IMAGE.pages[0]
        assert page.geometry_source == GeometrySource.OCR
        for block in page.text_blocks:
            assert block.geometry_source == GeometrySource.OCR

    def test_polygon_present_on_ocr(self) -> None:
        for page in GOLDEN_OCR_IMAGE.pages:
            for block in page.text_blocks:
                assert block.polygon is not None, (
                    "OCR blocks MUST have polygon data"
                )
                assert len(block.polygon.points) >= 4
                assert block.polygon.coordinate_space == CoordinateSpace.PIXELS

    def test_confidence_present_on_ocr(self) -> None:
        for page in GOLDEN_OCR_IMAGE.pages:
            for block in page.text_blocks:
                assert block.confidence is not None, (
                    "OCR blocks MUST have confidence scores"
                )
                assert 0.0 <= block.confidence <= 1.0

    def test_bbox_derived_from_polygon(self) -> None:
        """OCR bbox should be consistent with polygon bounding rectangle."""
        for page in GOLDEN_OCR_IMAGE.pages:
            for block in page.text_blocks:
                assert block.polygon is not None
                assert block.bbox is not None
                xs = [p.x for p in block.polygon.points]
                ys = [p.y for p in block.polygon.points]
                assert block.bbox.x0 == pytest.approx(min(xs), abs=1.0)
                assert block.bbox.y0 == pytest.approx(min(ys), abs=1.0)
                assert block.bbox.x1 == pytest.approx(max(xs), abs=1.0)
                assert block.bbox.y1 == pytest.approx(max(ys), abs=1.0)

    def test_round_trip_serialization(self) -> None:
        dumped = GOLDEN_OCR_IMAGE.model_dump(mode="json")
        restored = NormalizedExtractionOutput.model_validate(dumped)
        assert restored == GOLDEN_OCR_IMAGE


# ═══════════════════════════════════════════════════════════════════════════
# IngestionResult wrapper shape
# ═══════════════════════════════════════════════════════════════════════════


class TestIngestionResultShape:
    """Pin the wrapper shape that the API actually returns."""

    def test_successful_result_has_output_and_summary(self) -> None:
        result = IngestionResult(
            summary=IngestionResultSummary(
                document_id="doc-1",
                source_file=GOLDEN_READABLE_PDF.source_file,
                status=DocumentProcessingStatus.COMPLETED,
                requested_mode=IngestionModePreference.AUTO,
                resolved_mode=IngestionMode.READABLE_PDF,
                extractor_name="pymupdf-readable-pdf",
                page_count=1,
                text_block_count=2,
                geometry_present=True,
                geometry_sources=[GeometrySource.PDF_TEXT],
            ),
            output=GOLDEN_READABLE_PDF,
            errors=[],
        )
        assert result.output is not None
        assert result.summary.geometry_present is True
        assert result.errors == []

    def test_unsupported_result_has_no_output(self) -> None:
        result = IngestionResult(
            summary=IngestionResultSummary(
                document_id="doc-2",
                source_file=SourceFileMetadata(
                    filename="notes.txt",
                    classification="unsupported",
                ),
                status=DocumentProcessingStatus.UNSUPPORTED,
                requested_mode=IngestionModePreference.AUTO,
                resolved_mode=IngestionMode.UNSUPPORTED,
            ),
            output=None,
            errors=[{"code": "unsupported_file_type", "message": "Not supported", "recoverable": False}],
        )
        assert result.output is None
        assert len(result.errors) == 1
        assert result.summary.geometry_present is False

    def test_summary_round_trip(self) -> None:
        summary = IngestionResultSummary(
            document_id="doc-3",
            source_file=GOLDEN_READABLE_PDF.source_file,
            status=DocumentProcessingStatus.COMPLETED,
            requested_mode=IngestionModePreference.AUTO,
            resolved_mode=IngestionMode.READABLE_PDF,
            extractor_name="pymupdf-readable-pdf",
            page_count=1,
            text_block_count=2,
            geometry_present=True,
            geometry_sources=[GeometrySource.PDF_TEXT],
        )
        dumped = summary.model_dump(mode="json")
        restored = IngestionResultSummary.model_validate(dumped)
        assert restored == summary


# ═══════════════════════════════════════════════════════════════════════════
# Enum value contracts — downstream consumers depend on exact string values
# ═══════════════════════════════════════════════════════════════════════════


class TestEnumContracts:
    """Pin enum string values that frontend and SDK consumers depend on."""

    def test_ingestion_mode_values(self) -> None:
        assert IngestionMode.READABLE_PDF.value == "readable_pdf"
        assert IngestionMode.SCANNED_PDF.value == "scanned_pdf"
        assert IngestionMode.IMAGE.value == "image"
        assert IngestionMode.UNSUPPORTED.value == "unsupported"

    def test_coordinate_space_values(self) -> None:
        assert CoordinateSpace.PDF_POINTS.value == "pdf_points"
        assert CoordinateSpace.PIXELS.value == "pixels"
        assert CoordinateSpace.NORMALIZED.value == "normalized"

    def test_geometry_source_values(self) -> None:
        assert GeometrySource.PDF_TEXT.value == "pdf_text"
        assert GeometrySource.OCR.value == "ocr"

    def test_processing_status_values(self) -> None:
        assert DocumentProcessingStatus.PENDING.value == "pending"
        assert DocumentProcessingStatus.COMPLETED.value == "completed"
        assert DocumentProcessingStatus.FAILED.value == "failed"
        assert DocumentProcessingStatus.UNSUPPORTED.value == "unsupported"

    def test_mode_preference_values(self) -> None:
        assert IngestionModePreference.AUTO.value == "auto"
        assert IngestionModePreference.READABLE_PDF.value == "readable_pdf"
        assert IngestionModePreference.SCANNED_PDF.value == "scanned_pdf"
        assert IngestionModePreference.IMAGE.value == "image"
