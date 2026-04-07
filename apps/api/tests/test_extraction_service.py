"""Tests for the extraction foundation."""

from __future__ import annotations

from typing import Any

import pytest
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.extraction import (
    ExtractedFieldResult,
    ExtractionFieldDefinition,
    ExtractionRequest,
    ExtractionSchemaDefinition,
    ExtractionTemplateMetadata,
)
from casegraph_agent_sdk.ingestion import (
    CoordinateSpace,
    GeometrySource,
)
from casegraph_agent_sdk.tasks import (
    FinishReason,
    StructuredOutputResult,
    TaskExecutionResult,
)

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel
from app.extraction.grounding import GroundingService
from app.extraction.models import ExtractionRunModel
from app.extraction.registry import (
    ExtractionTemplate,
    ExtractionTemplateRegistry,
    build_default_extraction_registry,
    extraction_template_registry,
)
from app.extraction.service import ExtractionService, ExtractionServiceError
from app.ingestion.models import DocumentRecord
from app.review.models import PageRecord


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Template registry tests
# ---------------------------------------------------------------------------

def test_default_registry_has_builtin_templates() -> None:
    registry = build_default_extraction_registry()
    templates = registry.list_templates()
    ids = [t.template_id for t in templates]
    assert "contact_info" in ids
    assert "document_header" in ids
    assert "key_value_packet" in ids


def test_template_registry_register_and_get() -> None:
    registry = ExtractionTemplateRegistry()
    schema = ExtractionSchemaDefinition(
        fields=[
            ExtractionFieldDefinition(
                field_id="name",
                display_name="Name",
                field_type="string",
                description="A name field.",
            )
        ]
    )
    template = ExtractionTemplate(
        template_id="test_tpl",
        display_name="Test Template",
        schema_definition=schema,
    )
    registry.register(template)

    found = registry.get("test_tpl")
    assert found is not None
    assert found.metadata.template_id == "test_tpl"
    assert found.metadata.field_count == 1
    assert registry.get("nonexistent") is None


def test_template_metadata_response() -> None:
    resp = extraction_template_registry.list_metadata()
    assert len(resp.templates) == 3
    assert all(isinstance(t, ExtractionTemplateMetadata) for t in resp.templates)
    assert all(t.field_count > 0 for t in resp.templates)


def test_template_detail_includes_schema() -> None:
    template = extraction_template_registry.get("contact_info")
    assert template is not None
    detail = template.detail
    assert len(detail.schema_definition.fields) == 5
    assert detail.system_prompt != ""
    field_ids = [f.field_id for f in detail.schema_definition.fields]
    assert "full_name" in field_ids
    assert "email" in field_ids


# ---------------------------------------------------------------------------
# Schema → JSON Schema conversion tests
# ---------------------------------------------------------------------------

def test_schema_to_json_schema_basic() -> None:
    schema = ExtractionSchemaDefinition(
        fields=[
            ExtractionFieldDefinition(
                field_id="name",
                display_name="Name",
                field_type="string",
                required=True,
                description="The name.",
            ),
            ExtractionFieldDefinition(
                field_id="age",
                display_name="Age",
                field_type="integer",
                required=False,
            ),
        ]
    )
    js = schema.to_json_schema()
    assert js["type"] == "object"
    assert "name" in js["properties"]
    assert js["properties"]["name"]["type"] == "string"
    assert js["properties"]["age"]["type"] == "integer"
    assert "name" in js["required"]
    assert "age" not in js["required"]
    assert js["additionalProperties"] is False


def test_schema_to_json_schema_list_field() -> None:
    schema = ExtractionSchemaDefinition(
        fields=[
            ExtractionFieldDefinition(
                field_id="tags",
                display_name="Tags",
                field_type="list",
                item_type="string",
                description="A list of tags.",
            ),
        ]
    )
    js = schema.to_json_schema()
    assert js["properties"]["tags"]["type"] == "array"
    assert js["properties"]["tags"]["items"]["type"] == "string"


def test_schema_to_json_schema_list_of_objects_field() -> None:
    schema = ExtractionSchemaDefinition(
        fields=[
            ExtractionFieldDefinition(
                field_id="entries",
                display_name="Entries",
                field_type="list",
                item_type="object",
                nested_fields=[
                    ExtractionFieldDefinition(
                        field_id="key",
                        display_name="Key",
                        field_type="string",
                        required=True,
                    ),
                    ExtractionFieldDefinition(
                        field_id="value",
                        display_name="Value",
                        field_type="string",
                        required=True,
                    ),
                ],
            ),
        ]
    )
    js = schema.to_json_schema()
    entries = js["properties"]["entries"]
    assert entries["type"] == "array"
    assert entries["items"]["type"] == "object"
    assert entries["items"]["properties"]["key"]["type"] == "string"
    assert entries["items"]["properties"]["value"]["type"] == "string"
    assert "key" in entries["items"]["required"]
    assert "value" in entries["items"]["required"]


