"""Annotation service — CRUD operations for document annotations."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlmodel import Session, select

from casegraph_agent_sdk.annotations import (
    AnnotationAnchor,
    AnnotationBody,
    AnnotationListResponse,
    AnnotationRecord,
    CreateAnnotationRequest,
    PageAnnotationListResponse,
    PageWordsResponse,
    UpdateAnnotationRequest,
    WordArtifact,
)
from casegraph_agent_sdk.ingestion import (
    BoundingBoxArtifact,
    CoordinateSpace,
)

from app.ingestion.models import DocumentRecord
from app.persistence.database import isoformat_utc, utcnow
from app.review.annotation_models import AnnotationModel
from app.review.models import PageRecord


class AnnotationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_annotation(
        self, request: CreateAnnotationRequest,
    ) -> AnnotationRecord | None:
        doc = self._session.get(DocumentRecord, request.document_id)
        if doc is None:
            return None

        now = utcnow()
        annotation_id = f"ann-{uuid.uuid4().hex[:12]}"

        model = AnnotationModel(
            annotation_id=annotation_id,
            document_id=request.document_id,
            page_number=request.anchor.page_number,
            annotation_type=request.annotation_type,
            status="active",
            anchor_json=request.anchor.model_dump(mode="json"),
            body_json=request.body.model_dump(mode="json"),
            created_by=request.created_by,
            created_at=now,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_record(model)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_annotation(self, annotation_id: str) -> AnnotationRecord | None:
        model = self._session.get(AnnotationModel, annotation_id)
        if model is None or model.status == "deleted":
            return None
        return self._to_record(model)

    def list_document_annotations(
        self, document_id: str,
    ) -> AnnotationListResponse | None:
        doc = self._session.get(DocumentRecord, document_id)
        if doc is None:
            return None

        stmt = (
            select(AnnotationModel)
            .where(AnnotationModel.document_id == document_id)
            .where(AnnotationModel.status != "deleted")
            .order_by(AnnotationModel.page_number, AnnotationModel.created_at)
        )
        models = list(self._session.exec(stmt).all())
        return AnnotationListResponse(
            document_id=document_id,
            annotations=[self._to_record(m) for m in models],
            total_count=len(models),
        )

    def list_page_annotations(
        self, document_id: str, page_number: int,
    ) -> PageAnnotationListResponse | None:
        doc = self._session.get(DocumentRecord, document_id)
        if doc is None:
            return None

        stmt = (
            select(AnnotationModel)
            .where(AnnotationModel.document_id == document_id)
            .where(AnnotationModel.page_number == page_number)
            .where(AnnotationModel.status != "deleted")
            .order_by(AnnotationModel.created_at)
        )
        models = list(self._session.exec(stmt).all())
        return PageAnnotationListResponse(
            document_id=document_id,
            page_number=page_number,
            annotations=[self._to_record(m) for m in models],
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_annotation(
        self, annotation_id: str, request: UpdateAnnotationRequest,
    ) -> AnnotationRecord | None:
        model = self._session.get(AnnotationModel, annotation_id)
        if model is None or model.status == "deleted":
            return None

        if request.annotation_type is not None:
            model.annotation_type = request.annotation_type
        if request.body is not None:
            model.body_json = request.body.model_dump(mode="json")
        if request.status is not None:
            model.status = request.status
        model.updated_at = utcnow()

        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_record(model)

    # ------------------------------------------------------------------
    # Delete (soft)
    # ------------------------------------------------------------------

    def delete_annotation(self, annotation_id: str) -> bool:
        model = self._session.get(AnnotationModel, annotation_id)
        if model is None or model.status == "deleted":
            return False
        model.status = "deleted"
        model.updated_at = utcnow()
        self._session.add(model)
        self._session.commit()
        return True

    # ------------------------------------------------------------------
    # Word-level extraction
    # ------------------------------------------------------------------

    def get_page_words(
        self, document_id: str, page_number: int,
    ) -> PageWordsResponse | None:
        """Extract word-level bounding boxes from a page.

        For readable PDFs, uses PyMuPDF get_text("words") for precise
        word geometry.  For OCR pages, falls back to the stored text
        blocks (block-level granularity).
        """
        doc = self._session.get(DocumentRecord, document_id)
        if doc is None:
            return None

        page_record = self._session.exec(
            select(PageRecord)
            .where(PageRecord.document_id == document_id)
            .where(PageRecord.page_number == page_number)
        ).first()
        if page_record is None:
            return None

        # Try PyMuPDF word extraction from source file
        if doc.resolved_mode == "readable_pdf" and doc.source_file_path:
            words = self._extract_words_pymupdf(doc, page_number)
            if words is not None:
                return PageWordsResponse(
                    document_id=document_id,
                    page_number=page_number,
                    coordinate_space=CoordinateSpace.PDF_POINTS,
                    words=words,
                    word_count=len(words),
                )

        # Fallback: synthesize word artifacts from stored text blocks
        words = self._words_from_text_blocks(page_record)
        coord = (
            CoordinateSpace(page_record.coordinate_space)
            if page_record.coordinate_space
            else None
        )
        return PageWordsResponse(
            document_id=document_id,
            page_number=page_number,
            coordinate_space=coord,
            words=words,
            word_count=len(words),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _extract_words_pymupdf(
        self, doc: DocumentRecord, page_number: int,
    ) -> list[WordArtifact] | None:
        """Use PyMuPDF to extract word-level geometry from the source PDF."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return None

        from app.config import settings

        artifacts_base = Path(settings.artifacts_dir).resolve()
        source_path = (artifacts_base / doc.source_file_path).resolve()
        if not source_path.is_relative_to(artifacts_base) or not source_path.exists():
            return None

        try:
            pdf = fitz.open(str(source_path))
        except Exception:
            return None

        if page_number < 1 or page_number > len(pdf):
            pdf.close()
            return None

        page = pdf[page_number - 1]  # 0-indexed
        raw_words = page.get_text("words", sort=True)
        pdf.close()

        words: list[WordArtifact] = []
        for w in raw_words:
            # PyMuPDF word tuple: (x0, y0, x1, y1, text, block_no, line_no, word_no)
            x0, y0, x1, y1, text, block_no, line_no, word_no = w[:8]
            words.append(
                WordArtifact(
                    text=str(text),
                    bbox=BoundingBoxArtifact(
                        x0=float(x0),
                        y0=float(y0),
                        x1=float(x1),
                        y1=float(y1),
                        coordinate_space=CoordinateSpace.PDF_POINTS,
                    ),
                    block_number=int(block_no),
                    line_number=int(line_no),
                    word_number=int(word_no),
                    confidence=None,
                )
            )
        return words

    def _words_from_text_blocks(
        self, page_record: PageRecord,
    ) -> list[WordArtifact]:
        """Synthesize word-level artifacts from stored text blocks.

        This is a fallback for OCR pages where we don't have the source
        file or can't re-extract.  Each text block becomes one WordArtifact.
        """
        words: list[WordArtifact] = []
        for block in page_record.text_blocks_json:
            bbox_raw = block.get("bbox")
            if bbox_raw is None:
                continue
            words.append(
                WordArtifact(
                    text=block.get("text", ""),
                    bbox=BoundingBoxArtifact.model_validate(bbox_raw),
                    block_number=None,
                    line_number=None,
                    word_number=None,
                    confidence=block.get("confidence"),
                )
            )
        return words

    def _to_record(self, model: AnnotationModel) -> AnnotationRecord:
        return AnnotationRecord(
            annotation_id=model.annotation_id,
            document_id=model.document_id,
            annotation_type=model.annotation_type,
            status=model.status,
            anchor=AnnotationAnchor.model_validate(model.anchor_json),
            body=AnnotationBody.model_validate(model.body_json),
            created_by=model.created_by,
            created_at=isoformat_utc(model.created_at),
            updated_at=isoformat_utc(model.updated_at) if model.updated_at else None,
        )
