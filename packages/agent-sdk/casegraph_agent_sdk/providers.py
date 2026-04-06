"""Shared provider contracts for BYOK validation and model discovery."""

from enum import Enum

from pydantic import BaseModel, Field, SecretStr, field_validator


class ProviderId(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class ProviderCapabilityId(str, Enum):
    MODEL_DISCOVERY = "model_discovery"
    TEXT_GENERATION = "text_generation"
    EMBEDDINGS = "embeddings"
    VISION = "vision"
    TOOL_CALLING = "tool_calling"


class CapabilityPlaceholderStatus(str, Enum):
    IMPLEMENTED = "implemented"
    NOT_MODELED = "not_modeled"


class ProviderCapabilityPlaceholder(BaseModel):
    id: ProviderCapabilityId
    display_name: str
    status: CapabilityPlaceholderStatus


class ProviderSummary(BaseModel):
    id: ProviderId
    display_name: str
    capabilities: list[ProviderCapabilityPlaceholder] = Field(default_factory=list)


class ProvidersResponse(BaseModel):
    providers: list[ProviderSummary]


class ModelSummary(BaseModel):
    provider: ProviderId
    model_id: str
    display_name: str | None = None
    description: str | None = None
    created_at: str | None = None
    owned_by: str | None = None
    input_token_limit: int | None = None
    output_token_limit: int | None = None
    capabilities: list[str] = Field(default_factory=list)


class ProviderValidationRequest(BaseModel):
    provider: ProviderId
    api_key: SecretStr

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        trimmed_value = value.get_secret_value().strip()
        if not trimmed_value:
            raise ValueError("API key is required.")
        return SecretStr(trimmed_value)


class ProviderValidationResponse(BaseModel):
    provider: ProviderId
    valid: bool
    message: str
    error_code: str | None = None


class ModelDiscoveryRequest(BaseModel):
    provider: ProviderId
    api_key: SecretStr

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        trimmed_value = value.get_secret_value().strip()
        if not trimmed_value:
            raise ValueError("API key is required.")
        return SecretStr(trimmed_value)


class ModelDiscoveryResponse(BaseModel):
    provider: ProviderId
    models: list[ModelSummary] = Field(default_factory=list)