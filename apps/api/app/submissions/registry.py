"""Static registry of submission target metadata profiles."""

from __future__ import annotations

from casegraph_agent_sdk.submissions import (
    SubmissionMappingTargetField,
    SubmissionTargetListResponse,
    SubmissionTargetMetadata,
)


def _field(
    field_name: str,
    *,
    section: str,
    label: str,
    required: bool = False,
    source_paths: list[str],
    notes: list[str] | None = None,
) -> SubmissionMappingTargetField:
    return SubmissionMappingTargetField(
        field_name=field_name,
        target_section=section,
        display_label=label,
        field_type="text",
        required=required,
        candidate_source_paths=source_paths,
        notes=notes or [],
    )


_COMMON_FIELDS = [
    _field(
        "case_reference",
        section="case_context",
        label="Case Reference",
        required=True,
        source_paths=["case.case_id", "packet.case_id", "packet.case_summary.case_id"],
        notes=["Maps to the internal case identifier only."],
    ),
    _field(
        "case_title",
        section="case_context",
        label="Case Title",
        required=True,
        source_paths=["case.title", "packet.case_title", "packet.case_summary.title"],
    ),
    _field(
        "case_summary",
        section="case_context",
        label="Case Summary",
        source_paths=["case.summary", "packet.note", "packet.case_summary.summary"],
        notes=["Preview only. No narrative generation is added in this step."],
    ),
    _field(
        "case_status",
        section="case_context",
        label="Case Status",
        source_paths=["case.status", "packet.case_status", "packet.case_summary.status"],
    ),
    _field(
        "domain_pack_id",
        section="domain_context",
        label="Domain Pack",
        source_paths=["case.domain_pack_id", "packet.domain_pack_id", "packet.domain_metadata.domain_pack_id"],
    ),
    _field(
        "case_type_id",
        section="domain_context",
        label="Case Type",
        source_paths=["case.case_type_id", "packet.case_type_id", "packet.domain_metadata.case_type_id"],
    ),
    _field(
        "readiness_status",
        section="readiness",
        label="Readiness Status",
        source_paths=["packet.readiness_status", "packet.readiness_summary.readiness_status"],
    ),
    _field(
        "full_name",
        section="contact",
        label="Full Name",
        source_paths=["extraction.full_name"],
        notes=["Taken only from persisted extraction output when present."],
    ),
    _field(
        "email",
        section="contact",
        label="Email",
        source_paths=["extraction.email"],
    ),
    _field(
        "phone",
        section="contact",
        label="Phone",
        source_paths=["extraction.phone"],
    ),
    _field(
        "address",
        section="contact",
        label="Address",
        source_paths=["extraction.address"],
    ),
    _field(
        "organization",
        section="contact",
        label="Organization",
        source_paths=["extraction.organization"],
    ),
    _field(
        "document_title",
        section="document_context",
        label="Document Title",
        source_paths=["extraction.title"],
    ),
    _field(
        "document_date",
        section="document_context",
        label="Document Date",
        source_paths=["extraction.date"],
    ),
    _field(
        "reference_number",
        section="document_context",
        label="Reference Number",
        source_paths=["extraction.reference_number"],
    ),
]

_HANDOFF_FIELDS = [
    field for field in _COMMON_FIELDS
    if field.field_name in {
        "case_reference",
        "case_title",
        "case_summary",
        "readiness_status",
        "reference_number",
    }
]


class SubmissionTargetRegistry:
    def __init__(self) -> None:
        self._targets: dict[str, SubmissionTargetMetadata] = {}

    def register(self, target: SubmissionTargetMetadata) -> None:
        self._targets[target.target_id] = target

    def get(self, target_id: str) -> SubmissionTargetMetadata | None:
        return self._targets.get(target_id)

    def list_targets(self) -> SubmissionTargetListResponse:
        return SubmissionTargetListResponse(targets=list(self._targets.values()))


def build_submission_target_registry() -> SubmissionTargetRegistry:
    registry = SubmissionTargetRegistry()
    registry.register(
        SubmissionTargetMetadata(
            target_id="portal_submission",
            category="portal_submission",
            display_name="Generic Portal Submission",
            description="Generic portal-oriented submission placeholder using case, packet, and extraction metadata only.",
            notes=[
                "No portal selectors, URLs, or live write actions are defined.",
                "Dry-run planning can reference Playwright MCP metadata only.",
            ],
            supports_field_mapping=True,
            supports_file_attachments=True,
            supports_dry_run_preview=True,
            supports_live_submission=False,
            default_backend_ids=["playwright_mcp"],
            default_target_fields=list(_COMMON_FIELDS),
        )
    )
    registry.register(
        SubmissionTargetMetadata(
            target_id="insurer_portal_placeholder",
            category="portal_submission",
            display_name="Insurer Portal Placeholder",
            description="Portal placeholder for insurance-oriented cases. Metadata only; no insurer-specific rules or selectors.",
            notes=[
                "No payer or insurer integrations are implemented in this step.",
                "Use for draft review and future mapping-pack preparation only.",
            ],
            supported_domain_pack_ids=[
                "medical_insurance_us",
                "medical_insurance_india",
                "insurance_us",
                "insurance_india",
            ],
            supports_field_mapping=True,
            supports_file_attachments=True,
            supports_dry_run_preview=True,
            supports_live_submission=False,
            default_backend_ids=["playwright_mcp"],
            default_target_fields=list(_COMMON_FIELDS),
        )
    )
    registry.register(
        SubmissionTargetMetadata(
            target_id="tax_portal_placeholder",
            category="portal_submission",
            display_name="Tax Portal Placeholder",
            description="Portal placeholder for tax-oriented cases. Metadata only; no tax filing logic or agency-specific rules.",
            notes=[
                "No filing rules, thresholds, or agency workflows are encoded.",
                "Use for draft inspection and future automation planning only.",
            ],
            supported_domain_pack_ids=["tax_us", "tax_india"],
            supports_field_mapping=True,
            supports_file_attachments=True,
            supports_dry_run_preview=True,
            supports_live_submission=False,
            default_backend_ids=["playwright_mcp"],
            default_target_fields=list(_COMMON_FIELDS),
        )
    )
    registry.register(
        SubmissionTargetMetadata(
            target_id="form_packet_export",
            category="form_packet_export",
            display_name="Form / Packet Export",
            description="Structured draft metadata for future form rendering or packet-export preparation.",
            notes=[
                "No PDF renderer or final form template pack is implemented yet.",
                "Mappings remain preview-only until reviewed by an operator.",
            ],
            supports_field_mapping=True,
            supports_file_attachments=True,
            supports_dry_run_preview=True,
            supports_live_submission=False,
            default_target_fields=list(_COMMON_FIELDS),
        )
    )
    registry.register(
        SubmissionTargetMetadata(
            target_id="internal_handoff_packet",
            category="internal_handoff_packet",
            display_name="Internal Handoff Packet",
            description="Internal handoff draft for review, approval, and future export orchestration.",
            notes=[
                "No live delivery or external routing is executed in this step.",
                "Uses explicit case and packet state only.",
            ],
            supports_field_mapping=True,
            supports_file_attachments=True,
            supports_dry_run_preview=True,
            supports_live_submission=False,
            default_target_fields=list(_HANDOFF_FIELDS),
        )
    )
    return registry


submission_target_registry = build_submission_target_registry()