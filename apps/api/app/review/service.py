"""Read-side service for the document review surface."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from casegraph_agent_sdk.ingestion import (
    CoordinateSpace,
    DocumentProcessingStatus,
    GeometrySource,
    IngestionMode,
    IngestionModePreference,
    SourceFileMetadata,
    TextBlockArtifact,
)
from casegraph_agent_sdk.review import (
    DocumentPageListResponse,
    DocumentReviewCapability,
    DocumentReviewResponse,
    DocumentReviewSummary,
    OverlaySourceType,
    PageDimensions,
    PageReviewDetail,
    PageReviewSummary,
    geometry_source_to_overlay_type,
)

from app.cases.models import CaseDocumentLinkModel
from app.config import settings
from app.ingestion.models import DocumentRecord
from app.review.models import PageRecord

_TEXT_PREVIEW_LENGTH = 200


class DocumentReviewService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_document(self, document_id: str) -> DocumentReviewResponse | None:
        return self.get_document_review(document_id)

    def get_document_review(self, document_id: str) -> DocumentReviewResponse | None:
        doc = self._session.get(DocumentRecord, document_id)
        if doc is None:
            return None

        page_records = self._get_page_records(document_id)
        linked_case_ids = self._get_linked_case_ids(document_id)
        geometry_sources = [GeometrySource(s) for s in doc.geometry_sources_json]
        page_images_available = any(pr.has_page_image for pr in page_records)

        summary = DocumentReviewSummary(
            document_id=doc.document_id,
            source_file=SourceFileMetadata(
                filename=doc.filename,
                content_type=doc.content_type,
                extension=doc.extension,
                size_bytes=doc.size_bytes,
                sha256=doc.sha256,
                classification=doc.classification,
            ),
            status=DocumentProcessingStatus(doc.processing_status),
            ingestion_mode=IngestionMode(doc.resolved_mode),
            extractor_name=doc.extractor_name,
            page_count=doc.page_count,
            text_block_count=doc.text_block_count,
            geometry_available=doc.geometry_present,
            geometry_sources=geometry_sources,
            page_images_available=page_images_available,
            linked_case_ids=linked_case_ids,
        )

        pages = [self._page_record_to_summary(pr) for pr in page_records]

        overlay_types: list[OverlaySourceType] = [
            geometry_source_to_overlay_type(gs) for gs in geometry_sources
        ]

        limitations: list[str] = []
        if not page_images_available:
            limitations.append(
                "Page images are not available for this document. "
                "Only text and metadata inspection is possible."
            )
        if not doc.geometry_present:
            limitations.append(
                "No bounding-box or polygon geometry was produced during ingestion. "
                "Overlay rendering is not available."
            )

        capabilities = DocumentReviewCapability(
            can_show_pages=doc.page_count > 0,
            can_show_geometry=doc.geometry_present,
            can_show_page_images=page_images_available,
            overlay_source_types=overlay_types,
            limitations=limitations,
        )

        return DocumentReviewResponse(
            document=summary,
            pages=pages,
            capabilities=capabilities,
        )

    def list_document_pages(
        self,
        document_id: str,
    ) -> DocumentPageListResponse | None:
        doc = self._session.get(DocumentRecord, document_id)
        if doc is None:
            return None

        page_records = self._get_page_records(document_id)
        return DocumentPageListResponse(
            document_id=document_id,
            pages=[self._page_record_to_summary(record) for record in page_records],
        )

    def get_page_detail(
        self, document_id: str, page_number: int
    ) -> PageReviewDetail | None:
        record = self._get_page_record(document_id, page_number)
        if record is None:
            return None
        return self._page_record_to_detail(record)

    def get_page_image_path(
        self, document_id: str, page_number: int
    ) -> Path | None:
        record = self._get_page_record(document_id, page_number)
        if record is None or not record.has_page_image or not record.page_image_path:
            return None

        artifacts_base = Path(settings.artifacts_dir).resolve()
        full_path = (artifacts_base / record.page_image_path).resolve()

        if not full_path.is_relative_to(artifacts_base):
            return None
        if not full_path.exists():
            return None
        return full_path

    def _get_page_records(self, document_id: str) -> list[PageRecord]:
        statement = (
            select(PageRecord)
            .where(PageRecord.document_id == document_id)
            .order_by(PageRecord.page_number)
        )
        return list(self._session.exec(statement).all())

    def _get_page_record(
        self, document_id: str, page_number: int
    ) -> PageRecord | None:
        statement = (
            select(PageRecord)
            .where(PageRecord.document_id == document_id)
            .where(PageRecord.page_number == page_number)
        )
        return self._session.exec(statement).first()

    def _get_linked_case_ids(self, document_id: str) -> list[str]:
        statement = select(CaseDocumentLinkModel.case_id).where(
            CaseDocumentLinkModel.document_id == document_id
        )
        return list(self._session.exec(statement).all())

    def _page_record_to_summary(self, record: PageRecord) -> PageReviewSummary:
        text_preview = record.text[:_TEXT_PREVIEW_LENGTH]
        if len(record.text) > _TEXT_PREVIEW_LENGTH:
            text_preview += "..."

        return PageReviewSummary(
            page_number=record.page_number,
            dimensions=PageDimensions(
                width=record.width,
                height=record.height,
                coordinate_space=(
                    CoordinateSpace(record.coordinate_space)
                    if record.coordinate_space
                    else None
                ),
            ),
            geometry_source=(
                GeometrySource(record.geometry_source)
                if record.geometry_source
                else None
            ),
            text_block_count=len(record.text_blocks_json),
            has_geometry=any(
                b.get("bbox") is not None or b.get("polygon") is not None
                for b in record.text_blocks_json
            ),
            has_page_image=record.has_page_image,
            text_preview=text_preview,
        )

    def _page_record_to_detail(self, record: PageRecord) -> PageReviewDetail:
        text_blocks = [
            TextBlockArtifact.model_validate(block)
            for block in record.text_blocks_json
        ]

        return PageReviewDetail(
            page_number=record.page_number,
            dimensions=PageDimensions(
                width=record.width,
                height=record.height,
                coordinate_space=(
                    CoordinateSpace(record.coordinate_space)
                    if record.coordinate_space
                    else None
                ),
            ),
            text=record.text,
            geometry_source=(
                GeometrySource(record.geometry_source)
                if record.geometry_source
                else None
            ),
            text_blocks=text_blocks,
            has_page_image=record.has_page_image,
        )
