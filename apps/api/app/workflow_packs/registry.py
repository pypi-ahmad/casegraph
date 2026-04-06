"""Built-in workflow pack definitions and registry.

Registers domain workflow packs for prior authorization packet review,
pre-claim packet review, insurance claim intake review, coverage
correspondence review, tax intake packet review, and tax notice review.
These compose existing foundations into explicit, operator-centric stage
sequences.

These are operational workflow definitions — not rules engines, adjudication
tools, or autonomous submission pipelines.
"""

from __future__ import annotations

from casegraph_agent_sdk.workflow_packs import (
    WorkflowPackDefinition,
    WorkflowPackId,
    WorkflowPackMetadata,
    WorkflowPackStageDefinition,
    WorkflowPackListResponse,
    WorkflowPackDetailResponse,
)

# ---------------------------------------------------------------------------
# Stage sequence (shared across registered packs)
# ---------------------------------------------------------------------------

_STANDARD_STAGES: list[WorkflowPackStageDefinition] = [
    WorkflowPackStageDefinition(
        stage_id="intake_document_check",
        display_name="Intake & Document Linkage Check",
        description=(
            "Verify that the case has linked documents and identify "
            "missing document categories from the case type requirements."
        ),
    ),
    WorkflowPackStageDefinition(
        stage_id="extraction_pass",
        display_name="Extraction Coverage Review",
        description=(
            "Review persisted extraction runs for the case's currently "
            "linked documents. Indicates where extraction still needs to "
            "be run separately."
        ),
        depends_on=["intake_document_check"],
    ),
    WorkflowPackStageDefinition(
        stage_id="checklist_refresh",
        display_name="Checklist Generation / Refresh",
        description=(
            "Generate or refresh the case checklist from the domain pack "
            "case type requirements."
        ),
        depends_on=["extraction_pass"],
    ),
    WorkflowPackStageDefinition(
        stage_id="readiness_evaluation",
        display_name="Readiness Evaluation",
        description=(
            "Evaluate checklist coverage from linked documents and "
            "extraction results to produce a readiness summary."
        ),
        depends_on=["checklist_refresh"],
    ),
    WorkflowPackStageDefinition(
        stage_id="action_generation",
        display_name="Follow-Up Action Generation",
        description=(
            "Deterministically generate follow-up actions from explicit "
            "missing items, failed runs, and coverage gaps."
        ),
        depends_on=["readiness_evaluation"],
    ),
    WorkflowPackStageDefinition(
        stage_id="packet_assembly",
        display_name="Packet Assembly",
        description=(
            "Assemble a reviewable packet from current case state. "
            "Skipped if fewer than one document is linked."
        ),
        optional=True,
        depends_on=["action_generation"],
    ),
    WorkflowPackStageDefinition(
        stage_id="submission_draft_preparation",
        display_name="Submission Draft Preparation",
        description=(
            "Prepare a submission draft and dry-run automation plan "
            "if a packet exists and the case has sufficient state. "
            "Skipped if packet assembly was skipped."
        ),
        optional=True,
        depends_on=["packet_assembly"],
    ),
]

_STANDARD_LIMITATIONS: list[str] = [
    "No payer-specific rules, clinical guidance, or adjudication logic is included.",
    "Extraction uses generic templates only — no domain-specific clinical or insurance field extraction.",
    "Readiness evaluation reflects explicit document/extraction linkage, not clinical completeness.",
    "Follow-up actions are deterministic from explicit state gaps, not from domain intelligence.",
    "Packet assembly is a structured reflection of case state, not a formatted payer submission.",
    "Submission draft preparation creates a draft artifact only — no live submission is attempted.",
    "This workflow does not predict approval, denial, or any regulatory outcome.",
]

_INSURANCE_LIMITATIONS: list[str] = [
    "No insurer-specific rules, coverage logic, or adjudication intelligence is included.",
    "Extraction uses generic templates only — no policy-term or clause extraction.",
    "Readiness evaluation reflects explicit document/extraction linkage, not coverage completeness.",
    "Follow-up actions are deterministic from explicit state gaps, not coverage analysis.",
    "Packet assembly is a structured reflection of case state, not a formatted carrier submission.",
    "Submission draft preparation creates a draft artifact only — no live submission is attempted.",
    "This workflow does not determine coverage, predict outcomes, or interpret policy terms.",
]

