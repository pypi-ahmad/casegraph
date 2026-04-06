"""Route handlers for eval suites, runs, and capabilities."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from casegraph_agent_sdk.evals import (
    EvalCapabilitiesResponse,
    EvalRunDetailResponse,
    EvalRunRecord,
    EvalRunResponse,
    EvalSuiteDetailResponse,
    EvalSuiteListResponse,
)
from app.evals.service import (
    build_eval_capabilities,
    execute_eval_suite,
    get_eval_run,
    get_eval_suite,
    list_eval_runs,
    list_eval_suites,
)
from app.persistence.database import get_session

router = APIRouter(tags=["evals"])


@router.get("/evals/capabilities", response_model=EvalCapabilitiesResponse)
async def eval_capabilities() -> EvalCapabilitiesResponse:
    """Return metadata about configured eval and observability integrations."""
    return build_eval_capabilities()


@router.get("/evals/suites", response_model=EvalSuiteListResponse)
async def list_suites() -> EvalSuiteListResponse:
    """List all registered eval suites."""
    return list_eval_suites()


@router.get("/evals/suites/{suite_id}", response_model=EvalSuiteDetailResponse)
async def get_suite(suite_id: str) -> EvalSuiteDetailResponse:
    """Get detailed definition for a single eval suite."""
    result = get_eval_suite(suite_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Eval suite '{suite_id}' not found.")
    return result


@router.post("/evals/suites/{suite_id}/run", response_model=EvalRunResponse)
async def run_suite(
    suite_id: str,
    session: Session = Depends(get_session),
) -> EvalRunResponse:
    """Execute all cases in an eval suite."""
    return execute_eval_suite(session, suite_id)


@router.get("/evals/runs/{run_id}", response_model=EvalRunDetailResponse)
async def get_run(
    run_id: str,
    session: Session = Depends(get_session),
) -> EvalRunDetailResponse:
    """Load a specific eval run with assertion details."""
    result = get_eval_run(session, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Eval run '{run_id}' not found.")
    return result


@router.get("/evals/runs", response_model=list[EvalRunRecord])
async def list_runs(
    suite_id: str | None = None,
    session: Session = Depends(get_session),
) -> list[EvalRunRecord]:
    """List eval runs, optionally filtered by suite ID."""
    return list_eval_runs(session, suite_id=suite_id)
