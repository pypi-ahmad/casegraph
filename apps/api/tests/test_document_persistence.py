"""Tests for durable document persistence.

Verifies that ingestion stores the full extraction output, source file
reference, and page records in the database — and that the new retrieval
endpoints reconstitute correct data from the stored state.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from casegraph_agent_sdk.ingestion import (
    BoundingBoxArtifact,
    CoordinateSpace,
    DocumentDetailResponse,
    DocumentPagesResponse,
    DocumentProcessingStatus,
    GeometrySource,
    IngestionMode,
    IngestionResult,
    NormalizedExtractionOutput,
    PageArtifact,
    SourceFileMetadata,
    TextBlockArtifact,
)

from app.ingestion.models import DocumentRecord
from app.ingestion.registry import DocumentRegistryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_extraction_output(document_id: str) -> NormalizedExtractionOutput:
    return NormalizedExtractionOutput(
        document_id=document_id,
        source_file=SourceFileMetadata(
            filename="report.pdf",
            content_type="application/pdf",
            extension=".pdf",
            size_bytes=8192,
            sha256="deadbeef",
            classification="pdf",
        ),
        requested_mode="auto",
        resolved_mode=IngestionMode.READABLE_PDF,
        status=DocumentProcessingStatus.COMPLETED,
        extractor_name="pymupdf-readable-pdf",
        extracted_text="Hello world.",
        pages=[
            PageArtifact(
                page_number=1,
                width=612.0,
                height=792.0,
                coordinate_space=CoordinateSpace.PDF_POINTS,
                text="Hello world.",
                text_blocks=[
                    TextBlockArtifact(
                        block_id="p1-b1",
                        page_number=1,
                        text="Hello world.",
                        bbox=BoundingBoxArtifact(
                            x0=72, y0=72, x1=540, y1=100,
                            coordinate_space=CoordinateSpace.PDF_POINTS,
                        ),
                        confidence=None,
                        geometry_source=GeometrySource.PDF_TEXT,
                    )
                ],
                geometry_source=GeometrySource.PDF_TEXT,
            ),
        ],
    )


def _mock_ingestion_patches(fake_output: NormalizedExtractionOutput):
    """Return a list of context managers that mock the ingestion pipeline's
    external dependencies so it runs entirely in-memory."""
    from contextlib import contextmanager

    @contextmanager
    def combined():
        with (
            patch(
                "app.ingestion.service.persist_upload",
                new_callable=AsyncMock,
            ) as mock_persist,
            patch("app.ingestion.service.cleanup_upload"),
            patch(
                "app.ingestion.extractors.readable_pdf.ReadablePdfExtractor.has_readable_text_layer",
                return_value=True,
            ),
            patch(
                "app.ingestion.extractors.readable_pdf.ReadablePdfExtractor.extract",
                return_value=fake_output,
            ),
            patch(
                "app.ingestion.extractors.readable_pdf.ReadablePdfExtractor.is_available",
                return_value=True,
            ),
            patch(
                "app.ingestion.service.DocumentIngestionService._save_page_images",
                return_value={},
            ),
            patch(
                "app.ingestion.service.DocumentIngestionService._persist_source_file",
                return_value="documents/test-doc/source.pdf",
            ),
        ):
            from app.ingestion.file_utils import PersistedUpload

            mock_persist.return_value = PersistedUpload(
                path=Path("/tmp/fake/report.pdf"),
                temp_dir=Path("/tmp/fake"),
                metadata=fake_output.source_file,
            )
            yield

    return combined()


# ---------------------------------------------------------------------------
# Extraction output persistence
# ---------------------------------------------------------------------------


class TestExtractionOutputPersistence:
    """Verify that NormalizedExtractionOutput is stored and retrievable."""

    def test_ingestion_stores_extraction_output_in_db(
        self, client: TestClient, session: Session
    ) -> None:
        fake = _fake_extraction_output("will-be-replaced")

        with _mock_ingestion_patches(fake):
            resp = client.post(
                "/documents/ingest",
                files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"mode": "auto", "ocr_enabled": "false"},
            )

        assert resp.status_code == 200
        result = IngestionResult.model_validate(resp.json())
        doc_id = result.summary.document_id

        # Verify extraction_output_json is populated in DB
        record = session.get(DocumentRecord, doc_id)
        assert record is not None
        assert record.extraction_output_json is not None
        assert record.extraction_output_json["extracted_text"] == "Hello world."
        assert len(record.extraction_output_json["pages"]) == 1

    def test_extraction_output_roundtrips_through_sdk_model(
        self, client: TestClient, session: Session
    ) -> None:
        fake = _fake_extraction_output("will-be-replaced")

        with _mock_ingestion_patches(fake):
            resp = client.post(
                "/documents/ingest",
                files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"mode": "auto", "ocr_enabled": "false"},
            )

        doc_id = IngestionResult.model_validate(resp.json()).summary.document_id

        # Reconstitute from DB via registry
        registry = DocumentRegistryService(session)
        output = registry.get_document_output(doc_id)
        assert output is not None
        assert output.extracted_text == "Hello world."
        assert output.resolved_mode == IngestionMode.READABLE_PDF
        assert len(output.pages) == 1
        assert output.pages[0].text_blocks[0].block_id == "p1-b1"
        assert output.pages[0].text_blocks[0].bbox is not None
        assert output.pages[0].text_blocks[0].bbox.x0 == 72.0

    def test_failed_ingestion_stores_no_extraction_output(
        self, client: TestClient, session: Session
    ) -> None:
        with (
            patch("app.ingestion.service.persist_upload", new_callable=AsyncMock) as mock_persist,
            patch("app.ingestion.service.cleanup_upload"),
        ):
            from app.ingestion.file_utils import PersistedUpload

            mock_persist.return_value = PersistedUpload(
                path=Path("/tmp/fake/bad.txt"),
                temp_dir=Path("/tmp/fake"),
                metadata=SourceFileMetadata(
                    filename="bad.txt",
                    content_type="text/plain",
                    extension=".txt",
                    size_bytes=10,
                    sha256="abcd",
                    classification="unsupported",
                ),
            )
            resp = client.post(
                "/documents/ingest",
                files={"file": ("bad.txt", b"hello", "text/plain")},
                data={"mode": "auto", "ocr_enabled": "false"},
            )

        assert resp.status_code == 200
        result = IngestionResult.model_validate(resp.json())
        assert result.summary.status == DocumentProcessingStatus.UNSUPPORTED

        record = session.get(DocumentRecord, result.summary.document_id)
        assert record is not None
        assert record.extraction_output_json is None
        assert record.source_file_path is None


# ---------------------------------------------------------------------------
# Source file path persistence
# ---------------------------------------------------------------------------


class TestSourceFilePersistence:
    """Verify that the source_file_path is stored on DocumentRecord."""

    def test_source_file_path_stored(
        self, client: TestClient, session: Session
    ) -> None:
        fake = _fake_extraction_output("will-be-replaced")

        with _mock_ingestion_patches(fake):
            resp = client.post(
                "/documents/ingest",
                files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"mode": "auto", "ocr_enabled": "false"},
            )

        doc_id = IngestionResult.model_validate(resp.json()).summary.document_id
        record = session.get(DocumentRecord, doc_id)
        assert record is not None
        assert record.source_file_path == "documents/test-doc/source.pdf"

    def test_source_file_path_retrievable_via_registry(
        self, client: TestClient, session: Session
    ) -> None:
        fake = _fake_extraction_output("will-be-replaced")

        with _mock_ingestion_patches(fake):
            resp = client.post(
                "/documents/ingest",
                files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"mode": "auto", "ocr_enabled": "false"},
            )

        doc_id = IngestionResult.model_validate(resp.json()).summary.document_id
        registry = DocumentRegistryService(session)
        path = registry.get_source_file_path(doc_id)
        assert path == "documents/test-doc/source.pdf"


# ---------------------------------------------------------------------------
# Document detail endpoint
# ---------------------------------------------------------------------------


class TestDocumentDetailEndpoint:
    """GET /documents/{document_id} returns full detail."""

    def test_detail_includes_output_and_pages(
        self, client: TestClient
    ) -> None:
        fake = _fake_extraction_output("will-be-replaced")

        with _mock_ingestion_patches(fake):
            ingest_resp = client.post(
                "/documents/ingest",
                files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"mode": "auto", "ocr_enabled": "false"},
            )

        doc_id = IngestionResult.model_validate(ingest_resp.json()).summary.document_id

        resp = client.get(f"/documents/{doc_id}")
        assert resp.status_code == 200
        detail = DocumentDetailResponse.model_validate(resp.json())

        # Summary present
        assert detail.summary.document_id == doc_id
        assert detail.summary.status == DocumentProcessingStatus.COMPLETED

        # Full extraction output reconstituted
        assert detail.output is not None
        assert detail.output.extracted_text == "Hello world."
        assert detail.output.resolved_mode == IngestionMode.READABLE_PDF

        # Source file path
        assert detail.source_file_path is not None

        # Pages with text blocks
        assert len(detail.pages) == 1
        assert detail.pages[0].page_number == 1
        assert detail.pages[0].text == "Hello world."
        assert len(detail.pages[0].text_blocks) == 1
        assert detail.pages[0].text_blocks[0]["block_id"] == "p1-b1"

    def test_detail_404_for_missing_document(self, client: TestClient) -> None:
        resp = client.get("/documents/nonexistent-id")
        assert resp.status_code == 404

    def test_detail_for_failed_document_has_no_output(
        self, client: TestClient
    ) -> None:
        with (
            patch("app.ingestion.service.persist_upload", new_callable=AsyncMock) as mock_persist,
            patch("app.ingestion.service.cleanup_upload"),
        ):
            from app.ingestion.file_utils import PersistedUpload

            mock_persist.return_value = PersistedUpload(
                path=Path("/tmp/fake/bad.txt"),
                temp_dir=Path("/tmp/fake"),
                metadata=SourceFileMetadata(
                    filename="bad.txt",
                    content_type="text/plain",
                    extension=".txt",
                    size_bytes=10,
                    sha256="abcd",
                    classification="unsupported",
                ),
            )
            ingest_resp = client.post(
                "/documents/ingest",
                files={"file": ("bad.txt", b"hello", "text/plain")},
                data={"mode": "auto", "ocr_enabled": "false"},
            )

        doc_id = IngestionResult.model_validate(ingest_resp.json()).summary.document_id
        resp = client.get(f"/documents/{doc_id}")
        assert resp.status_code == 200
        detail = DocumentDetailResponse.model_validate(resp.json())
        assert detail.output is None
        assert detail.source_file_path is None
        assert detail.pages == []


# ---------------------------------------------------------------------------
# Document pages endpoint
# ---------------------------------------------------------------------------


class TestDocumentPagesEndpoint:
    """GET /documents/{document_id}/pages returns page-by-page detail."""

    def test_pages_endpoint_returns_page_data(self, client: TestClient) -> None:
        fake = _fake_extraction_output("will-be-replaced")

        with _mock_ingestion_patches(fake):
            ingest_resp = client.post(
                "/documents/ingest",
                files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"mode": "auto", "ocr_enabled": "false"},
            )

        doc_id = IngestionResult.model_validate(ingest_resp.json()).summary.document_id

        resp = client.get(f"/documents/{doc_id}/pages")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        pages = DocumentPagesResponse.model_validate(resp.json())
        assert pages.document_id == doc_id
        assert len(pages.pages) == 1
        page = pages.pages[0]
        assert page.page_number == 1
        assert page.width == 612.0
        assert page.height == 792.0
        assert page.coordinate_space == "pdf_points"
        assert page.geometry_source == "pdf_text"
        assert page.text == "Hello world."
        assert len(page.text_blocks) == 1

    def test_pages_endpoint_404_for_missing_document(self, client: TestClient) -> None:
        resp = client.get("/documents/nonexistent-id/pages")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Page record persistence
# ---------------------------------------------------------------------------


class TestPageRecordPersistence:
    """Verify page records are stored with full text block geometry."""

    def test_page_records_persisted_with_geometry(
        self, client: TestClient, session: Session
    ) -> None:
        fake = _fake_extraction_output("will-be-replaced")

        with _mock_ingestion_patches(fake):
            resp = client.post(
                "/documents/ingest",
                files={"file": ("report.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"mode": "auto", "ocr_enabled": "false"},
            )

        doc_id = IngestionResult.model_validate(resp.json()).summary.document_id

        registry = DocumentRegistryService(session)
        pages = registry.get_page_records(doc_id)
        assert len(pages) == 1

        page = pages[0]
        assert page.document_id == doc_id
        assert page.page_number == 1
        assert page.text == "Hello world."
        assert page.coordinate_space == "pdf_points"
        assert page.geometry_source == "pdf_text"
        assert len(page.text_blocks_json) == 1

        block = page.text_blocks_json[0]
        assert block["block_id"] == "p1-b1"
        assert block["bbox"]["x0"] == 72.0
        assert block["geometry_source"] == "pdf_text"


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------


class TestDocumentSchemaMigration:
    """The compatibility migration adds the new columns to legacy tables."""

    def test_legacy_table_gets_new_columns(self, tmp_path: Path) -> None:
        import sqlite3

        from app.persistence.database import configure_engine, init_database

        db_path = tmp_path / "legacy.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE documents (
                    document_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    content_type TEXT,
                    extension TEXT,
                    size_bytes INTEGER,
                    sha256 TEXT,
                    classification TEXT NOT NULL,
                    requested_mode TEXT NOT NULL,
                    resolved_mode TEXT NOT NULL,
                    processing_status TEXT NOT NULL,
                    extractor_name TEXT,
                    page_count INTEGER NOT NULL DEFAULT 0,
                    text_block_count INTEGER NOT NULL DEFAULT 0,
                    geometry_present BOOLEAN NOT NULL DEFAULT 0,
                    geometry_sources_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

        configure_engine(f"sqlite:///{db_path.as_posix()}")
        init_database()

        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(documents)")
            columns = {row[1] for row in cursor.fetchall()}

        assert "source_file_path" in columns
        assert "extraction_output_json" in columns
