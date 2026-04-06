"""Extraction service — orchestrates schema-driven extraction over documents.

Supports two extraction strategies:
- provider_structured: uses BYOK provider structured output via TaskExecutionService
- langextract_grounded: uses the LangExtract library for grounded extraction (optional)
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import ChangeSummary, FieldChangeRecord
from casegraph_agent_sdk.extraction import (
    DocumentExtractionListResponse,
    ExtractedFieldResult,
    ExtractionError,
    ExtractionEvent,
    ExtractionEventKind,
    ExtractionRequest,
    ExtractionResult,
    ExtractionRunMetadata,
    ExtractionStrategy,
)
from casegraph_agent_sdk.tasks import (
    ProviderSelection,
    StructuredOutputSchema,
)

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel
from app.audit.service import AuditTrailService, audit_actor, derived_ref, entity_ref, source_ref
from app.extraction.grounding import GroundingService
from app.extraction.models import ExtractionRunModel
from app.extraction.registry import ExtractionTemplate, extraction_template_registry
from app.ingestion.models import DocumentRecord
from app.review.models import PageRecord
from app.tasks.service import TaskExecutionService, TaskExecutionServiceError

# LangExtract is represented in the contracts and API surface, but the runtime
# adapter is intentionally not enabled in this build until a tested, schema-
# driven integration is added. Keep backend capability reporting honest.
_LANGEXTRACT_SCAFFOLDED_MESSAGE = (
    "LangExtract strategy is scaffolded in this build and is not executable yet. "
    "Only provider_structured extraction is currently available."
)


def langextract_available() -> bool:
    return False


class ExtractionServiceError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code

from app.persistence.database import isoformat_utc, utcnow


def _event(kind: ExtractionEventKind, **metadata: Any) -> ExtractionEvent:
    return ExtractionEvent(kind=kind, timestamp=isoformat_utc(utcnow()), metadata=metadata)


class ExtractionService:
    """Executes schema-driven extraction against documents."""

    def __init__(
        self,
        session: Session,
        *,
        task_execution_service: TaskExecutionService | None = None,
    ) -> None:
        self._session = session
        self._task_service = task_execution_service or TaskExecutionService()
        self._grounding = GroundingService(session)

    async def execute(self, request: ExtractionRequest) -> ExtractionResult:
        """Run a full extraction pipeline: resolve → extract → ground → persist."""
        extraction_id = str(uuid4())
        events: list[ExtractionEvent] = []
        events.append(_event(ExtractionEventKind.EXTRACTION_STARTED, extraction_id=extraction_id))

        # --- Resolve template ---
        template = extraction_template_registry.get(request.template_id)
        if template is None:
            raise ExtractionServiceError(
                f"Extraction template '{request.template_id}' not found.",
                status_code=404,
            )

        # --- Resolve document ---
        doc = self._session.get(DocumentRecord, request.document_id)
        if doc is None:
            raise ExtractionServiceError(
                f"Document '{request.document_id}' not found.",
                status_code=404,
            )

        self._validate_case_context(request.case_id, request.document_id)

        # --- Collect document text from page records ---
        document_text = self._collect_document_text(request.document_id)
        if not document_text.strip():
            return self._build_error_result(
                extraction_id=extraction_id,
                request=request,
                template=template,
                events=events,
                error_code="no_document_text",
                message="No extracted text available for this document.",
            )

        # --- Resolve strategy ---
        strategy = self._resolve_strategy(request.strategy, template, request)
        events.append(_event(
            ExtractionEventKind.STRATEGY_SELECTED,
            strategy=strategy,
            template_id=request.template_id,
        ))

        start_ms = time.monotonic_ns() // 1_000_000

        # --- Execute extraction ---
        try:
            if strategy == "provider_structured":
                fields, strategy_events = await self._extract_provider_structured(
                    request, template, document_text, extraction_id,
                )
            elif strategy == "langextract_grounded":
                fields, strategy_events = await self._extract_langextract(
                    request, template, document_text, extraction_id,
                )
            else:
                raise ExtractionServiceError(f"Unknown strategy: {strategy}")

            events.extend(strategy_events)

        except TaskExecutionServiceError as exc:
            return self._build_error_result(
                extraction_id=extraction_id,
                request=request,
                template=template,
                events=events,
                strategy_used=strategy,
                error_code="provider_error",
                message=exc.detail,
            )
        except Exception as exc:
            return self._build_error_result(
                extraction_id=extraction_id,
                request=request,
                template=template,
                events=events,
                strategy_used=strategy,
                error_code="extraction_error",
                message=f"Extraction failed: {exc}",
            )

        duration_ms = (time.monotonic_ns() // 1_000_000) - start_ms

        # --- Attach grounding ---
        grounding_attached = False
        try:
            fields = self._grounding.attach_grounding(request.document_id, fields)
            grounding_attached = any(len(f.grounding) > 0 for f in fields)
            if grounding_attached:
                events.append(_event(
                    ExtractionEventKind.GROUNDING_ATTACHED,
                    fields_with_grounding=sum(1 for f in fields if f.grounding),
                ))
        except Exception:
            pass  # Grounding is best-effort — don't fail the extraction

        events.append(_event(
            ExtractionEventKind.EXTRACTION_COMPLETED,
            extraction_id=extraction_id,
            fields_extracted=sum(1 for f in fields if f.is_present),
            duration_ms=duration_ms,
        ))

        fields_extracted = sum(1 for f in fields if f.is_present)
        run = ExtractionRunMetadata(
            extraction_id=extraction_id,
            document_id=request.document_id,
            template_id=request.template_id,
            case_id=request.case_id,
            strategy_used=strategy,
            provider=request.provider,
            model_id=request.model_id,
            status="completed",
            duration_ms=duration_ms,
            field_count=len(template.schema_definition.fields),
            fields_extracted=fields_extracted,
            grounding_available=grounding_attached,
        )

        result = ExtractionResult(
            run=run,
            fields=fields,
            events=events,
        )

        self._persist_result(result)
        return result

    def get_extraction(self, extraction_id: str) -> ExtractionResult | None:
        """Load a persisted extraction result."""
        record = self._session.get(ExtractionRunModel, extraction_id)
        if record is None:
            return None
        return self._record_to_result(record)

    def list_document_extractions(
        self, document_id: str
    ) -> DocumentExtractionListResponse:
        """List extraction runs for a document."""
        if self._session.get(DocumentRecord, document_id) is None:
            raise ExtractionServiceError(
                f"Document '{document_id}' not found.",
                status_code=404,
            )

        statement = (
            select(ExtractionRunModel)
            .where(ExtractionRunModel.document_id == document_id)
            .order_by(desc(ExtractionRunModel.created_at))
        )
        records = list(self._session.exec(statement).all())
        return DocumentExtractionListResponse(
            document_id=document_id,
            extractions=[self._record_to_run_metadata(r) for r in records],
        )

    # ------------------------------------------------------------------
    # Provider-backed structured extraction
    # ------------------------------------------------------------------

    async def _extract_provider_structured(
        self,
        request: ExtractionRequest,
        template: ExtractionTemplate,
        document_text: str,
        extraction_id: str,
    ) -> tuple[list[ExtractedFieldResult], list[ExtractionEvent]]:
        """Extract using provider-backed structured output."""
        events: list[ExtractionEvent] = []

        if not request.provider or not request.model_id or not request.api_key:
            raise ExtractionServiceError(
                "Provider, model_id, and api_key are required for provider_structured strategy.",
                status_code=400,
            )

        events.append(_event(
            ExtractionEventKind.PROVIDER_RESOLVED,
            provider=request.provider,
            model_id=request.model_id,
        ))

        # Build JSON Schema from template
        json_schema = template.schema_definition.to_json_schema()
        structured_output = StructuredOutputSchema(
            json_schema=json_schema,
            strict=False,
        )

        provider_selection = ProviderSelection(
            provider=request.provider,
            model_id=request.model_id,
            api_key=request.api_key,
        )

        system_prompt = template.system_prompt or (
            "You are a structured data extraction assistant. "
            "Extract the requested fields from the provided document text. "
            "Return only values explicitly present in the text. Use null for missing fields."
        )
        user_prompt = template.build_user_prompt(document_text)

        result, _task_events = await self._task_service.execute_prepared_prompt(
            task_id=f"extraction:{template.template_id}",
            provider_selection=provider_selection,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            structured_output=structured_output,
            max_tokens=request.max_tokens,
            temperature=request.temperature or 0.0,
            trace_name="extraction.provider_structured",
            trace_label=f"extraction.{template.template_id}",
            trace_metadata={
                "extraction_id": extraction_id,
                "template_id": template.template_id,
                "provider": request.provider,
                "model_id": request.model_id,
                "strategy": "provider_structured",
            },
            trace_input_data={"document_text_length": len(document_text)},
        )

        if result.error is not None:
            raise ExtractionServiceError(
                f"Provider extraction failed: {result.error.message}",
            )

        # Parse structured output into field results
        fields = self._parse_structured_fields(
            template, result.structured_output.parsed if result.structured_output else None,
        )

        return fields, events

    # ------------------------------------------------------------------
    # LangExtract-based grounded extraction
    # ------------------------------------------------------------------

    async def _extract_langextract(
        self,
        request: ExtractionRequest,
        template: ExtractionTemplate,
        document_text: str,
        extraction_id: str,
    ) -> tuple[list[ExtractedFieldResult], list[ExtractionEvent]]:
        raise ExtractionServiceError(
            _LANGEXTRACT_SCAFFOLDED_MESSAGE,
            status_code=400,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_strategy(
        self,
        requested: ExtractionStrategy,
        template: ExtractionTemplate,
        request: ExtractionRequest,
    ) -> ExtractionStrategy:
        """Resolve the actual extraction strategy to use."""
        if requested == "langextract_grounded":
            raise ExtractionServiceError(
                _LANGEXTRACT_SCAFFOLDED_MESSAGE,
                status_code=400,
            )

        if requested != "auto":
            return requested

        # Auto strategy: prefer template's preferred strategy
        preferred = template.preferred_strategy
        if preferred == "provider_structured" and request.provider:
            return "provider_structured"

        # Fallback: if provider credentials are given, use provider
        if request.provider and request.model_id and request.api_key:
            return "provider_structured"

        raise ExtractionServiceError(
            "Cannot resolve extraction strategy. "
            "Provide provider credentials for provider_structured. "
            + _LANGEXTRACT_SCAFFOLDED_MESSAGE,
            status_code=400,
        )

    def _collect_document_text(self, document_id: str) -> str:
        """Collect full document text from page records."""
        statement = (
            select(PageRecord)
            .where(PageRecord.document_id == document_id)
            .order_by(PageRecord.page_number)
        )
        pages = self._session.exec(statement).all()
        parts: list[str] = []
        for page in pages:
            if page.text:
                parts.append(f"--- Page {page.page_number} ---\n{page.text}")
        return "\n\n".join(parts)

    def _parse_structured_fields(
        self,
        template: ExtractionTemplate,
        parsed: dict[str, Any] | None,
    ) -> list[ExtractedFieldResult]:
        """Map structured output dict to ExtractedFieldResult list."""
        if not parsed:
            return [
                ExtractedFieldResult(
                    field_id=fd.field_id,
                    field_type=fd.field_type,
                    value=None,
                    is_present=False,
                )
                for fd in template.schema_definition.fields
            ]

        results: list[ExtractedFieldResult] = []
        for field_def in template.schema_definition.fields:
            value = parsed.get(field_def.field_id)
            is_present = value is not None and value != "" and value != []
            results.append(
                ExtractedFieldResult(
                    field_id=field_def.field_id,
                    field_type=field_def.field_type,
                    value=value,
                    raw_value=str(value) if value is not None else None,
                    is_present=is_present,
                )
            )
        return results

    def _persist_result(self, result: ExtractionResult) -> None:
        """Persist extraction result to database."""
        record = ExtractionRunModel(
            extraction_id=result.run.extraction_id,
            document_id=result.run.document_id,
            template_id=result.run.template_id,
            case_id=result.run.case_id,
            strategy_used=result.run.strategy_used,
            provider=result.run.provider,
            model_id=result.run.model_id,
            status=result.run.status,
            duration_ms=result.run.duration_ms,
            field_count=result.run.field_count,
            fields_extracted=result.run.fields_extracted,
            grounding_available=result.run.grounding_available,
            fields_json=[f.model_dump(mode="json") for f in result.fields],
            errors_json=[e.model_dump(mode="json") for e in result.errors],
            events_json=[e.model_dump(mode="json") for e in result.events],
        )
        self._session.merge(record)

        if result.run.case_id:
            document = self._session.get(DocumentRecord, result.run.document_id)
            audit = AuditTrailService(self._session)
            audit.append_event(
                case_id=result.run.case_id,
                category="extraction",
                event_type="extraction_completed",
                actor=audit_actor("service", actor_id="extraction.service", display_name="Extraction Service"),
                entity=entity_ref(
                    "extraction_run",
                    result.run.extraction_id,
                    case_id=result.run.case_id,
                    display_label=result.run.template_id,
                ),
                change_summary=ChangeSummary(
                    message="Extraction run persisted.",
                    field_changes=[
                        FieldChangeRecord(field_path="status", new_value=result.run.status),
                        FieldChangeRecord(field_path="fields_extracted", new_value=result.run.fields_extracted),
                        FieldChangeRecord(field_path="grounding_available", new_value=result.run.grounding_available),
                    ],
                ),
                related_entities=(
                    [entity_ref("document", result.run.document_id, case_id=result.run.case_id, display_label=document.filename)]
                    if document is not None
                    else []
                ),
                metadata={"template_id": result.run.template_id, "strategy_used": result.run.strategy_used},
            )
            audit.record_lineage(
                case_id=result.run.case_id,
                artifact=derived_ref("extraction_run", result.run.extraction_id, case_id=result.run.case_id, display_label=result.run.template_id),
                edges=[
                    (
                        "case_context",
                        source_ref("case", result.run.case_id, case_id=result.run.case_id, display_label=result.run.case_id, source_path="case"),
                        None,
                    ),
                    (
                        "document_source",
                        source_ref("document", result.run.document_id, case_id=result.run.case_id, display_label=document.filename if document is not None else result.run.document_id, source_path="document"),
                        None,
                    ),
                ],
                notes=["Extraction lineage is currently tracked at case/document/template granularity."],
                metadata={"template_id": result.run.template_id},
            )
        self._session.commit()

    def _record_to_result(self, record: ExtractionRunModel) -> ExtractionResult:
        """Reconstruct ExtractionResult from persisted record."""
        return ExtractionResult(
            run=self._record_to_run_metadata(record),
            fields=[
                ExtractedFieldResult.model_validate(f) for f in record.fields_json
            ],
            errors=[
                ExtractionError.model_validate(e) for e in record.errors_json
            ],
            events=[
                ExtractionEvent.model_validate(e) for e in record.events_json
            ],
        )

    def _record_to_run_metadata(
        self, record: ExtractionRunModel
    ) -> ExtractionRunMetadata:
        return ExtractionRunMetadata(
            extraction_id=record.extraction_id,
            document_id=record.document_id,
            template_id=record.template_id,
            case_id=record.case_id,
            strategy_used=record.strategy_used,
            provider=record.provider,
            model_id=record.model_id,
            status=record.status,
            duration_ms=record.duration_ms,
            field_count=record.field_count,
            fields_extracted=record.fields_extracted,
            grounding_available=record.grounding_available,
        )

    def _build_error_result(
        self,
        *,
        extraction_id: str,
        request: ExtractionRequest,
        template: ExtractionTemplate,
        events: list[ExtractionEvent],
        strategy_used: ExtractionStrategy | None = None,
        error_code: str,
        message: str,
    ) -> ExtractionResult:
        """Build a failed extraction result."""
        events.append(_event(
            ExtractionEventKind.EXTRACTION_FAILED,
            error_code=error_code,
            message=message,
        ))

        error = ExtractionError(code=error_code, message=message, recoverable=False)
        run = ExtractionRunMetadata(
            extraction_id=extraction_id,
            document_id=request.document_id,
            template_id=request.template_id,
            case_id=request.case_id,
            strategy_used=strategy_used or request.strategy,
            provider=request.provider,
            model_id=request.model_id,
            status="failed",
            field_count=len(template.schema_definition.fields),
            fields_extracted=0,
            grounding_available=False,
        )

        result = ExtractionResult(
            run=run,
            fields=[],
            errors=[error],
            events=events,
        )
        self._persist_result(result)
        return result

    def _validate_case_context(self, case_id: str | None, document_id: str) -> None:
        if case_id is None:
            return

        if self._session.get(CaseRecordModel, case_id) is None:
            raise ExtractionServiceError(
                f"Case '{case_id}' not found.",
                status_code=404,
            )

        link = self._session.exec(
            select(CaseDocumentLinkModel).where(
                CaseDocumentLinkModel.case_id == case_id,
                CaseDocumentLinkModel.document_id == document_id,
            )
        ).first()
        if link is None:
            raise ExtractionServiceError(
                "When case_id is provided, the document must already be linked to that case.",
                status_code=400,
            )
