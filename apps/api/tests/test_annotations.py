"""Tests for the annotation service and word-level extraction."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from casegraph_agent_sdk.annotations import (
    AnnotationAnchor,
    AnnotationBody,
    CreateAnnotationRequest,
    UpdateAnnotationRequest,
    WordArtifact,
)
from casegraph_agent_sdk.ingestion import BoundingBoxArtifact, CoordinateSpace

from app.ingestion.models import DocumentRecord
from app.review.annotation_models import AnnotationModel
from app.review.annotation_service import AnnotationService
from app.review.models import PageRecord


def _seed_document(session: Session) -> str:
    doc_id = "doc-ann-001"
    session.add(
        DocumentRecord(
            document_id=doc_id,
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
            page_id=f"{doc_id}:1",
            document_id=doc_id,
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
        )
    )
    session.add(
        PageRecord(
            page_id=f"{doc_id}:2",
            document_id=doc_id,
            page_number=2,
            width=612.0,
            height=792.0,
            coordinate_space="pdf_points",
            geometry_source="pdf_text",
            text="Page two",
            text_blocks_json=[
                {
                    "block_id": "page-2-block-1",
                    "page_number": 2,
                    "text": "Page two",
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
    return doc_id


def _make_anchor(page: int = 1) -> AnnotationAnchor:
    return AnnotationAnchor(
        page_number=page,
        bbox=BoundingBoxArtifact(
            x0=72.0,
            y0=72.0,
            x1=200.0,
            y1=90.0,
            coordinate_space=CoordinateSpace.PDF_POINTS,
        ),
        block_id="page-1-block-1",
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateAnnotation:
    def test_create_highlight(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        result = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id,
            annotation_type="highlight",
            anchor=_make_anchor(),
        ))
        assert result is not None
        assert result.annotation_type == "highlight"
        assert result.status == "active"
        assert result.document_id == doc_id
        assert result.anchor.page_number == 1
        assert result.annotation_id.startswith("ann-")

    def test_create_comment_with_body(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        result = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id,
            annotation_type="comment",
            anchor=_make_anchor(),
            body=AnnotationBody(text="Important note"),
        ))
        assert result is not None
        assert result.body.text == "Important note"

    def test_create_correction(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        result = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id,
            annotation_type="correction",
            anchor=_make_anchor(),
            body=AnnotationBody(text="Corrected text", original_text="Hello"),
        ))
        assert result is not None
        assert result.annotation_type == "correction"
        assert result.body.original_text == "Hello"

    def test_create_flag(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        result = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id,
            annotation_type="flag",
            anchor=_make_anchor(),
            body=AnnotationBody(text="Low confidence OCR region"),
        ))
        assert result is not None
        assert result.annotation_type == "flag"

    def test_create_redaction(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        result = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id,
            annotation_type="redaction",
            anchor=_make_anchor(),
            body=AnnotationBody(text="PII detected"),
        ))
        assert result is not None
        assert result.annotation_type == "redaction"

    def test_create_returns_none_for_missing_document(self, session: Session) -> None:
        svc = AnnotationService(session)
        result = svc.create_annotation(CreateAnnotationRequest(
            document_id="nonexistent",
            annotation_type="highlight",
            anchor=_make_anchor(),
        ))
        assert result is None

    def test_create_sets_created_by(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        result = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id,
            annotation_type="highlight",
            anchor=_make_anchor(),
            created_by="reviewer-1",
        ))
        assert result is not None
        assert result.created_by == "reviewer-1"


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


class TestReadAnnotation:
    def test_get_annotation_by_id(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        created = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id,
            annotation_type="comment",
            anchor=_make_anchor(),
            body=AnnotationBody(text="test"),
        ))
        assert created is not None
        fetched = svc.get_annotation(created.annotation_id)
        assert fetched is not None
        assert fetched.annotation_id == created.annotation_id

    def test_get_returns_none_for_missing(self, session: Session) -> None:
        svc = AnnotationService(session)
        assert svc.get_annotation("nonexistent") is None

    def test_list_document_annotations(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        for i in range(3):
            svc.create_annotation(CreateAnnotationRequest(
                document_id=doc_id,
                annotation_type="highlight",
                anchor=_make_anchor(page=1 if i < 2 else 2),
            ))
        result = svc.list_document_annotations(doc_id)
        assert result is not None
        assert result.total_count == 3
        assert len(result.annotations) == 3

    def test_list_returns_none_for_missing_doc(self, session: Session) -> None:
        svc = AnnotationService(session)
        assert svc.list_document_annotations("nonexistent") is None

    def test_list_page_annotations_filters_by_page(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id, annotation_type="highlight", anchor=_make_anchor(1),
        ))
        svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id, annotation_type="comment", anchor=_make_anchor(2),
        ))
        page1 = svc.list_page_annotations(doc_id, 1)
        assert page1 is not None
        assert len(page1.annotations) == 1
        assert page1.annotations[0].anchor.page_number == 1

        page2 = svc.list_page_annotations(doc_id, 2)
        assert page2 is not None
        assert len(page2.annotations) == 1
        assert page2.annotations[0].anchor.page_number == 2

    def test_list_excludes_deleted_annotations(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        created = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id, annotation_type="highlight", anchor=_make_anchor(),
        ))
        assert created is not None
        svc.delete_annotation(created.annotation_id)
        result = svc.list_document_annotations(doc_id)
        assert result is not None
        assert result.total_count == 0


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdateAnnotation:
    def test_update_annotation_type(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        created = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id, annotation_type="highlight", anchor=_make_anchor(),
        ))
        assert created is not None
        updated = svc.update_annotation(
            created.annotation_id,
            UpdateAnnotationRequest(annotation_type="flag"),
        )
        assert updated is not None
        assert updated.annotation_type == "flag"
        assert updated.updated_at is not None

    def test_update_body(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        created = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id, annotation_type="comment", anchor=_make_anchor(),
            body=AnnotationBody(text="original"),
        ))
        assert created is not None
        updated = svc.update_annotation(
            created.annotation_id,
            UpdateAnnotationRequest(body=AnnotationBody(text="revised")),
        )
        assert updated is not None
        assert updated.body.text == "revised"

    def test_update_status_to_resolved(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        created = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id, annotation_type="flag", anchor=_make_anchor(),
        ))
        assert created is not None
        updated = svc.update_annotation(
            created.annotation_id,
            UpdateAnnotationRequest(status="resolved"),
        )
        assert updated is not None
        assert updated.status == "resolved"

    def test_update_returns_none_for_missing(self, session: Session) -> None:
        svc = AnnotationService(session)
        assert svc.update_annotation(
            "nonexistent", UpdateAnnotationRequest(status="resolved"),
        ) is None

    def test_update_returns_none_for_deleted(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        created = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id, annotation_type="highlight", anchor=_make_anchor(),
        ))
        assert created is not None
        svc.delete_annotation(created.annotation_id)
        assert svc.update_annotation(
            created.annotation_id, UpdateAnnotationRequest(status="resolved"),
        ) is None


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteAnnotation:
    def test_soft_delete(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        created = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id, annotation_type="highlight", anchor=_make_anchor(),
        ))
        assert created is not None
        assert svc.delete_annotation(created.annotation_id) is True
        assert svc.get_annotation(created.annotation_id) is None

    def test_delete_returns_false_for_missing(self, session: Session) -> None:
        svc = AnnotationService(session)
        assert svc.delete_annotation("nonexistent") is False

    def test_double_delete_returns_false(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        created = svc.create_annotation(CreateAnnotationRequest(
            document_id=doc_id, annotation_type="highlight", anchor=_make_anchor(),
        ))
        assert created is not None
        assert svc.delete_annotation(created.annotation_id) is True
        assert svc.delete_annotation(created.annotation_id) is False


# ---------------------------------------------------------------------------
# Word-level extraction
# ---------------------------------------------------------------------------


class TestWordLevelExtraction:
    def test_words_from_text_blocks_fallback(self, session: Session) -> None:
        """Without source file, words are synthesized from text blocks."""
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        result = svc.get_page_words(doc_id, 1)
        assert result is not None
        assert result.document_id == doc_id
        assert result.page_number == 1
        assert result.word_count == 2  # Two text blocks
        assert result.words[0].text == "Hello"
        assert result.words[0].bbox.coordinate_space == CoordinateSpace.PDF_POINTS
        assert result.words[1].text == "world"

    def test_words_returns_none_for_missing_doc(self, session: Session) -> None:
        svc = AnnotationService(session)
        assert svc.get_page_words("nonexistent", 1) is None

    def test_words_returns_none_for_missing_page(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        assert svc.get_page_words(doc_id, 999) is None

    def test_words_page2_single_block(self, session: Session) -> None:
        doc_id = _seed_document(session)
        svc = AnnotationService(session)
        result = svc.get_page_words(doc_id, 2)
        assert result is not None
        assert result.word_count == 1
        assert result.words[0].text == "Page two"


# ---------------------------------------------------------------------------
# Router integration (via TestClient)
# ---------------------------------------------------------------------------


class TestAnnotationRouter:
    """Integration tests using the full app TestClient."""

    def test_create_annotation_missing_doc(self, client) -> None:
        response = client.post(
            "/documents/test-doc/annotations",
            json={
                "document_id": "test-doc",
                "annotation_type": "highlight",
                "anchor": {
                    "page_number": 1,
                    "bbox": {
                        "x0": 10, "y0": 20, "x1": 100, "y1": 40,
                        "coordinate_space": "pdf_points",
                    },
                    "block_id": None,
                },
            },
        )
        # Document doesn't exist in the test DB, expect 404
        assert response.status_code == 404

    def test_list_annotations_missing_doc(self, client) -> None:
        response = client.get("/documents/nonexistent/annotations")
        assert response.status_code == 404

    def test_get_annotation_missing(self, client) -> None:
        response = client.get("/annotations/nonexistent")
        assert response.status_code == 404

    def test_delete_annotation_missing(self, client) -> None:
        response = client.delete("/annotations/nonexistent")
        assert response.status_code == 404

    def test_document_id_mismatch_rejected(self, client) -> None:
        response = client.post(
            "/documents/doc-1/annotations",
            json={
                "document_id": "doc-2",
                "annotation_type": "highlight",
                "anchor": {
                    "page_number": 1,
                    "bbox": {
                        "x0": 10, "y0": 20, "x1": 100, "y1": 40,
                        "coordinate_space": "pdf_points",
                    },
                    "block_id": None,
                },
            },
        )
        assert response.status_code == 400

    def test_full_annotation_lifecycle(self, client, session) -> None:
        """Create, read, update, delete annotation via HTTP."""
        # Seed document
        session.add(DocumentRecord(
            document_id="doc-lifecycle",
            filename="test.pdf",
            content_type="application/pdf",
            extension=".pdf",
            size_bytes=1024,
            sha256="abc",
            classification="pdf",
            requested_mode="auto",
            resolved_mode="readable_pdf",
            processing_status="completed",
            page_count=1,
            text_block_count=0,
            geometry_present=False,
            geometry_sources_json=[],
        ))
        session.commit()

        # Create
        resp = client.post(
            "/documents/doc-lifecycle/annotations",
            json={
                "document_id": "doc-lifecycle",
                "annotation_type": "comment",
                "anchor": {
                    "page_number": 1,
                    "bbox": {"x0": 10, "y0": 20, "x1": 100, "y1": 40, "coordinate_space": "pdf_points"},
                    "block_id": None,
                },
                "body": {"text": "initial note", "original_text": None},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        ann_id = data["annotation_id"]
        assert data["annotation_type"] == "comment"

        # Read
        resp = client.get(f"/annotations/{ann_id}")
        assert resp.status_code == 200
        assert resp.json()["body"]["text"] == "initial note"

        # List
        resp = client.get("/documents/doc-lifecycle/annotations")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 1

        # Update
        resp = client.patch(
            f"/annotations/{ann_id}",
            json={"body": {"text": "revised note", "original_text": None}},
        )
        assert resp.status_code == 200
        assert resp.json()["body"]["text"] == "revised note"

        # Delete
        resp = client.delete(f"/annotations/{ann_id}")
        assert resp.status_code == 204

        # Verify deleted
        resp = client.get(f"/annotations/{ann_id}")
        assert resp.status_code == 404
