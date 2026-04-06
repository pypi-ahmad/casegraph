"""API request/response schemas for extraction endpoints."""

from __future__ import annotations

from pydantic import BaseModel, SecretStr, field_validator

from casegraph_agent_sdk.extraction import (
    ExtractionResult,
    ExtractionStrategy,
    ExtractionTemplateId,
)
from casegraph_agent_sdk.ingestion import DocumentId


class ExtractionExecuteRequestBody(BaseModel):
    """API request body for executing an extraction."""

    template_id: ExtractionTemplateId
    document_id: DocumentId
    case_id: str | None = None
    strategy: ExtractionStrategy = "auto"
    provider: str | None = None
    model_id: str | None = None
    api_key: SecretStr | None = None
    max_tokens: int | None = None
    temperature: float | None = None

    @field_validator("api_key")
    @classmethod
    def _api_key_non_empty(cls, v: SecretStr | None) -> SecretStr | None:
        if v is not None and not v.get_secret_value().strip():
            raise ValueError("api_key must not be empty when provided.")
        return v


class ExtractionExecuteResponseBody(BaseModel):
    """API response body for extraction execution."""

    result: ExtractionResult
