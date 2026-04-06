"""Built-in domain pack definitions for the CaseGraph platform.

Eight initial packs across four domains and two jurisdictions:
  medical_us, medical_india, medical_insurance_us, medical_insurance_india,
  insurance_us, insurance_india, tax_us, tax_india

Case type templates use minimal, operationally honest definitions.
Workflow bindings reference existing built-in generic workflows only.
Extraction bindings reference existing built-in extraction templates only.
No regulatory logic, payer rules, or tax rules are encoded.
"""

from __future__ import annotations

from casegraph_agent_sdk.domains import (
    CaseTypeTemplateMetadata,
    DocumentRequirementDefinition,
    DomainPackDetail,
    DomainPackMetadata,
    ExtractionBindingMetadata,
    WorkflowBindingMetadata,
)

from app.domains.registry import DomainPackRegistry, _build_capabilities


# ---------------------------------------------------------------------------
# Reusable binding references (point to real existing registries)
# ---------------------------------------------------------------------------

_TASK_WORKFLOW = WorkflowBindingMetadata(
    workflow_id="provider-task-execution",
    display_name="Provider Task Execution",
    description="Single-turn BYOK provider-backed task execution.",
    binding_notes="Built-in generic workflow. Useful for summarization, classification, and extraction tasks.",
)

_RAG_WORKFLOW = WorkflowBindingMetadata(
    workflow_id="rag-task-execution",
    display_name="Evidence-Backed Task Execution",
    description="Retrieval-augmented single-turn task execution with evidence citations.",
    binding_notes="Built-in generic RAG workflow. Requires indexed documents.",
)

_PRIOR_AUTH_WORKFLOW = WorkflowBindingMetadata(
    workflow_id="prior_auth_packet_review",
    display_name="Prior Auth Packet Review Workflow",
    description="End-to-end intake and review workflow for a prior authorization request packet.",
    binding_notes="Domain workflow pack. Composes document, extraction, readiness, packet, and submission-draft foundations.",
)

_PRE_CLAIM_WORKFLOW = WorkflowBindingMetadata(
    workflow_id="pre_claim_packet_review",
    display_name="Pre-Claim Packet Review Workflow",
    description="End-to-end intake and review workflow for a pre-claim or pre-authorization request packet.",
    binding_notes="Domain workflow pack. Composes document, extraction, readiness, packet, and submission-draft foundations.",
)

_INSURANCE_CLAIM_INTAKE_WORKFLOW = WorkflowBindingMetadata(
    workflow_id="insurance_claim_intake_review",
    display_name="Insurance Claim Intake Review Workflow",
    description="End-to-end intake and review workflow for a general insurance claim. Composes document, extraction, readiness, action, packet, and submission-draft foundations.",
    binding_notes="Domain workflow pack. Does not adjudicate, predict outcomes, or automate insurer decisions.",
)

_COVERAGE_CORRESPONDENCE_WORKFLOW = WorkflowBindingMetadata(
    workflow_id="coverage_correspondence_review",
    display_name="Coverage Correspondence Review Workflow",
    description="End-to-end review workflow for coverage-related correspondence and documentation. Composes document, extraction, readiness, action, packet, and submission-draft foundations.",
    binding_notes="Domain workflow pack. Does not make coverage determinations or interpret policy terms.",
)

_INSURANCE_CLAIM_INTAKE_WORKFLOW_INDIA = WorkflowBindingMetadata(
    workflow_id="insurance_claim_intake_review_india",
    display_name="Insurance Claim Intake Review Workflow (India)",
    description="End-to-end intake and review workflow for a general insurance claim in India. Composes document, extraction, readiness, action, packet, and submission-draft foundations.",
    binding_notes="Domain workflow pack. Does not adjudicate, predict outcomes, or automate insurer decisions.",
)

_COVERAGE_CORRESPONDENCE_WORKFLOW_INDIA = WorkflowBindingMetadata(
    workflow_id="coverage_correspondence_review_india",
    display_name="Coverage Correspondence Review Workflow (India)",
    description="End-to-end review workflow for coverage-related correspondence and documentation in India. Composes document, extraction, readiness, action, packet, and submission-draft foundations.",
    binding_notes="Domain workflow pack. Does not make coverage determinations or interpret policy terms.",
)