def test_schema_to_json_schema_object_field() -> None:
    schema = ExtractionSchemaDefinition(
        fields=[
            ExtractionFieldDefinition(
                field_id="address",
                display_name="Address",
                field_type="object",
                nested_fields=[
                    ExtractionFieldDefinition(
                        field_id="street",
                        display_name="Street",
                        field_type="string",
                        required=True,
                    ),
                    ExtractionFieldDefinition(
                        field_id="city",
                        display_name="City",
                        field_type="string",
                        required=False,
                    ),
                ],
            ),
        ]
    )
    js = schema.to_json_schema()
    addr = js["properties"]["address"]
    assert addr["type"] == "object"
    assert "street" in addr["properties"]
    assert "street" in addr["required"]
    assert "city" not in addr["required"]


def test_schema_to_json_schema_date_field() -> None:
    schema = ExtractionSchemaDefinition(
        fields=[
            ExtractionFieldDefinition(
                field_id="due_date",
                display_name="Due Date",
                field_type="date",
                description="Due date",
            ),
        ]
    )
    js = schema.to_json_schema()
    prop = js["properties"]["due_date"]
    assert prop["type"] == "string"
    assert "ISO 8601" in prop["description"]


# ---------------------------------------------------------------------------
# Grounding service tests
# ---------------------------------------------------------------------------

