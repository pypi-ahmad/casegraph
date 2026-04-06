"""Eval suite registry — built-in workflow evaluation suites.

Defines eval suites for the three real workflow pack domains:
  1. Medical insurance (prior auth / pre-claim)
  2. General insurance (claim intake / coverage correspondence)
  3. Tax (intake / notice review)

Each suite contains eval cases with fixtures and deterministic assertions.
Assertions are evaluated by the regression runner against real workflow
pack execution output.

These are seed regression suites — not full production benchmarks.
"""

from __future__ import annotations

from casegraph_agent_sdk.evals import (
    EvalAssertion,
    EvalCaseDefinition,
    EvalSuiteDefinition,
    EvalSuiteId,
    EvalSuiteListResponse,
)

from app.evals.fixtures import (
    FIXTURE_COVERAGE_REVIEW_PARTIAL,
    FIXTURE_INSURANCE_CLAIM_MISSING_POLICY,
    FIXTURE_PRE_CLAIM_MISSING_CLINICAL,
    FIXTURE_PRIOR_AUTH_COMPLETE,
    FIXTURE_PRIOR_AUTH_MISSING_REFERRAL,
    FIXTURE_TAX_INTAKE_MISSING_INCOME,
    FIXTURE_TAX_NOTICE_REVIEW_MISSING,
    FIXTURE_TAX_NOTICE_REVIEW_WITH_NOTICE,
)

# ---------------------------------------------------------------------------
# Reusable assertion patterns
# ---------------------------------------------------------------------------


def _assert_status(path: str, expected: str, desc: str = "") -> EvalAssertion:
    return EvalAssertion(
        assertion_type="status_equals",
        target_path=path,
        expected_value=expected,
        description=desc or f"Expect {path} == {expected}",
    )


def _assert_field_present(path: str, desc: str = "") -> EvalAssertion:
    return EvalAssertion(
        assertion_type="field_present",
        target_path=path,
        description=desc or f"Expect {path} to be present",
    )


def _assert_min_count(path: str, minimum: int, desc: str = "") -> EvalAssertion:
    return EvalAssertion(
        assertion_type="minimum_item_count",
        target_path=path,
        expected_value=minimum,
        description=desc or f"Expect {path} count >= {minimum}",
    )


def _assert_blocked(path: str, desc: str = "") -> EvalAssertion:
    return EvalAssertion(
        assertion_type="blocked_state_expected",
        target_path=path,
        expected_value="skipped",
        description=desc or f"Expect {path} to be skipped/blocked",
    )


def _assert_section_generated(path: str, desc: str = "") -> EvalAssertion:
    return EvalAssertion(
        assertion_type="section_generated",
        target_path=path,
        expected_value=True,
        description=desc or f"Expect {path} to be generated",
    )


# ---------------------------------------------------------------------------
# Suite: Medical Insurance Workflow Regression
# ---------------------------------------------------------------------------

