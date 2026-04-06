"""Router-level request/response schemas for task execution."""

from __future__ import annotations

from pydantic import BaseModel, Field, SecretStr, field_validator

from casegraph_agent_sdk.tasks import (
    TaskExecutionEvent,
    TaskExecutionResult,
    TaskInput,
)


class TaskExecuteRequestBody(BaseModel):
    """API-facing execution request that accepts api_key as SecretStr."""

    task_id: str
    input: TaskInput
    provider: str
    model_id: str
    api_key: SecretStr
    max_tokens: int | None = None
    temperature: float | None = None
    use_structured_output: bool = True

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        trimmed = value.get_secret_value().strip()
        if not trimmed:
            msg = "api_key must not be empty."
            raise ValueError(msg)
        return SecretStr(trimmed)


class TaskExecuteResponseBody(BaseModel):
    """API response wrapping the execution result and lifecycle events."""

    result: TaskExecutionResult
    events: list[TaskExecutionEvent] = Field(default_factory=list)
