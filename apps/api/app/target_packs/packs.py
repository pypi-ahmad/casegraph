"""Built-in target-pack metadata definitions.

These packs are generic, versioned operational metadata only. They do not
claim official payer, insurer, agency, portal, or form support.
"""

from __future__ import annotations

from casegraph_agent_sdk.target_packs import (
    TargetAutomationCompatibility,
    TargetFieldDefinition,
    TargetFieldSchema,
    TargetFieldSection,
    TargetOrganizationMetadata,
    TargetPackCompatibilityRecord,
    TargetPackDetail,
    TargetPackMetadata,
    TargetRequirementOverride,
    TargetSubmissionCompatibility,
    TargetTemplateBinding,
)

from app.target_packs.registry import TargetPackRegistry


def _field(
    field_id: str,
    *,
    label: str,
    field_type: str = "text",
    required: bool = False,
    description: str = "",
    candidate_source_paths: list[str],
    notes: list[str] | None = None,
) -> TargetFieldDefinition:
    return TargetFieldDefinition(
        field_id=field_id,
        display_name=label,
        field_type=field_type,
        required=required,
        description=description,
        candidate_source_paths=candidate_source_paths,
        notes=notes or [],
    )


def _section(
    section_id: str,
    *,
    label: str,
    description: str,
    fields: list[TargetFieldDefinition],
) -> TargetFieldSection:
    return TargetFieldSection(
        section_id=section_id,
        display_name=label,
        description=description,
        fields=fields,
    )


def _template_bindings() -> list[TargetTemplateBinding]:
    return [
        TargetTemplateBinding(
            binding_type="extraction_template",
            template_id="contact_info",
            display_name="Contact Information",
            description="Generic contact extraction metadata.",
        ),
        TargetTemplateBinding(
            binding_type="extraction_template",
            template_id="document_header",
            display_name="Document Header",
            description="Generic document reference extraction metadata.",
        ),
        TargetTemplateBinding(
            binding_type="extraction_template",
            template_id="key_value_packet",
            display_name="Key-Value Packet",
            description="Generic key-value extraction metadata.",
        ),
        TargetTemplateBinding(
            binding_type="communication_template",
            template_id="missing_document_request",
            display_name="Missing Document Request",
            description="Operator-reviewed missing item communication template.",
        ),
        TargetTemplateBinding(
            binding_type="communication_template",
            template_id="internal_handoff_note",
            display_name="Internal Handoff Note",
            description="Operator handoff communication template.",
        ),
        TargetTemplateBinding(
            binding_type="communication_template",
            template_id="packet_cover_note",
            display_name="Packet Cover Note",
            description="Packet summary communication template.",
        ),
    ]


def _submission_compatibility() -> TargetSubmissionCompatibility:
    return TargetSubmissionCompatibility(
        submission_target_ids=[
            "portal_submission",
            "form_packet_export",
            "internal_handoff_packet",
        ],
        notes=[
            "Compatibility indicates metadata can inform draft preparation.",
            "No official target profile or live submission support is implied.",
        ],
    )


def _automation_compatibility() -> TargetAutomationCompatibility:
    return TargetAutomationCompatibility(
        supported_backend_ids=["playwright_mcp"],
        supports_dry_run_planning=True,
        supports_live_execution=False,
        notes=[
            "Automation compatibility is planning metadata only.",
            "No selectors, routes, or live execution guarantees are defined.",
        ],
    )


_COMMON_LIMITATIONS = [
    "Target packs are versioned compatibility and schema metadata only.",
    "No official payer, insurer, agency, or portal integration is implemented.",
    "Field schemas are starter metadata for mapping and review, not authoritative form definitions.",
    "Requirement overrides refine or add metadata only and do not mutate base case-type requirements.",
]


