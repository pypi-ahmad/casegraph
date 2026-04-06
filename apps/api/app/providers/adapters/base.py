"""Shared adapter primitives for provider validation, model discovery, and completion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
import re
from typing import Any

import httpx

from app.providers.schemas import ModelSummary, ProviderId


REQUEST_ID_HEADERS = ("x-request-id", "request-id", "x-goog-request-id")


@dataclass(slots=True)
class ProviderAdapterError(Exception):
    provider: ProviderId
    error_code: str
    message: str
    http_status: int
    upstream_status_code: int | None = None
    upstream_request_id: str | None = None


@dataclass(slots=True)
class CompletionResponse:
    """Normalized provider completion response."""

    text: str | None = None
    finish_reason: str = "unknown"
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    provider_request_id: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


class BaseProviderAdapter(ABC):
    provider_id: ProviderId
    display_name: str

    @abstractmethod
    async def validate_api_key(self, api_key: str, client: httpx.AsyncClient) -> None:
        """Perform the lightest supported validation call for the provider."""

    @abstractmethod
    async def list_models(self, api_key: str, client: httpx.AsyncClient) -> list[ModelSummary]:
        """Fetch and normalize models from the provider."""

    @abstractmethod
    async def complete(
        self,
        api_key: str,
        client: httpx.AsyncClient,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
        json_schema: dict[str, Any] | None = None,
        json_schema_strict: bool = False,
    ) -> CompletionResponse:
        """Execute a text completion / chat completion request."""

    async def _post_json(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
    ) -> tuple[dict[str, Any], httpx.Response]:
        try:
            response = await client.post(url, headers=headers, json=json_body)
        except httpx.TimeoutException as exc:
            raise ProviderAdapterError(
                provider=self.provider_id,
                error_code="upstream_timeout",
                message=f"{self.display_name} did not respond in time.",
                http_status=504,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderAdapterError(
                provider=self.provider_id,
                error_code="upstream_unavailable",
                message=f"Unable to reach {self.display_name}.",
                http_status=502,
            ) from exc

        if response.is_error:
            raise self._build_error(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderAdapterError(
                provider=self.provider_id,
                error_code="invalid_upstream_response",
                message=f"{self.display_name} returned an invalid response.",
                http_status=502,
            ) from exc

        return payload, response

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await client.get(url, headers=headers, params=params)
        except httpx.TimeoutException as exc:
            raise ProviderAdapterError(
                provider=self.provider_id,
                error_code="upstream_timeout",
                message=f"{self.display_name} did not respond in time.",
                http_status=504,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderAdapterError(
                provider=self.provider_id,
                error_code="upstream_unavailable",
                message=f"Unable to reach {self.display_name}.",
                http_status=502,
            ) from exc

        if response.is_error:
            raise self._build_error(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderAdapterError(
                provider=self.provider_id,
                error_code="invalid_upstream_response",
                message=f"{self.display_name} returned an invalid response.",
                http_status=502,
            ) from exc

        if not isinstance(payload, dict):
            raise ProviderAdapterError(
                provider=self.provider_id,
                error_code="invalid_upstream_response",
                message=f"{self.display_name} returned an unexpected response shape.",
                http_status=502,
            )

        return payload

    def _build_error(self, response: httpx.Response) -> ProviderAdapterError:
        request_id = self._extract_request_id(response)
        upstream_status = response.status_code

        if upstream_status in {401, 403}:
            return ProviderAdapterError(
                provider=self.provider_id,
                error_code="authentication_failed",
                message=f"{self.display_name} rejected the API key.",
                http_status=401,
                upstream_status_code=upstream_status,
                upstream_request_id=request_id,
            )

        if upstream_status == 429:
            return ProviderAdapterError(
                provider=self.provider_id,
                error_code="rate_limited",
                message=f"{self.display_name} rate limited the request.",
                http_status=429,
                upstream_status_code=upstream_status,
                upstream_request_id=request_id,
            )

        if 400 <= upstream_status < 500:
            return ProviderAdapterError(
                provider=self.provider_id,
                error_code="provider_request_rejected",
                message=f"{self.display_name} rejected the request.",
                http_status=400,
                upstream_status_code=upstream_status,
                upstream_request_id=request_id,
            )

        return ProviderAdapterError(
            provider=self.provider_id,
            error_code="upstream_unavailable",
            message=f"{self.display_name} is unavailable right now.",
            http_status=502,
            upstream_status_code=upstream_status,
            upstream_request_id=request_id,
        )

    def _extract_request_id(self, response: httpx.Response) -> str | None:
        for header_name in REQUEST_ID_HEADERS:
            header_value = response.headers.get(header_name)
            if header_value:
                return header_value
        return None

    def _to_iso_timestamp(self, value: int | float | None) -> str | None:
        if value is None:
            return None
        return datetime.fromtimestamp(value, tz=UTC).isoformat()

    def _to_snake_case(self, value: str) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()