_TAX_LIMITATIONS: list[str] = [
    "No tax-law interpretation, filing-rule logic, or notice-resolution intelligence is included.",
    "Extraction uses generic templates only — no form-specific or notice-specific tax field extraction.",
    "Readiness evaluation reflects explicit document/extraction linkage, not filing completeness or legal sufficiency.",
    "Follow-up actions are deterministic from explicit state gaps, not from tax advice or notice interpretation.",
    "Packet assembly is a structured reflection of case state, not a formatted filing or agency response.",
    "Submission draft preparation creates a draft artifact only — no live filing or portal submission is attempted.",
    "This workflow does not determine tax liability, filing obligations, notice resolution, or legal outcomes.",
]


# ---------------------------------------------------------------------------
# Prior Auth Packet Review (medical_insurance_us)
# ---------------------------------------------------------------------------

_PRIOR_AUTH_REVIEW = WorkflowPackDefinition(
    metadata=WorkflowPackMetadata(
        workflow_pack_id="prior_auth_packet_review",
        display_name="Prior Authorization Packet Review",
        description=(
            "End-to-end intake and review workflow for a prior authorization "
            "request packet. Composes document linkage, extraction, checklist "
            "generation, readiness evaluation, action generation, and optional "
            "packet/submission-draft preparation into an explicit operator-reviewed "
            "sequence. Does not predict or automate approval decisions."
        ),
        version="0.1.0",
        domain_pack_id="medical_insurance_us",
        domain_category="medical_insurance",
        jurisdiction="us",
        compatible_case_type_ids=[
            "medical_insurance_us:prior_auth_review",
            "medical_insurance_us:claim_intake",
        ],
        stage_count=len(_STANDARD_STAGES),
        limitations=_STANDARD_LIMITATIONS,
    ),
    stages=_STANDARD_STAGES,
)


# ---------------------------------------------------------------------------
# Pre-Claim Packet Review (medical_insurance_india)
# ---------------------------------------------------------------------------

_PRE_CLAIM_REVIEW = WorkflowPackDefinition(
    metadata=WorkflowPackMetadata(
        workflow_pack_id="pre_claim_packet_review",
        display_name="Pre-Claim Packet Review",
        description=(
            "End-to-end intake and review workflow for a pre-claim or "
            "pre-authorization request packet. Composes document linkage, "
            "extraction, checklist generation, readiness evaluation, action "
            "generation, and optional packet/submission-draft preparation. "
            "Does not predict or automate approval decisions."
        ),
        version="0.1.0",
        domain_pack_id="medical_insurance_india",
        domain_category="medical_insurance",
        jurisdiction="india",
        compatible_case_type_ids=[
            "medical_insurance_india:pre_claim_review",
            "medical_insurance_india:claim_intake",
        ],
        stage_count=len(_STANDARD_STAGES),
        limitations=_STANDARD_LIMITATIONS,
    ),
    stages=_STANDARD_STAGES,
)


# ---------------------------------------------------------------------------
# Insurance Claim Intake Review (insurance_us + insurance_india)
# ---------------------------------------------------------------------------

_INSURANCE_CLAIM_INTAKE_US = WorkflowPackDefinition(
    metadata=WorkflowPackMetadata(
        workflow_pack_id="insurance_claim_intake_review",
        display_name="Insurance Claim Intake Review",
        description=(
            "End-to-end intake and review workflow for a general insurance "
            "claim or policy case. Composes document linkage, extraction, "
            "checklist generation, readiness evaluation, action generation, "
            "and optional packet/submission-draft preparation into an explicit "
            "operator-reviewed sequence. Does not adjudicate claims, predict "
            "outcomes, or determine coverage."
        ),
        version="0.1.0",
        domain_pack_id="insurance_us",
        domain_category="insurance",
        jurisdiction="us",
        compatible_case_type_ids=[
            "insurance_us:policy_review",
            "insurance_us:coverage_review",
        ],
        stage_count=len(_STANDARD_STAGES),
        limitations=_INSURANCE_LIMITATIONS,
    ),
    stages=_STANDARD_STAGES,
)