def build_default_target_pack_registry() -> TargetPackRegistry:
    registry = TargetPackRegistry()

    registry.register(
        TargetPackDetail(
            metadata=TargetPackMetadata(
                pack_id="generic_prior_auth_packet_v1",
                version="1.0.0",
                status="active_metadata",
                category="payer_prior_auth_pack",
                display_name="Generic Prior Authorization Packet",
                description="Generic target-pack metadata for prior authorization style packet preparation.",
                organization=TargetOrganizationMetadata(
                    organization_type="payer",
                    display_name="Generic Payer Target",
                    description="Generic payer-oriented metadata only. No named payer support is claimed.",
                ),
                notes=[
                    "Designed for operator-reviewed packet and draft preparation.",
                ],
                limitations=list(_COMMON_LIMITATIONS),
            ),
            compatibility=TargetPackCompatibilityRecord(
                compatible_domain_pack_ids=["medical_insurance_us"],
                compatible_case_type_ids=[
                    "medical_insurance_us:prior_auth_review",
                    "medical_insurance_us:claim_intake",
                ],
                compatible_workflow_pack_ids=["prior_auth_packet_review"],
                notes=["Compatibility is derived from existing generic medical insurance workflow metadata."],
            ),
            field_schema=TargetFieldSchema(
                sections=[
                    _section(
                        "requester_information",
                        label="Requester Information",
                        description="Generic requester/operator contact metadata.",
                        fields=[
                            _field("requester_name", label="Requester Name", required=True, candidate_source_paths=["extraction.full_name", "case.metadata.requester_name"]),
                            _field("requester_organization", label="Requester Organization", candidate_source_paths=["extraction.organization", "case.metadata.requester_organization"]),
                            _field("requester_contact", label="Requester Contact", candidate_source_paths=["extraction.phone", "extraction.email", "case.metadata.requester_contact"]),
                        ],
                    ),
                    _section(
                        "member_patient_identifiers",
                        label="Member / Patient Identifiers",
                        description="Generic identifier placeholders for the covered party.",
                        fields=[
                            _field("member_identifier", label="Member Identifier", field_type="identifier", required=True, candidate_source_paths=["case.metadata.member_identifier", "extraction.reference_number"]),
                            _field("patient_name", label="Patient Name", required=True, candidate_source_paths=["extraction.full_name", "case.metadata.patient_name"]),
                        ],
                    ),
                    _section(
                        "service_request_summary",
                        label="Service / Request Summary",
                        description="Generic request summary fields used for downstream mapping review.",
                        fields=[
                            _field("request_reference", label="Request Reference", field_type="identifier", candidate_source_paths=["case.metadata.external_reference", "extraction.reference_number"]),
                            _field("request_summary", label="Request Summary", field_type="long_text", required=True, candidate_source_paths=["case.summary", "packet.note"]),
                            _field("document_date", label="Document Date", field_type="date", candidate_source_paths=["extraction.date"]),
                        ],
                    ),
                    _section(
                        "supporting_document_list",
                        label="Supporting Document List",
                        description="Generic supporting document metadata.",
                        fields=[
                            _field("supporting_documents", label="Supporting Documents", field_type="document_list", candidate_source_paths=["packet.linked_documents.documents", "case.metadata.supporting_documents"], notes=["Document list previews are metadata only."]),
                        ],
                    ),
                    _section(
                        "operator_handoff_summary",
                        label="Operator / Handoff Summary",
                        description="Operational notes for downstream handoff and review.",
                        fields=[
                            _field("operator_summary", label="Operator Summary", field_type="long_text", candidate_source_paths=["case.summary", "packet.note"]),
                            _field("case_reference", label="Case Reference", field_type="identifier", required=True, candidate_source_paths=["case.case_id", "packet.case_id"]),
                        ],
                    ),
                ],
                notes=["All sections are metadata-only starter mappings for future downstream review."],
            ),
            requirement_overrides=[
                TargetRequirementOverride(
                    override_id="prior_auth_identity_refine",
                    mode="refine_requirement",
                    base_requirement_id="identity",
                    display_name="Member / Patient Identification",
                    description="Refines the generic identity requirement label for prior authorization style packets.",
                    document_category="identity",
                    priority="required",
                    requirement_group="member_identification",
                ),
                TargetRequirementOverride(
                    override_id="prior_auth_correspondence_add",
                    mode="add_requirement",
                    display_name="Coverage / Prior Auth Correspondence",
                    description="Optional correspondence that clarifies prior interactions for the target packet.",
                    document_category="insurer_payer_correspondence",
                    priority="recommended",
                    requirement_group="coverage_context",
                ),
            ],
            template_bindings=_template_bindings(),
            submission_compatibility=_submission_compatibility(),
            automation_compatibility=_automation_compatibility(),
        )
    )

    registry.register(
        TargetPackDetail(
            metadata=TargetPackMetadata(
                pack_id="generic_preclaim_packet_v1",
                version="1.0.0",
                status="active_metadata",
                category="payer_prior_auth_pack",
                display_name="Generic Pre-Claim Packet",
                description="Generic target-pack metadata for pre-claim or pre-submission packet preparation.",
                organization=TargetOrganizationMetadata(
                    organization_type="payer",
                    display_name="Generic Payer Pre-Claim Target",
                    description="Generic pre-claim metadata only. No named payer support is claimed.",
                ),
                limitations=list(_COMMON_LIMITATIONS),
            ),
            compatibility=TargetPackCompatibilityRecord(
                compatible_domain_pack_ids=["medical_insurance_india"],
                compatible_case_type_ids=[
                    "medical_insurance_india:pre_claim_review",
                    "medical_insurance_india:claim_intake",
                ],
                compatible_workflow_pack_ids=["pre_claim_packet_review"],
            ),
            field_schema=TargetFieldSchema(
                sections=[
                    _section(
                        "requester_information",
                        label="Requester Information",
                        description="Generic requester and organization context.",
                        fields=[
                            _field("requester_name", label="Requester Name", required=True, candidate_source_paths=["extraction.full_name", "case.metadata.requester_name"]),
                            _field("requester_organization", label="Requester Organization", candidate_source_paths=["extraction.organization", "case.metadata.requester_organization"]),
                        ],
                    ),
                    _section(
                        "member_patient_identifiers",
                        label="Member / Patient Identifiers",
                        description="Generic party identification metadata.",
                        fields=[
                            _field("member_identifier", label="Member Identifier", field_type="identifier", required=True, candidate_source_paths=["case.metadata.member_identifier", "extraction.reference_number"]),
                            _field("patient_name", label="Patient Name", required=True, candidate_source_paths=["extraction.full_name", "case.metadata.patient_name"]),
                        ],
                    ),
                    _section(
                        "preclaim_request_summary",
                        label="Pre-Claim Summary",
                        description="Generic summary fields for pre-claim preparation.",
                        fields=[
                            _field("preclaim_reference", label="Pre-Claim Reference", field_type="identifier", candidate_source_paths=["case.metadata.external_reference", "extraction.reference_number"]),
                            _field("preclaim_summary", label="Pre-Claim Summary", field_type="long_text", required=True, candidate_source_paths=["case.summary", "packet.note"]),
                        ],
                    ),
                    _section(
                        "supporting_document_list",
                        label="Supporting Document List",
                        description="Packet-linked document context.",
                        fields=[
                            _field("supporting_documents", label="Supporting Documents", field_type="document_list", candidate_source_paths=["packet.linked_documents.documents", "case.metadata.supporting_documents"]),
                        ],
                    ),
                ],
            ),
            requirement_overrides=[
                TargetRequirementOverride(
                    override_id="preclaim_identity_refine",
                    mode="refine_requirement",
                    base_requirement_id="identity",
                    display_name="Member / Patient Identification",
                    document_category="identity",
                    priority="required",
                    requirement_group="member_identification",
                ),
                TargetRequirementOverride(
                    override_id="preclaim_policy_document_add",
                    mode="add_requirement",
                    display_name="Policy or Coverage Reference",
                    description="Optional policy or coverage reference material for pre-claim packet review.",
                    document_category="policy_document",
                    priority="recommended",
                    requirement_group="coverage_context",
                ),
            ],
            template_bindings=_template_bindings(),
            submission_compatibility=_submission_compatibility(),
            automation_compatibility=_automation_compatibility(),
        )
    )

    registry.register(
        TargetPackDetail(
            metadata=TargetPackMetadata(
                pack_id="generic_insurance_claim_packet_v1",
                version="1.0.0",
                status="active_metadata",
                category="insurer_claim_pack",
                display_name="Generic Insurance Claim Packet",
                description="Generic target-pack metadata for insurance claim or policy packet preparation.",
                organization=TargetOrganizationMetadata(
                    organization_type="insurer",
                    display_name="Generic Insurer Target",
                    description="Generic insurer-oriented metadata only. No named carrier support is claimed.",
                ),
                limitations=list(_COMMON_LIMITATIONS),
            ),
            compatibility=TargetPackCompatibilityRecord(
                compatible_domain_pack_ids=["insurance_us", "insurance_india"],
                compatible_case_type_ids=[
                    "insurance_us:policy_review",
                    "insurance_us:coverage_review",
                    "insurance_india:policy_review",
                    "insurance_india:coverage_review",
                ],
                compatible_workflow_pack_ids=[
                    "insurance_claim_intake_review",
                    "insurance_claim_intake_review_india",
                ],
            ),
            field_schema=TargetFieldSchema(
                sections=[
                    _section(
                        "insured_party_identifiers",
                        label="Insured Party Identifiers",
                        description="Generic identifiers for the insured or claimant.",
                        fields=[
                            _field("insured_name", label="Insured / Claimant Name", required=True, candidate_source_paths=["extraction.full_name", "case.metadata.insured_name"]),
                            _field("policy_or_member_identifier", label="Policy or Member Identifier", field_type="identifier", required=True, candidate_source_paths=["case.metadata.policy_identifier", "case.metadata.member_identifier", "extraction.reference_number"]),
                        ],
                    ),
                    _section(
                        "policy_or_claim_reference",
                        label="Policy / Claim Reference",
                        description="Generic claim or policy metadata.",
                        fields=[
                            _field("claim_reference", label="Claim Reference", field_type="identifier", candidate_source_paths=["case.metadata.external_reference", "extraction.reference_number"]),
                            _field("claim_summary", label="Claim Summary", field_type="long_text", required=True, candidate_source_paths=["case.summary", "packet.note"]),
                        ],
                    ),
                    _section(
                        "supporting_document_list",
                        label="Supporting Document List",
                        description="Linked packet material for operator review.",
                        fields=[
                            _field("supporting_documents", label="Supporting Documents", field_type="document_list", candidate_source_paths=["packet.linked_documents.documents", "case.metadata.supporting_documents"]),
                        ],
                    ),
                    _section(
                        "operator_handoff_summary",
                        label="Operator / Handoff Summary",
                        description="Operational summary for downstream packet consumers.",
                        fields=[
                            _field("operator_summary", label="Operator Summary", field_type="long_text", candidate_source_paths=["case.summary", "packet.note"]),
                        ],
                    ),
                ],
            ),
            requirement_overrides=[
                TargetRequirementOverride(
                    override_id="insurance_policy_refine",
                    mode="refine_requirement",
                    base_requirement_id="policy_document",
                    display_name="Policy or Coverage Reference Document",
                    document_category="policy_document",
                    priority="required",
                    requirement_group="coverage_context",
                ),
                TargetRequirementOverride(
                    override_id="insurance_proof_of_loss_add",
                    mode="add_requirement",
                    display_name="Proof of Loss or Supporting Claim Material",
                    description="Optional claim support metadata where such material exists.",
                    document_category="proof_of_loss",
                    priority="recommended",
                    requirement_group="claim_support",
                ),
            ],
            template_bindings=_template_bindings(),
            submission_compatibility=_submission_compatibility(),
            automation_compatibility=_automation_compatibility(),
        )
    )

    registry.register(
        TargetPackDetail(
            metadata=TargetPackMetadata(
                pack_id="generic_coverage_correspondence_packet_v1",
                version="1.0.0",
                status="active_metadata",
                category="insurance_correspondence_pack",
                display_name="Generic Coverage Correspondence Packet",
                description="Generic target-pack metadata for insurance correspondence and coverage review packets.",
                organization=TargetOrganizationMetadata(
                    organization_type="insurer",
                    display_name="Generic Coverage Correspondence Target",
                    description="Generic insurer/correspondence metadata only.",
                ),
                limitations=list(_COMMON_LIMITATIONS),
            ),
            compatibility=TargetPackCompatibilityRecord(
                compatible_domain_pack_ids=["insurance_us", "insurance_india"],
                compatible_case_type_ids=[
                    "insurance_us:coverage_review",
                    "insurance_india:coverage_review",
                ],
                compatible_workflow_pack_ids=[
                    "coverage_correspondence_review",
                    "coverage_correspondence_review_india",
                ],
            ),
            field_schema=TargetFieldSchema(
                sections=[
                    _section(
                        "correspondence_reference_details",
                        label="Correspondence Reference Details",
                        description="Generic reference fields for coverage correspondence.",
                        fields=[
                            _field("reference_number", label="Reference Number", field_type="identifier", required=True, candidate_source_paths=["extraction.reference_number", "case.metadata.external_reference"]),
                            _field("document_date", label="Document Date", field_type="date", candidate_source_paths=["extraction.date"]),
                            _field("correspondence_summary", label="Correspondence Summary", field_type="long_text", required=True, candidate_source_paths=["case.summary", "packet.note"]),
                        ],
                    ),
                    _section(
                        "insured_party_identifiers",
                        label="Insured Party Identifiers",
                        description="Generic insured party metadata.",
                        fields=[
                            _field("insured_name", label="Insured / Claimant Name", required=True, candidate_source_paths=["extraction.full_name", "case.metadata.insured_name"]),
                            _field("policy_identifier", label="Policy Identifier", field_type="identifier", candidate_source_paths=["case.metadata.policy_identifier", "extraction.reference_number"]),
                        ],
                    ),
                    _section(
                        "supporting_document_list",
                        label="Supporting Document List",
                        description="Linked correspondence and supporting materials.",
                        fields=[
                            _field("supporting_documents", label="Supporting Documents", field_type="document_list", candidate_source_paths=["packet.linked_documents.documents", "case.metadata.supporting_documents"]),
                        ],
                    ),
                ],
            ),
            requirement_overrides=[
                TargetRequirementOverride(
                    override_id="coverage_correspondence_refine",
                    mode="refine_requirement",
                    base_requirement_id="insurer_payer_correspondence",
                    display_name="Coverage or Correspondence Reference",
                    document_category="insurer_payer_correspondence",
                    priority="required",
                    requirement_group="correspondence_context",
                ),
                TargetRequirementOverride(
                    override_id="coverage_policy_document_add",
                    mode="add_requirement",
                    display_name="Policy or Coverage Reference Document",
                    description="Optional policy reference used to interpret correspondence context during review.",
                    document_category="policy_document",
                    priority="recommended",
                    requirement_group="coverage_context",
                ),
            ],
            template_bindings=_template_bindings(),
            submission_compatibility=_submission_compatibility(),
            automation_compatibility=_automation_compatibility(),
        )
    )

    registry.register(
        TargetPackDetail(
            metadata=TargetPackMetadata(
                pack_id="generic_tax_notice_packet_v1",
                version="1.0.0",
                status="active_metadata",
                category="tax_notice_pack",
                display_name="Generic Tax Notice Packet",
                description="Generic target-pack metadata for tax notice review and response preparation.",
                organization=TargetOrganizationMetadata(
                    organization_type="tax_agency",
                    display_name="Generic Tax Agency Target",
                    description="Generic tax-agency-oriented metadata only. No named agency support is claimed.",
                ),
                limitations=list(_COMMON_LIMITATIONS),
            ),
            compatibility=TargetPackCompatibilityRecord(
                compatible_domain_pack_ids=["tax_us", "tax_india"],
                compatible_case_type_ids=[
                    "tax_us:notice_review",
                    "tax_india:notice_review",
                ],
                compatible_workflow_pack_ids=[
                    "tax_notice_review",
                    "tax_notice_review_india",
                ],
            ),
            field_schema=TargetFieldSchema(
                sections=[
                    _section(
                        "taxpayer_identifiers",
                        label="Taxpayer Identifiers",
                        description="Generic taxpayer identity and reference metadata.",
                        fields=[
                            _field("taxpayer_name", label="Taxpayer Name", required=True, candidate_source_paths=["extraction.full_name", "case.metadata.taxpayer_name"]),
                            _field("taxpayer_identifier", label="Taxpayer Identifier", field_type="identifier", required=True, candidate_source_paths=["case.metadata.taxpayer_identifier", "extraction.reference_number"]),
                        ],
                    ),
                    _section(
                        "notice_reference_details",
                        label="Notice Reference Details",
                        description="Generic notice or agency reference metadata.",
                        fields=[
                            _field("notice_reference", label="Notice Reference", field_type="identifier", required=True, candidate_source_paths=["extraction.reference_number", "case.metadata.external_reference"]),
                            _field("notice_date", label="Notice Date", field_type="date", candidate_source_paths=["extraction.date"]),
                            _field("notice_summary", label="Notice Summary", field_type="long_text", required=True, candidate_source_paths=["case.summary", "packet.note"]),
                        ],
                    ),
                    _section(
                        "supporting_document_list",
                        label="Supporting Document List",
                        description="Linked notice support materials.",
                        fields=[
                            _field("supporting_documents", label="Supporting Documents", field_type="document_list", candidate_source_paths=["packet.linked_documents.documents", "case.metadata.supporting_documents"]),
                        ],
                    ),
                ],
            ),
            requirement_overrides=[
                TargetRequirementOverride(
                    override_id="tax_notice_refine",
                    mode="refine_requirement",
                    base_requirement_id="tax_notice",
                    display_name="Tax Notice or Agency Correspondence",
                    document_category="tax_notice",
                    priority="required",
                    requirement_group="notice_context",
                ),
                TargetRequirementOverride(
                    override_id="tax_notice_income_add",
                    mode="add_requirement",
                    display_name="Supporting Income or Reference Material",
                    description="Optional supporting material used for tax notice review context.",
                    document_category="income_document",
                    priority="recommended",
                    requirement_group="supporting_context",
                ),
            ],
            template_bindings=_template_bindings(),
            submission_compatibility=_submission_compatibility(),
            automation_compatibility=_automation_compatibility(),
        )
    )

    registry.register(
        TargetPackDetail(
            metadata=TargetPackMetadata(
                pack_id="generic_tax_intake_packet_v1",
                version="1.0.0",
                status="active_metadata",
                category="tax_intake_pack",
                display_name="Generic Tax Intake Packet",
                description="Generic target-pack metadata for tax intake packet preparation.",
                organization=TargetOrganizationMetadata(
                    organization_type="tax_agency",
                    display_name="Generic Tax Intake Target",
                    description="Generic tax-intake metadata only.",
                ),
                limitations=list(_COMMON_LIMITATIONS),
            ),
            compatibility=TargetPackCompatibilityRecord(
                compatible_domain_pack_ids=["tax_us", "tax_india"],
                compatible_case_type_ids=[
                    "tax_us:intake_review",
                    "tax_india:intake_review",
                ],
                compatible_workflow_pack_ids=[
                    "tax_intake_packet_review",
                    "tax_intake_packet_review_india",
                ],
            ),
            field_schema=TargetFieldSchema(
                sections=[
                    _section(
                        "taxpayer_identifiers",
                        label="Taxpayer Identifiers",
                        description="Generic taxpayer identity metadata.",
                        fields=[
                            _field("taxpayer_name", label="Taxpayer Name", required=True, candidate_source_paths=["extraction.full_name", "case.metadata.taxpayer_name"]),
                            _field("taxpayer_identifier", label="Taxpayer Identifier", field_type="identifier", required=True, candidate_source_paths=["case.metadata.taxpayer_identifier", "extraction.reference_number"]),
                        ],
                    ),
                    _section(
                        "filing_context_summary",
                        label="Filing Context Summary",
                        description="Generic tax intake context fields.",
                        fields=[
                            _field("filing_reference", label="Filing Reference", field_type="identifier", candidate_source_paths=["case.metadata.external_reference", "extraction.reference_number"]),
                            _field("intake_summary", label="Intake Summary", field_type="long_text", required=True, candidate_source_paths=["case.summary", "packet.note"]),
                        ],
                    ),
                    _section(
                        "supporting_document_list",
                        label="Supporting Document List",
                        description="Linked tax intake support materials.",
                        fields=[
                            _field("supporting_documents", label="Supporting Documents", field_type="document_list", candidate_source_paths=["packet.linked_documents.documents", "case.metadata.supporting_documents"]),
                        ],
                    ),
                    _section(
                        "operator_handoff_summary",
                        label="Operator / Handoff Summary",
                        description="Operator notes for downstream tax packet review.",
                        fields=[
                            _field("operator_summary", label="Operator Summary", field_type="long_text", candidate_source_paths=["case.summary", "packet.note"]),
                        ],
                    ),
                ],
            ),
            requirement_overrides=[
                TargetRequirementOverride(
                    override_id="tax_intake_income_refine",
                    mode="refine_requirement",
                    base_requirement_id="income_document",
                    display_name="Income or Filing Support Document",
                    document_category="income_document",
                    priority="required",
                    requirement_group="filing_support",
                ),
                TargetRequirementOverride(
                    override_id="tax_intake_form_add",
                    mode="add_requirement",
                    display_name="Government Form or Filing Worksheet",
                    description="Optional form or worksheet material used during operator preparation.",
                    document_category="government_form",
                    priority="recommended",
                    requirement_group="filing_support",
                ),
            ],
            template_bindings=_template_bindings(),
            submission_compatibility=_submission_compatibility(),
            automation_compatibility=_automation_compatibility(),
        )
    )

    return registry


target_pack_registry = build_default_target_pack_registry()