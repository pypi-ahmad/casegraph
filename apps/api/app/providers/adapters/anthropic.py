"""Anthropic provider adapter."""

import json
from typing import Any

import httpx

from app.providers.adapters.base import BaseProviderAdapter, CompletionResponse
from app.providers.schemas import ModelSummary, ProviderId


class AnthropicProviderAdapter(BaseProviderAdapter):
    provider_id = ProviderId.ANTHROPIC
    display_name = "Anthropic"
    _models_url = "https://api.anthropic.com/v1/models"
    _messages_url = "https://api.anthropic.com/v1/messages"
    _api_version = "2023-06-01"

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "x-api-key": api_key,
            "anthropic-version": self._api_version,
            "content-type": "application/json",
            "accept": "application/json",
        }

    async def validate_api_key(self, api_key: str, client: httpx.AsyncClient) -> None:
        await self._get_json(
            client,
            url=self._models_url,
            headers=self._headers(api_key),
            params={"limit": 1},
        )

    async def list_models(self, api_key: str, client: httpx.AsyncClient) -> list[ModelSummary]:
        models: list[ModelSummary] = []
        after_id: str | None = None

        while True:
            params: dict[str, str | int] = {"limit": 100}
            if after_id is not None:
                params["after_id"] = after_id

            payload = await self._get_json(
                client,
                url=self._models_url,
                headers=self._headers(api_key),
                params=params,
            )

            data = payload.get("data", [])
            for item in data:
                model_id = item.get("id")
                if not isinstance(model_id, str) or not model_id:
                    continue

                models.append(
                    ModelSummary(
                        provider=self.provider_id,
                        model_id=model_id,
                        display_name=item.get("display_name") or model_id,
                        created_at=item.get("created_at"),
                        owned_by="anthropic",
                        input_token_limit=item.get("max_input_tokens"),
                        output_token_limit=item.get("max_tokens"),
                        capabilities=self._extract_capabilities(item.get("capabilities")),
                    )
                )

            if payload.get("has_more") is not True:
                break

            last_id = payload.get("last_id")
            if not isinstance(last_id, str) or not last_id:
                break
            after_id = last_id

        return models

    def _extract_capabilities(self, capabilities: Any) -> list[str]:
        if not isinstance(capabilities, dict):
            return []

        normalized_capabilities: list[str] = []
        for key, value in capabilities.items():
            if isinstance(value, dict) and value.get("supported") is True:
                normalized_capabilities.append(key)

        return sorted(normalized_capabilities)

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
        json_schema_strict: bool = False,  # noqa: ARG002
    ) -> CompletionResponse:
        body: dict[str, Any] = {
            "model": model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": max_tokens or 4096,
        }
        if temperature is not None:
            body["temperature"] = temperature

        if json_schema is not None:
            # Anthropic tool-use path for structured output
            body["tools"] = [
                {
                    "name": "task_output",
                    "description": "Return the structured result.",
                    "input_schema": json_schema,
                }
            ]
            body["tool_choice"] = {"type": "tool", "name": "task_output"}

        payload, response = await self._post_json(
            client, url=self._messages_url, headers=self._headers(api_key), json_body=body,
        )

        text: str | None = None
        structured_text: str | None = None
        for block in payload.get("content", []):
            if block.get("type") == "text":
                text = block.get("text")
            elif block.get("type") == "tool_use" and block.get("name") == "task_output":
                structured_text = json.dumps(block.get("input", {}))

        usage = payload.get("usage", {})

        return CompletionResponse(
            text=structured_text or text,
            finish_reason=self._normalize_finish_reason(payload.get("stop_reason")),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            total_tokens=(usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0) or None,
            provider_request_id=self._extract_request_id(response),
            raw_response=payload,
        )

    @staticmethod
    def _normalize_finish_reason(value: str | None) -> str:
        mapping = {"end_turn": "completed", "tool_use": "completed", "max_tokens": "max_tokens"}
        return mapping.get(value or "", "unknown")