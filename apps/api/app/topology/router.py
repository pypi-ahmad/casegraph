"""Route handler for the topology endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
import httpx
from pydantic import ValidationError

from app.runtime.schemas import AgentsResponse, WorkflowsResponse
from app.runtime.service import RuntimeProxyService
from app.topology.schemas import TopologyResponse
from app.topology.service import build_topology

router = APIRouter(tags=["topology"])

_UNAVAILABLE_MSG = "Agent runtime is unavailable — cannot build topology."


def get_runtime_service() -> RuntimeProxyService:
    return RuntimeProxyService()


@router.get("/topology", response_model=TopologyResponse)
async def get_topology(
    service: RuntimeProxyService = Depends(get_runtime_service),
) -> TopologyResponse:
    """Return a normalized graph of agents, workflows, and relationships."""
    try:
        agents_res, workflows_res = await _fetch_runtime(service)
    except (httpx.HTTPError, httpx.StreamError, ValidationError) as exc:
        raise HTTPException(status_code=502, detail=_UNAVAILABLE_MSG) from exc

    return build_topology(agents_res.agents, workflows_res.workflows)


async def _fetch_runtime(
    service: RuntimeProxyService,
) -> tuple[AgentsResponse, WorkflowsResponse]:
    agents = await service.list_agents()
    workflows = await service.list_workflows()
    return agents, workflows
