"""Persistence-backed registry of ingested document summaries."""

from __future__ import annotations

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.ingestion import (
    DocumentProcessingStatus,
    GeometrySource,
    IngestionMode,
    IngestionModePreference,
    IngestionResultSummary,
    NormalizedExtractionOutput,
    SourceFileMetadata,
)

from app.ingestion.models import DocumentRecord
from app.persistence.database import utcnow
from app.review.models import PageRecord


class DocumentRegistryService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record_summary(
        self,
        summary: IngestionResultSummary,
        *,
        extraction_output: NormalizedExtractionOutput | None = None,
        source_file_path: str | None = None,
    ) -> IngestionResultSummary:
        existing = self._session.get(DocumentRecord, summary.document_id)
        created_at = existing.created_at if existing is not None else None

        record = DocumentRecord(
            document_id=summary.document_id,
            filename=summary.source_file.filename,
            content_type=summary.source_file.content_type,
            extension=summary.source_file.extension,
            size_bytes=summary.source_file.size_bytes,
            sha256=summary.source_file.sha256,
            classification=summary.source_file.classification.value,
            requested_mode=summary.requested_mode.value,
            resolved_mode=summary.resolved_mode.value,
            processing_status=summary.status.value,
            extractor_name=summary.extractor_name,
            page_count=summary.page_count,
            text_block_count=summary.text_block_count,
            geometry_present=summary.geometry_present,
            geometry_sources_json=[item.value for item in summary.geometry_sources],
            source_file_path=source_file_path,
            extraction_output_json=(
                extraction_output.model_dump(mode="json")
                if extraction_output is not None
                else None
            ),
            created_at=created_at or utcnow(),
        )
        self._session.merge(record)
        self._session.commit()
        persisted = self._session.get(DocumentRecord, summary.document_id)
        assert persisted is not None
        return self._to_summary(persisted)

    def list_documents(
        self,
        *,
        status: DocumentProcessingStatus | None = None,
        limit: int = 100,
    ) -> list[IngestionResultSummary]:
        statement = select(DocumentRecord).order_by(desc(DocumentRecord.created_at)).limit(limit)
        if status is not None:
            statement = statement.where(DocumentRecord.processing_status == status.value)
        rows = self._session.exec(statement).all()
        return [self._to_summary(row) for row in rows]

    def get_document(self, document_id: str) -> IngestionResultSummary | None:
        record = self._session.get(DocumentRecord, document_id)
        if record is None:
            return None
        return self._to_summary(record)

    def persist_page_records(self, records: list[PageRecord]) -> None:
        for record in records:
            self._session.merge(record)
        self._session.commit()

    def get_document_output(
        self, document_id: str
    ) -> NormalizedExtractionOutput | None:
        """Return the stored NormalizedExtractionOutput for a document, or None."""
        record = self._session.get(DocumentRecord, document_id)
        if record is None or record.extraction_output_json is None:
            return None
        return NormalizedExtractionOutput.model_validate(record.extraction_output_json)

    def get_page_records(self, document_id: str) -> list[PageRecord]:
        """Return all PageRecord rows for a document, ordered by page number."""
        statement = (
            select(PageRecord)
            .where(PageRecord.document_id == document_id)
            .order_by(PageRecord.page_number)
        )
        return list(self._session.exec(statement).all())

    def get_source_file_path(self, document_id: str) -> str | None:
        """Return the artifact-relative path to the persisted source file."""
        record = self._session.get(DocumentRecord, document_id)
        if record is None:
            return None
        return record.source_file_path

    def _to_summary(self, record: DocumentRecord) -> IngestionResultSummary:
        return IngestionResultSummary(
            document_id=record.document_id,
            source_file=SourceFileMetadata(
                filename=record.filename,
                content_type=record.content_type,
                extension=record.extension,
                size_bytes=record.size_bytes,
                sha256=record.sha256,
                classification=record.classification,
            ),
            status=DocumentProcessingStatus(record.processing_status),
            requested_mode=IngestionModePreference(record.requested_mode),
            resolved_mode=IngestionMode(record.resolved_mode),
            extractor_name=record.extractor_name,
            page_count=record.page_count,
            text_block_count=record.text_block_count,
            geometry_present=record.geometry_present,
            geometry_sources=[GeometrySource(item) for item in record.geometry_sources_json],
        )