_MEDICAL_INSURANCE_SUITE = EvalSuiteDefinition(
    suite_id="medical_insurance_workflow_regression",
    display_name="Medical Insurance Workflow Regression",
    description=(
        "Seed regression suite for prior authorization and pre-claim "
        "workflow packs. Tests checklist generation, missing-document "
        "detection, readiness evaluation, and packet/draft gating."
    ),
    category="workflow_regression",
    target_type="workflow_pack",
    target_ids=["prior_auth_packet_review", "pre_claim_packet_review"],
    cases=[
        EvalCaseDefinition(
            case_id="prior_auth_missing_referral",
            display_name="Prior Auth — Missing Referral Order",
            description="Execute prior_auth_packet_review with identity-only fixture.",
            fixture=FIXTURE_PRIOR_AUTH_MISSING_REFERRAL,
            assertions=[
                _assert_status("run.status", "completed_partial", "Run should be partial"),
                _assert_status(
                    "stages.intake_document_check.status", "completed_partial",
                    "Intake should detect missing categories",
                ),
                _assert_min_count("stages.intake_document_check.summary.missing_categories", 1),
                _assert_section_generated(
                    "stages.checklist_refresh.summary.checklist_generated",
                    "Checklist should be generated from domain pack",
                ),
                _assert_blocked(
                    "stages.packet_assembly.status",
                    "Packet assembly should be skipped — only 1 doc linked",
                ),
            ],
        ),
        EvalCaseDefinition(
            case_id="prior_auth_complete",
            display_name="Prior Auth — All Required Documents",
            description="Execute prior_auth_packet_review with all required docs.",
            fixture=FIXTURE_PRIOR_AUTH_COMPLETE,
            assertions=[
                _assert_status("stages.intake_document_check.status", "completed"),
                _assert_section_generated(
                    "stages.checklist_refresh.summary.checklist_generated",
                ),
                _assert_field_present("stages.readiness_evaluation.summary.readiness_status"),
                _assert_section_generated(
                    "stages.packet_assembly.summary.packet_generated",
                    "Packet should be generated with all docs present",
                ),
            ],
        ),
        EvalCaseDefinition(
            case_id="pre_claim_missing_clinical",
            display_name="Pre-Claim — Missing Clinical Notes",
            description="Execute pre_claim_packet_review with missing clinical notes.",
            fixture=FIXTURE_PRE_CLAIM_MISSING_CLINICAL,
            assertions=[
                _assert_status("run.status", "completed_partial"),
                _assert_min_count("stages.intake_document_check.summary.missing_categories", 1),
                _assert_section_generated(
                    "stages.checklist_refresh.summary.checklist_generated",
                ),
            ],
        ),
    ],
    limitations=[
        "Seed fixtures only — 3 cases with minimal document setups.",
        "No clinical or payer-specific assertion logic.",
        "Extraction pass always reports completed_partial since no extraction runs exist in seed fixtures.",
    ],
)


# ---------------------------------------------------------------------------
# Suite: General Insurance Workflow Regression
# ---------------------------------------------------------------------------

_INSURANCE_SUITE = EvalSuiteDefinition(
    suite_id="insurance_workflow_regression",
    display_name="General Insurance Workflow Regression",
    description=(
        "Seed regression suite for insurance claim intake and coverage "
        "correspondence workflow packs."
    ),
    category="workflow_regression",
    target_type="workflow_pack",
    target_ids=[
        "insurance_claim_intake_review",
        "coverage_correspondence_review",
    ],
    cases=[
        EvalCaseDefinition(
            case_id="insurance_claim_missing_policy",
            display_name="Insurance Claim — Missing Policy",
            description="Execute insurance_claim_intake_review with missing policy_document.",
            fixture=FIXTURE_INSURANCE_CLAIM_MISSING_POLICY,
            assertions=[
                _assert_status("run.status", "completed_partial"),
                _assert_min_count("stages.intake_document_check.summary.missing_categories", 1),
                _assert_section_generated(
                    "stages.checklist_refresh.summary.checklist_generated",
                ),
            ],
        ),
        EvalCaseDefinition(
            case_id="coverage_review_partial",
            display_name="Coverage Review — Partial Documents",
            description="Execute coverage_correspondence_review with missing proof of loss.",
            fixture=FIXTURE_COVERAGE_REVIEW_PARTIAL,
            assertions=[
                _assert_status("stages.intake_document_check.status", "completed_partial"),
                _assert_section_generated(
                    "stages.checklist_refresh.summary.checklist_generated",
                ),
                _assert_field_present("stages.readiness_evaluation.summary.readiness_status"),
                _assert_section_generated(
                    "stages.packet_assembly.summary.packet_generated",
                    "Packet should still be generated — 2 docs linked",
                ),
            ],
        ),
    ],
    limitations=[
        "Seed fixtures only — 2 cases.",
        "No insurer-specific or coverage logic assertions.",
        "coverage_correspondence_review and insurance_claim_intake_review both target insurance_us:coverage_review.",
    ],
)


