from pathlib import Path

from casegraph_agent_sdk.ingestion import (
    FileTypeClassification,
    IngestionMode,
    IngestionModePreference,
    IngestionRequest,
    SourceFileMetadata,
)

from app.ingestion.routing import IngestionRouter


class FakeReadablePdfExtractor:
    def __init__(self, *, available: bool = True, has_text_layer: bool = True) -> None:
        self._available = available
        self._has_text_layer = has_text_layer

    def is_available(self) -> bool:
        return self._available

    def has_readable_text_layer(self, _file_path: Path) -> bool:
        return self._has_text_layer


class FakeOcrExtractor:
    def __init__(self, *, images_available: bool = True, scanned_pdf_available: bool = True) -> None:
        self._images_available = images_available
        self._scanned_pdf_available = scanned_pdf_available

    def is_available_for_images(self) -> bool:
        return self._images_available

    def is_available_for_scanned_pdfs(self) -> bool:
        return self._scanned_pdf_available


def build_metadata(classification: FileTypeClassification) -> SourceFileMetadata:
    return SourceFileMetadata(
        filename="sample.pdf" if classification == FileTypeClassification.PDF else "sample.png",
        content_type=(
            "application/pdf"
            if classification == FileTypeClassification.PDF
            else "image/png"
        ),
        extension=".pdf" if classification == FileTypeClassification.PDF else ".png",
        size_bytes=128,
        sha256="abc123",
        classification=classification,
    )


def test_auto_pdf_routes_to_readable_pdf_when_text_layer_exists() -> None:
    router = IngestionRouter(
        readable_pdf_extractor=FakeReadablePdfExtractor(has_text_layer=True),
        ocr_extractor=FakeOcrExtractor(),
    )

    decision = router.route(
        build_metadata(FileTypeClassification.PDF),
        IngestionRequest(requested_mode=IngestionModePreference.AUTO, ocr_enabled=False),
        Path("sample.pdf"),
    )

    assert decision.resolved_mode == IngestionMode.READABLE_PDF
    assert decision.errors == []


def test_explicit_readable_pdf_rejects_scanned_pdf_without_text_layer() -> None:
    router = IngestionRouter(
        readable_pdf_extractor=FakeReadablePdfExtractor(has_text_layer=False),
        ocr_extractor=FakeOcrExtractor(),
    )

    decision = router.route(
        build_metadata(FileTypeClassification.PDF),
        IngestionRequest(
            requested_mode=IngestionModePreference.READABLE_PDF,
            ocr_enabled=False,
        ),
        Path("sample.pdf"),
    )

    assert decision.resolved_mode == IngestionMode.UNSUPPORTED
    assert decision.errors[0].code == "readable_text_layer_not_detected"


def test_auto_pdf_requires_explicit_ocr_for_scanned_pdf() -> None:
    router = IngestionRouter(
        readable_pdf_extractor=FakeReadablePdfExtractor(has_text_layer=False),
        ocr_extractor=FakeOcrExtractor(scanned_pdf_available=True),
    )

    decision = router.route(
        build_metadata(FileTypeClassification.PDF),
        IngestionRequest(requested_mode=IngestionModePreference.AUTO, ocr_enabled=False),
        Path("sample.pdf"),
    )

    assert decision.resolved_mode == IngestionMode.UNSUPPORTED
    assert decision.errors[0].code == "ocr_required_for_scanned_pdf"


def test_auto_image_requires_explicit_ocr_enablement() -> None:
    router = IngestionRouter(
        readable_pdf_extractor=FakeReadablePdfExtractor(),
        ocr_extractor=FakeOcrExtractor(images_available=True),
    )

    decision = router.route(
        build_metadata(FileTypeClassification.IMAGE),
        IngestionRequest(requested_mode=IngestionModePreference.AUTO, ocr_enabled=False),
        Path("sample.png"),
    )

    assert decision.resolved_mode == IngestionMode.UNSUPPORTED
    assert decision.errors[0].code == "ocr_required_for_images"


def test_explicit_image_mode_routes_when_ocr_is_enabled() -> None:
    router = IngestionRouter(
        readable_pdf_extractor=FakeReadablePdfExtractor(),
        ocr_extractor=FakeOcrExtractor(images_available=True),
    )

    decision = router.route(
        build_metadata(FileTypeClassification.IMAGE),
        IngestionRequest(requested_mode=IngestionModePreference.IMAGE, ocr_enabled=True),
        Path("sample.png"),
    )

    assert decision.resolved_mode == IngestionMode.IMAGE
    assert decision.errors == []