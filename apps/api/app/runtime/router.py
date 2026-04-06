"""Route handlers for runtime metadata (proxied from agent-runtime)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
import httpx
from pydantic import ValidationError

from app.runtime.schemas import AgentsResponse, WorkflowsResponse
from app.runtime.service import RuntimeProxyService

router = APIRouter(tags=["runtime"])

_UNAVAILABLE_MSG = "Agent runtime is unavailable."


def get_runtime_service() -> RuntimeProxyService:
    return RuntimeProxyService()


@router.get("/agents", response_model=AgentsResponse)
@router.get("/runtime/agents", response_model=AgentsResponse, include_in_schema=False)
async def list_agents(
    service: RuntimeProxyService = Depends(get_runtime_service),
) -> AgentsResponse:
    try:
        return await service.list_agents()
    except (httpx.HTTPError, httpx.StreamError, ValidationError) as exc:
        raise HTTPException(status_code=502, detail=_UNAVAILABLE_MSG) from exc


@router.get("/workflows", response_model=WorkflowsResponse)
@router.get("/runtime/workflows", response_model=WorkflowsResponse, include_in_schema=False)
async def list_workflows(
    service: RuntimeProxyService = Depends(get_runtime_service),
) -> WorkflowsResponse:
    try:
        return await service.list_workflows()
    except (httpx.HTTPError, httpx.StreamError, ValidationError) as exc:
        raise HTTPException(status_code=502, detail=_UNAVAILABLE_MSG) from exc