_TAX_INTAKE_PACKET_WORKFLOW = WorkflowBindingMetadata(
    workflow_id="tax_intake_packet_review",
    display_name="Tax Intake Packet Review Workflow",
    description="End-to-end intake and review workflow for a tax intake packet. Composes document, extraction, readiness, action, packet, and submission-draft foundations.",
    binding_notes="Domain workflow pack. Does not provide tax advice, determine filing obligations, or automate submission decisions.",
)

_TAX_NOTICE_REVIEW_WORKFLOW = WorkflowBindingMetadata(
    workflow_id="tax_notice_review",
    display_name="Tax Notice Review Workflow",
    description="End-to-end review workflow for tax notices and government correspondence. Composes document, extraction, readiness, action, packet, and submission-draft foundations.",
    binding_notes="Domain workflow pack. Does not interpret notices as tax or legal advice and does not determine resolution steps.",
)

_TAX_INTAKE_PACKET_WORKFLOW_INDIA = WorkflowBindingMetadata(
    workflow_id="tax_intake_packet_review_india",
    display_name="Tax Intake Packet Review Workflow (India)",
    description="End-to-end intake and review workflow for a tax intake packet in India. Composes document, extraction, readiness, action, packet, and submission-draft foundations.",
    binding_notes="Domain workflow pack. Does not provide tax advice, determine filing obligations, or automate submission decisions.",
)

_TAX_NOTICE_REVIEW_WORKFLOW_INDIA = WorkflowBindingMetadata(
    workflow_id="tax_notice_review_india",
    display_name="Tax Notice Review Workflow (India)",
    description="End-to-end review workflow for tax notices and government correspondence in India. Composes document, extraction, readiness, action, packet, and submission-draft foundations.",
    binding_notes="Domain workflow pack. Does not interpret notices as tax or legal advice and does not determine resolution steps.",
)

_CONTACT_EXTRACTION = ExtractionBindingMetadata(
    extraction_template_id="contact_info",
    display_name="Contact Information",
    description="Extract contact details (name, email, phone, address, organization).",
    binding_notes="Built-in generic extraction template.",
)

_HEADER_EXTRACTION = ExtractionBindingMetadata(
    extraction_template_id="document_header",
    display_name="Document Header",
    description="Extract document metadata (title, date, author, type, reference number).",
    binding_notes="Built-in generic extraction template.",
)

_KV_EXTRACTION = ExtractionBindingMetadata(
    extraction_template_id="key_value_packet",
    display_name="Key-Value Packet",
    description="Extract all key-value pairs from a document.",
    binding_notes="Built-in generic extraction template.",
)

# ---------------------------------------------------------------------------
# Common document requirement patterns
# ---------------------------------------------------------------------------

_REQ_IDENTITY = DocumentRequirementDefinition(
    requirement_id="identity",
    display_name="Identity Document",
    description="Government-issued identity document for the primary party.",
    document_category="identity",
    priority="required",
    accepted_extensions=[".pdf", ".jpg", ".png"],
)

_REQ_SUPPORTING = DocumentRequirementDefinition(
    requirement_id="supporting_attachment",
    display_name="Supporting Attachment",
    description="Any additional supporting documentation.",
    document_category="supporting_attachment",
    priority="optional",
    accepted_extensions=[".pdf", ".jpg", ".png", ".docx"],
)


# ---------------------------------------------------------------------------
# Medical packs
# ---------------------------------------------------------------------------

