"""Eval service — capabilities, suite management, and run execution.

Composes:
  - eval/observability capabilities (existing)
  - eval suite registry (new)
  - workflow regression runner (new)
  - eval run persistence (new)
  - Langfuse eval boundary capture (optional)
"""

from __future__ import annotations

import logging
from datetime import UTC
from uuid import uuid4

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.evals import (
    BenchmarkSuiteMeta,
    EvalCapabilitiesResponse,
    EvalCaseResult,
    EvalRunDetailResponse,
    EvalRunRecord,
    EvalRunResponse,
    EvalRunStatus,
    EvalSuiteDefinition,
    EvalSuiteDetailResponse,
    EvalSuiteListResponse,
    IntegrationInfo,
)
from app.evals.models import EvalRunModel
from app.evals.regression import run_eval_suite
from app.evals.suites import get_eval_suite_registry
from app.observability.langfuse_client import get_langfuse, langfuse_configured
from app.persistence.database import isoformat_utc, utcnow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Promptfoo benchmark suites (static metadata — matches YAML configs)
# ---------------------------------------------------------------------------

_BENCHMARK_SUITES: list[BenchmarkSuiteMeta] = [
    BenchmarkSuiteMeta(
        id="provider-comparison",
        display_name="Provider Comparison",
        category="provider_comparison",
        description="Compares output quality across OpenAI, Anthropic, and Gemini for foundation-level prompts.",
        config_path="services/evals/promptfoo/provider-comparison.yaml",
    ),
    BenchmarkSuiteMeta(
        id="retrieval-eval",
        display_name="Retrieval Quality",
        category="retrieval",
        description="Evaluates CaseGraph knowledge-search retrieval quality against seed queries.",
        config_path="services/evals/promptfoo/retrieval-eval.yaml",
    ),
    BenchmarkSuiteMeta(
        id="agent-workflow-eval",
        display_name="Agent/Workflow Output",
        category="agent_workflow",
        description="Validates agent and workflow metadata endpoints return well-structured data.",
        config_path="services/evals/promptfoo/agent-workflow-eval.yaml",
    ),
    BenchmarkSuiteMeta(
        id="workflow-pack-extraction-eval",
        display_name="Workflow Pack Extraction Eval",
        category="agent_workflow",
        description="Evaluates provider-backed extraction subtasks used in workflow packs.",
        config_path="services/evals/promptfoo/workflow-pack-extraction-eval.yaml",
    ),
]

_LIMITATIONS: list[str] = [
    "Promptfoo configs use seed datasets — not real domain benchmarks.",
    "Workflow regression suites contain seed fixtures (8 fixtures, 8 eval cases) — not full benchmark coverage.",
    "Provider comparison evals require live API keys for OpenAI, Anthropic, and/or Gemini.",
    "Retrieval evals require the CaseGraph API running with indexed documents.",
    "Langfuse traces require a running Langfuse instance (local Docker or cloud).",
    "No CI pipeline for automated eval runs yet.",
    "No production red-team, adversarial, or domain-specific eval suites.",
    "Extraction pass always shows completed_partial in seed fixtures since no extraction runs exist.",
    "Provider comparison results are metadata-driven, not quality-ranked.",
]


def build_eval_capabilities() -> EvalCapabilitiesResponse:
    integrations: list[IntegrationInfo] = [
        IntegrationInfo(
            id="promptfoo",
            display_name="Promptfoo",
            status="available",
            notes=[
                "4 benchmark configs available (provider-comparison, retrieval, agent-workflow, workflow-pack-extraction).",
                "Run locally via: cd services/evals && npx promptfoo@latest eval -c promptfoo/<config>.yaml",
            ],
        ),
        IntegrationInfo(
            id="langfuse",
            display_name="Langfuse",
            status="configured" if langfuse_configured() else "not_configured",
            notes=[
                "Instrumentation hooks wired at provider validation/discovery and knowledge search boundaries.",
                "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable trace capture.",
            ]
            + (["Langfuse client is active and sending traces."] if langfuse_configured() else []),
        ),
        IntegrationInfo(
            id="workflow_regression",
            display_name="Workflow Regression Runner",
            status="configured",
            notes=[
                "3 workflow regression suites (medical insurance, general insurance, tax).",
                "8 eval cases with deterministic assertions against real workflow pack execution.",
                "Run via POST /evals/suites/{suite_id}/run.",
            ],
        ),
        IntegrationInfo(
            id="opentelemetry",
            display_name="OpenTelemetry",
            status="not_configured",
            notes=[
                "Structural placeholder only — not instrumented in this step.",
            ],
        ),
    ]

    return EvalCapabilitiesResponse(
        integrations=integrations,
        benchmark_suites=_BENCHMARK_SUITES,
        limitations=_LIMITATIONS,
    )


