"""Tests for the document review surface."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.ingestion import (
    CoordinateSpace,
    GeometrySource,
    IngestionMode,
)

from app.ingestion.models import DocumentRecord
from app.review.models import PageRecord
from app.review.service import DocumentReviewService


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_readable_pdf(session: Session) -> str:
    document_id = "doc-readable-001"
    session.add(
        DocumentRecord(
            document_id=document_id,
            filename="test.pdf",
            content_type="application/pdf",
            extension=".pdf",
            size_bytes=1024,
            sha256="abc123",
            classification="pdf",
            requested_mode="auto",
            resolved_mode="readable_pdf",
            processing_status="completed",
            extractor_name="pymupdf-readable-pdf",
            page_count=2,
            text_block_count=3,
            geometry_present=True,
            geometry_sources_json=["pdf_text"],
        )
    )
    session.add(
        PageRecord(
            page_id=f"{document_id}:1",
            document_id=document_id,
            page_number=1,
            width=612.0,
            height=792.0,
            coordinate_space="pdf_points",
            geometry_source="pdf_text",
            text="Hello world",
            text_blocks_json=[
                {
                    "block_id": "page-1-block-1",
                    "page_number": 1,
                    "text": "Hello",
                    "bbox": {
                        "x0": 72.0,
                        "y0": 72.0,
                        "x1": 200.0,
                        "y1": 90.0,
                        "coordinate_space": "pdf_points",
                    },
                    "polygon": None,
                    "confidence": None,
                    "geometry_source": "pdf_text",
                },
                {
                    "block_id": "page-1-block-2",
                    "page_number": 1,
                    "text": "world",
                    "bbox": {
                        "x0": 72.0,
                        "y0": 100.0,
                        "x1": 200.0,
                        "y1": 118.0,
                        "coordinate_space": "pdf_points",
                    },
                    "polygon": None,
                    "confidence": None,
                    "geometry_source": "pdf_text",
                },
            ],
            has_page_image=False,
            page_image_path=None,
        )
    )
    session.add(
        PageRecord(
            page_id=f"{document_id}:2",
            document_id=document_id,
            page_number=2,
            width=612.0,
            height=792.0,
            coordinate_space="pdf_points",
            geometry_source="pdf_text",
            text="Page two text",
            text_blocks_json=[
                {
                    "block_id": "page-2-block-1",
                    "page_number": 2,
                    "text": "Page two text",
                    "bbox": {
                        "x0": 72.0,
                        "y0": 72.0,
                        "x1": 300.0,
                        "y1": 90.0,
                        "coordinate_space": "pdf_points",
                    },
                    "polygon": None,
                    "confidence": None,
                    "geometry_source": "pdf_text",
                },
            ],
            has_page_image=False,
        )
    )
    session.commit()
    return document_id


def _seed_ocr_document(session: Session) -> str:
    document_id = "doc-ocr-001"
    session.add(
        DocumentRecord(
            document_id=document_id,
            filename="scan.pdf",
            content_type="application/pdf",
            extension=".pdf",
            size_bytes=2048,
            sha256="def456",
            classification="pdf",
            requested_mode="scanned_pdf",
            resolved_mode="scanned_pdf",
            processing_status="completed",
            extractor_name="rapidocr-onnxruntime",
            page_count=1,
            text_block_count=1,
            geometry_present=True,
            geometry_sources_json=["ocr"],
        )
    )
    session.add(
        PageRecord(
            page_id=f"{document_id}:1",
            document_id=document_id,
            page_number=1,
            width=1800.0,
            height=2400.0,
            coordinate_space="pixels",
            geometry_source="ocr",
            text="OCR text",
            text_blocks_json=[
                {
                    "block_id": "page-1-block-1",
                    "page_number": 1,
                    "text": "OCR text",
                    "bbox": {
                        "x0": 100.0,
                        "y0": 200.0,
                        "x1": 500.0,
                        "y1": 250.0,
                        "coordinate_space": "pixels",
                    },
                    "polygon": {
                        "points": [
                            {"x": 100.0, "y": 200.0},
                            {"x": 500.0, "y": 200.0},
                            {"x": 500.0, "y": 250.0},
                            {"x": 100.0, "y": 250.0},
                        ],
                        "coordinate_space": "pixels",
                    },
                    "confidence": 0.95,
                    "geometry_source": "ocr",
                },
            ],
            has_page_image=True,
            page_image_path="documents/doc-ocr-001/pages/page-1.png",
        )
    )
    session.commit()
    return document_id


def test_document_review_returns_readable_pdf_data(session: Session) -> None:
    document_id = _seed_readable_pdf(session)
    service = DocumentReviewService(session)

    review = service.get_document_review(document_id)
    assert review is not None
    assert review.document.document_id == document_id
    assert review.document.ingestion_mode == IngestionMode.READABLE_PDF
    assert review.document.page_count == 2
    assert review.document.text_block_count == 3
    assert review.document.geometry_available is True
    assert GeometrySource.PDF_TEXT in review.document.geometry_sources
    assert review.document.page_images_available is False
    assert len(review.pages) == 2
    assert review.pages[0].page_number == 1
    assert review.pages[0].text_block_count == 2
    assert review.pages[0].has_geometry is True
    assert review.pages[0].has_page_image is False
    assert review.capabilities.can_show_pages is True
    assert review.capabilities.can_show_geometry is True
    assert review.capabilities.can_show_page_images is False
    assert "readable_pdf_extraction" in review.capabilities.overlay_source_types


def test_document_review_returns_ocr_data(session: Session) -> None:
    document_id = _seed_ocr_document(session)
    service = DocumentReviewService(session)

    review = service.get_document_review(document_id)
    assert review is not None
    assert review.document.ingestion_mode == IngestionMode.SCANNED_PDF
    assert review.document.geometry_available is True
    assert GeometrySource.OCR in review.document.geometry_sources
    assert review.document.page_images_available is True
    assert len(review.pages) == 1
    assert review.pages[0].has_page_image is True
    assert review.capabilities.can_show_page_images is True
    assert "ocr_extraction" in review.capabilities.overlay_source_types


def test_page_detail_returns_text_blocks(session: Session) -> None:
    document_id = _seed_readable_pdf(session)
    service = DocumentReviewService(session)

    detail = service.get_page_detail(document_id, 1)
    assert detail is not None
    assert detail.page_number == 1
    assert detail.text == "Hello world"
    assert len(detail.text_blocks) == 2
    assert detail.text_blocks[0].block_id == "page-1-block-1"
    assert detail.text_blocks[0].bbox is not None
    assert detail.text_blocks[0].bbox.coordinate_space == CoordinateSpace.PDF_POINTS
    assert detail.text_blocks[0].geometry_source == GeometrySource.PDF_TEXT


def test_page_detail_returns_ocr_polygon_and_confidence(session: Session) -> None:
    document_id = _seed_ocr_document(session)
    service = DocumentReviewService(session)

    detail = service.get_page_detail(document_id, 1)
    assert detail is not None
    assert len(detail.text_blocks) == 1
    block = detail.text_blocks[0]
    assert block.polygon is not None
    assert len(block.polygon.points) == 4
    assert block.confidence == pytest.approx(0.95)
    assert block.geometry_source == GeometrySource.OCR


def test_page_detail_returns_none_for_missing_page(session: Session) -> None:
    document_id = _seed_readable_pdf(session)
    service = DocumentReviewService(session)

    assert service.get_page_detail(document_id, 999) is None


def test_document_review_returns_none_for_missing_doc(session: Session) -> None:
    service = DocumentReviewService(session)
    assert service.get_document_review("nonexistent") is None


def test_page_image_path_validates_existence(session: Session, tmp_path: Path) -> None:
    """Page image path returns None when the file does not exist."""
    document_id = _seed_ocr_document(session)
    service = DocumentReviewService(session)

    # The path references a file that does not exist on disk
    path = service.get_page_image_path(document_id, 1)
    assert path is None


def test_page_review_summary_text_preview(session: Session) -> None:
    document_id = _seed_readable_pdf(session)
    service = DocumentReviewService(session)

    review = service.get_document_review(document_id)
    assert review is not None
    assert review.pages[0].text_preview == "Hello world"


def test_document_review_capabilities_report_limitations(session: Session) -> None:
    document_id = _seed_readable_pdf(session)
    service = DocumentReviewService(session)

    review = service.get_document_review(document_id)
    assert review is not None
    assert any("Page images" in l for l in review.capabilities.limitations)


def test_ingestion_service_persists_page_records(session: Session) -> None:
    """Verify that the ingestion service's page persistence path works."""
    from app.ingestion.registry import DocumentRegistryService

    registry = DocumentRegistryService(session)

    records = [
        PageRecord(
            page_id="test-doc:1",
            document_id="test-doc",
            page_number=1,
            width=100.0,
            height=200.0,
            coordinate_space="pdf_points",
            geometry_source="pdf_text",
            text="test content",
            text_blocks_json=[],
            has_page_image=False,
        )
    ]
    registry.persist_page_records(records)

    from sqlmodel import select

    result = session.exec(
        select(PageRecord).where(PageRecord.document_id == "test-doc")
    ).all()
    assert len(result) == 1
    assert result[0].text == "test content"