def _medical_us_case_types() -> list[CaseTypeTemplateMetadata]:
    return [
        CaseTypeTemplateMetadata(
            case_type_id="medical_us:record_review",
            display_name="Medical Record Review",
            description="Review and organize a set of medical records for a patient case.",
            domain_pack_id="medical_us",
            typical_stages=["open", "document_collection", "under_review", "closed"],
            workflow_bindings=[_TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _CONTACT_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="clinical_notes",
                    display_name="Clinical Notes",
                    description="Physician or provider clinical notes relevant to the case.",
                    document_category="clinical_notes",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="diagnostic_reports",
                    display_name="Diagnostic Reports",
                    description="Lab results, imaging reports, or other diagnostic documents.",
                    document_category="diagnostic_report",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
        CaseTypeTemplateMetadata(
            case_type_id="medical_us:referral_review",
            display_name="Referral Packet Review",
            description="Review a referral packet from a referring provider.",
            domain_pack_id="medical_us",
            typical_stages=["open", "intake", "under_review", "pending_action", "closed"],
            workflow_bindings=[_TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _CONTACT_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="referral_order",
                    display_name="Referral / Order",
                    description="Referral letter or order from the referring provider.",
                    document_category="referral_order",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="prior_records",
                    display_name="Prior Medical Records",
                    description="Relevant prior medical records accompanying the referral.",
                    document_category="prior_records",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
    ]


def _medical_india_case_types() -> list[CaseTypeTemplateMetadata]:
    return [
        CaseTypeTemplateMetadata(
            case_type_id="medical_india:record_review",
            display_name="Medical Record Review",
            description="Review and organize medical records for a patient case in India.",
            domain_pack_id="medical_india",
            typical_stages=["open", "document_collection", "under_review", "closed"],
            workflow_bindings=[_TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _CONTACT_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="clinical_notes",
                    display_name="Clinical Notes",
                    description="Physician or provider clinical notes.",
                    document_category="clinical_notes",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="diagnostic_reports",
                    display_name="Diagnostic Reports",
                    description="Lab results, imaging reports, or other diagnostics.",
                    document_category="diagnostic_report",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
        CaseTypeTemplateMetadata(
            case_type_id="medical_india:referral_review",
            display_name="Referral Packet Review",
            description="Review a referral packet from a referring provider in India.",
            domain_pack_id="medical_india",
            typical_stages=["open", "intake", "under_review", "pending_action", "closed"],
            workflow_bindings=[_TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _CONTACT_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="referral_order",
                    display_name="Referral / Order",
                    description="Referral letter or order from the referring provider.",
                    document_category="referral_order",
                    priority="required",
                ),
                _REQ_SUPPORTING,
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Medical insurance packs
# ---------------------------------------------------------------------------

def _medical_insurance_us_case_types() -> list[CaseTypeTemplateMetadata]:
    return [
        CaseTypeTemplateMetadata(
            case_type_id="medical_insurance_us:prior_auth_review",
            display_name="Prior Authorization Packet Review",
            description="Organize and review documents for a prior authorization request. Does not predict or automate approval decisions.",
            domain_pack_id="medical_insurance_us",
            typical_stages=["open", "intake", "document_collection", "under_review", "pending_action", "escalated", "closed"],
            workflow_bindings=[_PRIOR_AUTH_WORKFLOW, _TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _CONTACT_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="clinical_notes",
                    display_name="Clinical Notes / Letter of Medical Necessity",
                    description="Clinical documentation supporting the authorization request.",
                    document_category="clinical_notes",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="referral_order",
                    display_name="Physician Order / Referral",
                    description="Physician order or referral for the requested service.",
                    document_category="referral_order",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="insurer_correspondence",
                    display_name="Insurer / Payer Correspondence",
                    description="Prior correspondence with the insurance company related to this request.",
                    document_category="insurer_payer_correspondence",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
        CaseTypeTemplateMetadata(
            case_type_id="medical_insurance_us:claim_intake",
            display_name="Claim Intake Review",
            description="Organize and review documents for a medical insurance claim submission. Does not adjudicate or predict outcomes.",
            domain_pack_id="medical_insurance_us",
            typical_stages=["open", "intake", "document_collection", "under_review", "closed"],
            workflow_bindings=[_PRIOR_AUTH_WORKFLOW, _TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="claim_form",
                    display_name="Claim Form",
                    description="Completed claim form or equivalent documentation.",
                    document_category="claim_form",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="invoice_bill",
                    display_name="Invoice / Bill",
                    description="Itemized invoice or bill from the healthcare provider.",
                    document_category="invoice_bill",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="clinical_notes",
                    display_name="Clinical Notes",
                    description="Clinical documentation supporting the claim.",
                    document_category="clinical_notes",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
    ]


def _medical_insurance_india_case_types() -> list[CaseTypeTemplateMetadata]:
    return [
        CaseTypeTemplateMetadata(
            case_type_id="medical_insurance_india:pre_claim_review",
            display_name="Pre-Claim Packet Review",
            description="Organize and review documents for a pre-claim or pre-authorization request in India. Does not predict approval.",
            domain_pack_id="medical_insurance_india",
            typical_stages=["open", "intake", "document_collection", "under_review", "pending_action", "closed"],
            workflow_bindings=[_PRE_CLAIM_WORKFLOW, _TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _CONTACT_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="clinical_notes",
                    display_name="Clinical Notes / Treating Doctor Certificate",
                    description="Clinical documentation from the treating doctor.",
                    document_category="clinical_notes",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="insurer_correspondence",
                    display_name="Insurer / TPA Correspondence",
                    description="Correspondence with the insurance company or TPA.",
                    document_category="insurer_payer_correspondence",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
        CaseTypeTemplateMetadata(
            case_type_id="medical_insurance_india:claim_intake",
            display_name="Claim Intake Review",
            description="Organize and review documents for a medical insurance claim in India. Does not adjudicate or predict outcomes.",
            domain_pack_id="medical_insurance_india",
            typical_stages=["open", "intake", "document_collection", "under_review", "closed"],
            workflow_bindings=[_PRE_CLAIM_WORKFLOW, _TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="claim_form",
                    display_name="Claim Form",
                    description="Completed claim form.",
                    document_category="claim_form",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="invoice_bill",
                    display_name="Hospital Invoice / Bill",
                    description="Itemized invoice or bill from the hospital or provider.",
                    document_category="invoice_bill",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="diagnostic_reports",
                    display_name="Diagnostic Reports",
                    description="Lab results, imaging reports, or discharge summary.",
                    document_category="diagnostic_report",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# General insurance packs
# ---------------------------------------------------------------------------

def _insurance_us_case_types() -> list[CaseTypeTemplateMetadata]:
    return [
        CaseTypeTemplateMetadata(
            case_type_id="insurance_us:policy_review",
            display_name="Policy Document Review",
            description="Review and organize policy documents for a general insurance case.",
            domain_pack_id="insurance_us",
            typical_stages=["open", "document_collection", "under_review", "closed"],
            workflow_bindings=[_INSURANCE_CLAIM_INTAKE_WORKFLOW, _TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _CONTACT_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="policy_document",
                    display_name="Policy Document",
                    description="The insurance policy document or declaration page.",
                    document_category="policy_document",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="insurer_correspondence",
                    display_name="Insurer / Carrier Correspondence",
                    description="Correspondence with the insurance carrier or underwriter.",
                    document_category="insurer_payer_correspondence",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
        CaseTypeTemplateMetadata(
            case_type_id="insurance_us:coverage_review",
            display_name="Coverage Packet Review",
            description="Review documents related to a coverage determination. Does not make coverage decisions.",
            domain_pack_id="insurance_us",
            typical_stages=["open", "intake", "document_collection", "under_review", "pending_action", "closed"],
            workflow_bindings=[_COVERAGE_CORRESPONDENCE_WORKFLOW, _INSURANCE_CLAIM_INTAKE_WORKFLOW, _TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _CONTACT_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="policy_document",
                    display_name="Policy Document",
                    description="The relevant policy document.",
                    document_category="policy_document",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="proof_of_loss",
                    display_name="Proof of Loss / Claim Documentation",
                    description="Proof of loss form or claim-related documentation.",
                    document_category="proof_of_loss",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="insurer_correspondence",
                    display_name="Insurer / Carrier Correspondence",
                    description="Correspondence with the insurance carrier regarding coverage.",
                    document_category="insurer_payer_correspondence",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
    ]


def _insurance_india_case_types() -> list[CaseTypeTemplateMetadata]:
    return [
        CaseTypeTemplateMetadata(
            case_type_id="insurance_india:policy_review",
            display_name="Policy Document Review",
            description="Review and organize policy documents for a general insurance case in India.",
            domain_pack_id="insurance_india",
            typical_stages=["open", "document_collection", "under_review", "closed"],
            workflow_bindings=[_INSURANCE_CLAIM_INTAKE_WORKFLOW_INDIA, _TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _CONTACT_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="policy_document",
                    display_name="Policy Document",
                    description="The insurance policy document.",
                    document_category="policy_document",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="insurer_correspondence",
                    display_name="Insurer / TPA Correspondence",
                    description="Correspondence with the insurance company or intermediary.",
                    document_category="insurer_payer_correspondence",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
        CaseTypeTemplateMetadata(
            case_type_id="insurance_india:coverage_review",
            display_name="Coverage Packet Review",
            description="Review documents for a coverage determination in India. Does not make coverage decisions.",
            domain_pack_id="insurance_india",
            typical_stages=["open", "intake", "document_collection", "under_review", "pending_action", "closed"],
            workflow_bindings=[_COVERAGE_CORRESPONDENCE_WORKFLOW_INDIA, _INSURANCE_CLAIM_INTAKE_WORKFLOW_INDIA, _TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _CONTACT_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="policy_document",
                    display_name="Policy Document",
                    description="The relevant policy document.",
                    document_category="policy_document",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="proof_of_loss",
                    display_name="Proof of Loss / Claim Documentation",
                    description="Proof of loss form or claim documentation.",
                    document_category="proof_of_loss",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="insurer_correspondence",
                    display_name="Insurer / TPA Correspondence",
                    description="Correspondence with the insurance company or TPA regarding coverage.",
                    document_category="insurer_payer_correspondence",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Tax packs
# ---------------------------------------------------------------------------

def _tax_us_case_types() -> list[CaseTypeTemplateMetadata]:
    return [
        CaseTypeTemplateMetadata(
            case_type_id="tax_us:intake_review",
            display_name="Tax Intake Packet Review",
            description="Organize and review documents for a tax case intake. Does not provide tax advice or prepare filings.",
            domain_pack_id="tax_us",
            typical_stages=["open", "intake", "document_collection", "under_review", "closed"],
            workflow_bindings=[_TAX_INTAKE_PACKET_WORKFLOW, _TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="income_document",
                    display_name="Income Document",
                    description="Income-related documents (pay stubs, statements, etc.).",
                    document_category="income_document",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="government_form",
                    display_name="Government Tax Form",
                    description="Any government-issued tax form related to the case.",
                    document_category="government_form",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
        CaseTypeTemplateMetadata(
            case_type_id="tax_us:notice_review",
            display_name="Tax Notice Review",
            description="Review and organize documents related to a tax notice or correspondence. Does not provide tax advice.",
            domain_pack_id="tax_us",
            typical_stages=["open", "document_collection", "under_review", "pending_action", "closed"],
            workflow_bindings=[_TAX_NOTICE_REVIEW_WORKFLOW, _TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="tax_notice",
                    display_name="Tax Notice",
                    description="The tax notice or government correspondence.",
                    document_category="tax_notice",
                    priority="required",
                ),
                _REQ_SUPPORTING,
            ],
        ),
    ]


def _tax_india_case_types() -> list[CaseTypeTemplateMetadata]:
    return [
        CaseTypeTemplateMetadata(
            case_type_id="tax_india:intake_review",
            display_name="Tax Intake Packet Review",
            description="Organize and review documents for a tax case intake in India. Does not provide tax advice or prepare filings.",
            domain_pack_id="tax_india",
            typical_stages=["open", "intake", "document_collection", "under_review", "closed"],
            workflow_bindings=[_TAX_INTAKE_PACKET_WORKFLOW_INDIA, _TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="income_document",
                    display_name="Income Document",
                    description="Income-related documents (salary slips, Form 16, etc.).",
                    document_category="income_document",
                    priority="required",
                ),
                DocumentRequirementDefinition(
                    requirement_id="government_form",
                    display_name="Government Tax Form",
                    description="Any government-issued tax form related to the case.",
                    document_category="government_form",
                    priority="recommended",
                ),
                _REQ_SUPPORTING,
            ],
        ),
        CaseTypeTemplateMetadata(
            case_type_id="tax_india:notice_review",
            display_name="Tax Notice Review",
            description="Review and organize documents related to a tax notice in India. Does not provide tax advice.",
            domain_pack_id="tax_india",
            typical_stages=["open", "document_collection", "under_review", "pending_action", "closed"],
            workflow_bindings=[_TAX_NOTICE_REVIEW_WORKFLOW_INDIA, _TASK_WORKFLOW, _RAG_WORKFLOW],
            extraction_bindings=[_HEADER_EXTRACTION, _KV_EXTRACTION],
            document_requirements=[
                _REQ_IDENTITY,
                DocumentRequirementDefinition(
                    requirement_id="tax_notice",
                    display_name="Tax Notice",
                    description="The tax notice or government correspondence.",
                    document_category="tax_notice",
                    priority="required",
                ),
                _REQ_SUPPORTING,
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Pack factory
# ---------------------------------------------------------------------------

def _build_pack(
    *,
    pack_id: str,
    display_name: str,
    description: str,
    domain_category: str,
    jurisdiction: str,
    case_types: list[CaseTypeTemplateMetadata],
) -> DomainPackDetail:
    capabilities = _build_capabilities(case_types)
    metadata = DomainPackMetadata(
        pack_id=pack_id,
        display_name=display_name,
        description=description,
        domain_category=domain_category,
        jurisdiction=jurisdiction,
        case_type_count=len(case_types),
        capabilities=capabilities,
    )
    return DomainPackDetail(metadata=metadata, case_types=case_types)


def build_default_domain_pack_registry() -> DomainPackRegistry:
    """Build registry with all built-in domain packs."""
    registry = DomainPackRegistry()

    registry.register(_build_pack(
        pack_id="medical_us",
        display_name="Medical (US)",
        description="Medical record management and referral review for US healthcare operations.",
        domain_category="medical",
        jurisdiction="us",
        case_types=_medical_us_case_types(),
    ))

    registry.register(_build_pack(
        pack_id="medical_india",
        display_name="Medical (India)",
        description="Medical record management and referral review for India healthcare operations.",
        domain_category="medical",
        jurisdiction="india",
        case_types=_medical_india_case_types(),
    ))

    registry.register(_build_pack(
        pack_id="medical_insurance_us",
        display_name="Medical Insurance (US)",
        description="Prior authorization and claim intake review for US medical insurance operations.",
        domain_category="medical_insurance",
        jurisdiction="us",
        case_types=_medical_insurance_us_case_types(),
    ))

    registry.register(_build_pack(
        pack_id="medical_insurance_india",
        display_name="Medical Insurance (India)",
        description="Pre-claim and claim intake review for India medical insurance operations.",
        domain_category="medical_insurance",
        jurisdiction="india",
        case_types=_medical_insurance_india_case_types(),
    ))

    registry.register(_build_pack(
        pack_id="insurance_us",
        display_name="Insurance (US)",
        description="Policy and coverage document review for US general insurance operations.",
        domain_category="insurance",
        jurisdiction="us",
        case_types=_insurance_us_case_types(),
    ))

    registry.register(_build_pack(
        pack_id="insurance_india",
        display_name="Insurance (India)",
        description="Policy and coverage document review for India general insurance operations.",
        domain_category="insurance",
        jurisdiction="india",
        case_types=_insurance_india_case_types(),
    ))

    registry.register(_build_pack(
        pack_id="tax_us",
        display_name="Taxation (US)",
        description="Tax intake and notice review for US tax operations.",
        domain_category="taxation",
        jurisdiction="us",
        case_types=_tax_us_case_types(),
    ))

    registry.register(_build_pack(
        pack_id="tax_india",
        display_name="Taxation (India)",
        description="Tax intake and notice review for India tax operations.",
        domain_category="taxation",
        jurisdiction="india",
        case_types=_tax_india_case_types(),
    ))

    return registry


domain_pack_registry = build_default_domain_pack_registry()