def _seed_document_with_pages(session: Session) -> str:
    document_id = "doc-extract-001"
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
            page_count=1,
            text_block_count=2,
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
            text="John Doe\njohn.doe@example.com\n555-0123",
            text_blocks_json=[
                {
                    "block_id": "page-1-block-1",
                    "page_number": 1,
                    "text": "John Doe",
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
                    "text": "john.doe@example.com 555-0123",
                    "bbox": {
                        "x0": 72.0,
                        "y0": 100.0,
                        "x1": 300.0,
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
    session.commit()
    return document_id


def _seed_case(session: Session, case_id: str = "case-001") -> str:
    session.add(
        CaseRecordModel(
            case_id=case_id,
            title="Case Title",
            status="open",
        )
    )
    session.commit()
    return case_id


def _link_case_document(session: Session, case_id: str, document_id: str) -> None:
    session.add(
        CaseDocumentLinkModel(
            link_id=f"{case_id}:{document_id}",
            case_id=case_id,
            document_id=document_id,
        )
    )
    session.commit()


class _FakeTaskExecutionService:
    async def execute_prepared_prompt(self, **_: Any) -> tuple[TaskExecutionResult, list[Any]]:
        return (
            TaskExecutionResult(
                task_id="extraction:contact_info",
                provider="openai",
                model_id="gpt-4o-mini",
                finish_reason=FinishReason.COMPLETED,
                output_text='{"full_name": "John Doe", "email": "john.doe@example.com", "phone": "555-0123", "address": null, "organization": null}',
                structured_output=StructuredOutputResult(
                    parsed={
                        "full_name": "John Doe",
                        "email": "john.doe@example.com",
                        "phone": "555-0123",
                        "address": None,
                        "organization": None,
                    },
                    raw_text='{"full_name": "John Doe"}',
                    schema_valid=True,
                    validation_errors=[],
                ),
                duration_ms=42,
            ),
            [],
        )


def test_grounding_attaches_block_references(session: Session) -> None:
    document_id = _seed_document_with_pages(session)
    service = GroundingService(session)

    fields = [
        ExtractedFieldResult(
            field_id="full_name",
            field_type="string",
            value="John Doe",
            is_present=True,
        ),
        ExtractedFieldResult(
            field_id="email",
            field_type="string",
            value="john.doe@example.com",
            is_present=True,
        ),
    ]

    enriched = service.attach_grounding(document_id, fields)

    # full_name should match block-1
    name_field = enriched[0]
    assert len(name_field.grounding) >= 1
    ref = name_field.grounding[0]
    assert ref.document_id == document_id
    assert ref.page_number == 1
    assert ref.block_id == "page-1-block-1"
    assert ref.grounding_method == "text_block_match"
    assert ref.bbox is not None
    assert ref.bbox.x0 == 72.0
    assert ref.bbox.coordinate_space == CoordinateSpace.PDF_POINTS

    # email should match block-2
    email_field = enriched[1]
    assert len(email_field.grounding) >= 1
    assert email_field.grounding[0].block_id == "page-1-block-2"


def test_grounding_skips_empty_fields(session: Session) -> None:
    document_id = _seed_document_with_pages(session)
    service = GroundingService(session)

    fields = [
        ExtractedFieldResult(
            field_id="phone",
            field_type="string",
            value=None,
            is_present=False,
        ),
    ]

    enriched = service.attach_grounding(document_id, fields)
    assert len(enriched[0].grounding) == 0


def test_grounding_returns_geometry_when_available(session: Session) -> None:
    document_id = _seed_document_with_pages(session)
    service = GroundingService(session)

    fields = [
        ExtractedFieldResult(
            field_id="name",
            field_type="string",
            value="John Doe",
            is_present=True,
        ),
    ]

    enriched = service.attach_grounding(document_id, fields)
    ref = enriched[0].grounding[0]
    assert ref.geometry_source == GeometrySource.PDF_TEXT
    assert ref.coordinate_space == CoordinateSpace.PDF_POINTS
    assert ref.bbox is not None


def test_grounding_no_match_returns_empty(session: Session) -> None:
    document_id = _seed_document_with_pages(session)
    service = GroundingService(session)

    fields = [
        ExtractedFieldResult(
            field_id="org",
            field_type="string",
            value="Nonexistent Corp",
            is_present=True,
        ),
    ]

    enriched = service.attach_grounding(document_id, fields)
    assert len(enriched[0].grounding) == 0


# ---------------------------------------------------------------------------
# Extraction persistence tests
# ---------------------------------------------------------------------------

def test_extraction_run_persists_and_loads(session: Session) -> None:
    record = ExtractionRunModel(
        extraction_id="ext-001",
        document_id="doc-001",
        template_id="contact_info",
        strategy_used="provider_structured",
        provider="openai",
        model_id="gpt-4o-mini",
        status="completed",
        duration_ms=1500,
        field_count=5,
        fields_extracted=3,
        grounding_available=True,
        fields_json=[
            {
                "field_id": "full_name",
                "field_type": "string",
                "value": "John Doe",
                "raw_value": "John Doe",
                "is_present": True,
                "grounding": [],
            }
        ],
        errors_json=[],
        events_json=[
            {
                "kind": "extraction_started",
                "timestamp": "2026-04-04T00:00:00Z",
                "metadata": {},
            }
        ],
    )
    session.add(record)
    session.commit()

    loaded = session.get(ExtractionRunModel, "ext-001")
    assert loaded is not None
    assert loaded.document_id == "doc-001"
    assert loaded.status == "completed"
    assert loaded.fields_extracted == 3
    assert len(loaded.fields_json) == 1
    assert loaded.fields_json[0]["field_id"] == "full_name"


def test_extraction_service_list_document_extractions(session: Session) -> None:
    session.add(
        DocumentRecord(
            document_id="doc-list",
            filename="list.pdf",
            content_type="application/pdf",
            extension=".pdf",
            size_bytes=100,
            sha256="list123",
            classification="pdf",
            requested_mode="auto",
            resolved_mode="readable_pdf",
            processing_status="completed",
            extractor_name="pymupdf-readable-pdf",
            page_count=1,
            text_block_count=0,
            geometry_present=False,
            geometry_sources_json=[],
        )
    )

    # Seed two extraction records
    for i in range(2):
        session.add(
            ExtractionRunModel(
                extraction_id=f"ext-list-{i}",
                document_id="doc-list",
                template_id="contact_info",
                strategy_used="provider_structured",
                status="completed",
                field_count=5,
                fields_extracted=3,
                fields_json=[],
                errors_json=[],
                events_json=[],
            )
        )
    session.commit()

    service = ExtractionService(session)
    resp = service.list_document_extractions("doc-list")
    assert resp.document_id == "doc-list"
    assert len(resp.extractions) == 2


def test_extraction_service_list_document_extractions_requires_existing_document(
    session: Session,
) -> None:
    service = ExtractionService(session)
    with pytest.raises(ExtractionServiceError) as exc:
        service.list_document_extractions("missing-doc")
    assert exc.value.status_code == 404


def test_extraction_service_get_extraction(session: Session) -> None:
    session.add(
        ExtractionRunModel(
            extraction_id="ext-get-001",
            document_id="doc-get",
            template_id="document_header",
            strategy_used="provider_structured",
            status="completed",
            field_count=5,
            fields_extracted=2,
            fields_json=[
                {
                    "field_id": "title",
                    "field_type": "string",
                    "value": "Test Document",
                    "raw_value": "Test Document",
                    "is_present": True,
                    "grounding": [],
                }
            ],
            errors_json=[],
            events_json=[],
        )
    )
    session.commit()

    service = ExtractionService(session)
    result = service.get_extraction("ext-get-001")
    assert result is not None
    assert result.run.extraction_id == "ext-get-001"
    assert result.run.template_id == "document_header"
    assert len(result.fields) == 1
    assert result.fields[0].field_id == "title"
    assert result.fields[0].value == "Test Document"


def test_extraction_service_get_missing_returns_none(session: Session) -> None:
    service = ExtractionService(session)
    assert service.get_extraction("nonexistent") is None


@pytest.mark.anyio
async def test_provider_structured_extraction_executes_end_to_end(
    session: Session,
) -> None:
    document_id = _seed_document_with_pages(session)
    service = ExtractionService(
        session,
        task_execution_service=_FakeTaskExecutionService(),
    )

    result = await service.execute(
        ExtractionRequest(
            template_id="contact_info",
            document_id=document_id,
            strategy="provider_structured",
            provider="openai",
            model_id="gpt-4o-mini",
            api_key="test-key",
        )
    )

    assert result.run.status == "completed"
    assert result.run.strategy_used == "provider_structured"
    assert result.run.fields_extracted == 3
    assert result.run.grounding_available is True

    fields_by_id = {field.field_id: field for field in result.fields}
    assert fields_by_id["full_name"].value == "John Doe"
    assert fields_by_id["email"].value == "john.doe@example.com"
    assert fields_by_id["phone"].value == "555-0123"
    assert fields_by_id["full_name"].grounding[0].block_id == "page-1-block-1"
    assert fields_by_id["email"].grounding[0].block_id == "page-1-block-2"

    persisted = session.get(ExtractionRunModel, result.run.extraction_id)
    assert persisted is not None
    assert persisted.document_id == document_id
    assert persisted.template_id == "contact_info"
    assert persisted.strategy_used == "provider_structured"


@pytest.mark.anyio
async def test_provider_structured_extraction_rejects_missing_case(
    session: Session,
) -> None:
    document_id = _seed_document_with_pages(session)
    service = ExtractionService(
        session,
        task_execution_service=_FakeTaskExecutionService(),
    )

    with pytest.raises(ExtractionServiceError) as exc:
        await service.execute(
            ExtractionRequest(
                template_id="contact_info",
                document_id=document_id,
                case_id="missing-case",
                strategy="provider_structured",
                provider="openai",
                model_id="gpt-4o-mini",
                api_key="test-key",
            )
        )

    assert exc.value.status_code == 404
    assert "Case 'missing-case' not found" in exc.value.detail


@pytest.mark.anyio
async def test_provider_structured_extraction_rejects_unlinked_case_document(
    session: Session,
) -> None:
    document_id = _seed_document_with_pages(session)
    case_id = _seed_case(session)
    service = ExtractionService(
        session,
        task_execution_service=_FakeTaskExecutionService(),
    )

    with pytest.raises(ExtractionServiceError) as exc:
        await service.execute(
            ExtractionRequest(
                template_id="contact_info",
                document_id=document_id,
                case_id=case_id,
                strategy="provider_structured",
                provider="openai",
                model_id="gpt-4o-mini",
                api_key="test-key",
            )
        )

    assert exc.value.status_code == 400
    assert "document must already be linked to that case" in exc.value.detail


@pytest.mark.anyio
async def test_provider_structured_extraction_accepts_linked_case_document(
    session: Session,
) -> None:
    document_id = _seed_document_with_pages(session)
    case_id = _seed_case(session)
    _link_case_document(session, case_id, document_id)
    service = ExtractionService(
        session,
        task_execution_service=_FakeTaskExecutionService(),
    )

    result = await service.execute(
        ExtractionRequest(
            template_id="contact_info",
            document_id=document_id,
            case_id=case_id,
            strategy="provider_structured",
            provider="openai",
            model_id="gpt-4o-mini",
            api_key="test-key",
        )
    )

    assert result.run.case_id == case_id
    persisted = session.get(ExtractionRunModel, result.run.extraction_id)
    assert persisted is not None
    assert persisted.case_id == case_id


# ---------------------------------------------------------------------------
# Template prompt building tests
# ---------------------------------------------------------------------------

def test_template_build_user_prompt_with_template() -> None:
    template = ExtractionTemplate(
        template_id="test",
        display_name="Test",
        schema_definition=ExtractionSchemaDefinition(fields=[]),
        user_prompt_template="Extract from:\n{{document_text}}",
    )
    prompt = template.build_user_prompt("Hello world")
    assert "Hello world" in prompt
    assert "Extract from:" in prompt


def test_template_build_user_prompt_default() -> None:
    template = ExtractionTemplate(
        template_id="test",
        display_name="Test",
        schema_definition=ExtractionSchemaDefinition(fields=[]),
    )
    prompt = template.build_user_prompt("Hello world")
    assert "Hello world" in prompt
    assert "Extract the requested fields" in prompt
