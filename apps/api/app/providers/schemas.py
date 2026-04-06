"""Provider request and response schemas.

Shared contracts are imported from the SDK.  Only API-layer extras
(error-detail envelope) are defined here.
"""

from pydantic import BaseModel

from casegraph_agent_sdk import (
    CapabilityPlaceholderStatus,
    ModelDiscoveryRequest,
    ModelDiscoveryResponse,
    ModelSummary,
    ProviderCapabilityId,
    ProviderCapabilityPlaceholder,
    ProviderId,
    ProviderSummary,
    ProvidersResponse,
    ProviderValidationRequest,
    ProviderValidationResponse,
)


class ProviderErrorDetail(BaseModel):
    provider: ProviderId
    message: str
    error_code: str
    upstream_status_code: int | None = None
    upstream_request_id: str | None = None


__all__ = [
    "CapabilityPlaceholderStatus",
    "ModelDiscoveryRequest",
    "ModelDiscoveryResponse",
    "ModelSummary",
    "ProviderCapabilityId",
    "ProviderCapabilityPlaceholder",
    "ProviderErrorDetail",
    "ProviderId",
    "ProviderSummary",
    "ProvidersResponse",
    "ProviderValidationRequest",
    "ProviderValidationResponse",
]