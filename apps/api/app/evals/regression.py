"""Workflow regression runner.

Materializes eval fixtures into real database objects, executes a
workflow pack, and evaluates deterministic assertions against the
run output.  Each assertion uses explicit path-based checks on the
WorkflowPackRunResponse — no fuzzy scoring or fabricated outputs.

This is a small modular runner, not a custom eval framework.
"""

from __future__ import annotations

import logging
import time
from uuid import uuid4

from sqlmodel import Session

from casegraph_agent_sdk.evals import (
    AssertionResultStatus,
    EvalAssertion,
    EvalAssertionResult,
    EvalCaseDefinition,
    EvalCaseResult,
    EvalFixtureMeta,
    EvalRunRecord,
    EvalRunStatus,
    EvalSuiteDefinition,
)
from casegraph_agent_sdk.workflow_packs import (
    WorkflowPackExecutionRequest,
    WorkflowPackRunResponse,
)

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel
from app.ingestion.models import DocumentRecord
from app.persistence.database import utcnow
from app.workflow_packs.service import WorkflowPackOrchestrationService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain pack → metadata lookup
# ---------------------------------------------------------------------------

_DOMAIN_CATEGORY_MAP: dict[str, str] = {
    "medical_insurance_us": "medical_insurance",
    "medical_insurance_india": "medical_insurance",
    "insurance_us": "insurance",
    "insurance_india": "insurance",
    "tax_us": "taxation",
    "tax_india": "taxation",
    "medical_us": "medical",
    "medical_india": "medical",
}

_JURISDICTION_MAP: dict[str, str] = {
    "medical_insurance_us": "us",
    "medical_insurance_india": "india",
    "insurance_us": "us",
    "insurance_india": "india",
    "tax_us": "us",
    "tax_india": "india",
    "medical_us": "us",
    "medical_india": "india",
}


# ---------------------------------------------------------------------------
# Fixture materialization
# ---------------------------------------------------------------------------


def _materialize_fixture(
    session: Session,
    fixture: EvalFixtureMeta,
) -> CaseRecordModel:
    """Create a real case and linked documents from a fixture definition."""
    case = CaseRecordModel(
        case_id=str(uuid4()),
        title=f"Eval: {fixture.display_name}",
        category="operations",
        status="open",
        summary=fixture.description,
        current_stage="intake",
        domain_pack_id=fixture.domain_pack_id,
        case_type_id=fixture.case_type_id,
        jurisdiction=_JURISDICTION_MAP.get(fixture.domain_pack_id, "us"),
        domain_category=_DOMAIN_CATEGORY_MAP.get(fixture.domain_pack_id, ""),
    )
    session.add(case)
    session.flush()

    for filename in fixture.document_filenames:
        doc = DocumentRecord(
            document_id=str(uuid4()),
            filename=filename,
            content_type="application/pdf",
            classification="document",
            requested_mode="auto",
            resolved_mode="auto",
            processing_status="completed",
            page_count=1,
        )
        session.add(doc)
        session.add(CaseDocumentLinkModel(
            link_id=str(uuid4()),
            case_id=case.case_id,
            document_id=doc.document_id,
        ))

    session.flush()
    return case


# ---------------------------------------------------------------------------
# Assertion evaluation
# ---------------------------------------------------------------------------


