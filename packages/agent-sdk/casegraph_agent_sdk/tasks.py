"""Shared contracts for provider-backed LLM task execution."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Task identity & classification
# ---------------------------------------------------------------------------

TaskId = str

TaskCategory = Literal[
    "text_generation",
    "classification",
    "extraction",
    "summarization",
    "custom",
]


class TaskDefinitionMeta(BaseModel):
    """Metadata describing a registered generic task."""

    task_id: TaskId
    display_name: str
    category: TaskCategory
    description: str
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema describing expected input fields.",
    )
    output_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema describing expected structured output fields.",
    )
    supports_structured_output: bool = True


# ---------------------------------------------------------------------------
# Task input / output envelopes
# ---------------------------------------------------------------------------


class TaskInput(BaseModel):
    """Generic typed input for a task execution request."""

    text: str = Field(description="Primary text input for the task.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional task-specific parameters.",
    )


class StructuredOutputSchema(BaseModel):
    """Describes the expected structured output contract for a task."""

    json_schema: dict[str, Any] = Field(
        description="JSON Schema the model output should conform to.",
    )
    strict: bool = Field(
        default=False,
        description="Whether the provider should enforce strict schema compliance.",
    )


# ---------------------------------------------------------------------------
# Provider / model selection
# ---------------------------------------------------------------------------


class ProviderSelection(BaseModel):
    """Identifies the provider + model + credential for a task execution."""

    provider: str = Field(description="Provider identifier (openai, anthropic, gemini).")
    model_id: str = Field(description="Model identifier as returned by model discovery.")
    api_key: str = Field(description="Request-scoped API key (never persisted).")


# ---------------------------------------------------------------------------
# Execution request
# ---------------------------------------------------------------------------


class TaskExecutionRequest(BaseModel):
    """Full request to execute a registered task against a provider/model."""

    task_id: TaskId
    input: TaskInput
    provider_selection: ProviderSelection
    structured_output: StructuredOutputSchema | None = None
    max_tokens: int | None = Field(
        default=None,
        description="Optional max output tokens. Provider default used when absent.",
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Optional sampling temperature.",
    )


# ---------------------------------------------------------------------------
# Finish / usage / error normalization
# ---------------------------------------------------------------------------


class FinishReason(str, Enum):
    """Normalized finish reason across providers."""

    COMPLETED = "completed"
    MAX_TOKENS = "max_tokens"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"
    UNKNOWN = "unknown"


class UsageMetadata(BaseModel):
    """Normalized token/cost usage metadata."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class TaskExecutionError(BaseModel):
    """Normalized error from a provider-backed execution attempt."""

    error_code: str
    message: str
    provider: str | None = None
    model_id: str | None = None
    recoverable: bool = False
    upstream_status_code: int | None = None


# ---------------------------------------------------------------------------
# Execution result
# ---------------------------------------------------------------------------


class StructuredOutputResult(BaseModel):
    """Result of structured output extraction."""

    parsed: dict[str, Any] | None = Field(
        default=None,
        description="Parsed structured output conforming to the requested schema.",
    )
    raw_text: str | None = Field(
        default=None,
        description="Raw model response text before parsing.",
    )
    schema_valid: bool = Field(
        default=False,
        description="Whether the parsed output validated against the schema.",
    )
    validation_errors: list[str] = Field(default_factory=list)


class TaskExecutionResult(BaseModel):
    """Normalized result from a provider-backed task execution."""

    task_id: TaskId
    provider: str
    model_id: str
    finish_reason: FinishReason
    output_text: str | None = None
    structured_output: StructuredOutputResult | None = None
    usage: UsageMetadata | None = None
    error: TaskExecutionError | None = None
    duration_ms: int | None = None
    provider_request_id: str | None = None


# ---------------------------------------------------------------------------
# Task registry response
# ---------------------------------------------------------------------------


class TaskRegistryResponse(BaseModel):
    """Response listing all registered task definitions."""

    tasks: list[TaskDefinitionMeta] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Task execution event types (for run lifecycle integration)
# ---------------------------------------------------------------------------

TaskExecutionEventKind = Literal[
    "task_selected",
    "provider_resolved",
    "model_invoked",
    "model_completed",
    "structured_output_validated",
    "model_failed",
    # RAG-specific event kinds
    "retrieval_started",
    "retrieval_completed",
    "retrieval_failed",
    "evidence_selected",
    "context_assembled",
    "citations_attached",
]


class TaskExecutionEvent(BaseModel):
    """A single event emitted during provider-backed task execution."""

    kind: TaskExecutionEventKind
    timestamp: str
    metadata: dict[str, Any] = Field(default_factory=dict)
