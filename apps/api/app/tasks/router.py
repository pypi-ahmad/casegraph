"""Route handlers for task registry and provider-backed task execution."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from casegraph_agent_sdk.tasks import (
    ProviderSelection,
    StructuredOutputSchema,
    TaskExecutionRequest,
    TaskRegistryResponse,
)

from app.config import settings
from app.persistence.database import get_session
from app.tasks.models import TaskExecutionRecordModel
from app.tasks.registry import task_registry
from app.tasks.schemas import TaskExecuteRequestBody, TaskExecuteResponseBody
from app.tasks.service import TaskExecutionService, TaskExecutionServiceError

router = APIRouter(tags=["tasks"])


def get_task_execution_service() -> TaskExecutionService:
    return TaskExecutionService(timeout_seconds=settings.provider_request_timeout_seconds)


@router.get("/tasks", response_model=TaskRegistryResponse)
async def list_tasks() -> TaskRegistryResponse:
    """Return metadata for all registered task definitions."""
    return TaskRegistryResponse(tasks=task_registry.list_metadata())


@router.post("/tasks/execute", response_model=TaskExecuteResponseBody)
async def execute_task(
    body: TaskExecuteRequestBody,
    service: TaskExecutionService = Depends(get_task_execution_service),
    session: Session = Depends(get_session),
) -> TaskExecuteResponseBody:
    """Execute a registered task against the specified provider/model."""
    task_def = task_registry.get(body.task_id)
    if task_def is None:
        raise HTTPException(status_code=404, detail=f"Task '{body.task_id}' is not registered.")

    structured_output: StructuredOutputSchema | None = None
    if body.use_structured_output and task_def.meta.supports_structured_output:
        structured_output = StructuredOutputSchema(
            json_schema=task_def.meta.output_schema,
            strict=False,
        )

    request = TaskExecutionRequest(
        task_id=body.task_id,
        input=body.input,
        provider_selection=ProviderSelection(
            provider=body.provider,
            model_id=body.model_id,
            api_key=body.api_key.get_secret_value(),
        ),
        structured_output=structured_output,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
    )

    try:
        result, events = await service.execute(request)
    except TaskExecutionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    # Persist execution record
    record = TaskExecutionRecordModel(
        execution_id=str(uuid4()),
        task_id=result.task_id,
        provider=result.provider,
        model_id=result.model_id,
        finish_reason=result.finish_reason.value,
        output_text=result.output_text,
        structured_output_json=result.structured_output.model_dump() if result.structured_output else None,
        usage_json=result.usage.model_dump() if result.usage else None,
        error_json=result.error.model_dump() if result.error else None,
        events_json=[e.model_dump() for e in events],
        duration_ms=result.duration_ms,
        provider_request_id=result.provider_request_id,
    )
    session.add(record)
    session.commit()

    return TaskExecuteResponseBody(result=result, events=events)
