"""OpenAI provider adapter."""

from typing import Any

import httpx

from app.providers.adapters.base import BaseProviderAdapter, CompletionResponse
from app.providers.schemas import ModelSummary, ProviderId


class OpenAIProviderAdapter(BaseProviderAdapter):
    provider_id = ProviderId.OPENAI
    display_name = "OpenAI"
    _models_url = "https://api.openai.com/v1/models"
    _chat_url = "https://api.openai.com/v1/chat/completions"

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def validate_api_key(self, api_key: str, client: httpx.AsyncClient) -> None:
        await self._get_json(client, url=self._models_url, headers=self._headers(api_key))

    async def list_models(self, api_key: str, client: httpx.AsyncClient) -> list[ModelSummary]:
        payload = await self._get_json(client, url=self._models_url, headers=self._headers(api_key))
        models: list[ModelSummary] = []

        for item in payload.get("data", []):
            model_id = item.get("id")
            if not isinstance(model_id, str) or not model_id:
                continue

            models.append(
                ModelSummary(
                    provider=self.provider_id,
                    model_id=model_id,
                    display_name=model_id,
                    created_at=self._to_iso_timestamp(item.get("created")),
                    owned_by=item.get("owned_by"),
                )
            )

        return models

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
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if temperature is not None:
            body["temperature"] = temperature

        if json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "task_output",
                    "strict": json_schema_strict,
                    "schema": json_schema,
                },
            }

        payload, response = await self._post_json(
            client, url=self._chat_url, headers=self._headers(api_key), json_body=body,
        )

        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message", {})
        usage = payload.get("usage", {})

        return CompletionResponse(
            text=message.get("content"),
            finish_reason=self._normalize_finish_reason(choice.get("finish_reason")),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            provider_request_id=self._extract_request_id(response),
            raw_response=payload,
        )

    @staticmethod
    def _normalize_finish_reason(value: str | None) -> str:
        mapping = {"stop": "completed", "length": "max_tokens", "content_filter": "content_filter"}
        return mapping.get(value or "", "unknown")