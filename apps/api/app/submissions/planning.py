"""Deterministic dry-run automation planning for submission drafts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from casegraph_agent_sdk.automation import AutomationCapabilitiesResponse
from casegraph_agent_sdk.packets import PacketManifest
from casegraph_agent_sdk.submissions import (
    ApprovalRequirementMetadata,
    AutomationFallbackRoutingHint,
    AutomationPlan,
    AutomationPlanStep,
    DryRunResultSummary,
    ExecutionGuardrailMetadata,
    NormalizedOperationResult,
    NormalizedResultIssue,
    SubmissionDraftStatus,
    SubmissionMappingFieldDefinition,
    SubmissionTargetMetadata,
)
from casegraph_agent_sdk.target_packs import (
    CaseTargetPackSelection,
    TargetAutomationCompatibility,
)


def build_automation_plan(
    *,
    draft_id: str,
    target: SubmissionTargetMetadata,
    draft_status: SubmissionDraftStatus,
    approval: ApprovalRequirementMetadata,
    mappings: list[SubmissionMappingFieldDefinition],
    manifest: PacketManifest,
    capabilities: AutomationCapabilitiesResponse,
    target_pack_selection: CaseTargetPackSelection | None = None,
    target_pack_automation_compatibility: TargetAutomationCompatibility | None = None,
    generated_at: datetime | None = None,
) -> tuple[AutomationPlan, NormalizedOperationResult]:
    now = generated_at or datetime.now(UTC)
    tools = list(capabilities.tools)
    backends = list(capabilities.backends)
    tool_ids = {tool.id for tool in tools}
    backend_ids = {backend.id for backend in backends}

    browser_backend_id = "playwright_mcp" if "playwright_mcp" in backend_ids else None
    browser_tool_id = "playwright.navigate" if "playwright.navigate" in tool_ids else None
    computer_use_provider_ids = [
        provider.provider_id
        for provider in capabilities.computer_use_providers
        if provider.computer_use_support != "not_supported"
    ]

    steps: list[AutomationPlanStep] = []
    issues: list[NormalizedResultIssue] = []

    if target.category == "portal_submission":
        steps.append(
            _step(
                1,
                "open_target",
                status="future_automation_placeholder",
                title="Open submission target",
                description="Open the target profile in a future browser automation flow.",
                target_reference=target.target_id,
                tool_id=browser_tool_id,
                backend_id=browser_backend_id,
                execution_mode="playwright_mcp",
                notes=_browser_step_notes(browser_backend_id, browser_tool_id),
            )
        )
        steps.append(
            _step(
                2,
                "navigate_section",
                status="future_automation_placeholder",
                title="Navigate to draft field section",
                description="Move to the relevant form or portal section before any future field population.",
                target_reference=f"{target.target_id}:draft_fields",
                tool_id=browser_tool_id,
                backend_id=browser_backend_id,
                execution_mode="computer_use_fallback",
                checkpoint_required=True,
                checkpoint_reason=(
                    "Operator review is required before continuing past non-deterministic section navigation."
                ),
                fallback_hint=AutomationFallbackRoutingHint(
                    recommended_mode="computer_use_fallback",
                    reason="Deterministic Playwright selectors or routes are not defined for this section.",
                    supported_provider_ids=computer_use_provider_ids,
                    notes=[
                        "Computer-use execution is metadata-only in this build.",
                        "Resume can continue past this checkpoint without executing computer-use actions.",
                    ],
                ),
                notes=[
                    "No selector set or portal route is defined in this step.",
                    *(_browser_step_notes(browser_backend_id, browser_tool_id)),
                ],
            )
        )

    step_index = len(steps) + 1
    for mapping in mappings:
        requires_human = mapping.status in {
            "unresolved",
            "candidate_available",
            "requires_human_input",
        }
        notes = list(mapping.notes)
        if mapping.value_preview and mapping.value_preview.notes:
            notes.extend(mapping.value_preview.notes)
        if requires_human:
            notes.append("Operator review is required before any future field automation uses this mapping.")
        else:
            notes.append("Preview only. No field selector or live browser write action is defined in this step.")

        steps.append(
            _step(
                step_index,
                "populate_field_placeholder",
                status="requires_human_input" if requires_human else "future_automation_placeholder",
                title=f"Populate {mapping.target_field.display_label or mapping.target_field.field_name}",
                description=(
                    mapping.value_preview.text_value
                    if mapping.value_preview and mapping.value_preview.text_value
                    else "No current preview value available."
                ),
                target_reference=(
                    f"{mapping.target_field.target_section}.{mapping.target_field.field_name}"
                ),
                mapping_id=mapping.mapping_id,
                tool_id=browser_tool_id if target.category == "portal_submission" else None,
                backend_id=browser_backend_id if target.category == "portal_submission" else None,
                execution_mode="blocked",
                notes=notes,
            )
        )
        step_index += 1

    documents = _linked_documents(manifest)
    if target.supports_file_attachments:
        for document in documents:
            steps.append(
                _step(
                    step_index,
                    "attach_document_placeholder",
                    status="future_automation_placeholder",
                    title=f"Attach {document.get('filename', 'document')}",
                    description="Future attachment step derived from a document already linked to the case packet.",
                    target_reference=document.get("filename", ""),
                    related_document_id=document.get("document_id"),
                    tool_id=browser_tool_id if target.category == "portal_submission" else None,
                    backend_id=browser_backend_id if target.category == "portal_submission" else None,
                    execution_mode="blocked",
                    notes=[
                        "No live upload action is executed in this step.",
                        "Attachment planning is based only on packet-linked documents.",
                    ],
                )
            )
            step_index += 1

    steps.append(
        _step(
            step_index,
            "review_before_submit",
            status="informational",
            title="Review draft and approval metadata",
            description="Validate mappings, attachments, and operator approval state before any future execution path.",
            target_reference=draft_id,
            execution_mode="manual_only",
            checkpoint_required=True,
            checkpoint_reason="Operator confirmation is required before continuing beyond the review checkpoint.",
            fallback_hint=AutomationFallbackRoutingHint(
                recommended_mode="manual_only",
                reason="This checkpoint represents explicit human review rather than an automated browser action.",
                notes=[
                    "Approve/continue records operator intent and allows the run to proceed.",
                    "No browser action is executed for this step.",
                ],
            ),
            notes=[
                f"Current approval status: {approval.approval_status}.",
                "No execution occurs in this step.",
            ],
        )
    )
    step_index += 1

    steps.append(
        _step(
            step_index,
            "submit_blocked_placeholder",
            status="blocked",
            title="Submit action blocked",
            description="Live submission remains blocked in this build.",
            target_reference=target.target_id,
            execution_mode="blocked",
            notes=[
                "No browser write action, portal posting, or external submission is executed.",
                "This step exists only to keep future execution boundaries explicit.",
            ],
        )
    )

    missing_required = sum(
        1
        for mapping in mappings
        if mapping.target_field.required
        and mapping.status in {"unresolved", "candidate_available", "requires_human_input"}
    )

    if target.category == "portal_submission" and browser_tool_id is None:
        issues.append(
            NormalizedResultIssue(
                severity="warning",
                code="browser_tool_metadata_missing",
                message="No Playwright navigation tool metadata is currently available from the automation foundation.",
            )
        )

    if target.category == "portal_submission" and browser_backend_id is None:
        issues.append(
            NormalizedResultIssue(
                severity="warning",
                code="browser_backend_missing",
                message="No Playwright MCP backend metadata is currently available for portal-oriented planning.",
            )
        )

    if missing_required > 0:
        issues.append(
            NormalizedResultIssue(
                severity="warning",
                code="required_mappings_missing",
                message=f"{missing_required} required mapping(s) still need operator input or confirmation.",
                related_entity_type="submission_draft",
                related_entity_id=draft_id,
            )
        )

    issues.append(
        NormalizedResultIssue(
            severity="info",
            code="live_submission_blocked",
            message="Live submission remains blocked by guardrails in this foundation step.",
            related_entity_type="submission_target",
            related_entity_id=target.target_id,
        )
    )

    status = _derive_plan_status(
        draft_status=draft_status,
        approval_status=approval.approval_status,
        missing_required_mappings=missing_required,
        target=target,
        browser_backend_available=browser_backend_id is not None,
    )

    allowed_backend_ids = [backend for backend in target.default_backend_ids if backend in backend_ids]
    if target_pack_automation_compatibility and target_pack_automation_compatibility.supported_backend_ids:
        allowed_backend_ids = [
            backend
            for backend in allowed_backend_ids
            if backend in target_pack_automation_compatibility.supported_backend_ids
        ]

    guardrails_notes = [
        "This plan is a dry-run metadata preview only.",
        "Future execution must remain approval-gated.",
    ]
    if target_pack_automation_compatibility is not None:
        guardrails_notes.extend(target_pack_automation_compatibility.notes)

    guardrails = ExecutionGuardrailMetadata(
        requires_operator_approval=True,
        approval_status=approval.approval_status,
        browser_write_actions_blocked=True,
        live_submission_blocked=True,
        allowed_backend_ids=allowed_backend_ids,
        allowed_tool_ids=[tool_id for tool_id in [browser_tool_id] if tool_id],
        blocked_actions=[
            "live_form_fill",
            "live_attachment_upload",
            "live_submission",
        ],
        notes=guardrails_notes,
    )

    summary = DryRunResultSummary(
        plan_status=status,
        total_steps=len(steps),
        informational_steps=sum(1 for step in steps if step.status == "informational"),
        future_automation_steps=sum(1 for step in steps if step.status == "future_automation_placeholder"),
        requires_human_input_steps=sum(1 for step in steps if step.status == "requires_human_input"),
        blocked_steps=sum(1 for step in steps if step.status == "blocked"),
        missing_required_mapping_count=missing_required,
        attachment_count=len(documents),
        referenced_tool_count=len({step.tool_id for step in steps if step.tool_id}),
        referenced_backend_count=len({step.backend_id for step in steps if step.backend_id}),
        notes=[
            "Steps marked future_automation_placeholder are inspectable planning metadata only.",
            "Blocked submission steps are intentional guardrails in this build.",
        ],
    )

    plan = AutomationPlan(
        plan_id=str(uuid4()),
        draft_id=draft_id,
        target_id=target.target_id,
        target_pack_selection=target_pack_selection,
        target_pack_automation_compatibility=target_pack_automation_compatibility,
        status=status,
        dry_run=True,
        generated_at=now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        guardrails=guardrails,
        dry_run_summary=summary,
        steps=steps,
    )

    result = NormalizedOperationResult(
        success=True,
        message="Dry-run automation plan generated from current draft, packet, and automation capability metadata.",
        issues=issues,
    )
    return plan, result


def _step(
    step_index: int,
    step_type: str,
    *,
    status: str,
    title: str,
    description: str,
    target_reference: str,
    notes: list[str],
    tool_id: str | None = None,
    backend_id: str | None = None,
    execution_mode: str = "blocked",
    checkpoint_required: bool = False,
    checkpoint_reason: str = "",
    fallback_hint: AutomationFallbackRoutingHint | None = None,
    mapping_id: str | None = None,
    related_document_id: str | None = None,
) -> AutomationPlanStep:
    return AutomationPlanStep(
        step_id=str(uuid4()),
        step_index=step_index,
        step_type=step_type,
        status=status,
        title=title,
        description=description,
        target_reference=target_reference,
        tool_id=tool_id,
        backend_id=backend_id,
        execution_mode=execution_mode,
        checkpoint_required=checkpoint_required,
        checkpoint_reason=checkpoint_reason,
        fallback_hint=fallback_hint,
        mapping_id=mapping_id,
        related_document_id=related_document_id,
        notes=notes,
    )


def _browser_step_notes(browser_backend_id: str | None, browser_tool_id: str | None) -> list[str]:
    notes = [
        "Current execution only navigates when a real HTTP/HTTPS URL is available.",
        "This plan step does not include a real portal URL or selector set.",
    ]
    if browser_backend_id is None:
        notes.append("No Playwright MCP backend metadata is currently available.")
    if browser_tool_id is None:
        notes.append("No Playwright navigation tool metadata is currently available.")
    return notes


def _linked_documents(manifest: PacketManifest) -> list[dict]:
    for section in manifest.sections:
        if section.section_type == "linked_documents":
            documents = section.data.get("documents", [])
            if isinstance(documents, list):
                return [doc for doc in documents if isinstance(doc, dict)]
    return []


def _derive_plan_status(
    *,
    draft_status: SubmissionDraftStatus,
    approval_status: str,
    missing_required_mappings: int,
    target: SubmissionTargetMetadata,
    browser_backend_available: bool,
) -> str:
    if draft_status == "blocked":
        return "blocked"
    if approval_status == "rejected":
        return "blocked"
    if missing_required_mappings > 0:
        return "partial"
    if target.category == "portal_submission" and not browser_backend_available:
        return "partial"
    if approval_status == "approved_for_future_execution":
        return "approved_for_future_execution"
    return "awaiting_operator_review"