"""Task execution service — dispatches generic tasks to provider adapters."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from casegraph_agent_sdk.tasks import (
    FinishReason,
    ProviderSelection,
    StructuredOutputResult,
    StructuredOutputSchema,
    TaskExecutionError,
    TaskExecutionEvent,
    TaskExecutionRequest,
    TaskExecutionResult,
    UsageMetadata,
)

from app.observability.tracing import trace_span
from app.providers.adapters.base import ProviderAdapterError
from app.providers.registry import get_provider_adapter
from app.providers.schemas import ProviderId
from app.tasks.registry import TaskDefinition, task_registry


class TaskExecutionServiceError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code

from app.persistence.database import isoformat_utc, utcnow


def _event(kind: str, **metadata: Any) -> TaskExecutionEvent:
    return TaskExecutionEvent(kind=kind, timestamp=isoformat_utc(utcnow()), metadata=metadata)


class TaskExecutionService:
    """Executes registered tasks against provider adapters."""

    def __init__(self, *, timeout_seconds: float = 120.0) -> None:
        self._timeout = httpx.Timeout(timeout_seconds, connect=10.0)

    async def execute(self, request: TaskExecutionRequest) -> tuple[TaskExecutionResult, list[TaskExecutionEvent]]:
        """Execute a task and return (result, events)."""
        events: list[TaskExecutionEvent] = []

        # --- Resolve task definition ---
        task_def = task_registry.get(request.task_id)
        if task_def is None:
            raise TaskExecutionServiceError(
                f"Task '{request.task_id}' is not registered.", status_code=404,
            )
        events.append(_event("task_selected", task_id=request.task_id, category=task_def.meta.category))

        # --- Build prompts ---
        user_prompt = task_def.build_user_prompt(
            request.input.text, request.input.parameters,
        )
        system_prompt = task_def.system_prompt

        # --- Build structured output schema if requested ---
        structured_output = self._resolve_structured_output(request, task_def)

        result, completion_events = await self.execute_prepared_prompt(
            task_id=request.task_id,
            provider_selection=request.provider_selection,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            structured_output=structured_output,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            trace_name="task.execute",
            trace_label=f"task.{request.task_id}",
            trace_metadata={
                "task_id": request.task_id,
                "provider": request.provider_selection.provider,
                "model_id": request.provider_selection.model_id,
            },
            trace_input_data={"text": request.input.text},
        )

        return result, events + completion_events

    async def execute_prepared_prompt(
        self,
        *,
        task_id: str,
        provider_selection: ProviderSelection,
        system_prompt: str,
        user_prompt: str,
        structured_output: StructuredOutputSchema | None,
        max_tokens: int | None,
        temperature: float | None,
        trace_name: str,
        trace_label: str,
        trace_metadata: dict[str, Any],
        trace_input_data: dict[str, Any] | None = None,
    ) -> tuple[TaskExecutionResult, list[TaskExecutionEvent]]:
        """Execute a prepared prompt through the shared provider-backed path."""
        events: list[TaskExecutionEvent] = []

        # --- Resolve provider adapter ---
        try:
            provider_id = ProviderId(provider_selection.provider)
        except ValueError:
            raise TaskExecutionServiceError(
                f"Unknown provider: {provider_selection.provider}", status_code=400,
            )

        adapter = get_provider_adapter(provider_id)
        model_id = provider_selection.model_id
        events.append(_event(
            "provider_resolved",
            provider=provider_id.value,
            model_id=model_id,
        ))
        events.append(_event("model_invoked", provider=provider_id.value, model_id=model_id))

        start_ms = time.monotonic_ns() // 1_000_000

        with trace_span(
            name=trace_name,
            trace_name=trace_label,
            metadata=trace_metadata,
            input_data=trace_input_data,
        ) as ctx:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    completion = await adapter.complete(
                        provider_selection.api_key,
                        client,
                        model=model_id,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        json_schema=structured_output.json_schema if structured_output is not None else None,
                        json_schema_strict=structured_output.strict if structured_output is not None else False,
                    )
            except ProviderAdapterError as exc:
                duration_ms = (time.monotonic_ns() // 1_000_000) - start_ms
                ctx["status"] = "error"
                ctx["output"] = {"error_code": exc.error_code}
                error = TaskExecutionError(
                    error_code=exc.error_code,
                    message=exc.message,
                    provider=provider_id.value,
                    model_id=model_id,
                    recoverable=exc.error_code in {"upstream_timeout", "rate_limited"},
                    upstream_status_code=exc.upstream_status_code,
                )
                events.append(_event(
                    "model_failed",
                    error_code=exc.error_code,
                    message=exc.message,
                    duration_ms=duration_ms,
                ))
                return TaskExecutionResult(
                    task_id=task_id,
                    provider=provider_id.value,
                    model_id=model_id,
                    finish_reason=FinishReason.ERROR,
                    error=error,
                    duration_ms=duration_ms,
                ), events

            duration_ms = (time.monotonic_ns() // 1_000_000) - start_ms

            # --- Normalize result ---
            finish_reason = FinishReason(completion.finish_reason) if completion.finish_reason in {r.value for r in FinishReason} else FinishReason.UNKNOWN
            usage = UsageMetadata(
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                total_tokens=completion.total_tokens,
            )

            parsed_structured_output = None
            if structured_output is not None and completion.text is not None:
                parsed_structured_output = self._parse_structured_output(
                    completion.text,
                    structured_output.json_schema,
                )
                events.append(_event(
                    "structured_output_validated",
                    schema_valid=parsed_structured_output.schema_valid,
                    validation_errors=parsed_structured_output.validation_errors,
                ))

            events.append(_event(
                "model_completed",
                finish_reason=finish_reason.value,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                duration_ms=duration_ms,
                provider_request_id=completion.provider_request_id,
            ))

            ctx["output"] = {
                "finish_reason": finish_reason.value,
                "input_tokens": completion.input_tokens,
                "output_tokens": completion.output_tokens,
                "duration_ms": duration_ms,
            }

        return TaskExecutionResult(
            task_id=task_id,
            provider=provider_id.value,
            model_id=model_id,
            finish_reason=finish_reason,
            output_text=completion.text,
            structured_output=parsed_structured_output,
            usage=usage,
            duration_ms=duration_ms,
            provider_request_id=completion.provider_request_id,
        ), events

    def _resolve_structured_output(
        self,
        request: TaskExecutionRequest,
        task_def: TaskDefinition,
    ) -> StructuredOutputSchema | None:
        """Resolve the structured output contract, if applicable."""
        if request.structured_output is not None:
            return request.structured_output

        if task_def.meta.supports_structured_output and task_def.meta.output_schema:
            return StructuredOutputSchema(
                json_schema=task_def.meta.output_schema,
                strict=False,
            )

        return None

    def _parse_structured_output(
        self,
        raw_text: str,
        schema: dict[str, Any],
    ) -> StructuredOutputResult:
        """Attempt to parse the raw text as JSON and validate loosely against schema."""
        try:
            parsed = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError) as exc:
            return StructuredOutputResult(
                parsed=None,
                raw_text=raw_text,
                schema_valid=False,
                validation_errors=[f"JSON parse error: {exc}"],
            )

        if not isinstance(parsed, dict):
            return StructuredOutputResult(
                parsed=None,
                raw_text=raw_text,
                schema_valid=False,
                validation_errors=["Expected a JSON object, got a different type."],
            )

        # Basic required-field validation (no full JSON Schema validator dependency)
        errors: list[str] = []
        required = schema.get("required", [])
        for field_name in required:
            if field_name not in parsed:
                errors.append(f"Missing required field: {field_name}")

        return StructuredOutputResult(
            parsed=parsed,
            raw_text=raw_text,
            schema_valid=len(errors) == 0,
            validation_errors=errors,
        )
