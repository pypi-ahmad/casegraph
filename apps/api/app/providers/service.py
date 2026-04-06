"""Service layer for BYOK provider validation and model discovery."""

import httpx

from app.observability.tracing import trace_span
from app.providers.adapters.base import ProviderAdapterError
from app.providers.registry import get_provider_adapter, list_provider_summaries
from app.providers.schemas import (
    ModelDiscoveryRequest,
    ModelDiscoveryResponse,
    ProvidersResponse,
    ProviderValidationRequest,
    ProviderValidationResponse,
)


class ProviderService:
    def __init__(self, timeout_seconds: float) -> None:
        self._timeout = httpx.Timeout(timeout_seconds)

    def list_providers(self) -> ProvidersResponse:
        return ProvidersResponse(providers=list_provider_summaries())

    async def validate_provider_key(
        self, request: ProviderValidationRequest
    ) -> ProviderValidationResponse:
        adapter = get_provider_adapter(request.provider)
        api_key = request.api_key.get_secret_value()

        with trace_span(
            name="provider.validate_key",
            metadata={"provider": request.provider},
        ) as ctx:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                try:
                    await adapter.validate_api_key(api_key, client)
                except ProviderAdapterError as exc:
                    ctx["status"] = "error"
                    ctx["output"] = {"valid": False, "error_code": exc.error_code}
                    return ProviderValidationResponse(
                        provider=request.provider,
                        valid=False,
                        message=exc.message,
                        error_code=exc.error_code,
                    )

            ctx["output"] = {"valid": True}
        return ProviderValidationResponse(
            provider=request.provider,
            valid=True,
            message=f"{adapter.display_name} API key validated successfully.",
            error_code=None,
        )

    async def discover_models(self, request: ModelDiscoveryRequest) -> ModelDiscoveryResponse:
        adapter = get_provider_adapter(request.provider)
        api_key = request.api_key.get_secret_value()

        with trace_span(
            name="provider.discover_models",
            metadata={"provider": request.provider},
        ) as ctx:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                models = await adapter.list_models(api_key, client)

            normalized_models = sorted(
                models,
                key=lambda item: ((item.display_name or item.model_id).lower(), item.model_id.lower()),
            )
            ctx["output"] = {"model_count": len(normalized_models)}

        return ModelDiscoveryResponse(provider=request.provider, models=normalized_models)