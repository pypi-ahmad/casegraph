"""Route handlers for BYOK provider operations."""

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.providers.adapters.base import ProviderAdapterError
from app.providers.schemas import (
    ModelDiscoveryRequest,
    ModelDiscoveryResponse,
    ProviderErrorDetail,
    ProvidersResponse,
    ProviderValidationRequest,
    ProviderValidationResponse,
)
from app.providers.service import ProviderService


router = APIRouter(prefix="/providers", tags=["providers"])


def get_provider_service() -> ProviderService:
    return ProviderService(timeout_seconds=settings.provider_request_timeout_seconds)


@router.get("", response_model=ProvidersResponse)
async def list_providers(
    provider_service: ProviderService = Depends(get_provider_service),
) -> ProvidersResponse:
    return provider_service.list_providers()


@router.post("/validate", response_model=ProviderValidationResponse)
async def validate_provider_key(
    request: ProviderValidationRequest,
    provider_service: ProviderService = Depends(get_provider_service),
) -> ProviderValidationResponse:
    return await provider_service.validate_provider_key(request)


@router.post("/models", response_model=ModelDiscoveryResponse)
async def list_provider_models(
    request: ModelDiscoveryRequest,
    provider_service: ProviderService = Depends(get_provider_service),
) -> ModelDiscoveryResponse:
    try:
        return await provider_service.discover_models(request)
    except ProviderAdapterError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=ProviderErrorDetail(
                provider=exc.provider,
                message=exc.message,
                error_code=exc.error_code,
                upstream_status_code=exc.upstream_status_code,
                upstream_request_id=exc.upstream_request_id,
            ).model_dump(),
        ) from exc