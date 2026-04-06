"""Tests for eval suites, fixtures, regression runner, and API endpoints."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from casegraph_agent_sdk.evals import (
    EvalAssertion,
    EvalAssertionResult,
    EvalCaseDefinition,
    EvalCaseResult,
    EvalFixtureMeta,
    EvalRunRecord,
    EvalSuiteDefinition,
)

from app.evals.fixtures import get_all_fixtures, get_fixture
from app.evals.models import EvalRunModel
from app.evals.regression import (
    _evaluate_assertion,
    _normalize_run_output,
    _resolve_path,
    run_eval_case,
    run_eval_suite,
)
from app.evals.router import router as evals_router
from app.evals.service import (
    build_eval_capabilities,
    execute_eval_suite,
    get_eval_suite,
    list_eval_suites,
)
from app.evals.suites import (
    EvalSuiteRegistry,
    build_default_eval_suite_registry,
    get_eval_suite_registry,
)
from app.persistence.database import get_session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session() -> Session:
    import app.cases.models  # noqa: F401
    import app.evals.models  # noqa: F401
    import app.extraction.models  # noqa: F401
    import app.ingestion.models  # noqa: F401
    import app.operator_review.models  # noqa: F401
    import app.packets.models  # noqa: F401
    import app.readiness.models  # noqa: F401
    import app.submissions.models  # noqa: F401
    import app.workflow_packs.models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture()
def client(session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(evals_router)

    def _get_session() -> Session:
        return session

    app.dependency_overrides[get_session] = _get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixture registry tests
# ---------------------------------------------------------------------------


class TestFixtureRegistry:
    def test_all_fixtures_returns_eight(self) -> None:
        fixtures = get_all_fixtures()
        assert len(fixtures) == 8

    def test_all_fixtures_have_unique_ids(self) -> None:
        fixtures = get_all_fixtures()
        ids = [f.fixture_id for f in fixtures]
        assert len(ids) == len(set(ids))

    def test_get_fixture_by_id(self) -> None:
        fixture = get_fixture("prior_auth_missing_referral")
        assert fixture is not None
        assert fixture.domain_pack_id == "medical_insurance_us"
        assert fixture.case_type_id == "medical_insurance_us:prior_auth_review"
        assert len(fixture.document_filenames) == 1

    def test_get_fixture_unknown_returns_none(self) -> None:
        assert get_fixture("nonexistent_fixture") is None

    def test_fixture_domains_span_three_packs(self) -> None:
        fixtures = get_all_fixtures()
        domain_packs = {f.domain_pack_id for f in fixtures}
        assert {"medical_insurance_us", "insurance_us", "tax_us"}.issubset(domain_packs)


# ---------------------------------------------------------------------------
# Suite registry tests
# ---------------------------------------------------------------------------


class TestSuiteRegistry:
    def test_default_registry_has_three_suites(self) -> None:
        registry = build_default_eval_suite_registry()
        suites = registry.list_suites()
        assert len(suites) == 3

    def test_registry_get_returns_correct_suite(self) -> None:
        registry = build_default_eval_suite_registry()
        suite = registry.get("medical_insurance_workflow_regression")
        assert suite is not None
        assert suite.display_name == "Medical Insurance Workflow Regression"
        assert len(suite.cases) == 3

    def test_registry_get_unknown_returns_none(self) -> None:
        registry = build_default_eval_suite_registry()
        assert registry.get("nonexistent_suite") is None

    def test_medical_insurance_suite_has_expected_targets(self) -> None:
        registry = build_default_eval_suite_registry()
        suite = registry.get("medical_insurance_workflow_regression")
        assert suite is not None
        assert "prior_auth_packet_review" in suite.target_ids
        assert "pre_claim_packet_review" in suite.target_ids

    def test_insurance_suite_has_expected_cases(self) -> None:
        registry = build_default_eval_suite_registry()
        suite = registry.get("insurance_workflow_regression")
        assert suite is not None
        assert len(suite.cases) == 2
        case_ids = {c.case_id for c in suite.cases}
        assert "insurance_claim_missing_policy" in case_ids
        assert "coverage_review_partial" in case_ids

    def test_tax_suite_has_three_cases(self) -> None:
        registry = build_default_eval_suite_registry()
        suite = registry.get("tax_workflow_regression")
        assert suite is not None
        assert len(suite.cases) == 3

    def test_all_cases_have_assertions(self) -> None:
        registry = build_default_eval_suite_registry()
        for suite in registry.list_suites():
            for case in suite.cases:
                assert len(case.assertions) > 0, (
                    f"Case {case.case_id} in suite {suite.suite_id} has no assertions"
                )

    def test_singleton_returns_same_instance(self) -> None:
        a = get_eval_suite_registry()
        b = get_eval_suite_registry()
        assert a is b

    def test_list_response_shape(self) -> None:
        registry = build_default_eval_suite_registry()
        resp = registry.list_response()
        assert len(resp.suites) == 3
        for s in resp.suites:
            assert s.suite_id
            assert s.display_name
            assert s.category


# ---------------------------------------------------------------------------
# Assertion evaluator unit tests
# ---------------------------------------------------------------------------


class TestAssertionEvaluator:
    def test_resolve_path_simple(self) -> None:
        data = {"run": {"status": "completed"}}
        assert _resolve_path(data, "run.status") == "completed"

    def test_resolve_path_deep(self) -> None:
        data = {"stages": {"intake": {"summary": {"count": 5}}}}
        assert _resolve_path(data, "stages.intake.summary.count") == 5

    def test_resolve_path_missing(self) -> None:
        assert _resolve_path({"a": 1}, "b.c") is None

    def test_status_equals_pass(self) -> None:
        assertion = EvalAssertion(
            assertion_type="status_equals",
            target_path="run.status",
            expected_value="completed",
            description="Run should be completed",
        )
        data = {"run": {"status": "completed"}}
        result = _evaluate_assertion(assertion, data)
        assert result.status == "pass"

    def test_status_equals_fail(self) -> None:
        assertion = EvalAssertion(
            assertion_type="status_equals",
            target_path="run.status",
            expected_value="completed",
            description="Run should be completed",
        )
        data = {"run": {"status": "failed"}}
        result = _evaluate_assertion(assertion, data)
        assert result.status == "fail"
        assert "failed" in (result.message or "")

    def test_field_present_pass(self) -> None:
        assertion = EvalAssertion(
            assertion_type="field_present",
            target_path="stages.readiness.summary",
            description="Field should exist",
        )
        data = {"stages": {"readiness": {"summary": {"status": "ok"}}}}
        result = _evaluate_assertion(assertion, data)
        assert result.status == "pass"

    def test_field_present_fail(self) -> None:
        assertion = EvalAssertion(
            assertion_type="field_present",
            target_path="stages.readiness.missing_field",
            description="Field should exist",
        )
        data = {"stages": {"readiness": {"summary": "ok"}}}
        result = _evaluate_assertion(assertion, data)
        assert result.status == "fail"

    def test_field_absent_pass(self) -> None:
        assertion = EvalAssertion(
            assertion_type="field_absent",
            target_path="stages.nonexistent.field",
            description="Field should not exist",
        )
        result = _evaluate_assertion(assertion, {"stages": {}})
        assert result.status == "pass"

    def test_field_absent_fail(self) -> None:
        assertion = EvalAssertion(
            assertion_type="field_absent",
            target_path="value",
            description="Field should not exist",
        )
        result = _evaluate_assertion(assertion, {"value": "present"})
        assert result.status == "fail"

    def test_minimum_item_count_pass(self) -> None:
        assertion = EvalAssertion(
            assertion_type="minimum_item_count",
            target_path="items",
            expected_value=2,
            description="At least 2 items",
        )
        result = _evaluate_assertion(assertion, {"items": [1, 2, 3]})
        assert result.status == "pass"

    def test_minimum_item_count_fail(self) -> None:
        assertion = EvalAssertion(
            assertion_type="minimum_item_count",
            target_path="items",
            expected_value=5,
            description="At least 5 items",
        )
        result = _evaluate_assertion(assertion, {"items": [1, 2]})
        assert result.status == "fail"

    def test_blocked_state_pass(self) -> None:
        assertion = EvalAssertion(
            assertion_type="blocked_state_expected",
            target_path="stages.packet.status",
            expected_value="skipped",
            description="Should be skipped",
        )
        data = {"stages": {"packet": {"status": "skipped"}}}
        result = _evaluate_assertion(assertion, data)
        assert result.status == "pass"

    def test_blocked_state_fail(self) -> None:
        assertion = EvalAssertion(
            assertion_type="blocked_state_expected",
            target_path="stages.packet.status",
            expected_value="skipped",
            description="Should be skipped",
        )
        data = {"stages": {"packet": {"status": "completed"}}}
        result = _evaluate_assertion(assertion, data)
        assert result.status == "fail"

    def test_section_generated_pass(self) -> None:
        assertion = EvalAssertion(
            assertion_type="section_generated",
            target_path="stages.checklist.summary.generated",
            expected_value=True,
            description="Checklist generated",
        )
        data = {"stages": {"checklist": {"summary": {"generated": True}}}}
        result = _evaluate_assertion(assertion, data)
        assert result.status == "pass"

    def test_section_generated_fail(self) -> None:
        assertion = EvalAssertion(
            assertion_type="section_generated",
            target_path="stages.checklist.summary.generated",
            expected_value=True,
            description="Checklist generated",
        )
        data = {"stages": {"checklist": {"summary": {"generated": False}}}}
        result = _evaluate_assertion(assertion, data)
        assert result.status == "fail"

    def test_required_reference_present_pass(self) -> None:
        assertion = EvalAssertion(
            assertion_type="required_reference_present",
            target_path="ref",
            description="Has reference",
        )
        result = _evaluate_assertion(assertion, {"ref": "abc-123"})
        assert result.status == "pass"

    def test_required_reference_present_fail(self) -> None:
        assertion = EvalAssertion(
            assertion_type="required_reference_present",
            target_path="ref",
            description="Has reference",
        )
        result = _evaluate_assertion(assertion, {"ref": None})
        assert result.status == "fail"


# ---------------------------------------------------------------------------
# Regression runner integration tests
# ---------------------------------------------------------------------------


class TestRegressionRunner:
    def test_run_medical_insurance_suite(self, session: Session) -> None:
        registry = build_default_eval_suite_registry()
        suite = registry.get("medical_insurance_workflow_regression")
        assert suite is not None

        record = run_eval_suite(session, suite)

        assert record.run_id
        assert record.suite_id == "medical_insurance_workflow_regression"
        assert record.total_cases == 3
        assert record.status in ("completed", "completed_partial", "failed")
        assert record.passed_cases + record.failed_cases + record.error_cases + record.skipped_cases == 3
        assert record.duration_ms > 0
        assert len(record.case_results) == 3

        for cr in record.case_results:
            assert cr.case_id
            assert cr.display_name
            assert cr.status in ("pass", "fail", "error", "skipped")
            assert cr.duration_ms >= 0

    def test_run_insurance_suite(self, session: Session) -> None:
        registry = build_default_eval_suite_registry()
        suite = registry.get("insurance_workflow_regression")
        assert suite is not None

        record = run_eval_suite(session, suite)

        assert record.total_cases == 2
        assert record.suite_id == "insurance_workflow_regression"
        assert len(record.case_results) == 2

    def test_run_tax_suite(self, session: Session) -> None:
        registry = build_default_eval_suite_registry()
        suite = registry.get("tax_workflow_regression")
        assert suite is not None

        record = run_eval_suite(session, suite)

        assert record.total_cases == 3
        assert record.suite_id == "tax_workflow_regression"
        assert len(record.case_results) == 3

    def test_eval_case_captures_error_gracefully(self, session: Session) -> None:
        """An eval case with a bad fixture domain should produce an error result, not crash."""
        bad_fixture = EvalFixtureMeta(
            fixture_id="bad_fixture",
            display_name="Bad Fixture",
            description="Fixture with non-existent domain pack",
            domain_pack_id="nonexistent_domain",
            case_type_id="nonexistent:case_type",
            document_filenames=[],
        )
        case_def = EvalCaseDefinition(
            case_id="bad_case",
            display_name="Bad Case",
            description="Should error gracefully.",
            fixture=bad_fixture,
            assertions=[
                EvalAssertion(
                    assertion_type="status_equals",
                    target_path="run.status",
                    expected_value="completed",
                    description="Irrelevant",
                ),
            ],
        )
        suite = EvalSuiteDefinition(
            suite_id="bad_suite",
            display_name="Bad Suite",
            description="Suite with invalid fixture.",
            category="workflow_regression",
            target_type="workflow_pack",
            target_ids=["prior_auth_packet_review"],
            cases=[case_def],
        )

        result = run_eval_case(session, case_def, suite)
        assert result.status == "error"
        assert result.error_message


# ---------------------------------------------------------------------------
# Service layer tests
# ---------------------------------------------------------------------------


class TestEvalService:
    def test_build_capabilities_returns_integrations(self) -> None:
        caps = build_eval_capabilities()
        assert len(caps.integrations) >= 3
        ids = {i.id for i in caps.integrations}
        assert "promptfoo" in ids
        assert "workflow_regression" in ids

    def test_build_capabilities_returns_benchmark_suites(self) -> None:
        caps = build_eval_capabilities()
        assert len(caps.benchmark_suites) >= 3
        config_paths = {s.config_path for s in caps.benchmark_suites}
        assert any("provider-comparison" in p for p in config_paths)

    def test_build_capabilities_lists_limitations(self) -> None:
        caps = build_eval_capabilities()
        assert len(caps.limitations) > 0

    def test_list_suites(self) -> None:
        resp = list_eval_suites()
        assert len(resp.suites) == 3

    def test_get_suite_found(self) -> None:
        resp = get_eval_suite("medical_insurance_workflow_regression")
        assert resp is not None
        assert resp.definition.suite_id == "medical_insurance_workflow_regression"

    def test_get_suite_not_found(self) -> None:
        assert get_eval_suite("nonexistent") is None

    def test_execute_eval_suite_persists_run(self, session: Session) -> None:
        resp = execute_eval_suite(session, "medical_insurance_workflow_regression")
        assert resp.success is not None
        assert resp.run.run_id
        assert resp.run.suite_id == "medical_insurance_workflow_regression"

        # Verify persistence
        row = session.get(EvalRunModel, resp.run.run_id)
        assert row is not None
        assert row.suite_id == "medical_insurance_workflow_regression"
        assert row.total_cases == 3

    def test_execute_eval_suite_not_found(self, session: Session) -> None:
        resp = execute_eval_suite(session, "nonexistent_suite")
        assert resp.success is False
        assert "not found" in resp.message.lower()


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestEvalRoutes:
    def test_get_capabilities(self, client: TestClient) -> None:
        resp = client.get("/evals/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert "integrations" in data
        assert "benchmark_suites" in data
        assert "limitations" in data

    def test_list_suites(self, client: TestClient) -> None:
        resp = client.get("/evals/suites")
        assert resp.status_code == 200
        data = resp.json()
        assert "suites" in data
        assert len(data["suites"]) == 3

    def test_get_suite_found(self, client: TestClient) -> None:
        resp = client.get("/evals/suites/medical_insurance_workflow_regression")
        assert resp.status_code == 200
        data = resp.json()
        assert data["definition"]["suite_id"] == "medical_insurance_workflow_regression"

    def test_get_suite_not_found(self, client: TestClient) -> None:
        resp = client.get("/evals/suites/nonexistent_suite")
        assert resp.status_code == 404

    def test_run_suite(self, client: TestClient) -> None:
        resp = client.post("/evals/suites/medical_insurance_workflow_regression/run")
        assert resp.status_code == 200
        data = resp.json()
        assert "run" in data
        assert data["run"]["suite_id"] == "medical_insurance_workflow_regression"
        assert data["run"]["total_cases"] == 3

    def test_run_suite_not_found(self, client: TestClient) -> None:
        resp = client.post("/evals/suites/nonexistent/run")
        assert resp.status_code == 200  # returns run response with success=false
        data = resp.json()
        assert data["success"] is False

    def test_get_run(self, client: TestClient) -> None:
        # First, execute a suite to create a run
        run_resp = client.post("/evals/suites/medical_insurance_workflow_regression/run")
        run_id = run_resp.json()["run"]["run_id"]

        resp = client.get(f"/evals/runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run"]["run_id"] == run_id

    def test_get_run_not_found(self, client: TestClient) -> None:
        resp = client.get("/evals/runs/nonexistent-run-id")
        assert resp.status_code == 404

    def test_list_runs(self, client: TestClient) -> None:
        # Create a run first
        client.post("/evals/suites/tax_workflow_regression/run")
        resp = client.get("/evals/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_runs_filter_by_suite(self, client: TestClient) -> None:
        # Create runs for two different suites
        client.post("/evals/suites/medical_insurance_workflow_regression/run")
        client.post("/evals/suites/tax_workflow_regression/run")

        resp = client.get("/evals/runs?suite_id=tax_workflow_regression")
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["suite_id"] == "tax_workflow_regression" for r in data)
