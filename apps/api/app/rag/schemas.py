"""Router-level request/response schemas for RAG task execution."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, SecretStr, field_validator

from casegraph_agent_sdk.rag import (
    RagTaskExecutionResult,
    RetrievalScope,
)
from casegraph_agent_sdk.tasks import TaskExecutionEvent


class RagExecuteRequestBody(BaseModel):
    """API-facing RAG execution request that accepts api_key as SecretStr."""

    task_id: str
    query: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    provider: str
    model_id: str
    api_key: SecretStr
    retrieval_scope: RetrievalScope = Field(default_factory=RetrievalScope)
    top_k: int = Field(default=5, ge=1, le=50)
    max_tokens: int | None = None
    temperature: float | None = None
    use_structured_output: bool = False

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        trimmed = value.get_secret_value().strip()
        if not trimmed:
            msg = "api_key must not be empty."
            raise ValueError(msg)
        return SecretStr(trimmed)


class RagExecuteResponseBody(BaseModel):
    """API response wrapping the RAG execution result and lifecycle events."""

    result: RagTaskExecutionResult
    events: list[TaskExecutionEvent] = Field(default_factory=list)
