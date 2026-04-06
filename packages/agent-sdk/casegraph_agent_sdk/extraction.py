"""Shared extraction contracts for the CaseGraph platform.

These types define schema-driven extraction: templates, field definitions,
extraction strategies, results with per-field grounding, and geometry-aware
source references.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.ingestion import (
    BoundingBoxArtifact,
    CoordinateSpace,
    DocumentId,
    GeometrySource,
    PolygonArtifact,
)


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

ExtractionTemplateId = str
ExtractionId = str


# ---------------------------------------------------------------------------
# Enums and literals
# ---------------------------------------------------------------------------

ExtractionFieldType = Literal[
    "string",
    "integer",
    "number",
    "boolean",
    "date",
    "list",
    "object",
]

ExtractionStrategy = Literal[
    "provider_structured",
    "langextract_grounded",
    "auto",
]

ExtractionStatus = Literal[
    "pending",
    "running",
    "completed",
    "partial",
    "failed",
]


class ExtractionEventKind(str, Enum):
    EXTRACTION_STARTED = "extraction_started"
    STRATEGY_SELECTED = "extraction_strategy_selected"
    PROVIDER_RESOLVED = "provider_resolved"
    LANGEXTRACT_SELECTED = "langextract_selected"
    EXTRACTION_COMPLETED = "extraction_completed"
    GROUNDING_ATTACHED = "grounding_attached"
    EXTRACTION_FAILED = "extraction_failed"


# ---------------------------------------------------------------------------
# Field and schema definitions
# ---------------------------------------------------------------------------

class ExtractionFieldDefinition(BaseModel):
    """Single field in an extraction schema."""

    field_id: str
    display_name: str
    field_type: ExtractionFieldType
    description: str = ""
    required: bool = True
    # For list fields: the type of each item
    item_type: ExtractionFieldType | None = None
    # For object fields: nested field definitions
    nested_fields: list[ExtractionFieldDefinition] | None = None


class ExtractionSchemaDefinition(BaseModel):
    """Complete extraction schema — an ordered collection of field definitions."""

    fields: list[ExtractionFieldDefinition]

    def to_json_schema(self) -> dict[str, Any]:
        """Build a JSON Schema object suitable for structured output."""
        properties: dict[str, Any] = {}
        required_fields: list[str] = []

        for field_def in self.fields:
            properties[field_def.field_id] = _field_to_json_schema(field_def)
            if field_def.required:
                required_fields.append(field_def.field_id)

        return {
            "type": "object",
            "properties": properties,
            "required": required_fields,
            "additionalProperties": False,
        }


def _field_to_json_schema(field_def: ExtractionFieldDefinition) -> dict[str, Any]:
    """Convert a single field definition to JSON Schema."""
    type_map: dict[str, str] = {
        "string": "string",
        "integer": "integer",
        "number": "number",
        "boolean": "boolean",
        "date": "string",
    }

    if field_def.field_type == "list":
        item_schema: dict[str, Any] = {"type": "string"}
        if field_def.item_type == "object":
            item_schema = _nested_object_schema(field_def.nested_fields)
        elif field_def.item_type and field_def.item_type != "list":
            item_schema = {"type": type_map.get(field_def.item_type, "string")}
        return {
            "type": "array",
            "items": item_schema,
            "description": field_def.description,
        }

    if field_def.field_type == "object":
        object_schema = _nested_object_schema(field_def.nested_fields)
        if field_def.description:
            object_schema["description"] = field_def.description
        return object_schema

    json_type = type_map.get(field_def.field_type, "string")
    schema: dict[str, Any] = {"type": json_type}
    if field_def.description:
        schema["description"] = field_def.description
    if field_def.field_type == "date":
        schema["description"] = (
            (field_def.description + " " if field_def.description else "")
            + "ISO 8601 date string."
        ).strip()
    return schema


def _nested_object_schema(
    nested_fields: list[ExtractionFieldDefinition] | None,
) -> dict[str, Any]:
    nested_props: dict[str, Any] = {}
    nested_required: list[str] = []
    for nested_field in nested_fields or []:
        nested_props[nested_field.field_id] = _field_to_json_schema(nested_field)
        if nested_field.required:
            nested_required.append(nested_field.field_id)
    return {
        "type": "object",
        "properties": nested_props,
        "required": nested_required,
        "additionalProperties": False,
    }


# ---------------------------------------------------------------------------
# Template metadata
# ---------------------------------------------------------------------------

class ExtractionTemplateMetadata(BaseModel):
    """Metadata for a registered extraction template."""

    template_id: ExtractionTemplateId
    display_name: str
    description: str = ""
    category: str = "general"
    preferred_strategy: ExtractionStrategy = "provider_structured"
    field_count: int = 0


class ExtractionTemplateDetail(BaseModel):
    """Full template with schema and prompt guidance."""

    metadata: ExtractionTemplateMetadata
    schema_definition: ExtractionSchemaDefinition
    system_prompt: str = ""
    user_prompt_template: str = ""


# ---------------------------------------------------------------------------
# Grounding and source references
# ---------------------------------------------------------------------------

class GroundingReference(BaseModel):
    """Source evidence reference for a single extracted value.

    All fields are optional because the precision of grounding varies
    by extraction strategy and source document type.
    """

    document_id: DocumentId | None = None
    page_number: int | None = None
    block_id: str | None = None
    chunk_id: str | None = None
    text_span: str | None = None
    geometry_source: GeometrySource | None = None
    coordinate_space: CoordinateSpace | None = None
    bbox: BoundingBoxArtifact | None = None
    polygon: PolygonArtifact | None = None
    grounding_method: str | None = None


# ---------------------------------------------------------------------------
# Extraction request
# ---------------------------------------------------------------------------

class ExtractionRequest(BaseModel):
    """Request to execute an extraction against a document."""

    template_id: ExtractionTemplateId
    document_id: DocumentId
    case_id: str | None = None
    strategy: ExtractionStrategy = "auto"
    # Provider selection for provider_structured strategy
    provider: str | None = None
    model_id: str | None = None
    api_key: str | None = None
    # Execution parameters
    max_tokens: int | None = None
    temperature: float | None = None


# ---------------------------------------------------------------------------
# Extraction results
# ---------------------------------------------------------------------------

class ExtractedFieldResult(BaseModel):
    """Result for a single extracted field."""

    field_id: str
    field_type: ExtractionFieldType
    value: Any = None
    raw_value: str | None = None
    is_present: bool = True
    grounding: list[GroundingReference] = Field(default_factory=list)


class ExtractionError(BaseModel):
    """Normalized extraction error."""

    code: str
    message: str
    recoverable: bool = False


class ExtractionEvent(BaseModel):
    """Lifecycle event emitted during extraction."""

    kind: ExtractionEventKind
    timestamp: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractionRunMetadata(BaseModel):
    """Metadata about the extraction execution."""

    extraction_id: ExtractionId
    document_id: DocumentId
    template_id: ExtractionTemplateId
    case_id: str | None = None
    strategy_used: ExtractionStrategy
    provider: str | None = None
    model_id: str | None = None
    status: ExtractionStatus
    duration_ms: int | None = None
    field_count: int = 0
    fields_extracted: int = 0
    grounding_available: bool = False


class ExtractionResult(BaseModel):
    """Complete extraction result with fields and grounding."""

    run: ExtractionRunMetadata
    fields: list[ExtractedFieldResult] = Field(default_factory=list)
    errors: list[ExtractionError] = Field(default_factory=list)
    events: list[ExtractionEvent] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------

class ExtractionTemplateListResponse(BaseModel):
    """List of registered extraction templates."""

    templates: list[ExtractionTemplateMetadata] = Field(default_factory=list)
    available_strategies: list[ExtractionStrategy] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DocumentExtractionListResponse(BaseModel):
    """List of extractions for a specific document."""

    document_id: DocumentId
    extractions: list[ExtractionRunMetadata] = Field(default_factory=list)
