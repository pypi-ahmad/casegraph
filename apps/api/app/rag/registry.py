"""RAG task registry — evidence-backed generic infrastructure tasks."""

from __future__ import annotations

from casegraph_agent_sdk.rag import RagTaskDefinitionMeta


class RagTaskDefinition:
    """A registered evidence-backed task with prompt templates."""

    def __init__(
        self,
        meta: RagTaskDefinitionMeta,
        *,
        system_prompt: str,
        user_prompt_template: str,
    ) -> None:
        self.meta = meta
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template

    def build_user_prompt(self, query: str, evidence_context: str) -> str:
        """Build the user prompt from query and formatted evidence."""
        return (
            self.user_prompt_template
            .replace("{{query}}", query)
            .replace("{{evidence}}", evidence_context)
        )


class RagTaskRegistry:
    """In-memory registry of evidence-backed task definitions."""

    def __init__(self) -> None:
        self._tasks: dict[str, RagTaskDefinition] = {}

    def register(self, definition: RagTaskDefinition) -> None:
        self._tasks[definition.meta.task_id] = definition

    def get(self, task_id: str) -> RagTaskDefinition | None:
        return self._tasks.get(task_id)

    def list_definitions(self) -> list[RagTaskDefinition]:
        return list(self._tasks.values())

    def list_metadata(self) -> list[RagTaskDefinitionMeta]:
        return [d.meta for d in self._tasks.values()]


# ---------------------------------------------------------------------------
# Built-in evidence-backed tasks
# ---------------------------------------------------------------------------

_ANSWER_WITH_EVIDENCE = RagTaskDefinition(
    meta=RagTaskDefinitionMeta(
        task_id="answer_with_evidence",
        display_name="Answer with Evidence",
        category="text_generation",
        description=(
            "Answer a question using retrieved evidence chunks. "
            "Citations reference the numbered evidence sources."
        ),
        requires_evidence=True,
        returns_citations=True,
        supports_structured_output=False,
    ),
    system_prompt=(
        "You are a precise research assistant. "
        "Answer the user's question using ONLY the provided evidence. "
        "Cite evidence by referencing the numbered sources like [1], [2], etc. "
        "If the evidence does not contain enough information to answer, say so honestly. "
        "Do not fabricate information beyond what the evidence supports."
    ),
    user_prompt_template=(
        "Evidence:\n{{evidence}}\n\n"
        "Question: {{query}}\n\n"
        "Answer the question using only the evidence above. "
        "Cite sources using [1], [2], etc."
    ),
)

_SUMMARIZE_WITH_EVIDENCE = RagTaskDefinition(
    meta=RagTaskDefinitionMeta(
        task_id="summarize_with_evidence",
        display_name="Summarize with Evidence",
        category="summarization",
        description=(
            "Produce a summary of the retrieved evidence chunks. "
            "Citations reference the numbered evidence sources."
        ),
        requires_evidence=True,
        returns_citations=True,
        supports_structured_output=True,
        output_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Concise summary of the evidence."},
                "key_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key points extracted from the evidence.",
                },
            },
            "required": ["summary"],
        },
    ),
    system_prompt=(
        "You are a precise summarization assistant. "
        "Summarize the provided evidence clearly and accurately. "
        "Cite evidence by referencing the numbered sources like [1], [2], etc. "
        "Do not add information beyond what the evidence contains. "
        "Output valid JSON matching the requested schema when structured output is requested."
    ),
    user_prompt_template=(
        "Evidence:\n{{evidence}}\n\n"
        "Instruction: {{query}}\n\n"
        "Summarize the evidence above. Cite sources using [1], [2], etc."
    ),
)

_EXTRACT_WITH_EVIDENCE = RagTaskDefinition(
    meta=RagTaskDefinitionMeta(
        task_id="extract_with_evidence",
        display_name="Extract Fields with Evidence",
        category="extraction",
        description=(
            "Extract structured key-value fields from retrieved evidence. "
            "Each extracted field references the evidence source it came from."
        ),
        requires_evidence=True,
        returns_citations=True,
        supports_structured_output=True,
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
                            "source": {"type": "string", "description": "Evidence source reference like [1]."},
                        },
                        "required": ["key", "value"],
                    },
                    "description": "Extracted key-value pairs with source references.",
                },
            },
            "required": ["fields"],
        },
    ),
    system_prompt=(
        "You are a structured field extraction assistant. "
        "Extract meaningful key-value pairs from the provided evidence. "
        "Include a source reference for each field indicating which evidence chunk it came from, "
        "using [1], [2], etc. "
        "Do not fabricate information beyond what the evidence contains. "
        "Output valid JSON matching the requested schema when structured output is requested."
    ),
    user_prompt_template=(
        "Evidence:\n{{evidence}}\n\n"
        "Instruction: {{query}}\n\n"
        "Extract structured fields from the evidence above. "
        "Include source references using [1], [2], etc."
    ),
)


def build_default_rag_registry() -> RagTaskRegistry:
    """Create and return the RAG task registry with built-in tasks."""
    registry = RagTaskRegistry()
    registry.register(_ANSWER_WITH_EVIDENCE)
    registry.register(_SUMMARIZE_WITH_EVIDENCE)
    registry.register(_EXTRACT_WITH_EVIDENCE)
    return registry


rag_task_registry = build_default_rag_registry()