def _resolve_path(data: dict, path: str):
    """Navigate a dotted path like stages.intake_document_check.status."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def _normalize_run_output(response: WorkflowPackRunResponse) -> dict:
    """Flatten a run response into a navigable dict for assertion resolution."""
    run = response.run
    stages: dict[str, dict] = {}
    for sr in run.stage_results:
        stages[sr.stage_id] = {
            "status": sr.status,
            "display_name": sr.display_name,
            "summary": dict(sr.summary),
            "error_message": sr.error_message,
            "notes": list(sr.notes),
        }

    return {
        "run": {
            "status": run.status,
            "workflow_pack_id": run.workflow_pack_id,
            "case_id": run.case_id,
        },
        "stages": stages,
        "recommendation": run.review_recommendation.model_dump(mode="json"),
    }


def _evaluate_assertion(
    assertion: EvalAssertion,
    data: dict,
) -> EvalAssertionResult:
    """Evaluate a single assertion against flattened run data."""
    actual = _resolve_path(data, assertion.target_path)

    if assertion.assertion_type == "status_equals":
        passed = actual == assertion.expected_value
        return EvalAssertionResult(
            assertion_id=assertion.assertion_id,
            assertion_type=assertion.assertion_type,
            status="pass" if passed else "fail",
            actual_value=actual,
            expected_value=assertion.expected_value,
            message=assertion.description if passed else (
                f"Expected {assertion.target_path} == {assertion.expected_value!r}, "
                f"got {actual!r}"
            ),
        )

    if assertion.assertion_type == "field_present":
        passed = actual is not None
        return EvalAssertionResult(
            assertion_id=assertion.assertion_id,
            assertion_type=assertion.assertion_type,
            status="pass" if passed else "fail",
            actual_value=actual,
            message=assertion.description if passed else (
                f"Expected {assertion.target_path} to be present, but it was None"
            ),
        )

    if assertion.assertion_type == "field_absent":
        passed = actual is None
        return EvalAssertionResult(
            assertion_id=assertion.assertion_id,
            assertion_type=assertion.assertion_type,
            status="pass" if passed else "fail",
            actual_value=actual,
            message=assertion.description if passed else (
                f"Expected {assertion.target_path} to be absent, got {actual!r}"
            ),
        )

    if assertion.assertion_type == "minimum_item_count":
        count = len(actual) if isinstance(actual, (list, dict)) else 0
        minimum = assertion.expected_value or 0
        passed = count >= minimum
        return EvalAssertionResult(
            assertion_id=assertion.assertion_id,
            assertion_type=assertion.assertion_type,
            status="pass" if passed else "fail",
            actual_value=count,
            expected_value=minimum,
            message=assertion.description if passed else (
                f"Expected {assertion.target_path} count >= {minimum}, got {count}"
            ),
        )

    if assertion.assertion_type == "blocked_state_expected":
        passed = actual in ("skipped", "blocked")
        return EvalAssertionResult(
            assertion_id=assertion.assertion_id,
            assertion_type=assertion.assertion_type,
            status="pass" if passed else "fail",
            actual_value=actual,
            expected_value=assertion.expected_value,
            message=assertion.description if passed else (
                f"Expected {assertion.target_path} to be skipped/blocked, got {actual!r}"
            ),
        )

    if assertion.assertion_type == "section_generated":
        passed = actual is True or actual == "true"
        return EvalAssertionResult(
            assertion_id=assertion.assertion_id,
            assertion_type=assertion.assertion_type,
            status="pass" if passed else "fail",
            actual_value=actual,
            expected_value=True,
            message=assertion.description if passed else (
                f"Expected {assertion.target_path} to be true, got {actual!r}"
            ),
        )

    if assertion.assertion_type == "requirement_status_expected":
        passed = actual == assertion.expected_value
        return EvalAssertionResult(
            assertion_id=assertion.assertion_id,
            assertion_type=assertion.assertion_type,
            status="pass" if passed else "fail",
            actual_value=actual,
            expected_value=assertion.expected_value,
            message=assertion.description if passed else (
                f"Expected {assertion.target_path} == {assertion.expected_value!r}, got {actual!r}"
            ),
        )

    if assertion.assertion_type == "required_reference_present":
        passed = actual is not None and actual != ""
        return EvalAssertionResult(
            assertion_id=assertion.assertion_id,
            assertion_type=assertion.assertion_type,
            status="pass" if passed else "fail",
            actual_value=actual,
            message=assertion.description if passed else (
                f"Expected {assertion.target_path} to contain a reference"
            ),
        )

    return EvalAssertionResult(
        assertion_id=assertion.assertion_id,
        assertion_type=assertion.assertion_type,
        status="skipped",
        message=f"Unsupported assertion type: {assertion.assertion_type}",
    )


# ---------------------------------------------------------------------------
# Case runner
# ---------------------------------------------------------------------------


def _determine_workflow_pack_id(
    case_def: EvalCaseDefinition,
    suite: EvalSuiteDefinition,
) -> str:
    """Determine which workflow pack to execute for a given eval case."""
    case_type_id = case_def.fixture.case_type_id
    # Find a matching target workflow pack for this case type
    from app.workflow_packs.registry import get_workflow_pack_registry
    registry = get_workflow_pack_registry()
    for target_id in suite.target_ids:
        pack = registry.get(target_id)
        if pack and case_type_id in pack.metadata.compatible_case_type_ids:
            return target_id
    # Fallback to first target
    return suite.target_ids[0] if suite.target_ids else ""


def run_eval_case(
    session: Session,
    case_def: EvalCaseDefinition,
    suite: EvalSuiteDefinition,
) -> EvalCaseResult:
    """Run a single eval case: materialize fixture, execute workflow, assert."""
    start = time.monotonic()
    try:
        case = _materialize_fixture(session, case_def.fixture)
        workflow_pack_id = _determine_workflow_pack_id(case_def, suite)

        service = WorkflowPackOrchestrationService(session)
        response = service.execute(WorkflowPackExecutionRequest(
            case_id=case.case_id,
            workflow_pack_id=workflow_pack_id,
            operator_id="eval-runner",
        ))

        data = _normalize_run_output(response)
        assertion_results = [
            _evaluate_assertion(a, data) for a in case_def.assertions
        ]

        all_pass = all(r.status == "pass" for r in assertion_results)
        any_fail = any(r.status == "fail" for r in assertion_results)
        any_error = any(r.status == "error" for r in assertion_results)

        if any_error:
            overall = "error"
        elif any_fail:
            overall = "fail"
        elif all_pass:
            overall = "pass"
        else:
            overall = "skipped"

        return EvalCaseResult(
            case_id=case_def.case_id,
            display_name=case_def.display_name,
            status=overall,
            assertion_results=assertion_results,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    except Exception as exc:
        logger.warning("Eval case '%s' failed.", case_def.case_id, exc_info=True)
        return EvalCaseResult(
            case_id=case_def.case_id,
            display_name=case_def.display_name,
            status="error",
            error_message=str(exc)[:1000],
            duration_ms=(time.monotonic() - start) * 1000,
        )


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------


def run_eval_suite(
    session: Session,
    suite: EvalSuiteDefinition,
) -> EvalRunRecord:
    """Run all cases in an eval suite and produce a run record."""
    run_id = str(uuid4())
    start = time.monotonic()

    case_results: list[EvalCaseResult] = []
    for case_def in suite.cases:
        result = run_eval_case(session, case_def, suite)
        case_results.append(result)

    passed = sum(1 for r in case_results if r.status == "pass")
    failed = sum(1 for r in case_results if r.status == "fail")
    errors = sum(1 for r in case_results if r.status == "error")
    skipped = sum(1 for r in case_results if r.status == "skipped")
    duration = (time.monotonic() - start) * 1000

    status: EvalRunStatus = "completed"
    if errors > 0:
        status = "failed"
    elif failed > 0:
        status = "completed_partial"

    from app.persistence.database import isoformat_utc, utcnow as _utcnow

    now = _utcnow()

    return EvalRunRecord(
        run_id=run_id,
        suite_id=suite.suite_id,
        status=status,
        case_results=case_results,
        total_cases=len(case_results),
        passed_cases=passed,
        failed_cases=failed,
        error_cases=errors,
        skipped_cases=skipped,
        started_at=isoformat_utc(now),
        completed_at=isoformat_utc(now),
        duration_ms=duration,
        notes=suite.limitations,
    )
