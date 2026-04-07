"""Submission draft and dry-run automation planning service."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from uuid import uuid4

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import ChangeSummary, FieldChangeRecord
from casegraph_agent_sdk.automation import AutomationCapabilitiesResponse
from casegraph_agent_sdk.packets import PacketManifest
from casegraph_agent_sdk.submissions import (
    ApprovalRequirementMetadata,
    AutomationPlan,
    AutomationPlanGenerateResponse,
    AutomationPlanResponse,
    CreateSubmissionDraftRequest,
    GenerateAutomationPlanRequest,
    NormalizedOperationResult,
    NormalizedResultIssue,
    SubmissionApprovalUpdateResponse,
    SubmissionDraftCreateResponse,
    SubmissionDraftDetailResponse,
    SubmissionDraftListResponse,
    SubmissionDraftSourceMetadata,
    SubmissionDraftSummary,
    SubmissionTargetListResponse,
    SubmissionTargetMetadata,
    UpdateSubmissionApprovalRequest,
    ExecutionGuardrailMetadata,
    DryRunResultSummary,
    SubmissionMappingFieldDefinition,
    SubmissionFieldValuePreview,
    SubmissionMappingSourceReference,
    SubmissionMappingTargetField,
)

from app.cases.models import CaseRecordModel
from app.audit.service import AuditTrailService, audit_actor, derived_ref, entity_ref, source_ref
from app.extraction.models import ExtractionRunModel
from app.packets.models import PacketRecordModel
from app.persistence.database import isoformat_utc, utcnow
from app.readiness.models import ChecklistModel
from app.reviewed_handoff.service import ReviewedHandoffService, ReviewedHandoffServiceError
from app.submissions.errors import SubmissionDraftServiceError
from app.submissions.mapping import build_source_metadata_and_mappings
from app.submissions.models import (
    AutomationPlanModel,
    AutomationPlanStepModel,
    SubmissionDraftModel,
    SubmissionMappingModel,
)
from app.submissions.planning import build_automation_plan
from app.submissions.registry import submission_target_registry
from app.target_packs.context import (
    build_submission_target_fields,
    get_case_target_pack_selection,
    merge_submission_target_fields,
)
from app.target_packs.packs import target_pack_registry


async def _empty_automation_capabilities_loader() -> AutomationCapabilitiesResponse:
    return AutomationCapabilitiesResponse()


class SubmissionDraftService:
    def __init__(
        self,
        session: Session,
        *,
        automation_capabilities_loader: Callable[[], Awaitable[AutomationCapabilitiesResponse]] | None = None,
    ) -> None:
        self._session = session
        self._automation_capabilities_loader = (
            automation_capabilities_loader or _empty_automation_capabilities_loader
        )

    def list_targets(self) -> SubmissionTargetListResponse:
        return submission_target_registry.list_targets()

    def create_draft(
        self,
        case_id: str,
        request: CreateSubmissionDraftRequest,
    ) -> SubmissionDraftCreateResponse:
        case = self._require_case(case_id)
        packet = self._require_packet(request.packet_id)
        if packet.case_id != case_id:
            raise SubmissionDraftServiceError(
                "Packet does not belong to this case.",
                status_code=400,
            )

        target = self._require_target(request.submission_target_id)
        selected_target_pack, resolved_target_pack, target, target_pack_issues = self._resolve_target_pack_context(
            case.case_metadata_json,
            target,
        )
        manifest = PacketManifest.model_validate(packet.manifest_json)
        extraction_runs = self._list_extraction_runs(case_id)
        reviewed_snapshot = None
        if manifest.source_mode == "reviewed_snapshot" and manifest.source_reviewed_snapshot_id:
            try:
                reviewed_snapshot = ReviewedHandoffService(self._session).get_snapshot(
                    manifest.source_reviewed_snapshot_id
                ).snapshot
            except ReviewedHandoffServiceError as exc:
                raise SubmissionDraftServiceError(exc.detail, status_code=exc.status_code) from exc
        source_metadata, mappings = build_source_metadata_and_mappings(
            case,
            manifest,
            extraction_runs,
            target,
            reviewed_snapshot,
            target_fields=target.default_target_fields,
            target_pack_selection=selected_target_pack,
        )
        issues = self._compatibility_issues(target, case)
        issues.extend(target_pack_issues)
        unresolved_count = self._count_unresolved_mappings(mappings)
        missing_required = self._count_missing_required_mappings(mappings)

        now = utcnow()
        self._supersede_existing_drafts(case_id, packet.packet_id, target.target_id, now)

        draft_status, approval_status = self._derive_draft_and_approval_status(
            issues=issues,
            missing_required_mappings=missing_required,
        )

        draft = SubmissionDraftModel(
            draft_id=str(uuid4()),
            case_id=case.case_id,
            packet_id=packet.packet_id,
            source_mode=manifest.source_mode,
            source_reviewed_snapshot_id=manifest.source_reviewed_snapshot_id,
            case_title=case.title,
            submission_target_id=target.target_id,
            submission_target_category=target.category,
            status=draft_status,
            domain_pack_id=case.domain_pack_id,
            case_type_id=case.case_type_id,
            mapping_count=len(mappings),
            unresolved_mapping_count=unresolved_count,
            source_metadata_json=source_metadata.model_dump(mode="json"),
            note=request.note.strip(),
            requires_operator_approval=True,
            approval_status=approval_status,
            created_at=now,
            updated_at=now,
        )
        self._session.add(draft)

        mapping_models = [self._mapping_to_model(draft.draft_id, mapping, now) for mapping in mappings]
        for model in mapping_models:
            self._session.add(model)

        audit = AuditTrailService(self._session)
        audit.append_event(
            case_id=case.case_id,
            category="submission_draft",
            event_type="submission_draft_created",
            actor=audit_actor("service", actor_id="submissions.service", display_name="Submission Draft Service"),
            entity=entity_ref(
                "submission_draft",
                draft.draft_id,
                case_id=case.case_id,
                display_label=target.target_id,
            ),
            change_summary=ChangeSummary(
                message=(
                    "Submission draft created from reviewed snapshot and packet state."
                    if manifest.source_mode == "reviewed_snapshot"
                    else "Submission draft created from current case, packet, and extraction state."
                ),
                field_changes=[
                    FieldChangeRecord(field_path="status", new_value=draft.status),
                    FieldChangeRecord(field_path="approval_status", new_value=draft.approval_status),
                    FieldChangeRecord(field_path="mapping_count", new_value=draft.mapping_count),
                    FieldChangeRecord(field_path="unresolved_mapping_count", new_value=draft.unresolved_mapping_count),
                ],
            ),
            metadata={
                "packet_id": packet.packet_id,
                "target_id": target.target_id,
                "source_mode": manifest.source_mode,
                "source_reviewed_snapshot_id": manifest.source_reviewed_snapshot_id,
            },
        )

        lineage_edges = [
            (
                "case_context",
                source_ref("case", case.case_id, case_id=case.case_id, display_label=case.title, source_path="case"),
                None,
            ),
            (
                "packet_source",
                source_ref("packet", packet.packet_id, case_id=case.case_id, display_label=packet.case_title, source_path="packet"),
                None,
            ),
        ]
        checklist = self._session.exec(
            select(ChecklistModel).where(ChecklistModel.case_id == case.case_id)
        ).first()
        if checklist is not None:
            lineage_edges.append(
                (
                    "checklist_reference",
                    source_ref("checklist", checklist.checklist_id, case_id=case.case_id, display_label="Case checklist", source_path="readiness.checklist"),
                    None,
                )
            )
        for extraction in extraction_runs:
            lineage_edges.append(
                (
                    "extraction_source",
                    source_ref("extraction_run", extraction.extraction_id, case_id=case.case_id, display_label=extraction.template_id, source_path="case.extractions"),
                    {"document_id": extraction.document_id},
                )
            )
        if manifest.source_mode == "reviewed_snapshot" and manifest.source_reviewed_snapshot_id:
            lineage_edges.append(
                (
                    "snapshot_source",
                    source_ref(
                        "reviewed_snapshot",
                        manifest.source_reviewed_snapshot_id,
                        case_id=case.case_id,
                        display_label=manifest.source_reviewed_snapshot_id,
                        source_path="reviewed_snapshot",
                    ),
                    {"signoff_status": manifest.source_snapshot_signoff_status},
                )
            )
        audit.record_lineage(
            case_id=case.case_id,
            artifact=derived_ref("submission_draft", draft.draft_id, case_id=case.case_id, display_label=target.target_id),
            edges=lineage_edges,
            notes=[
                "Submission draft lineage reflects the packet, checklist reference, and extraction runs available at draft creation time.",
                "When the packet source mode is reviewed_snapshot, the draft also records the reviewed handoff snapshot used for downstream mapping.",
            ],
            metadata={"target_id": target.target_id, "source_mode": manifest.source_mode},
        )

        self._session.commit()

        result_issues = list(issues)
        if missing_required > 0:
            result_issues.append(
                NormalizedResultIssue(
                    severity="warning",
                    code="missing_required_mappings",
                    message=f"{missing_required} required mapping(s) need operator input or confirmation.",
                    related_entity_type="submission_draft",
                    related_entity_id=draft.draft_id,
                )
            )

        message = (
            "Submission draft created from reviewed snapshot and packet state."
            if draft.source_mode == "reviewed_snapshot"
            else "Submission draft created from current case, packet, and extraction state."
        )
        if draft_status == "blocked":
            message = "Submission draft created, but current case metadata blocks this target profile."
        elif draft_status == "mapping_incomplete":
            message = "Submission draft created with incomplete mappings that require operator review."

        return SubmissionDraftCreateResponse(
            result=NormalizedOperationResult(
                success=True,
                message=message,
                issues=result_issues,
            ),
            draft=self._to_summary(draft),
            target=target,
            source_metadata=source_metadata,
            mappings=mappings,
            approval=self._to_approval(draft),
        )

    def list_drafts(self, case_id: str) -> SubmissionDraftListResponse:
        self._require_case(case_id)
        drafts = list(self._session.exec(
            select(SubmissionDraftModel)
            .where(SubmissionDraftModel.case_id == case_id)
            .order_by(desc(SubmissionDraftModel.created_at), desc(SubmissionDraftModel.draft_id))
        ).all())
        return SubmissionDraftListResponse(drafts=[self._to_summary(draft) for draft in drafts])

    def get_draft(self, draft_id: str) -> SubmissionDraftDetailResponse:
        draft = self._require_draft(draft_id)
        target = self._require_target(draft.submission_target_id)
        source_metadata = SubmissionDraftSourceMetadata.model_validate(draft.source_metadata_json)
        _selection, _pack, target, _issues = self._resolve_target_pack_context(
            {"target_pack_selection": source_metadata.target_pack_selection.model_dump(mode="json")}
            if source_metadata.target_pack_selection is not None
            else {},
            target,
        )
        mappings = self._load_mappings(draft_id, target=target)
        plan = self._load_latest_plan(draft_id)
        return SubmissionDraftDetailResponse(
            draft=self._to_summary(draft),
            target=target,
            source_metadata=source_metadata,
            mappings=mappings,
            approval=self._to_approval(draft),
            plan=plan,
        )

    async def generate_plan(
        self,
        draft_id: str,
        request: GenerateAutomationPlanRequest | None = None,
    ) -> AutomationPlanGenerateResponse:
        if request is not None and request.dry_run is False:
            raise SubmissionDraftServiceError(
                "Only dry-run automation planning is supported in this foundation step.",
                status_code=400,
            )

        draft = self._require_draft(draft_id)
        target = self._require_target(draft.submission_target_id)
        source_metadata = SubmissionDraftSourceMetadata.model_validate(draft.source_metadata_json)
        selected_target_pack, resolved_target_pack, target, _issues = self._resolve_target_pack_context(
            {"target_pack_selection": source_metadata.target_pack_selection.model_dump(mode="json")}
            if source_metadata.target_pack_selection is not None
            else {},
            target,
        )
        packet = self._require_packet(draft.packet_id)
        manifest = PacketManifest.model_validate(packet.manifest_json)
        mappings = self._load_mappings(draft_id, target=target)
        capabilities = await self._automation_capabilities_loader()
        now = utcnow()

        plan, result = build_automation_plan(
            draft_id=draft_id,
            target=target,
            draft_status=draft.status,
            approval=self._to_approval(draft),
            mappings=mappings,
            manifest=manifest,
            capabilities=capabilities,
            target_pack_selection=selected_target_pack,
            target_pack_automation_compatibility=(
                resolved_target_pack.automation_compatibility if resolved_target_pack is not None else None
            ),
            generated_at=now,
        )
        plan.source_mode = draft.source_mode
        plan.source_reviewed_snapshot_id = draft.source_reviewed_snapshot_id

        plan_model = AutomationPlanModel(
            plan_id=plan.plan_id,
            draft_id=draft_id,
            target_id=target.target_id,
            source_mode=draft.source_mode,
            source_reviewed_snapshot_id=draft.source_reviewed_snapshot_id,
            status=plan.status,
            dry_run=request.dry_run if request is not None else True,
            guardrails_json=plan.guardrails.model_dump(mode="json"),
            dry_run_summary_json=plan.dry_run_summary.model_dump(mode="json"),
            created_at=now,
            updated_at=now,
        )
        self._session.add(plan_model)
        for step in plan.steps:
            self._session.add(
                AutomationPlanStepModel(
                    step_id=step.step_id,
                    plan_id=plan.plan_id,
                    step_index=step.step_index,
                    step_type=step.step_type,
                    status=step.status,
                    title=step.title,
                    description=step.description,
                    target_reference=step.target_reference,
                    tool_id=step.tool_id,
                    backend_id=step.backend_id,
                    execution_mode=step.execution_mode,
                    checkpoint_required=step.checkpoint_required,
                    checkpoint_reason=step.checkpoint_reason,
                    fallback_hint_json=step.fallback_hint.model_dump(mode="json") if step.fallback_hint else {},
                    mapping_id=step.mapping_id,
                    related_document_id=step.related_document_id,
                    notes_json=list(step.notes),
                    created_at=now,
                )
            )

        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=draft.case_id,
            category="automation",
            event_type="automation_plan_generated",
            actor=audit_actor("service", actor_id="submissions.service", display_name="Submission Draft Service"),
            entity=entity_ref(
                "automation_plan",
                plan.plan_id,
                case_id=draft.case_id,
                display_label=target.target_id,
            ),
            change_summary=ChangeSummary(
                message="Dry-run automation plan generated for submission draft.",
                field_changes=[
                    FieldChangeRecord(field_path="status", new_value=plan.status),
                    FieldChangeRecord(field_path="step_count", new_value=len(plan.steps)),
                ],
            ),
            metadata={"draft_id": draft.draft_id, "target_id": target.target_id},
        )
        decision = audit.append_decision(
            case_id=draft.case_id,
            decision_type="automation_plan_generated",
            actor=audit_actor("service", actor_id="submissions.service", display_name="Submission Draft Service"),
            source_entity=entity_ref("automation_plan", plan.plan_id, case_id=draft.case_id, display_label=target.target_id),
            outcome=plan.status,
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)
        audit.record_lineage(
            case_id=draft.case_id,
            artifact=derived_ref("automation_plan", plan.plan_id, case_id=draft.case_id, display_label=target.target_id),
            edges=[
                (
                    "case_context",
                    source_ref("case", draft.case_id, case_id=draft.case_id, display_label=draft.case_title, source_path="case"),
                    None,
                ),
                (
                    "draft_source",
                    source_ref("submission_draft", draft.draft_id, case_id=draft.case_id, display_label=target.target_id, source_path="submission_draft"),
                    None,
                ),
                (
                    "packet_source",
                    source_ref("packet", packet.packet_id, case_id=draft.case_id, display_label=packet.case_title, source_path="packet"),
                    None,
                ),
                *(
                    [
                        (
                            "snapshot_source",
                            source_ref(
                                "reviewed_snapshot",
                                draft.source_reviewed_snapshot_id,
                                case_id=draft.case_id,
                                display_label=draft.source_reviewed_snapshot_id,
                                source_path="reviewed_snapshot",
                            ),
                            None,
                        )
                    ]
                    if draft.source_mode == "reviewed_snapshot" and draft.source_reviewed_snapshot_id
                    else []
                ),
            ],
            notes=["Automation plan lineage is anchored to the submission draft and packet used during dry-run planning."],
            metadata={
                "target_id": target.target_id,
                "step_count": len(plan.steps),
                "source_mode": draft.source_mode,
            },
        )

        draft.updated_at = now
        self._session.add(draft)
        self._session.commit()

        return AutomationPlanGenerateResponse(
            result=result,
            draft=self._to_summary(draft),
            plan=plan,
        )

    def get_plan(self, draft_id: str) -> AutomationPlanResponse:
        self._require_draft(draft_id)
        plan = self._load_latest_plan(draft_id)
        if plan is None:
            raise SubmissionDraftServiceError(
                "Automation plan not found for this submission draft.",
                status_code=404,
            )
        return AutomationPlanResponse(plan=plan)

    def update_approval(
        self,
        draft_id: str,
        request: UpdateSubmissionApprovalRequest,
    ) -> SubmissionApprovalUpdateResponse:
        draft = self._require_draft(draft_id)
        previous_approval_status = draft.approval_status
        if draft.status == "superseded_placeholder":
            raise SubmissionDraftServiceError(
                "Superseded drafts cannot be approved.",
                status_code=400,
            )

        now = utcnow()
        result_issues: list[NormalizedResultIssue] = []

        if request.approval_status == "approved_for_future_execution":
            if draft.status in {"mapping_incomplete", "blocked"}:
                raise SubmissionDraftServiceError(
                    "Draft must have complete required mappings before approval.",
                    status_code=400,
                )
            latest_plan = self._load_latest_plan(draft_id)
            if latest_plan is None:
                raise SubmissionDraftServiceError(
                    "Generate a dry-run automation plan before approval.",
                    status_code=400,
                )
            if not request.approved_by.strip():
                raise SubmissionDraftServiceError(
                    "approved_by is required when marking a draft approved.",
                    status_code=400,
                )
            draft.approval_status = request.approval_status
            draft.approved_by = request.approved_by.strip()
            draft.approved_at = now
            draft.approval_note = request.approval_note.strip()
            draft.status = "approved_for_future_execution"
        elif request.approval_status == "rejected":
            if not request.approved_by.strip():
                raise SubmissionDraftServiceError(
                    "approved_by is required when rejecting a draft.",
                    status_code=400,
                )
            draft.approval_status = "rejected"
            draft.approved_by = request.approved_by.strip()
            draft.approved_at = now
            draft.approval_note = request.approval_note.strip()
            draft.status = "blocked"
            result_issues.append(
                NormalizedResultIssue(
                    severity="warning",
                    code="approval_rejected",
                    message="Operator approval was recorded as rejected.",
                    related_entity_type="submission_draft",
                    related_entity_id=draft.draft_id,
                )
            )
        else:
            draft.approval_status = request.approval_status
            draft.approved_by = ""
            draft.approved_at = None
            draft.approval_note = request.approval_note.strip()
            if draft.status == "mapping_incomplete":
                pass
            elif draft.status == "superseded_placeholder":
                pass
            elif draft.status == "blocked" and previous_approval_status != "rejected":
                pass
            else:
                draft.status = "awaiting_operator_review"

        draft.updated_at = now
        self._session.add(draft)
        self._synchronize_latest_plan_approval(draft, now)

        approval_actor = (
            audit_actor("operator", actor_id=request.approved_by.strip(), display_name=request.approved_by.strip())
            if request.approved_by.strip()
            else audit_actor("service", actor_id="submissions.service", display_name="Submission Draft Service")
        )
        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=draft.case_id,
            category="submission_draft",
            event_type="submission_approval_updated",
            actor=approval_actor,
            entity=entity_ref("submission_draft", draft.draft_id, case_id=draft.case_id, display_label=draft.submission_target_id),
            change_summary=ChangeSummary(
                message="Submission draft approval metadata updated.",
                field_changes=[
                    FieldChangeRecord(field_path="approval_status", old_value=previous_approval_status, new_value=draft.approval_status),
                    FieldChangeRecord(field_path="status", new_value=draft.status),
                ],
            ),
            metadata={"approved_by": draft.approved_by},
        )
        decision = audit.append_decision(
            case_id=draft.case_id,
            decision_type="draft_approval_updated",
            actor=approval_actor,
            source_entity=entity_ref("submission_draft", draft.draft_id, case_id=draft.case_id, display_label=draft.submission_target_id),
            outcome=draft.approval_status,
            reason=draft.approval_note,
            note=draft.approval_note,
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)

        self._session.commit()

        return SubmissionApprovalUpdateResponse(
            result=NormalizedOperationResult(
                success=True,
                message="Submission draft approval metadata updated.",
                issues=result_issues,
            ),
            draft=self._to_summary(draft),
            approval=self._to_approval(draft),
        )

    def _require_case(self, case_id: str) -> CaseRecordModel:
        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise SubmissionDraftServiceError(
                f"Case '{case_id}' not found.",
                status_code=404,
            )
        return case

    def _require_packet(self, packet_id: str) -> PacketRecordModel:
        packet = self._session.get(PacketRecordModel, packet_id)
        if packet is None:
            raise SubmissionDraftServiceError(
                f"Packet '{packet_id}' not found.",
                status_code=404,
            )
        return packet

    def _require_draft(self, draft_id: str) -> SubmissionDraftModel:
        draft = self._session.get(SubmissionDraftModel, draft_id)
        if draft is None:
            raise SubmissionDraftServiceError(
                f"Submission draft '{draft_id}' not found.",
                status_code=404,
            )
        return draft

    def _require_target(self, target_id: str) -> SubmissionTargetMetadata:
        target = submission_target_registry.get(target_id)
        if target is None:
            raise SubmissionDraftServiceError(
                f"Submission target '{target_id}' not found.",
                status_code=404,
            )
        return target

    def _list_extraction_runs(self, case_id: str) -> list[ExtractionRunModel]:
        return list(self._session.exec(
            select(ExtractionRunModel)
            .where(ExtractionRunModel.case_id == case_id)
            .order_by(desc(ExtractionRunModel.created_at), desc(ExtractionRunModel.extraction_id))
        ).all())

    def _compatibility_issues(
        self,
        target: SubmissionTargetMetadata,
        case: CaseRecordModel,
    ) -> list[NormalizedResultIssue]:
        issues: list[NormalizedResultIssue] = []
        if target.supported_domain_pack_ids:
            if not case.domain_pack_id:
                issues.append(
                    NormalizedResultIssue(
                        severity="warning",
                        code="missing_domain_pack_context",
                        message="Case has no domain pack metadata, so target applicability cannot be confirmed.",
                        related_entity_type="case",
                        related_entity_id=case.case_id,
                    )
                )
            elif case.domain_pack_id not in target.supported_domain_pack_ids:
                issues.append(
                    NormalizedResultIssue(
                        severity="warning",
                        code="target_domain_mismatch",
                        message="Current case domain pack does not match this submission target profile.",
                        related_entity_type="case",
                        related_entity_id=case.case_id,
                    )
                )
        if target.supported_case_type_ids and case.case_type_id not in target.supported_case_type_ids:
            issues.append(
                NormalizedResultIssue(
                    severity="warning",
                    code="target_case_type_mismatch",
                    message="Current case type does not match this submission target profile.",
                    related_entity_type="case",
                    related_entity_id=case.case_id,
                )
            )
        return issues

    def _derive_draft_and_approval_status(
        self,
        *,
        issues: list[NormalizedResultIssue],
        missing_required_mappings: int,
    ) -> tuple[str, str]:
        if issues:
            return "blocked", "not_requested"
        if missing_required_mappings > 0:
            return "mapping_incomplete", "not_requested"
        return "awaiting_operator_review", "awaiting_operator_review"

    def _supersede_existing_drafts(
        self,
        case_id: str,
        packet_id: str,
        target_id: str,
        now: datetime,
    ) -> None:
        existing = list(self._session.exec(
            select(SubmissionDraftModel)
            .where(SubmissionDraftModel.case_id == case_id)
            .where(SubmissionDraftModel.packet_id == packet_id)
            .where(SubmissionDraftModel.submission_target_id == target_id)
            .where(SubmissionDraftModel.status != "superseded_placeholder")
        ).all())
        for draft in existing:
            draft.status = "superseded_placeholder"
            draft.updated_at = now
            self._session.add(draft)

    def _mapping_to_model(
        self,
        draft_id: str,
        mapping: SubmissionMappingFieldDefinition,
        now: datetime,
    ) -> SubmissionMappingModel:
        preview = mapping.value_preview
        source = mapping.source_reference or (preview.source_reference if preview else None)
        return SubmissionMappingModel(
            mapping_id=mapping.mapping_id,
            draft_id=draft_id,
            target_field_name=mapping.target_field.field_name,
            target_section=mapping.target_field.target_section,
            target_label=mapping.target_field.display_label,
            target_field_type=mapping.target_field.field_type,
            target_required=mapping.target_field.required,
            status=mapping.status,
            source_entity_type=source.source_entity_type if source else None,
            source_entity_id=source.source_entity_id if source else None,
            source_path=source.source_path if source else None,
            source_label=source.display_label if source else None,
            preview_text=preview.text_value if preview else None,
            preview_json=preview.raw_value if preview else None,
            notes_json=list(mapping.notes),
            created_at=now,
            updated_at=now,
        )

    def _load_mappings(
        self,
        draft_id: str,
        *,
        target: SubmissionTargetMetadata | None = None,
    ) -> list[SubmissionMappingFieldDefinition]:
        rows = list(self._session.exec(
            select(SubmissionMappingModel)
            .where(SubmissionMappingModel.draft_id == draft_id)
            .order_by(SubmissionMappingModel.created_at, SubmissionMappingModel.mapping_id)
        ).all())
        target_fields = {
            (field.field_name, field.target_section): field
            for field in (target.default_target_fields if target else [])
        }
        return [
            self._mapping_from_model(
                row,
                target_field_template=target_fields.get((row.target_field_name, row.target_section)),
            )
            for row in rows
        ]

    def _mapping_from_model(
        self,
        row: SubmissionMappingModel,
        *,
        target_field_template: SubmissionMappingTargetField | None = None,
    ) -> SubmissionMappingFieldDefinition:
        source_reference = None
        if row.source_entity_type:
            source_reference = SubmissionMappingSourceReference(
                source_entity_type=row.source_entity_type,
                source_entity_id=row.source_entity_id or "",
                source_path=row.source_path or "",
                display_label=row.source_label or "",
            )

        value_preview = None
        if row.preview_text is not None or row.preview_json is not None:
            value_preview = SubmissionFieldValuePreview(
                value_present=True,
                text_value=row.preview_text or "",
                raw_value=row.preview_json,
                source_reference=source_reference,
                notes=[],
            )

        return SubmissionMappingFieldDefinition(
            mapping_id=row.mapping_id,
            target_field=SubmissionMappingTargetField(
                field_name=row.target_field_name,
                target_section=row.target_section,
                display_label=row.target_label,
                field_type=row.target_field_type,
                required=row.target_required,
                candidate_source_paths=list(target_field_template.candidate_source_paths)
                if target_field_template
                else [],
                notes=list(target_field_template.notes) if target_field_template else [],
            ),
            status=row.status,
            source_reference=source_reference,
            value_preview=value_preview,
            notes=list(row.notes_json),
        )

    def _latest_plan_record(self, draft_id: str) -> AutomationPlanModel | None:
        return self._session.exec(
            select(AutomationPlanModel)
            .where(AutomationPlanModel.draft_id == draft_id)
            .order_by(desc(AutomationPlanModel.created_at), desc(AutomationPlanModel.plan_id))
        ).first()

    def _load_latest_plan(self, draft_id: str) -> AutomationPlan | None:
        record = self._latest_plan_record(draft_id)
        if record is None:
            return None
        draft = self._require_draft(record.draft_id)
        source_metadata = SubmissionDraftSourceMetadata.model_validate(draft.source_metadata_json)
        resolved_target_pack = target_pack_registry.resolve_selection(
            source_metadata.target_pack_selection
        )
        steps = list(self._session.exec(
            select(AutomationPlanStepModel)
            .where(AutomationPlanStepModel.plan_id == record.plan_id)
            .order_by(AutomationPlanStepModel.step_index, AutomationPlanStepModel.step_id)
        ).all())
        return AutomationPlan(
            plan_id=record.plan_id,
            draft_id=record.draft_id,
            target_id=record.target_id,
            target_pack_selection=source_metadata.target_pack_selection,
            target_pack_automation_compatibility=(
                resolved_target_pack.automation_compatibility if resolved_target_pack is not None else None
            ),
            source_mode=record.source_mode,
            source_reviewed_snapshot_id=record.source_reviewed_snapshot_id,
            status=record.status,
            dry_run=record.dry_run,
            generated_at=isoformat_utc(record.created_at),
            guardrails=ExecutionGuardrailMetadata.model_validate(record.guardrails_json),
            dry_run_summary=DryRunResultSummary.model_validate(record.dry_run_summary_json),
            steps=[
                self._step_from_model(step)
                for step in steps
            ],
        )

    def _step_from_model(self, row: AutomationPlanStepModel):
        from casegraph_agent_sdk.submissions import AutomationFallbackRoutingHint, AutomationPlanStep

        return AutomationPlanStep(
            step_id=row.step_id,
            step_index=row.step_index,
            step_type=row.step_type,
            status=row.status,
            title=row.title,
            description=row.description,
            target_reference=row.target_reference,
            tool_id=row.tool_id,
            backend_id=row.backend_id,
            execution_mode=row.execution_mode,
            checkpoint_required=row.checkpoint_required,
            checkpoint_reason=row.checkpoint_reason,
            fallback_hint=(
                AutomationFallbackRoutingHint.model_validate(row.fallback_hint_json)
                if row.fallback_hint_json else None
            ),
            mapping_id=row.mapping_id,
            related_document_id=row.related_document_id,
            notes=list(row.notes_json),
        )

    def _synchronize_latest_plan_approval(self, draft: SubmissionDraftModel, now: datetime) -> None:
        record = self._latest_plan_record(draft.draft_id)
        if record is None:
            return
        guardrails = ExecutionGuardrailMetadata.model_validate(record.guardrails_json)
        guardrails.approval_status = draft.approval_status
        record.guardrails_json = guardrails.model_dump(mode="json")

        summary = DryRunResultSummary.model_validate(record.dry_run_summary_json)
        if draft.approval_status == "rejected":
            record.status = "blocked"
            summary.plan_status = "blocked"
        elif record.status not in {"blocked", "partial"}:
            record.status = (
                "approved_for_future_execution"
                if draft.approval_status == "approved_for_future_execution"
                else "awaiting_operator_review"
            )
            summary.plan_status = record.status
        record.dry_run_summary_json = summary.model_dump(mode="json")
        record.updated_at = now
        self._session.add(record)

    def _to_summary(self, draft: SubmissionDraftModel) -> SubmissionDraftSummary:
        source_metadata = SubmissionDraftSourceMetadata.model_validate(draft.source_metadata_json)
        return SubmissionDraftSummary(
            draft_id=draft.draft_id,
            case_id=draft.case_id,
            case_title=draft.case_title,
            packet_id=draft.packet_id,
            source_mode=draft.source_mode,
            source_reviewed_snapshot_id=draft.source_reviewed_snapshot_id,
            submission_target_id=draft.submission_target_id,
            submission_target_category=draft.submission_target_category,
            target_pack_selection=source_metadata.target_pack_selection,
            status=draft.status,
            approval_status=draft.approval_status,
            mapping_count=draft.mapping_count,
            unresolved_mapping_count=draft.unresolved_mapping_count,
            created_at=isoformat_utc(draft.created_at),
            updated_at=isoformat_utc(draft.updated_at),
            note=draft.note,
        )

    def _resolve_target_pack_context(
        self,
        case_metadata: dict[str, object],
        target: SubmissionTargetMetadata,
    ):
        selection = get_case_target_pack_selection(case_metadata)
        if selection is None:
            return None, None, target, []

        pack = target_pack_registry.get(selection.pack_id)
        if pack is None:
            return selection, None, target, [
                NormalizedResultIssue(
                    severity="warning",
                    code="selected_target_pack_missing",
                    message="Case references a target pack that is no longer registered.",
                )
            ]

        resolved_pack = target_pack_registry.resolve_selection(selection)
        if resolved_pack is None:
            return selection, None, target, [
                NormalizedResultIssue(
                    severity="warning",
                    code="selected_target_pack_version_mismatch",
                    message=(
                        "Case references a target-pack version that no longer matches "
                        "the current registry entry."
                    ),
                    related_entity_type="target_pack",
                    related_entity_id=selection.pack_id,
                )
            ]

        pack = resolved_pack

        if target.target_id not in pack.submission_compatibility.submission_target_ids:
            return selection, pack, target, [
                NormalizedResultIssue(
                    severity="warning",
                    code="target_pack_submission_target_mismatch",
                    message="Selected target pack is not compatible with the chosen submission target.",
                    related_entity_type="submission_target",
                    related_entity_id=target.target_id,
                )
            ]

        merged_target = target.model_copy(
            update={
                "default_target_fields": merge_submission_target_fields(
                    list(target.default_target_fields),
                    build_submission_target_fields(pack),
                )
            }
        )
        return selection, pack, merged_target, []

    def _to_approval(self, draft: SubmissionDraftModel) -> ApprovalRequirementMetadata:
        return ApprovalRequirementMetadata(
            requires_operator_approval=draft.requires_operator_approval,
            approval_status=draft.approval_status,
            approved_by=draft.approved_by,
            approved_at=isoformat_utc(draft.approved_at) if draft.approved_at else "",
            approval_note=draft.approval_note,
            scope="future_execution",
        )

    def _count_unresolved_mappings(self, mappings: list[SubmissionMappingFieldDefinition]) -> int:
        return sum(
            1
            for mapping in mappings
            if mapping.status in {"unresolved", "candidate_available", "requires_human_input"}
        )

    def _count_missing_required_mappings(self, mappings: list[SubmissionMappingFieldDefinition]) -> int:
        return sum(
            1
            for mapping in mappings
            if mapping.target_field.required
            and mapping.status in {"unresolved", "candidate_available", "requires_human_input"}
        )