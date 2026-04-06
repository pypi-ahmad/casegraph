"""Provider registry for supported BYOK integrations."""

from dataclasses import dataclass

from app.providers.adapters.anthropic import AnthropicProviderAdapter
from app.providers.adapters.base import BaseProviderAdapter
from app.providers.adapters.gemini import GeminiProviderAdapter
from app.providers.adapters.openai import OpenAIProviderAdapter
from app.providers.schemas import (
    CapabilityPlaceholderStatus,
    ProviderCapabilityId,
    ProviderCapabilityPlaceholder,
    ProviderId,
    ProviderSummary,
)


def _capability_placeholders() -> list[ProviderCapabilityPlaceholder]:
    return [
        ProviderCapabilityPlaceholder(
            id=ProviderCapabilityId.MODEL_DISCOVERY,
            display_name="Model discovery",
            status=CapabilityPlaceholderStatus.IMPLEMENTED,
        ),
        ProviderCapabilityPlaceholder(
            id=ProviderCapabilityId.TEXT_GENERATION,
            display_name="Text generation",
            status=CapabilityPlaceholderStatus.IMPLEMENTED,
        ),
        ProviderCapabilityPlaceholder(
            id=ProviderCapabilityId.EMBEDDINGS,
            display_name="Embeddings",
            status=CapabilityPlaceholderStatus.NOT_MODELED,
        ),
        ProviderCapabilityPlaceholder(
            id=ProviderCapabilityId.VISION,
            display_name="Vision",
            status=CapabilityPlaceholderStatus.NOT_MODELED,
        ),
        ProviderCapabilityPlaceholder(
            id=ProviderCapabilityId.TOOL_CALLING,
            display_name="Tool calling",
            status=CapabilityPlaceholderStatus.NOT_MODELED,
        ),
    ]


@dataclass(frozen=True)
class ProviderRegistration:
    summary: ProviderSummary
    adapter_type: type[BaseProviderAdapter]


REGISTRY: dict[ProviderId, ProviderRegistration] = {
    ProviderId.OPENAI: ProviderRegistration(
        summary=ProviderSummary(
            id=ProviderId.OPENAI,
            display_name="OpenAI",
            capabilities=_capability_placeholders(),
        ),
        adapter_type=OpenAIProviderAdapter,
    ),
    ProviderId.ANTHROPIC: ProviderRegistration(
        summary=ProviderSummary(
            id=ProviderId.ANTHROPIC,
            display_name="Anthropic",
            capabilities=_capability_placeholders(),
        ),
        adapter_type=AnthropicProviderAdapter,
    ),
    ProviderId.GEMINI: ProviderRegistration(
        summary=ProviderSummary(
            id=ProviderId.GEMINI,
            display_name="Gemini",
            capabilities=_capability_placeholders(),
        ),
        adapter_type=GeminiProviderAdapter,
    ),
}


PROVIDER_ORDER = [ProviderId.OPENAI, ProviderId.ANTHROPIC, ProviderId.GEMINI]


def list_provider_summaries() -> list[ProviderSummary]:
    return [REGISTRY[provider_id].summary for provider_id in PROVIDER_ORDER]


def get_provider_adapter(provider_id: ProviderId) -> BaseProviderAdapter:
    return REGISTRY[provider_id].adapter_type()