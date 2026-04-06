"""Route handlers for workflow pack discovery and execution."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from casegraph_agent_sdk.workflow_packs import (
    WorkflowPackDetailResponse,
    WorkflowPackExecutionRequest,
    WorkflowPackListResponse,
    WorkflowPackRunResponse,
    WorkflowPackRunSummaryResponse,
)

from app.persistence.database import get_session
from app.workflow_packs.errors import WorkflowPackError
from app.workflow_packs.registry import get_workflow_pack_registry
from app.workflow_packs.service import WorkflowPackOrchestrationService

router = APIRouter(tags=["workflow-packs"])


def _handle(exc: WorkflowPackError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get(
    "/workflow-packs",
    response_model=WorkflowPackListResponse,
)
async def list_workflow_packs() -> WorkflowPackListResponse:
    return get_workflow_pack_registry().list_metadata()


@router.get(
    "/workflow-packs/{workflow_pack_id}",
    response_model=WorkflowPackDetailResponse,
)
async def get_workflow_pack(workflow_pack_id: str) -> WorkflowPackDetailResponse:
    detail = get_workflow_pack_registry().get_detail(workflow_pack_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Workflow pack '{workflow_pack_id}' not found.")
    return detail


@router.post(
    "/cases/{case_id}/workflow-packs/{workflow_pack_id}/execute",
    response_model=WorkflowPackRunResponse,
)
async def execute_workflow_pack(
    case_id: str,
    workflow_pack_id: str,
    body: WorkflowPackExecutionRequest,
    session: Session = Depends(get_session),
) -> WorkflowPackRunResponse:
    if body.case_id != case_id:
        body.case_id = case_id
    if body.workflow_pack_id != workflow_pack_id:
        body.workflow_pack_id = workflow_pack_id
    service = WorkflowPackOrchestrationService(session)
    try:
        return service.execute(body)
    except WorkflowPackError as exc:
        raise _handle(exc) from exc


@router.get(
    "/workflow-pack-runs/{run_id}",
    response_model=WorkflowPackRunSummaryResponse,
)
async def get_workflow_pack_run(
    run_id: str,
    session: Session = Depends(get_session),
) -> WorkflowPackRunSummaryResponse:
    service = WorkflowPackOrchestrationService(session)
    try:
        return service.get_run(run_id)
    except WorkflowPackError as exc:
        raise _handle(exc) from exc


@router.get(
    "/cases/{case_id}/workflow-pack-runs",
    response_model=list[WorkflowPackRunResponse],
)
async def list_case_workflow_pack_runs(
    case_id: str,
    session: Session = Depends(get_session),
) -> list[WorkflowPackRunResponse]:
    service = WorkflowPackOrchestrationService(session)
    runs = service.list_runs(case_id)
    return [
        WorkflowPackRunResponse(
            success=run.status not in ("failed", "blocked"),
            message=f"Run status: {run.status}.",
            run=run,
        )
        for run in runs
    ]
