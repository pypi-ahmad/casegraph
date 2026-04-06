"""Agent runtime — FastAPI entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from casegraph_agent_sdk.agents import AgentsResponse
from casegraph_workflows.schemas import (
    WorkflowDefinition,
    WorkflowStepDefinition,
    WorkflowsResponse,
)
from casegraph_workflows.registry import workflow_registry

from app.agents import IntakeAgent, ReviewAgent, RouterAgent
from app.config import settings
from app.graphs.supervisor import build_supervisor_graph
from app.registry import agent_registry
from app.services import RuntimeService
from app.tools.registry import tool_registry
from app.tools.playwright_mcp import PlaywrightNavigateTool, PlaywrightSnapshotTool
from app.tools.computer_use import ComputerUseScreenshotTool

_supervisor_graph = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _supervisor_graph

    # -- Register agents ----------------------------------------------------
    agent_registry.register(IntakeAgent())
    agent_registry.register(RouterAgent())
    agent_registry.register(ReviewAgent())

    # -- Register automation tools ------------------------------------------
    tool_registry.register(PlaywrightNavigateTool())
    tool_registry.register(PlaywrightSnapshotTool())
    tool_registry.register(ComputerUseScreenshotTool())

    # -- Register placeholder workflows -------------------------------------
    workflow_registry.register(
        WorkflowDefinition(
            id="intake-review",
            display_name="Intake → Review",
            description="Two-step workflow: intake then review.",
            steps=[
                WorkflowStepDefinition(
                    id="step-1",
                    display_name="Intake",
                    agent_id="intake",
                    description="Receive and validate the incoming request.",
                ),
                WorkflowStepDefinition(
                    id="step-2",
                    display_name="Review",
                    agent_id="review",
                    description="Review the intake output.",
                    depends_on=["step-1"],
                ),
            ],
        )
    )
    workflow_registry.register(
        WorkflowDefinition(
            id="intake-route-review",
            display_name="Intake -> Route -> Review",
            description="Three-step workflow: intake, route, then review.",
            steps=[
                WorkflowStepDefinition(
                    id="step-1",
                    display_name="Intake",
                    agent_id="intake",
                    description="Receive the incoming request.",
                ),
                WorkflowStepDefinition(
                    id="step-2",
                    display_name="Route",
                    agent_id="router",
                    description="Determine the appropriate downstream agent.",
                    depends_on=["step-1"],
                ),
                WorkflowStepDefinition(
                    id="step-3",
                    display_name="Review",
                    agent_id="review",
                    description="Review the routed output.",
                    depends_on=["step-2"],
                ),
            ],
        )
    )

    # -- Build supervisor graph ---------------------------------------------
    _supervisor_graph = build_supervisor_graph(agent_registry.list_agents())

    yield

    _supervisor_graph = None


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

_service = RuntimeService()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/agents", response_model=AgentsResponse)
async def list_agents() -> AgentsResponse:
    return _service.list_agents()


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict:
    meta = _service.get_agent(agent_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return meta.model_dump()


@app.get("/workflows", response_model=WorkflowsResponse)
async def list_workflows() -> WorkflowsResponse:
    return _service.list_workflows()


@app.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str) -> dict:
    definition = _service.get_workflow(workflow_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return definition.model_dump()


@app.get("/tools")
async def list_tools() -> dict:
    return {"tools": [t.model_dump() for t in tool_registry.list_metadata()]}
