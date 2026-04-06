"""Route handlers for automation execution runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from casegraph_agent_sdk.execution import (
    ApproveCheckpointRequest,
    AutomationCheckpointResponse,
    AutomationExecutionRequest,
    AutomationResumeRequest,
    AutomationRunArtifactsResponse,
    AutomationRunCheckpointsResponse,
    AutomationRunDetailResponse,
    AutomationRunEventsResponse,
    AutomationRunListResponse,
    AutomationRunResponse,
    AutomationRunStepsResponse,
    BlockCheckpointRequest,
    SkipCheckpointRequest,
)

from app.automation.service import AutomationService
from app.config import settings
from app.execution.errors import AutomationExecutionError
from app.execution.service import AutomationExecutionService
from app.persistence.database import get_session

router = APIRouter(tags=["automation-execution"])

_automation_service = AutomationService(
    runtime_base_url=settings.agent_runtime_url,
    timeout_seconds=settings.agent_runtime_timeout_seconds,
)


def _handle(exc: AutomationExecutionError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _get_service(session: Session = Depends(get_session)) -> AutomationExecutionService:
    from app.automation.service import playwright_mcp_url

    return AutomationExecutionService(
        session,
        playwright_mcp_url=playwright_mcp_url(),
        automation_capabilities_loader=_automation_service.get_capabilities,
    )


@router.post(
    "/submission-drafts/{draft_id}/execute",
    response_model=AutomationRunResponse,
)
async def execute_automation_plan(
    draft_id: str,
    body: AutomationExecutionRequest,
    service: AutomationExecutionService = Depends(_get_service),
) -> AutomationRunResponse:
    if body.draft_id != draft_id:
        body.draft_id = draft_id
    try:
        return await service.execute(body)
    except AutomationExecutionError as exc:
        raise _handle(exc) from exc


@router.get(
    "/cases/{case_id}/automation-runs",
    response_model=AutomationRunListResponse,
)
async def list_case_automation_runs(
    case_id: str,
    service: AutomationExecutionService = Depends(_get_service),
) -> AutomationRunListResponse:
    try:
        return service.list_runs_for_case(case_id)
    except AutomationExecutionError as exc:
        raise _handle(exc) from exc


@router.get(
    "/automation-runs/{run_id}",
    response_model=AutomationRunResponse,
)
async def get_automation_run(
    run_id: str,
    service: AutomationExecutionService = Depends(_get_service),
) -> AutomationRunResponse:
    try:
        return service.get_run(run_id)
    except AutomationExecutionError as exc:
        raise _handle(exc) from exc


@router.get(
    "/automation-runs/{run_id}/detail",
    response_model=AutomationRunDetailResponse,
)
async def get_automation_run_detail(
    run_id: str,
    service: AutomationExecutionService = Depends(_get_service),
) -> AutomationRunDetailResponse:
    try:
        return service.get_run_detail(run_id)
    except AutomationExecutionError as exc:
        raise _handle(exc) from exc


@router.get(
    "/automation-runs/{run_id}/steps",
    response_model=AutomationRunStepsResponse,
)
async def get_automation_run_steps(
    run_id: str,
    service: AutomationExecutionService = Depends(_get_service),
) -> AutomationRunStepsResponse:
    try:
        return service.get_run_steps(run_id)
    except AutomationExecutionError as exc:
        raise _handle(exc) from exc


@router.get(
    "/automation-runs/{run_id}/artifacts",
    response_model=AutomationRunArtifactsResponse,
)
async def get_automation_run_artifacts(
    run_id: str,
    service: AutomationExecutionService = Depends(_get_service),
) -> AutomationRunArtifactsResponse:
    try:
        return service.get_run_artifacts(run_id)
    except AutomationExecutionError as exc:
        raise _handle(exc) from exc


@router.get(
    "/automation-runs/{run_id}/events",
    response_model=AutomationRunEventsResponse,
)
async def get_automation_run_events(
    run_id: str,
    service: AutomationExecutionService = Depends(_get_service),
) -> AutomationRunEventsResponse:
    try:
        return service.get_run_events(run_id)
    except AutomationExecutionError as exc:
        raise _handle(exc) from exc


@router.get(
    "/automation-runs/{run_id}/checkpoints",
    response_model=AutomationRunCheckpointsResponse,
)
async def get_automation_run_checkpoints(
    run_id: str,
    service: AutomationExecutionService = Depends(_get_service),
) -> AutomationRunCheckpointsResponse:
    try:
        return service.get_run_checkpoints(run_id)
    except AutomationExecutionError as exc:
        raise _handle(exc) from exc


@router.post(
    "/automation-runs/{run_id}/checkpoints/{checkpoint_id}/approve",
    response_model=AutomationCheckpointResponse,
)
async def approve_automation_checkpoint(
    run_id: str,
    checkpoint_id: str,
    body: ApproveCheckpointRequest,
    service: AutomationExecutionService = Depends(_get_service),
) -> AutomationCheckpointResponse:
    try:
        return service.approve_checkpoint(run_id, checkpoint_id, body)
    except AutomationExecutionError as exc:
        raise _handle(exc) from exc


@router.post(
    "/automation-runs/{run_id}/checkpoints/{checkpoint_id}/skip",
    response_model=AutomationCheckpointResponse,
)
async def skip_automation_checkpoint(
    run_id: str,
    checkpoint_id: str,
    body: SkipCheckpointRequest,
    service: AutomationExecutionService = Depends(_get_service),
) -> AutomationCheckpointResponse:
    try:
        return service.skip_checkpoint(run_id, checkpoint_id, body)
    except AutomationExecutionError as exc:
        raise _handle(exc) from exc


@router.post(
    "/automation-runs/{run_id}/checkpoints/{checkpoint_id}/block",
    response_model=AutomationCheckpointResponse,
)
async def block_automation_checkpoint(
    run_id: str,
    checkpoint_id: str,
    body: BlockCheckpointRequest,
    service: AutomationExecutionService = Depends(_get_service),
) -> AutomationCheckpointResponse:
    try:
        return service.block_checkpoint(run_id, checkpoint_id, body)
    except AutomationExecutionError as exc:
        raise _handle(exc) from exc


@router.post(
    "/automation-runs/{run_id}/resume",
    response_model=AutomationRunResponse,
)
async def resume_automation_run(
    run_id: str,
    body: AutomationResumeRequest,
    service: AutomationExecutionService = Depends(_get_service),
) -> AutomationRunResponse:
    try:
        return await service.resume(run_id, body)
    except AutomationExecutionError as exc:
        raise _handle(exc) from exc
