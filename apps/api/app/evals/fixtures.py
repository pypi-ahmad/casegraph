"""Eval fixture registry — seed fixtures for workflow evaluation suites.

Each fixture describes a minimal, honest case setup for one eval scenario.
Fixtures are lightweight metadata — the regression runner materializes
them into real database objects when executing a suite.

These are seed fixtures, not production benchmark datasets.
"""

from __future__ import annotations

from casegraph_agent_sdk.evals import EvalFixtureMeta

# ---------------------------------------------------------------------------
# Medical insurance fixtures
# ---------------------------------------------------------------------------

FIXTURE_PRIOR_AUTH_MISSING_REFERRAL = EvalFixtureMeta(
    fixture_id="prior_auth_missing_referral",
    display_name="Prior Auth — Missing Referral Order",
    description=(
        "Prior authorization case with an identity document linked but "
        "the required referral/order and clinical notes are missing."
    ),
    domain_pack_id="medical_insurance_us",
    case_type_id="medical_insurance_us:prior_auth_review",
    document_filenames=["patient_id.pdf"],
    notes=["Seed fixture — 1 of 3 required document categories present."],
)

FIXTURE_PRIOR_AUTH_COMPLETE = EvalFixtureMeta(
    fixture_id="prior_auth_complete",
    display_name="Prior Auth — All Required Documents",
    description=(
        "Prior authorization case with identity, clinical notes, and "
        "referral order documents linked."
    ),
    domain_pack_id="medical_insurance_us",
    case_type_id="medical_insurance_us:prior_auth_review",
    document_filenames=["patient_id.pdf", "clinical_notes.pdf", "referral_order.pdf"],
    notes=["Seed fixture — all 3 required document categories present."],
)

FIXTURE_PRE_CLAIM_MISSING_CLINICAL = EvalFixtureMeta(
    fixture_id="pre_claim_missing_clinical",
    display_name="Pre-Claim — Missing Clinical Notes",
    description=(
        "India pre-claim case with an identity document but "
        "the required clinical notes are missing."
    ),
    domain_pack_id="medical_insurance_india",
    case_type_id="medical_insurance_india:pre_claim_review",
    document_filenames=["aadhaar_card.pdf"],
    notes=["Seed fixture — 1 of 2 required document categories present."],
)

# ---------------------------------------------------------------------------
# General insurance fixtures
# ---------------------------------------------------------------------------

FIXTURE_INSURANCE_CLAIM_MISSING_POLICY = EvalFixtureMeta(
    fixture_id="insurance_claim_missing_policy",
    display_name="Insurance Claim — Missing Policy Document",
    description=(
        "General insurance policy review with identity document "
        "but the required policy document is missing."
    ),
    domain_pack_id="insurance_us",
    case_type_id="insurance_us:policy_review",
    document_filenames=["driver_license.pdf"],
    notes=["Seed fixture — policy_document category is missing."],
)

FIXTURE_COVERAGE_REVIEW_PARTIAL = EvalFixtureMeta(
    fixture_id="coverage_review_partial",
    display_name="Coverage Review — Partial (No Proof of Loss)",
    description=(
        "Coverage review case with identity and policy documents "
        "but proof of loss is missing."
    ),
    domain_pack_id="insurance_us",
    case_type_id="insurance_us:coverage_review",
    document_filenames=["driver_license.pdf", "policy_doc.pdf"],
    notes=["Seed fixture — proof_of_loss category is missing."],
)

# ---------------------------------------------------------------------------
# Tax fixtures
# ---------------------------------------------------------------------------

FIXTURE_TAX_INTAKE_MISSING_INCOME = EvalFixtureMeta(
    fixture_id="tax_intake_missing_income",
    display_name="Tax Intake — Missing Income Document",
    description=(
        "Tax intake case with identity document but the "
        "required income document category is missing."
    ),
    domain_pack_id="tax_us",
    case_type_id="tax_us:intake_review",
    document_filenames=["passport.pdf"],
    notes=["Seed fixture — income_document category is missing."],
)

FIXTURE_TAX_NOTICE_REVIEW_WITH_NOTICE = EvalFixtureMeta(
    fixture_id="tax_notice_with_notice",
    display_name="Tax Notice — Notice Document Present",
    description=(
        "Tax notice review case with identity and a tax notice document linked."
    ),
    domain_pack_id="tax_us",
    case_type_id="tax_us:notice_review",
    document_filenames=["passport.pdf", "irs_notice.pdf"],
    notes=["Seed fixture — required tax_notice category present."],
)

FIXTURE_TAX_NOTICE_REVIEW_MISSING = EvalFixtureMeta(
    fixture_id="tax_notice_missing_docs",
    display_name="Tax Notice — No Documents",
    description=(
        "Tax notice review case with no documents linked at all."
    ),
    domain_pack_id="tax_us",
    case_type_id="tax_us:notice_review",
    document_filenames=[],
    notes=["Seed fixture — no documents. All required categories missing."],
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_ALL_FIXTURES: list[EvalFixtureMeta] = [
    FIXTURE_PRIOR_AUTH_MISSING_REFERRAL,
    FIXTURE_PRIOR_AUTH_COMPLETE,
    FIXTURE_PRE_CLAIM_MISSING_CLINICAL,
    FIXTURE_INSURANCE_CLAIM_MISSING_POLICY,
    FIXTURE_COVERAGE_REVIEW_PARTIAL,
    FIXTURE_TAX_INTAKE_MISSING_INCOME,
    FIXTURE_TAX_NOTICE_REVIEW_WITH_NOTICE,
    FIXTURE_TAX_NOTICE_REVIEW_MISSING,
]


def get_all_fixtures() -> list[EvalFixtureMeta]:
    return list(_ALL_FIXTURES)


def get_fixture(fixture_id: str) -> EvalFixtureMeta | None:
    return next((f for f in _ALL_FIXTURES if f.fixture_id == fixture_id), None)
