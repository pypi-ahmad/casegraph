"""Extraction template registry — definitions and built-in generic templates."""

from __future__ import annotations

from casegraph_agent_sdk.extraction import (
    ExtractionFieldDefinition,
    ExtractionSchemaDefinition,
    ExtractionStrategy,
    ExtractionTemplateDetail,
    ExtractionTemplateId,
    ExtractionTemplateListResponse,
    ExtractionTemplateMetadata,
)


class ExtractionTemplate:
    """In-memory extraction template with schema and prompt configuration."""

    def __init__(
        self,
        *,
        template_id: ExtractionTemplateId,
        display_name: str,
        description: str = "",
        category: str = "general",
        preferred_strategy: ExtractionStrategy = "provider_structured",
        schema_definition: ExtractionSchemaDefinition,
        system_prompt: str = "",
        user_prompt_template: str = "",
    ) -> None:
        self.template_id = template_id
        self.display_name = display_name
        self.description = description
        self.category = category
        self.preferred_strategy = preferred_strategy
        self.schema_definition = schema_definition
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template

    @property
    def metadata(self) -> ExtractionTemplateMetadata:
        return ExtractionTemplateMetadata(
            template_id=self.template_id,
            display_name=self.display_name,
            description=self.description,
            category=self.category,
            preferred_strategy=self.preferred_strategy,
            field_count=len(self.schema_definition.fields),
        )

    @property
    def detail(self) -> ExtractionTemplateDetail:
        return ExtractionTemplateDetail(
            metadata=self.metadata,
            schema_definition=self.schema_definition,
            system_prompt=self.system_prompt,
            user_prompt_template=self.user_prompt_template,
        )

    def build_user_prompt(self, document_text: str) -> str:
        """Build user prompt with document text substituted."""
        if self.user_prompt_template:
            return self.user_prompt_template.replace("{{document_text}}", document_text)
        return f"Extract the requested fields from the following document text:\n\n{document_text}"


class ExtractionTemplateRegistry:
    """In-memory registry of extraction templates."""

    def __init__(self) -> None:
        self._templates: dict[ExtractionTemplateId, ExtractionTemplate] = {}

    def register(self, template: ExtractionTemplate) -> None:
        self._templates[template.template_id] = template

    def get(self, template_id: ExtractionTemplateId) -> ExtractionTemplate | None:
        return self._templates.get(template_id)

    def list_templates(self) -> list[ExtractionTemplate]:
        return list(self._templates.values())

    def list_metadata(self) -> ExtractionTemplateListResponse:
        return ExtractionTemplateListResponse(
            templates=[t.metadata for t in self._templates.values()]
        )


# ---------------------------------------------------------------------------
# Built-in generic templates
# ---------------------------------------------------------------------------

_CONTACT_INFO_SCHEMA = ExtractionSchemaDefinition(
    fields=[
        ExtractionFieldDefinition(
            field_id="full_name",
            display_name="Full Name",
            field_type="string",
            description="Full name of the primary contact or person.",
            required=False,
        ),
        ExtractionFieldDefinition(
            field_id="email",
            display_name="Email Address",
            field_type="string",
            description="Email address if present.",
            required=False,
        ),
        ExtractionFieldDefinition(
            field_id="phone",
            display_name="Phone Number",
            field_type="string",
            description="Phone number if present.",
            required=False,
        ),
        ExtractionFieldDefinition(
            field_id="address",
            display_name="Mailing Address",
            field_type="string",
            description="Mailing or street address if present.",
            required=False,
        ),
        ExtractionFieldDefinition(
            field_id="organization",
            display_name="Organization",
            field_type="string",
            description="Company or organization name if present.",
            required=False,
        ),
    ]
)

_DOCUMENT_HEADER_SCHEMA = ExtractionSchemaDefinition(
    fields=[
        ExtractionFieldDefinition(
            field_id="title",
            display_name="Document Title",
            field_type="string",
            description="Title or heading of the document.",
            required=False,
        ),
        ExtractionFieldDefinition(
            field_id="date",
            display_name="Document Date",
            field_type="date",
            description="Date the document was created, issued, or effective.",
            required=False,
        ),
        ExtractionFieldDefinition(
            field_id="author",
            display_name="Author",
            field_type="string",
            description="Author, sender, or originator of the document.",
            required=False,
        ),
        ExtractionFieldDefinition(
            field_id="document_type",
            display_name="Document Type",
            field_type="string",
            description="Type or category of the document (e.g. letter, invoice, report).",
            required=False,
        ),
        ExtractionFieldDefinition(
            field_id="reference_number",
            display_name="Reference Number",
            field_type="string",
            description="Any reference number, case number, or identifier mentioned.",
            required=False,
        ),
    ]
)

_KEY_VALUE_SCHEMA = ExtractionSchemaDefinition(
    fields=[
        ExtractionFieldDefinition(
            field_id="entries",
            display_name="Key-Value Entries",
            field_type="list",
            description="List of key-value pairs extracted from the document.",
            item_type="object",
            required=True,
            nested_fields=[
                ExtractionFieldDefinition(
                    field_id="key",
                    display_name="Key",
                    field_type="string",
                    description="The field name or label.",
                    required=True,
                ),
                ExtractionFieldDefinition(
                    field_id="value",
                    display_name="Value",
                    field_type="string",
                    description="The extracted value.",
                    required=True,
                ),
            ],
        ),
    ]
)


def build_default_extraction_registry() -> ExtractionTemplateRegistry:
    """Build registry with built-in generic templates."""
    registry = ExtractionTemplateRegistry()

    registry.register(
        ExtractionTemplate(
            template_id="contact_info",
            display_name="Contact Information",
            description="Extract contact details such as name, email, phone, address, and organization.",
            category="general",
            preferred_strategy="provider_structured",
            schema_definition=_CONTACT_INFO_SCHEMA,
            system_prompt=(
                "You are a structured data extraction assistant. "
                "Extract contact information from the provided document text. "
                "Return only values that are explicitly present in the text. "
                "Use null for any field not found in the document."
            ),
        )
    )

    registry.register(
        ExtractionTemplate(
            template_id="document_header",
            display_name="Document Header",
            description="Extract document metadata such as title, date, author, type, and reference number.",
            category="general",
            preferred_strategy="provider_structured",
            schema_definition=_DOCUMENT_HEADER_SCHEMA,
            system_prompt=(
                "You are a structured data extraction assistant. "
                "Extract document header metadata from the provided text. "
                "Return only values that are explicitly present in the text. "
                "Use null for any field not found in the document."
            ),
        )
    )

    registry.register(
        ExtractionTemplate(
            template_id="key_value_packet",
            display_name="Key-Value Packet",
            description="Extract all key-value pairs found in the document.",
            category="general",
            preferred_strategy="provider_structured",
            schema_definition=_KEY_VALUE_SCHEMA,
            system_prompt=(
                "You are a structured data extraction assistant. "
                "Extract all identifiable key-value pairs from the provided document text. "
                "Each entry should have a descriptive key and its corresponding value. "
                "Only extract pairs that are clearly present in the text."
            ),
        )
    )

    return registry


extraction_template_registry = build_default_extraction_registry()