_INSURANCE_CLAIM_INTAKE_INDIA = WorkflowPackDefinition(
    metadata=WorkflowPackMetadata(
        workflow_pack_id="insurance_claim_intake_review_india",
        display_name="Insurance Claim Intake Review (India)",
        description=(
            "End-to-end intake and review workflow for a general insurance "
            "claim or policy case in India. Composes document linkage, extraction, "
            "checklist generation, readiness evaluation, action generation, "
            "and optional packet/submission-draft preparation. Does not adjudicate "
            "claims, predict outcomes, or determine coverage."
        ),
        version="0.1.0",
        domain_pack_id="insurance_india",
        domain_category="insurance",
        jurisdiction="india",
        compatible_case_type_ids=[
            "insurance_india:policy_review",
            "insurance_india:coverage_review",
        ],
        stage_count=len(_STANDARD_STAGES),
        limitations=_INSURANCE_LIMITATIONS,
    ),
    stages=_STANDARD_STAGES,
)


# ---------------------------------------------------------------------------
# Coverage Correspondence Review (insurance_us + insurance_india)
# ---------------------------------------------------------------------------

_COVERAGE_CORRESPONDENCE_US = WorkflowPackDefinition(
    metadata=WorkflowPackMetadata(
        workflow_pack_id="coverage_correspondence_review",
        display_name="Coverage Correspondence Review",
        description=(
            "End-to-end review workflow for coverage-related correspondence "
            "and documentation. Composes document linkage, extraction, checklist "
            "generation, readiness evaluation, action generation, and optional "
            "packet/submission-draft preparation. Does not make coverage "
            "determinations, interpret policy terms, or automate insurer decisions."
        ),
        version="0.1.0",
        domain_pack_id="insurance_us",
        domain_category="insurance",
        jurisdiction="us",
        compatible_case_type_ids=[
            "insurance_us:coverage_review",
        ],
        stage_count=len(_STANDARD_STAGES),
        limitations=_INSURANCE_LIMITATIONS,
    ),
    stages=_STANDARD_STAGES,
)

_COVERAGE_CORRESPONDENCE_INDIA = WorkflowPackDefinition(
    metadata=WorkflowPackMetadata(
        workflow_pack_id="coverage_correspondence_review_india",
        display_name="Coverage Correspondence Review (India)",
        description=(
            "End-to-end review workflow for coverage-related correspondence "
            "and documentation in India. Composes document linkage, extraction, "
            "checklist generation, readiness evaluation, action generation, "
            "and optional packet/submission-draft preparation. Does not make "
            "coverage determinations or interpret policy terms."
        ),
        version="0.1.0",
        domain_pack_id="insurance_india",
        domain_category="insurance",
        jurisdiction="india",
        compatible_case_type_ids=[
            "insurance_india:coverage_review",
        ],
        stage_count=len(_STANDARD_STAGES),
        limitations=_INSURANCE_LIMITATIONS,
    ),
    stages=_STANDARD_STAGES,
)


# ---------------------------------------------------------------------------
# Tax Intake Packet Review (tax_us + tax_india)
# ---------------------------------------------------------------------------

_TAX_INTAKE_PACKET_REVIEW_US = WorkflowPackDefinition(
    metadata=WorkflowPackMetadata(
        workflow_pack_id="tax_intake_packet_review",
        display_name="Tax Intake Packet Review",
        description=(
            "End-to-end intake and review workflow for a tax intake packet. "
            "Composes document linkage, extraction, checklist generation, "
            "readiness evaluation, action generation, and optional "
            "packet/submission-draft preparation into an explicit operator-reviewed "
            "sequence. Does not provide tax advice or determine filing readiness."
        ),
        version="0.1.0",
        domain_pack_id="tax_us",
        domain_category="taxation",
        jurisdiction="us",
        compatible_case_type_ids=[
            "tax_us:intake_review",
        ],
        stage_count=len(_STANDARD_STAGES),
        limitations=_TAX_LIMITATIONS,
    ),
    stages=_STANDARD_STAGES,
)

_TAX_INTAKE_PACKET_REVIEW_INDIA = WorkflowPackDefinition(
    metadata=WorkflowPackMetadata(
        workflow_pack_id="tax_intake_packet_review_india",
        display_name="Tax Intake Packet Review (India)",
        description=(
            "End-to-end intake and review workflow for a tax intake packet in India. "
            "Composes document linkage, extraction, checklist generation, readiness "
            "evaluation, action generation, and optional packet/submission-draft "
            "preparation. Does not provide tax advice or determine filing readiness."
        ),
        version="0.1.0",
        domain_pack_id="tax_india",
        domain_category="taxation",
        jurisdiction="india",
        compatible_case_type_ids=[
            "tax_india:intake_review",
        ],
        stage_count=len(_STANDARD_STAGES),
        limitations=_TAX_LIMITATIONS,
    ),
    stages=_STANDARD_STAGES,
)


