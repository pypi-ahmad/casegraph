"""Task registry — generic infrastructure tasks for provider-backed execution."""

from __future__ import annotations

from casegraph_agent_sdk.tasks import TaskDefinitionMeta


class TaskDefinition:
    """A registered task with metadata and a prompt builder."""

    def __init__(
        self,
        meta: TaskDefinitionMeta,
        *,
        system_prompt: str,
        user_prompt_template: str,
    ) -> None:
        self.meta = meta
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template

    def build_user_prompt(self, text: str, parameters: dict) -> str:  # noqa: ARG002
        """Build the user prompt from task input."""
        return self.user_prompt_template.replace("{{text}}", text)


class TaskRegistry:
    """In-memory registry of available task definitions."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskDefinition] = {}

    def register(self, definition: TaskDefinition) -> None:
        self._tasks[definition.meta.task_id] = definition

    def get(self, task_id: str) -> TaskDefinition | None:
        return self._tasks.get(task_id)

    def list_definitions(self) -> list[TaskDefinition]:
        return list(self._tasks.values())

    def list_metadata(self) -> list[TaskDefinitionMeta]:
        return [d.meta for d in self._tasks.values()]


# ---------------------------------------------------------------------------
# Built-in generic infrastructure tasks
# ---------------------------------------------------------------------------

_SUMMARIZE_TEXT = TaskDefinition(
    meta=TaskDefinitionMeta(
        task_id="summarize_text",
        display_name="Summarize Text",
        category="summarization",
        description="Produce a concise summary of the provided text.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to summarize."},
            },
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Concise summary."},
            },
            "required": ["summary"],
        },
        supports_structured_output=True,
    ),
    system_prompt=(
        "You are a concise summarization assistant. "
        "Produce a clear, accurate summary of the provided text. "
        "Output valid JSON matching the requested schema."
    ),
    user_prompt_template="Summarize the following text:\n\n{{text}}",
)

_CLASSIFY_TEXT = TaskDefinition(
    meta=TaskDefinitionMeta(
        task_id="classify_text",
        display_name="Classify Text",
        category="classification",
        description="Classify the provided text into a category with a confidence score.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to classify."},
            },
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Assigned category label."},
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Classification confidence score.",
                },
                "reasoning": {"type": "string", "description": "Brief reasoning."},
            },
            "required": ["category", "confidence"],
        },
        supports_structured_output=True,
    ),
    system_prompt=(
        "You are a text classification assistant. "
        "Classify the provided text into a meaningful category. "
        "Assign a confidence score between 0 and 1. "
        "Output valid JSON matching the requested schema."
    ),
    user_prompt_template="Classify the following text:\n\n{{text}}",
)

_EXTRACT_FIELDS = TaskDefinition(
    meta=TaskDefinitionMeta(
        task_id="extract_structured_fields",
        display_name="Extract Structured Fields",
        category="extraction",
        description="Extract structured key-value fields from the provided text.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to extract fields from."},
            },
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"},
                            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        },
                        "required": ["key", "value"],
                    },
                    "description": "Extracted key-value pairs.",
                },
            },
            "required": ["fields"],
        },
        supports_structured_output=True,
    ),
    system_prompt=(
        "You are a structured field extraction assistant. "
        "Extract meaningful key-value pairs from the provided text. "
        "Output valid JSON matching the requested schema."
    ),
    user_prompt_template="Extract structured fields from the following text:\n\n{{text}}",
)


def build_default_task_registry() -> TaskRegistry:
    """Create and return the task registry populated with built-in tasks."""
    registry = TaskRegistry()
    registry.register(_SUMMARIZE_TEXT)
    registry.register(_CLASSIFY_TEXT)
    registry.register(_EXTRACT_FIELDS)
    return registry


task_registry = build_default_task_registry()
