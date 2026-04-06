"""Proxy service that fetches runtime metadata from the agent-runtime."""

from __future__ import annotations

import httpx
from casegraph_agent_sdk.agents import AgentsResponse
from casegraph_workflows.schemas import WorkflowsResponse

from app.config import settings


class RuntimeProxyService:
    def __init__(self) -> None:
        self._base_url = settings.agent_runtime_url.rstrip("/")
        self._timeout = httpx.Timeout(settings.agent_runtime_timeout_seconds)

    async def list_agents(self) -> AgentsResponse:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/agents")
            response.raise_for_status()
            return AgentsResponse.model_validate(response.json())

    async def list_workflows(self) -> WorkflowsResponse:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/workflows")
            response.raise_for_status()
            return WorkflowsResponse.model_validate(response.json())
