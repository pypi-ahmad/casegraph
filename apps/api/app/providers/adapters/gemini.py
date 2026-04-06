"""Gemini provider adapter."""

from typing import Any

import httpx

from app.providers.adapters.base import BaseProviderAdapter, CompletionResponse
from app.providers.schemas import ModelSummary, ProviderId


class GeminiProviderAdapter(BaseProviderAdapter):
    provider_id = ProviderId.GEMINI
    display_name = "Gemini"
    _models_url = "https://generativelanguage.googleapis.com/v1beta/models"
    _generate_base = "https://generativelanguage.googleapis.com/v1beta/models"

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "x-goog-api-key": api_key,
            "accept": "application/json",
        }

    async def validate_api_key(self, api_key: str, client: httpx.AsyncClient) -> None:
        await self._get_json(
            client,
            url=self._models_url,
            headers=self._headers(api_key),
            params={"pageSize": 1},
        )

    async def list_models(self, api_key: str, client: httpx.AsyncClient) -> list[ModelSummary]:
        models: list[ModelSummary] = []
        page_token: str | None = None

        while True:
            params: dict[str, str | int] = {"pageSize": 1000}
            if page_token is not None:
                params["pageToken"] = page_token

            payload = await self._get_json(
                client,
                url=self._models_url,
                headers=self._headers(api_key),
                params=params,
            )

            for item in payload.get("models", []):
                raw_name = item.get("name")
                if not isinstance(raw_name, str) or not raw_name:
                    continue

                model_id = self._normalize_model_id(raw_name, item.get("baseModelId"))
                models.append(
                    ModelSummary(
                        provider=self.provider_id,
                        model_id=model_id,
                        display_name=item.get("displayName") or model_id,
                        description=item.get("description"),
                        input_token_limit=item.get("inputTokenLimit"),
                        output_token_limit=item.get("outputTokenLimit"),
                        capabilities=self._extract_capabilities(item.get("supportedGenerationMethods")),
                    )
                )

            next_page_token = payload.get("nextPageToken")
            if not isinstance(next_page_token, str) or not next_page_token:
                break
            page_token = next_page_token

        return models

    def _normalize_model_id(self, raw_name: str, base_model_id: Any) -> str:
        if isinstance(base_model_id, str) and base_model_id:
            return base_model_id
        return raw_name.removeprefix("models/")

    def _extract_capabilities(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []

        capabilities = [self._to_snake_case(item) for item in value if isinstance(item, str) and item]
        return sorted(set(capabilities))

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
        url = f"{self._generate_base}/{model}:generateContent"
        headers = self._headers(api_key)
        headers["content-type"] = "application/json"

        body: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
        }

        generation_config: dict[str, Any] = {}
        if max_tokens is not None:
            generation_config["maxOutputTokens"] = max_tokens
        if temperature is not None:
            generation_config["temperature"] = temperature

        if json_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = json_schema

        if generation_config:
            body["generationConfig"] = generation_config

        payload, response = await self._post_json(
            client, url=url, headers=headers, json_body=body,
        )

        candidates = payload.get("candidates", [])
        candidate = candidates[0] if candidates else {}
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        text = parts[0].get("text") if parts else None

        usage = payload.get("usageMetadata", {})

        return CompletionResponse(
            text=text,
            finish_reason=self._normalize_finish_reason(candidate.get("finishReason")),
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
            total_tokens=usage.get("totalTokenCount"),
            provider_request_id=self._extract_request_id(response),
            raw_response=payload,
        )

    @staticmethod
    def _normalize_finish_reason(value: str | None) -> str:
        mapping = {"STOP": "completed", "MAX_TOKENS": "max_tokens", "SAFETY": "content_filter"}
        return mapping.get(value or "", "unknown")