# ---------------------------------------------------------------------------
# Tax Notice Review (tax_us + tax_india)
# ---------------------------------------------------------------------------

_TAX_NOTICE_REVIEW_US = WorkflowPackDefinition(
    metadata=WorkflowPackMetadata(
        workflow_pack_id="tax_notice_review",
        display_name="Tax Notice Review",
        description=(
            "End-to-end review workflow for tax notices and government correspondence. "
            "Composes document linkage, extraction, checklist generation, readiness "
            "evaluation, action generation, and optional packet/submission-draft "
            "preparation. Does not provide tax advice or determine notice resolution."
        ),
        version="0.1.0",
        domain_pack_id="tax_us",
        domain_category="taxation",
        jurisdiction="us",
        compatible_case_type_ids=[
            "tax_us:notice_review",
        ],
        stage_count=len(_STANDARD_STAGES),
        limitations=_TAX_LIMITATIONS,
    ),
    stages=_STANDARD_STAGES,
)

_TAX_NOTICE_REVIEW_INDIA = WorkflowPackDefinition(
    metadata=WorkflowPackMetadata(
        workflow_pack_id="tax_notice_review_india",
        display_name="Tax Notice Review (India)",
        description=(
            "End-to-end review workflow for tax notices and government correspondence "
            "in India. Composes document linkage, extraction, checklist generation, "
            "readiness evaluation, action generation, and optional packet/submission-"
            "draft preparation. Does not provide tax advice or determine notice resolution."
        ),
        version="0.1.0",
        domain_pack_id="tax_india",
        domain_category="taxation",
        jurisdiction="india",
        compatible_case_type_ids=[
            "tax_india:notice_review",
        ],
        stage_count=len(_STANDARD_STAGES),
        limitations=_TAX_LIMITATIONS,
    ),
    stages=_STANDARD_STAGES,
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class WorkflowPackRegistry:
    """In-memory registry of workflow pack definitions."""

    def __init__(self) -> None:
        self._packs: dict[WorkflowPackId, WorkflowPackDefinition] = {}

    def register(self, definition: WorkflowPackDefinition) -> None:
        self._packs[definition.metadata.workflow_pack_id] = definition

    def get(self, pack_id: WorkflowPackId) -> WorkflowPackDefinition | None:
        return self._packs.get(pack_id)

    def list_packs(self) -> list[WorkflowPackDefinition]:
        return list(self._packs.values())

    def list_metadata(self) -> WorkflowPackListResponse:
        return WorkflowPackListResponse(
            packs=[p.metadata for p in self._packs.values()]
        )

    def get_detail(self, pack_id: WorkflowPackId) -> WorkflowPackDetailResponse | None:
        definition = self._packs.get(pack_id)
        if definition is None:
            return None
        return WorkflowPackDetailResponse(definition=definition)

    def packs_for_case_type(self, case_type_id: str) -> list[WorkflowPackDefinition]:
        return [
            p for p in self._packs.values()
            if case_type_id in p.metadata.compatible_case_type_ids
        ]


def build_default_workflow_pack_registry() -> WorkflowPackRegistry:
    """Build the default registry with built-in workflow packs."""
    registry = WorkflowPackRegistry()
    registry.register(_PRIOR_AUTH_REVIEW)
    registry.register(_PRE_CLAIM_REVIEW)
    registry.register(_INSURANCE_CLAIM_INTAKE_US)
    registry.register(_INSURANCE_CLAIM_INTAKE_INDIA)
    registry.register(_COVERAGE_CORRESPONDENCE_US)
    registry.register(_COVERAGE_CORRESPONDENCE_INDIA)
    registry.register(_TAX_INTAKE_PACKET_REVIEW_US)
    registry.register(_TAX_INTAKE_PACKET_REVIEW_INDIA)
    registry.register(_TAX_NOTICE_REVIEW_US)
    registry.register(_TAX_NOTICE_REVIEW_INDIA)
    return registry


_default_registry: WorkflowPackRegistry | None = None


def get_workflow_pack_registry() -> WorkflowPackRegistry:
    """Return the singleton workflow pack registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_workflow_pack_registry()
    return _default_registry