# ---------------------------------------------------------------------------
# Suite: Tax Workflow Regression
# ---------------------------------------------------------------------------

_TAX_SUITE = EvalSuiteDefinition(
    suite_id="tax_workflow_regression",
    display_name="Tax Workflow Regression",
    description=(
        "Seed regression suite for tax intake and tax notice review "
        "workflow packs."
    ),
    category="workflow_regression",
    target_type="workflow_pack",
    target_ids=["tax_intake_packet_review", "tax_notice_review"],
    cases=[
        EvalCaseDefinition(
            case_id="tax_intake_missing_income",
            display_name="Tax Intake — Missing Income Document",
            description="Execute tax_intake_packet_review with missing income_document category.",
            fixture=FIXTURE_TAX_INTAKE_MISSING_INCOME,
            assertions=[
                _assert_status("run.status", "completed_partial"),
                _assert_status(
                    "stages.intake_document_check.status", "completed_partial",
                ),
                _assert_min_count("stages.intake_document_check.summary.missing_categories", 1),
                _assert_section_generated(
                    "stages.checklist_refresh.summary.checklist_generated",
                ),
            ],
        ),
        EvalCaseDefinition(
            case_id="tax_notice_with_notice",
            display_name="Tax Notice — Notice Document Present",
            description="Execute tax_notice_review with tax notice and identity documents.",
            fixture=FIXTURE_TAX_NOTICE_REVIEW_WITH_NOTICE,
            assertions=[
                _assert_section_generated(
                    "stages.checklist_refresh.summary.checklist_generated",
                ),
                _assert_field_present("stages.readiness_evaluation.summary.readiness_status"),
                _assert_section_generated(
                    "stages.packet_assembly.summary.packet_generated",
                    "Packet should be generated — 2 docs linked",
                ),
            ],
        ),
        EvalCaseDefinition(
            case_id="tax_notice_missing_docs",
            display_name="Tax Notice — No Documents",
            description="Execute tax_notice_review with no documents linked.",
            fixture=FIXTURE_TAX_NOTICE_REVIEW_MISSING,
            assertions=[
                _assert_status("run.status", "completed_partial"),
                _assert_status(
                    "stages.intake_document_check.status", "completed_partial",
                ),
                _assert_blocked(
                    "stages.packet_assembly.status",
                    "Packet assembly should be skipped — no docs linked",
                ),
                _assert_blocked(
                    "stages.submission_draft_preparation.status",
                    "Submission draft should be skipped — no packet available",
                ),
            ],
        ),
    ],
    limitations=[
        "Seed fixtures only — 3 cases.",
        "No tax-law or filing-rule assertion logic.",
        "Only US jurisdiction tested in seed suites.",
    ],
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_ALL_SUITES: list[EvalSuiteDefinition] = [
    _MEDICAL_INSURANCE_SUITE,
    _INSURANCE_SUITE,
    _TAX_SUITE,
]


class EvalSuiteRegistry:
    """In-memory registry of eval suite definitions."""

    def __init__(self) -> None:
        self._suites: dict[EvalSuiteId, EvalSuiteDefinition] = {}

    def register(self, suite: EvalSuiteDefinition) -> None:
        self._suites[suite.suite_id] = suite

    def get(self, suite_id: EvalSuiteId) -> EvalSuiteDefinition | None:
        return self._suites.get(suite_id)

    def list_suites(self) -> list[EvalSuiteDefinition]:
        return list(self._suites.values())

    def list_response(self) -> EvalSuiteListResponse:
        return EvalSuiteListResponse(suites=list(self._suites.values()))


def build_default_eval_suite_registry() -> EvalSuiteRegistry:
    """Build the default registry with built-in eval suites."""
    registry = EvalSuiteRegistry()
    for suite in _ALL_SUITES:
        registry.register(suite)
    return registry


_default_registry: EvalSuiteRegistry | None = None


def get_eval_suite_registry() -> EvalSuiteRegistry:
    """Return the singleton eval suite registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_eval_suite_registry()
    return _default_registry