# ---------------------------------------------------------------------------
# Suite management
# ---------------------------------------------------------------------------


def list_eval_suites() -> EvalSuiteListResponse:
    return get_eval_suite_registry().list_response()


def get_eval_suite(suite_id: str) -> EvalSuiteDetailResponse | None:
    suite = get_eval_suite_registry().get(suite_id)
    if suite is None:
        return None
    return EvalSuiteDetailResponse(definition=suite)


# ---------------------------------------------------------------------------
# Run execution
# ---------------------------------------------------------------------------


def execute_eval_suite(session: Session, suite_id: str) -> EvalRunResponse:
    """Execute all cases in an eval suite and persist the run."""
    suite = get_eval_suite_registry().get(suite_id)
    if suite is None:
        return EvalRunResponse(
            success=False,
            message=f"Eval suite '{suite_id}' not found.",
            run=EvalRunRecord(run_id="", suite_id=suite_id, status="failed"),
        )

    # Capture Langfuse trace boundary if configured
    langfuse = get_langfuse()
    trace = None
    if langfuse:
        try:
            trace = langfuse.trace(
                name=f"eval_suite_run:{suite_id}",
                metadata={"suite_id": suite_id, "category": suite.category},
            )
        except Exception:
            logger.debug("Langfuse trace creation skipped.", exc_info=True)

    run_record = run_eval_suite(session, suite)

    # Persist run
    now = utcnow()
    run_model = EvalRunModel(
        run_id=run_record.run_id,
        suite_id=suite_id,
        status=run_record.status,
        case_results_json=[cr.model_dump(mode="json") for cr in run_record.case_results],
        total_cases=run_record.total_cases,
        passed_cases=run_record.passed_cases,
        failed_cases=run_record.failed_cases,
        error_cases=run_record.error_cases,
        skipped_cases=run_record.skipped_cases,
        notes_json=list(run_record.notes),
        created_at=now,
        started_at=now,
        completed_at=now,
        duration_ms=run_record.duration_ms,
    )
    session.add(run_model)
    session.commit()

    # Complete Langfuse trace
    if trace:
        try:
            trace.update(
                metadata={
                    "status": run_record.status,
                    "passed": run_record.passed_cases,
                    "failed": run_record.failed_cases,
                    "duration_ms": run_record.duration_ms,
                },
            )
        except Exception:
            logger.debug("Langfuse trace update skipped.", exc_info=True)

    return EvalRunResponse(
        success=run_record.status not in ("failed",),
        message=f"Suite '{suite_id}' completed: {run_record.passed_cases}/{run_record.total_cases} passed.",
        run=run_record,
    )


# ---------------------------------------------------------------------------
# Run retrieval
# ---------------------------------------------------------------------------


def get_eval_run(session: Session, run_id: str) -> EvalRunDetailResponse | None:
    """Load a persisted eval run."""
    row = session.get(EvalRunModel, run_id)
    if row is None:
        return None

    suite = get_eval_suite_registry().get(row.suite_id)
    return EvalRunDetailResponse(
        run=EvalRunRecord(
            run_id=row.run_id,
            suite_id=row.suite_id,
            status=row.status,
            case_results=[
                EvalCaseResult.model_validate(cr) for cr in row.case_results_json
            ],
            total_cases=row.total_cases,
            passed_cases=row.passed_cases,
            failed_cases=row.failed_cases,
            error_cases=row.error_cases,
            skipped_cases=row.skipped_cases,
            started_at=isoformat_utc(row.started_at) if row.started_at else "",
            completed_at=isoformat_utc(row.completed_at) if row.completed_at else "",
            duration_ms=row.duration_ms,
            notes=list(row.notes_json),
        ),
        suite_display_name=suite.display_name if suite else "",
    )


def list_eval_runs(session: Session, suite_id: str | None = None) -> list[EvalRunRecord]:
    """List persisted eval runs, optionally filtered by suite."""
    query = select(EvalRunModel).order_by(desc(EvalRunModel.created_at))
    if suite_id:
        query = query.where(EvalRunModel.suite_id == suite_id)
    rows = list(session.exec(query).all())
    return [
        EvalRunRecord(
            run_id=row.run_id,
            suite_id=row.suite_id,
            status=row.status,
            total_cases=row.total_cases,
            passed_cases=row.passed_cases,
            failed_cases=row.failed_cases,
            error_cases=row.error_cases,
            skipped_cases=row.skipped_cases,
            started_at=isoformat_utc(row.started_at) if row.started_at else "",
            completed_at=isoformat_utc(row.completed_at) if row.completed_at else "",
            duration_ms=row.duration_ms,
            notes=list(row.notes_json),
        )
        for row in rows
    ]
