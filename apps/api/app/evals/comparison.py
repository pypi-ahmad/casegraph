"""Provider comparison harness for selected extraction/drafting tasks.

Compares providers only on tasks the system already supports:
  - provider-backed structured extraction
  - generic summarize/classify tasks via TaskExecutionService

Comparisons are metadata- and output-shape-driven. No fake ranking
dashboards or statistical significance claims.  When a provider key
is missing, the entry records a clear incomplete state.
"""

from __future__ import annotations

import logging
import time

from sqlmodel import Session

from casegraph_agent_sdk.evals import (
    ProviderComparisonEntry,
    ProviderComparisonResult,
)

logger = logging.getLogger(__name__)


async def compare_extraction_task(
    *,
    session: Session,
    case_id: str,
    document_id: str,
    template_id: str,
    provider_selections: list[dict[str, str]],
) -> ProviderComparisonResult:
    """Compare extraction results across providers for a single document.

    Each entry in provider_selections should have:
      {"provider_id": "openai", "model_id": "gpt-4o-mini", "api_key": "sk-..."}

    Returns metadata about each provider's extraction attempt.
    Does not rank providers or claim one is better.
    """
    from app.extraction.service import ExtractionService
    from casegraph_agent_sdk.extraction import ExtractionRequest

    entries: list[ProviderComparisonEntry] = []
    service = ExtractionService(session)

    for selection in provider_selections:
        provider_id = selection.get("provider_id", "")
        model_id = selection.get("model_id", "")
        api_key = selection.get("api_key", "")
        start = time.monotonic()

        try:
            result = await service.execute(ExtractionRequest(
                template_id=template_id,
                document_id=document_id,
                case_id=case_id,
                strategy="provider_structured",
                provider=provider_id,
                model_id=model_id,
                api_key=api_key or None,
            ))
            latency = (time.monotonic() - start) * 1000
            entries.append(ProviderComparisonEntry(
                provider_id=provider_id,
                model_id=model_id,
                completed=result.run.status == "completed",
                latency_ms=latency,
                output_summary=f"{result.run.fields_extracted} field(s) extracted",
                notes=[f"Extraction status: {result.run.status}"],
            ))
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            error_msg = str(exc)[:500]
            is_key_missing = "api_key" in error_msg.lower() or "not configured" in error_msg.lower()
            entries.append(ProviderComparisonEntry(
                provider_id=provider_id,
                model_id=model_id,
                completed=False,
                error_message=error_msg,
                latency_ms=latency,
                notes=[
                    "Provider key may be missing or provider is not configured."
                    if is_key_missing
                    else f"Extraction failed: {error_msg[:200]}"
                ],
            ))

    return ProviderComparisonResult(
        task_description=f"Structured extraction with template '{template_id}'",
        entries=entries,
        notes=[
            "Comparison is output-shape-driven, not quality-ranked.",
            "Missing provider keys result in incomplete entries.",
        ],
    )


async def compare_task_execution(
    *,
    prompt: str,
    provider_selections: list[dict[str, str]],
    task_id: str = "summarize",
) -> ProviderComparisonResult:
    """Compare generic task execution across providers.

    Uses the existing TaskExecutionService for provider-backed tasks.
    Does not rank outputs or claim superiority.
    """
    from app.tasks.service import TaskExecutionService
    from casegraph_agent_sdk.tasks import (
        ProviderSelection,
        TaskExecutionRequest,
        TaskInput,
    )

    entries: list[ProviderComparisonEntry] = []
    service = TaskExecutionService()

    for selection in provider_selections:
        provider_id = selection.get("provider_id", "")
        model_id = selection.get("model_id", "")
        api_key = selection.get("api_key", "")
        start = time.monotonic()

        try:
            result, _events = await service.execute(TaskExecutionRequest(
                task_id=task_id,
                input=TaskInput(text=prompt),
                provider_selection=ProviderSelection(
                    provider=provider_id,
                    model_id=model_id,
                    api_key=api_key,
                ),
            ))
            latency = (time.monotonic() - start) * 1000
            output_text = (result.output_text or "")[:200]
            entries.append(ProviderComparisonEntry(
                provider_id=provider_id,
                model_id=model_id,
                completed=result.finish_reason.value == "completed",
                latency_ms=latency,
                output_summary=output_text,
                notes=[f"Finish reason: {result.finish_reason.value}"],
            ))
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            error_msg = str(exc)[:500]
            entries.append(ProviderComparisonEntry(
                provider_id=provider_id,
                model_id=model_id,
                completed=False,
                error_message=error_msg,
                latency_ms=latency,
                notes=["Task execution failed — check provider configuration."],
            ))

    return ProviderComparisonResult(
        task_description=f"Provider-backed '{task_id}' task",
        entries=entries,
        notes=[
            "Comparison is metadata-driven, not quality-ranked.",
            "Missing provider keys result in incomplete entries.",
            "Output summaries are truncated to 200 characters.",
        ],
    )
