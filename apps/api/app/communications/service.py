"""Case-scoped communication draft service.

This service builds reviewable draft content from explicit persisted case
state only. It does not send messages, infer recipient details, or assert
 medical, legal, tax, or payer correctness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import ChangeSummary, FieldChangeRecord
from casegraph_agent_sdk.communications import (
    CommunicationCopyExportArtifact,
    CommunicationDraftDetailResponse,
    CommunicationDraftEvidenceReference,
    CommunicationDraftGenerateRequest,
    CommunicationDraftGenerateResponse,
    CommunicationDraftGenerationMetadata,
    CommunicationDraftListResponse,
    CommunicationDraftRecord,
    CommunicationDraftReviewMetadata,
    CommunicationDraftReviewUpdateRequest,
    CommunicationDraftReviewUpdateResponse,
    CommunicationDraftSection,
    CommunicationDraftSourceEntityReference,
    CommunicationDraftSourceMetadata,
    CommunicationDraftSourceResponse,
    CommunicationDraftSummary,
    CommunicationTemplateMetadata,
)
from casegraph_agent_sdk.packets import PacketManifest
from casegraph_agent_sdk.rag import RetrievalScope
from casegraph_agent_sdk.readiness import CaseChecklist, ChecklistItem, ReadinessSummary
from casegraph_agent_sdk.submissions import NormalizedOperationResult, NormalizedResultIssue
from casegraph_agent_sdk.tasks import StructuredOutputSchema
from casegraph_agent_sdk.workflow_packs import (
    OperatorReviewRecommendation,
    WorkflowPackRunRecord,
    WorkflowPackStageResult,
)

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel, WorkflowRunRecordModel
from app.audit.service import AuditTrailService, audit_actor, derived_ref, entity_ref, source_ref
from app.communications.errors import CommunicationDraftServiceError
from app.communications.models import CommunicationDraftModel
from app.communications.registry import get_communication_template_registry
from app.config import settings
from app.extraction.models import ExtractionRunModel
from app.ingestion.models import DocumentRecord
from app.knowledge.dependencies import get_search_service
from app.operator_review.models import ActionItemModel, ReviewNoteModel
from app.packets.models import PacketRecordModel
from app.rag.evidence import EvidenceSelector
from app.readiness.service import ReadinessService
from app.tasks.service import TaskExecutionService
from app.workflow_packs.models import WorkflowPackRunModel
from app.persistence.database import isoformat_utc


@dataclass
class _CommunicationContext:
    case: CaseRecordModel
    linked_documents: list[DocumentRecord]
    extraction_runs: list[ExtractionRunModel]
    checklist: CaseChecklist | None
    readiness: ReadinessSummary | None
    open_actions: list[ActionItemModel]
    review_notes: list[ReviewNoteModel]
    packets: list[PacketRecordModel]
    workflow_runs: list[WorkflowRunRecordModel]
    workflow_pack_runs: list[WorkflowPackRunModel]


@dataclass
class _DraftBuildResult:
    title: str
    subject: str
    sections: list[CommunicationDraftSection]
    source_entities: list[CommunicationDraftSourceEntityReference]
    evidence_references: list[CommunicationDraftEvidenceReference]
    source_notes: list[str]
    issues: list[NormalizedResultIssue]


class CommunicationDraftService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._readiness = ReadinessService(session)
        self._task_service = TaskExecutionService(
            timeout_seconds=settings.provider_request_timeout_seconds,
        )
        search_service = get_search_service()
        self._evidence_selector = EvidenceSelector(search_service) if search_service is not None else None

    @staticmethod
    def list_templates() -> CommunicationTemplateListResponse:
        return get_communication_template_registry().list_metadata()

    def list_drafts(self, case_id: str) -> CommunicationDraftListResponse:
        self._require_case(case_id)
        rows = list(
            self._session.exec(
                select(CommunicationDraftModel)
                .where(CommunicationDraftModel.case_id == case_id)
                .order_by(desc(CommunicationDraftModel.updated_at), desc(CommunicationDraftModel.created_at))
            ).all()
        )
        return CommunicationDraftListResponse(drafts=[self._to_summary(row) for row in rows])

    async def generate_draft(
        self,
        case_id: str,
        request: CommunicationDraftGenerateRequest,
    ) -> CommunicationDraftGenerateResponse:
        definition = get_communication_template_registry().get(request.template_id)
        if definition is None:
            raise CommunicationDraftServiceError(
                f"Communication template '{request.template_id}' was not found.",
                status_code=404,
            )

        if request.strategy == "provider_assisted_draft" and request.provider_selection is None:
            raise CommunicationDraftServiceError(
                "Provider selection is required when requesting a provider-assisted communication draft.",
                status_code=400,
            )

        context = self._load_context(case_id)
        selected_packet = self._resolve_packet(context, request.packet_id)
        selected_workflow_run = self._resolve_workflow_run(context, request.workflow_run_id)
        selected_workflow_pack_run = self._resolve_workflow_pack_run(
            context,
            request.workflow_pack_run_id,
        )

        build_result = self._build_draft(
            definition.metadata,
            context,
            selected_packet=selected_packet,
            selected_workflow_run=selected_workflow_run,
            selected_workflow_pack_run=selected_workflow_pack_run,
            include_document_evidence=request.include_document_evidence,
        )

        source_metadata = self._build_source_metadata(
            context,
            selected_packet=selected_packet,
            selected_workflow_run=selected_workflow_run,
            selected_workflow_pack_run=selected_workflow_pack_run,
            evidence_references=build_result.evidence_references,
            notes=build_result.source_notes,
        )

        generation_notes: list[str] = []
        if request.note.strip():
            generation_notes.append("Operator note was recorded for traceability but not injected into draft content.")
            build_result.issues.append(
                NormalizedResultIssue(
                    severity="info",
                    code="operator_note_not_applied",
                    message="The operator note was not inserted into the draft body.",
                )
            )

        title = build_result.title
        subject = build_result.subject
        sections = build_result.sections
        strategy = "deterministic_template_only"
        result_message = "Communication draft generated from explicit case state."
        generation = CommunicationDraftGenerationMetadata(
            strategy="deterministic_template_only",
            used_document_evidence=any(
                reference.kind == "retrieved_document_chunk"
                for reference in build_result.evidence_references
            ),
            notes=list(generation_notes),
        )

        if request.strategy == "provider_assisted_draft" and request.provider_selection is not None:
            rewrite = await self._rewrite_with_provider(
                template=definition.metadata,
                provider_selection=request.provider_selection,
                title=title,
                subject=subject,
                sections=sections,
                source_metadata=source_metadata,
                source_entities=build_result.source_entities,
                evidence_references=build_result.evidence_references,
            )
            generation.provider = rewrite["generation"].provider
            generation.model_id = rewrite["generation"].model_id
            generation.finish_reason = rewrite["generation"].finish_reason
            generation.duration_ms = rewrite["generation"].duration_ms
            generation.provider_request_id = rewrite["generation"].provider_request_id
            generation.usage = rewrite["generation"].usage
            generation.error = rewrite["generation"].error
            generation.notes.extend(rewrite["generation"].notes)
            if rewrite["rewritten"]:
                title = rewrite["title"]
                subject = rewrite["subject"]
                sections = rewrite["sections"]
                strategy = "provider_assisted_draft"
                generation.strategy = "provider_assisted_draft"
                result_message = (
                    "Communication draft generated from explicit case state with provider-assisted phrasing."
                )
            else:
                build_result.issues.extend(rewrite["issues"])
                result_message = (
                    "Communication draft generated from explicit case state. Provider-assisted phrasing was unavailable, so the deterministic draft was saved."
                )

        now = datetime.now(UTC)
        review = CommunicationDraftReviewMetadata(
            requires_human_review=True,
            last_updated_by=request.operator_id.strip(),
            last_updated_at=isoformat_utc(now),
        )

        model = CommunicationDraftModel(
            draft_id=str(uuid4()),
            case_id=context.case.case_id,
            template_id=definition.metadata.template_id,
            draft_type=definition.metadata.draft_type,
            audience_type=definition.metadata.audience_type,
            status="needs_human_review",
            strategy=strategy,
            packet_id=selected_packet.packet_id if selected_packet is not None else None,
            workflow_run_id=selected_workflow_run.run_id if selected_workflow_run is not None else None,
            workflow_pack_run_id=(
                selected_workflow_pack_run.run_id if selected_workflow_pack_run is not None else None
            ),
            title=title,
            subject=subject,
            sections_json=[section.model_dump(mode="json") for section in sections],
            source_metadata_json=source_metadata.model_dump(mode="json"),
            source_entities_json=[entity.model_dump(mode="json") for entity in build_result.source_entities],
            evidence_references_json=[
                reference.model_dump(mode="json") for reference in build_result.evidence_references
            ],
            review_json=review.model_dump(mode="json"),
            generation_json=generation.model_dump(mode="json"),
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)

        generation_actor = (
            audit_actor("operator", actor_id=request.operator_id.strip(), display_name=request.operator_id.strip())
            if request.operator_id.strip()
            else audit_actor("service", actor_id="communications.service", display_name="Communication Draft Service")
        )
        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=context.case.case_id,
            category="communication",
            event_type="communication_draft_generated",
            actor=generation_actor,
            entity=entity_ref(
                "communication_draft",
                model.draft_id,
                case_id=context.case.case_id,
                display_label=definition.metadata.template_id,
            ),
            change_summary=ChangeSummary(message=result_message),
            metadata={"template_id": definition.metadata.template_id, "strategy": strategy},
        )
        decision = audit.append_decision(
            case_id=context.case.case_id,
            decision_type="communication_draft_generated",
            actor=generation_actor,
            source_entity=entity_ref("communication_draft", model.draft_id, case_id=context.case.case_id, display_label=definition.metadata.template_id),
            outcome=model.status,
            note=request.note.strip(),
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)
        lineage_edges = [
            (
                "case_context",
                source_ref("case", context.case.case_id, case_id=context.case.case_id, display_label=context.case.title, source_path="case"),
                None,
            ),
        ]
        if context.checklist is not None:
            lineage_edges.append(
                (
                    "checklist_reference",
                    source_ref("checklist", context.checklist.checklist_id, case_id=context.case.case_id, display_label="Case checklist", source_path="readiness.checklist"),
                    None,
                )
            )
        if selected_packet is not None:
            lineage_edges.append(
                (
                    "packet_source",
                    source_ref("packet", selected_packet.packet_id, case_id=context.case.case_id, display_label=selected_packet.case_title, source_path="packet"),
                    None,
                )
            )
        if selected_workflow_run is not None:
            lineage_edges.append(
                (
                    "workflow_reference",
                    source_ref("workflow_run", selected_workflow_run.run_id, case_id=context.case.case_id, display_label=selected_workflow_run.workflow_id, source_path="workflow_run"),
                    None,
                )
            )
        if selected_workflow_pack_run is not None:
            lineage_edges.append(
                (
                    "workflow_pack_reference",
                    source_ref("workflow_pack_run", selected_workflow_pack_run.run_id, case_id=context.case.case_id, display_label=selected_workflow_pack_run.workflow_pack_id, source_path="workflow_pack_run"),
                    None,
                )
            )
        audit.record_lineage(
            case_id=context.case.case_id,
            artifact=derived_ref("communication_draft", model.draft_id, case_id=context.case.case_id, display_label=definition.metadata.template_id),
            edges=lineage_edges,
            notes=["Communication draft lineage reflects the explicit case references selected during draft generation."],
            metadata={"template_id": definition.metadata.template_id, "strategy": strategy},
        )
        self._session.commit()
        self._session.refresh(model)

        draft = self._to_record(model)
        return CommunicationDraftGenerateResponse(
            result=NormalizedOperationResult(
                success=True,
                message=result_message,
                issues=build_result.issues,
            ),
            draft=draft,
            template=definition.metadata,
            copy_artifacts=self._build_copy_artifacts(draft),
        )

    def get_draft(self, draft_id: str) -> CommunicationDraftDetailResponse:
        model = self._require_draft(draft_id)
        draft = self._to_record(model)
        template = get_communication_template_registry().get(draft.template_id)
        return CommunicationDraftDetailResponse(
            draft=draft,
            template=template.metadata if template is not None else None,
            copy_artifacts=self._build_copy_artifacts(draft),
        )

    def get_sources(self, draft_id: str) -> CommunicationDraftSourceResponse:
        draft = self._to_record(self._require_draft(draft_id))
        return CommunicationDraftSourceResponse(
            draft_id=draft.draft_id,
            source_metadata=draft.source_metadata,
            source_entities=draft.source_entities,
            evidence_references=draft.evidence_references,
        )

    def update_review(
        self,
        draft_id: str,
        request: CommunicationDraftReviewUpdateRequest,
    ) -> CommunicationDraftReviewUpdateResponse:
        model = self._require_draft(draft_id)
        try:
            review = CommunicationDraftReviewMetadata.model_validate(model.review_json or {})
        except (ValidationError, TypeError, ValueError) as exc:
            raise CommunicationDraftServiceError(
                f"Communication draft '{draft_id}' contains invalid persisted review metadata and could not be updated.",
                status_code=500,
            ) from exc
        now = datetime.now(UTC)
        reviewer = request.reviewed_by.strip()
        previous_status = model.status
        previous_reviewed_by = review.reviewed_by
        previous_review_notes = review.review_notes
        previous_requires_human_review = review.requires_human_review

        if request.status is not None:
            model.status = request.status
            review.requires_human_review = request.status == "needs_human_review"
        if reviewer:
            review.reviewed_by = reviewer
            review.last_updated_by = reviewer
        if request.review_notes.strip():
            review.review_notes = request.review_notes.strip()
        if request.status is not None or reviewer or request.review_notes.strip():
            review.reviewed_at = isoformat_utc(now)

        if not review.last_updated_by and review.reviewed_by:
            review.last_updated_by = review.reviewed_by
        review.last_updated_at = isoformat_utc(now)

        model.review_json = review.model_dump(mode="json")
        model.updated_at = now
        self._session.add(model)

        review_actor = (
            audit_actor("operator", actor_id=reviewer, display_name=reviewer)
            if reviewer
            else audit_actor("service", actor_id="communications.service", display_name="Communication Draft Service")
        )
        field_changes: list[FieldChangeRecord] = []
        if previous_status != model.status:
            field_changes.append(
                FieldChangeRecord(field_path="status", old_value=previous_status, new_value=model.status)
            )
        if previous_reviewed_by != review.reviewed_by:
            field_changes.append(
                FieldChangeRecord(
                    field_path="review.reviewed_by",
                    old_value=previous_reviewed_by,
                    new_value=review.reviewed_by,
                )
            )
        if previous_review_notes != review.review_notes:
            field_changes.append(
                FieldChangeRecord(
                    field_path="review.review_notes",
                    old_value=previous_review_notes,
                    new_value=review.review_notes,
                )
            )
        if previous_requires_human_review != review.requires_human_review:
            field_changes.append(
                FieldChangeRecord(
                    field_path="review.requires_human_review",
                    old_value=previous_requires_human_review,
                    new_value=review.requires_human_review,
                )
            )

        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=model.case_id,
            category="communication",
            event_type="communication_draft_review_updated",
            actor=review_actor,
            entity=entity_ref(
                "communication_draft",
                model.draft_id,
                case_id=model.case_id,
                display_label=model.template_id,
            ),
            change_summary=ChangeSummary(
                message="Communication draft review metadata updated.",
                field_changes=field_changes,
            ),
            metadata={"reviewed_by": review.reviewed_by, "status": model.status},
        )
        decision = audit.append_decision(
            case_id=model.case_id,
            decision_type="communication_draft_review_updated",
            actor=review_actor,
            source_entity=entity_ref(
                "communication_draft",
                model.draft_id,
                case_id=model.case_id,
                display_label=model.template_id,
            ),
            outcome=model.status,
            note=review.review_notes,
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)

        self._session.commit()
        self._session.refresh(model)

        return CommunicationDraftReviewUpdateResponse(
            result=NormalizedOperationResult(
                success=True,
                message="Communication draft review metadata updated.",
            ),
            draft=self._to_record(model),
        )

    def _build_draft(
        self,
        template: CommunicationTemplateMetadata,
        context: _CommunicationContext,
        *,
        selected_packet: PacketRecordModel | None,
        selected_workflow_run: WorkflowRunRecordModel | None,
        selected_workflow_pack_run: WorkflowPackRunModel | None,
        include_document_evidence: bool,
    ) -> _DraftBuildResult:
        if template.template_id == "missing_document_request":
            return self._build_missing_document_request(
                context,
                selected_workflow_pack_run=selected_workflow_pack_run,
                include_document_evidence=include_document_evidence,
            )
        if template.template_id == "internal_handoff_note":
            return self._build_internal_handoff_note(
                context,
                selected_packet=selected_packet,
                selected_workflow_run=selected_workflow_run,
                selected_workflow_pack_run=selected_workflow_pack_run,
                include_document_evidence=include_document_evidence,
            )
        if template.template_id == "packet_cover_note":
            return self._build_packet_cover_note(
                context,
                selected_packet=selected_packet,
                selected_workflow_pack_run=selected_workflow_pack_run,
                include_document_evidence=include_document_evidence,
            )
        raise CommunicationDraftServiceError(
            f"Communication template '{template.template_id}' is not implemented.",
            status_code=501,
        )

    def _build_missing_document_request(
        self,
        context: _CommunicationContext,
        *,
        selected_workflow_pack_run: WorkflowPackRunModel | None,
        include_document_evidence: bool,
    ) -> _DraftBuildResult:
        missing_items = self._missing_required_items(context)
        if not missing_items:
            raise CommunicationDraftServiceError(
                "A missing-document request draft requires at least one required checklist item that is still missing or unresolved.",
                status_code=400,
            )

        entities: list[CommunicationDraftSourceEntityReference] = []
        evidence: list[CommunicationDraftEvidenceReference] = []
        issues: list[NormalizedResultIssue] = []
        notes: list[str] = []
        seen_entities: set[tuple[str, str, str]] = set()

        self._append_source_entity(
            entities,
            seen_entities,
            CommunicationDraftSourceEntityReference(
                source_entity_type="case",
                source_entity_id=context.case.case_id,
                display_label=context.case.title,
                source_path="case",
            ),
        )

        if context.checklist is not None:
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="checklist",
                    source_entity_id=context.checklist.checklist_id,
                    display_label="Case checklist",
                    source_path="readiness.checklist",
                ),
            )

        for item in missing_items:
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="checklist_item",
                    source_entity_id=item.item_id,
                    display_label=item.display_name,
                    source_path=f"readiness.items.{item.item_id}",
                ),
            )
            evidence.append(
                CommunicationDraftEvidenceReference(
                    evidence_id=f"checklist-item-{item.item_id}",
                    label=f"Checklist item: {item.display_name}",
                    kind="state_summary",
                    snippet_text=(
                        f"Required checklist item '{item.display_name}' is currently '{item.status}'. "
                        f"{item.description.strip() or 'No supporting case-linked artifact currently resolves this item.'}"
                    ),
                    source_entity_type="checklist_item",
                    source_entity_id=item.item_id,
                )
            )

        if selected_workflow_pack_run is not None:
            recommendation = self._workflow_pack_recommendation(selected_workflow_pack_run)
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="workflow_pack_run",
                    source_entity_id=selected_workflow_pack_run.run_id,
                    display_label="Workflow pack run",
                    source_path=f"workflow_pack_runs.{selected_workflow_pack_run.run_id}",
                ),
            )
            if recommendation.has_missing_required_documents or recommendation.notes:
                evidence.append(
                    CommunicationDraftEvidenceReference(
                        evidence_id=f"workflow-pack-{selected_workflow_pack_run.run_id}",
                        label="Workflow pack recommendation",
                        kind="state_summary",
                        snippet_text=(
                            "Workflow pack review recommendation notes: "
                            + "; ".join(recommendation.notes or ["Missing required documents remain."])
                        ),
                        source_entity_type="workflow_pack_run",
                        source_entity_id=selected_workflow_pack_run.run_id,
                    )
                )

        doc_refs, doc_issues, doc_notes = self._select_document_evidence(
            context,
            include_document_evidence=include_document_evidence,
            query=(
                f"{context.case.title} missing required documents "
                + " ".join(item.display_name for item in missing_items[:4])
            ),
        )
        issues.extend(doc_issues)
        notes.extend(doc_notes)
        evidence.extend(doc_refs)
        for reference in doc_refs:
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="document",
                    source_entity_id=reference.source_entity_id,
                    display_label=reference.label,
                    source_path=f"documents.{reference.source_entity_id}",
                ),
            )

        readiness_status = context.readiness.readiness_status if context.readiness is not None else "not_evaluated"
        title = f"Missing document request draft - {context.case.title}"
        subject = f"Additional case materials needed: {context.case.title}"

        request_bullets = [
            (
                f"{item.display_name}: "
                f"{item.description.strip() or 'This required item is not yet supported by linked case artifacts.'} "
                f"Current status: {item.status.replace('_', ' ')}."
            )
            for item in missing_items
        ]
        evidence_bullets = [reference.snippet_text for reference in evidence]
        if not evidence_bullets:
            evidence_bullets.append("No document-evidence snippets were attached to this draft.")

        sections = [
            CommunicationDraftSection(
                section_type="summary",
                title="Current State",
                body=(
                    f"This draft is grounded in the current case checklist for {context.case.title}. "
                    f"{len(missing_items)} required item(s) remain unresolved. "
                    f"Readiness status is {readiness_status.replace('_', ' ')}."
                ),
                evidence_reference_ids=[
                    reference.evidence_id
                    for reference in evidence
                    if reference.source_entity_type in {"checklist_item", "workflow_pack_run"}
                ],
            ),
            CommunicationDraftSection(
                section_type="request_items",
                title="Requested Items",
                bullet_items=request_bullets,
                evidence_reference_ids=[
                    reference.evidence_id
                    for reference in evidence
                    if reference.source_entity_type == "checklist_item"
                ],
            ),
            CommunicationDraftSection(
                section_type="evidence_snippets",
                title="Grounding Notes",
                bullet_items=evidence_bullets,
                evidence_reference_ids=[reference.evidence_id for reference in evidence],
            ),
            CommunicationDraftSection(
                section_type="closing",
                title="Review Gate",
                body=(
                    "This draft intentionally omits recipient identity, contact details, delivery channel, and deadline language. "
                    "Confirm final wording and delivery details during operator review."
                ),
            ),
        ]

        return _DraftBuildResult(
            title=title,
            subject=subject,
            sections=sections,
            source_entities=entities,
            evidence_references=evidence,
            source_notes=notes,
            issues=issues,
        )

    def _build_internal_handoff_note(
        self,
        context: _CommunicationContext,
        *,
        selected_packet: PacketRecordModel | None,
        selected_workflow_run: WorkflowRunRecordModel | None,
        selected_workflow_pack_run: WorkflowPackRunModel | None,
        include_document_evidence: bool,
    ) -> _DraftBuildResult:
        entities: list[CommunicationDraftSourceEntityReference] = []
        evidence: list[CommunicationDraftEvidenceReference] = []
        issues: list[NormalizedResultIssue] = []
        notes: list[str] = []
        seen_entities: set[tuple[str, str, str]] = set()

        missing_items = self._missing_required_items(context)

        self._append_source_entity(
            entities,
            seen_entities,
            CommunicationDraftSourceEntityReference(
                source_entity_type="case",
                source_entity_id=context.case.case_id,
                display_label=context.case.title,
                source_path="case",
            ),
        )

        if context.readiness is not None:
            evidence.append(
                CommunicationDraftEvidenceReference(
                    evidence_id=f"readiness-{context.readiness.checklist_id}",
                    label="Readiness summary",
                    kind="state_summary",
                    snippet_text=(
                        f"Readiness status is '{context.readiness.readiness_status}' with "
                        f"{context.readiness.missing_items} missing item(s) and "
                        f"{context.readiness.needs_review_items} item(s) needing review."
                    ),
                    source_entity_type="readiness_summary",
                    source_entity_id=context.readiness.checklist_id,
                )
            )

        for action in context.open_actions[:8]:
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="action_item",
                    source_entity_id=action.action_item_id,
                    display_label=action.title,
                    source_path=f"actions.{action.action_item_id}",
                ),
            )
            evidence.append(
                CommunicationDraftEvidenceReference(
                    evidence_id=f"action-{action.action_item_id}",
                    label=f"Open action: {action.title}",
                    kind="state_summary",
                    snippet_text=(
                        f"Open action '{action.title}' is priority '{action.priority}' and sourced from {action.source}. "
                        f"{action.source_reason or action.description}"
                    ),
                    source_entity_type="action_item",
                    source_entity_id=action.action_item_id,
                )
            )

        if selected_workflow_run is not None:
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="workflow_run",
                    source_entity_id=selected_workflow_run.run_id,
                    display_label=selected_workflow_run.workflow_id,
                    source_path=f"workflow_runs.{selected_workflow_run.run_id}",
                ),
            )
            evidence.append(
                CommunicationDraftEvidenceReference(
                    evidence_id=f"workflow-run-{selected_workflow_run.run_id}",
                    label="Workflow run status",
                    kind="state_summary",
                    snippet_text=(
                        f"Workflow run '{selected_workflow_run.workflow_id}' is currently '{selected_workflow_run.status}'."
                    ),
                    source_entity_type="workflow_run",
                    source_entity_id=selected_workflow_run.run_id,
                )
            )

        if selected_workflow_pack_run is not None:
            recommendation = self._workflow_pack_recommendation(selected_workflow_pack_run)
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="workflow_pack_run",
                    source_entity_id=selected_workflow_pack_run.run_id,
                    display_label="Workflow pack run",
                    source_path=f"workflow_pack_runs.{selected_workflow_pack_run.run_id}",
                ),
            )
            evidence.append(
                CommunicationDraftEvidenceReference(
                    evidence_id=f"workflow-pack-{selected_workflow_pack_run.run_id}",
                    label="Workflow pack recommendation",
                    kind="state_summary",
                    snippet_text=(
                        f"Workflow pack run status is '{selected_workflow_pack_run.status}' and the suggested next stage is "
                        f"'{recommendation.suggested_next_stage}'."
                    ),
                    source_entity_type="workflow_pack_run",
                    source_entity_id=selected_workflow_pack_run.run_id,
                )
            )

        latest_review_note = context.review_notes[0] if context.review_notes else None
        if latest_review_note is not None:
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="review_note",
                    source_entity_id=latest_review_note.note_id,
                    display_label="Latest review note",
                    source_path=f"review_notes.{latest_review_note.note_id}",
                ),
            )
            evidence.append(
                CommunicationDraftEvidenceReference(
                    evidence_id=f"review-note-{latest_review_note.note_id}",
                    label="Latest review note",
                    kind="state_summary",
                    snippet_text=latest_review_note.body,
                    source_entity_type="review_note",
                    source_entity_id=latest_review_note.note_id,
                )
            )

        if selected_packet is not None:
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="packet",
                    source_entity_id=selected_packet.packet_id,
                    display_label="Latest packet",
                    source_path=f"packets.{selected_packet.packet_id}",
                ),
            )

        doc_refs, doc_issues, doc_notes = self._select_document_evidence(
            context,
            include_document_evidence=include_document_evidence,
            query=(
                f"{context.case.title} internal handoff summary "
                + " ".join(action.title for action in context.open_actions[:4])
            ),
        )
        issues.extend(doc_issues)
        notes.extend(doc_notes)
        evidence.extend(doc_refs)
        for reference in doc_refs:
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="document",
                    source_entity_id=reference.source_entity_id,
                    display_label=reference.label,
                    source_path=f"documents.{reference.source_entity_id}",
                ),
            )

        follow_up_items = [
            f"Open action: {action.title} ({action.priority}) - {action.description or action.source_reason}"
            for action in context.open_actions[:6]
        ]
        if not follow_up_items:
            follow_up_items.append("No open action items are currently persisted for this case.")
        for item in missing_items[:4]:
            follow_up_items.append(
                f"Checklist gap: {item.display_name} remains {item.status.replace('_', ' ')}."
            )

        evidence_bullets = [reference.snippet_text for reference in evidence]
        if not evidence_bullets:
            evidence_bullets.append("No additional grounding notes were attached.")

        latest_note_text = latest_review_note.body if latest_review_note is not None else "No persisted review note is currently attached."
        title = f"Internal handoff note - {context.case.title}"
        subject = f"Internal handoff summary: {context.case.title}"
        sections = [
            CommunicationDraftSection(
                section_type="summary",
                title="Case Summary",
                body=(
                    f"Case '{context.case.title}' is currently in stage '{context.case.current_stage or 'intake'}' "
                    f"with status '{context.case.status}'. "
                    f"There are {len(context.open_actions)} open action(s) and {len(missing_items)} unresolved required checklist item(s)."
                ),
                evidence_reference_ids=[reference.evidence_id for reference in evidence[:3]],
            ),
            CommunicationDraftSection(
                section_type="follow_up_items",
                title="Follow-Up Items",
                bullet_items=follow_up_items,
                evidence_reference_ids=[
                    reference.evidence_id
                    for reference in evidence
                    if reference.source_entity_type in {"action_item", "checklist_item", "workflow_run"}
                ],
            ),
            CommunicationDraftSection(
                section_type="evidence_snippets",
                title="Grounding Notes",
                bullet_items=evidence_bullets,
                evidence_reference_ids=[reference.evidence_id for reference in evidence],
            ),
            CommunicationDraftSection(
                section_type="operator_review_note",
                title="Latest Review Context",
                body=latest_note_text,
                evidence_reference_ids=[
                    reference.evidence_id
                    for reference in evidence
                    if reference.source_entity_type in {"review_note", "workflow_pack_run"}
                ],
            ),
            CommunicationDraftSection(
                section_type="closing",
                title="Review Gate",
                body=(
                    "This handoff draft is a summary of persisted case state only. "
                    "Validate any next-step recommendations during operator review."
                ),
            ),
        ]

        return _DraftBuildResult(
            title=title,
            subject=subject,
            sections=sections,
            source_entities=entities,
            evidence_references=evidence,
            source_notes=notes,
            issues=issues,
        )

    def _build_packet_cover_note(
        self,
        context: _CommunicationContext,
        *,
        selected_packet: PacketRecordModel | None,
        selected_workflow_pack_run: WorkflowPackRunModel | None,
        include_document_evidence: bool,
    ) -> _DraftBuildResult:
        if selected_packet is None:
            raise CommunicationDraftServiceError(
                "A packet cover note draft requires a real generated packet for the case.",
                status_code=400,
            )

        manifest = PacketManifest.model_validate(selected_packet.manifest_json)
        entities: list[CommunicationDraftSourceEntityReference] = []
        evidence: list[CommunicationDraftEvidenceReference] = []
        issues: list[NormalizedResultIssue] = []
        notes: list[str] = []
        seen_entities: set[tuple[str, str, str]] = set()

        self._append_source_entity(
            entities,
            seen_entities,
            CommunicationDraftSourceEntityReference(
                source_entity_type="case",
                source_entity_id=context.case.case_id,
                display_label=context.case.title,
                source_path="case",
            ),
        )
        self._append_source_entity(
            entities,
            seen_entities,
            CommunicationDraftSourceEntityReference(
                source_entity_type="packet",
                source_entity_id=selected_packet.packet_id,
                display_label="Generated packet",
                source_path=f"packets.{selected_packet.packet_id}",
            ),
        )

        evidence.append(
            CommunicationDraftEvidenceReference(
                evidence_id=f"packet-{selected_packet.packet_id}",
                label="Packet manifest",
                kind="state_summary",
                snippet_text=(
                    f"Packet '{selected_packet.packet_id}' contains {manifest.linked_document_count} linked document(s), "
                    f"{manifest.extraction_count} extraction result(s), and readiness status '{manifest.readiness_status}'."
                ),
                source_entity_type="packet",
                source_entity_id=selected_packet.packet_id,
            )
        )

        for section in manifest.sections[:6]:
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="packet_section",
                    source_entity_id=section.section_type,
                    display_label=section.title,
                    source_path=f"packets.{selected_packet.packet_id}.sections.{section.section_type}",
                ),
            )
            if not section.empty:
                evidence.append(
                    CommunicationDraftEvidenceReference(
                        evidence_id=f"packet-section-{selected_packet.packet_id}-{section.section_type}",
                        label=f"Packet section: {section.title}",
                        kind="state_summary",
                        snippet_text=f"Packet section '{section.title}' contains {section.item_count} item(s).",
                        source_entity_type="packet_section",
                        source_entity_id=section.section_type,
                    )
                )

        if selected_workflow_pack_run is not None:
            recommendation = self._workflow_pack_recommendation(selected_workflow_pack_run)
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="workflow_pack_run",
                    source_entity_id=selected_workflow_pack_run.run_id,
                    display_label="Workflow pack run",
                    source_path=f"workflow_pack_runs.{selected_workflow_pack_run.run_id}",
                ),
            )
            evidence.append(
                CommunicationDraftEvidenceReference(
                    evidence_id=f"packet-workflow-pack-{selected_workflow_pack_run.run_id}",
                    label="Workflow pack recommendation",
                    kind="state_summary",
                    snippet_text=(
                        f"Workflow pack suggested next stage '{recommendation.suggested_next_stage}' with run status "
                        f"'{selected_workflow_pack_run.status}'."
                    ),
                    source_entity_type="workflow_pack_run",
                    source_entity_id=selected_workflow_pack_run.run_id,
                )
            )

        doc_refs, doc_issues, doc_notes = self._select_document_evidence(
            context,
            include_document_evidence=include_document_evidence,
            query=f"{context.case.title} packet summary cover note",
        )
        issues.extend(doc_issues)
        notes.extend(doc_notes)
        evidence.extend(doc_refs)
        for reference in doc_refs:
            self._append_source_entity(
                entities,
                seen_entities,
                CommunicationDraftSourceEntityReference(
                    source_entity_type="document",
                    source_entity_id=reference.source_entity_id,
                    display_label=reference.label,
                    source_path=f"documents.{reference.source_entity_id}",
                ),
            )

        section_bullets = [
            f"{section.title}: {section.item_count} item(s)."
            for section in manifest.sections
            if not section.empty
        ]
        if not section_bullets:
            section_bullets.append("The packet currently has no populated sections.")

        packet_context = [
            f"Packet ID: {selected_packet.packet_id}",
            f"Generated at: {isoformat_utc(selected_packet.generated_at)}",
            f"Readiness status: {manifest.readiness_status}",
            f"Linked documents: {manifest.linked_document_count}",
            f"Extraction results: {manifest.extraction_count}",
            f"Open actions: {manifest.open_action_count}",
        ]
        title = f"Packet cover note draft - {context.case.title}"
        subject = f"Packet cover note: {context.case.title}"
        sections = [
            CommunicationDraftSection(
                section_type="summary",
                title="Packet Summary",
                body=(
                    f"This draft summarizes packet '{selected_packet.packet_id}' for case '{context.case.title}'. "
                    f"The packet reflects persisted case state at {isoformat_utc(selected_packet.generated_at)}."
                ),
                evidence_reference_ids=[f"packet-{selected_packet.packet_id}"],
            ),
            CommunicationDraftSection(
                section_type="packet_context",
                title="Packet Context",
                bullet_items=packet_context,
                evidence_reference_ids=[
                    reference.evidence_id
                    for reference in evidence
                    if reference.source_entity_type in {"packet", "packet_section", "workflow_pack_run"}
                ],
            ),
            CommunicationDraftSection(
                section_type="evidence_snippets",
                title="Grounding Notes",
                bullet_items=section_bullets + [reference.snippet_text for reference in doc_refs],
                evidence_reference_ids=[reference.evidence_id for reference in evidence],
            ),
            CommunicationDraftSection(
                section_type="closing",
                title="Review Gate",
                body=(
                    "Confirm packet contents, recipient, and delivery instructions during operator review. "
                    "This feature does not send the packet or infer routing details."
                ),
            ),
        ]

        return _DraftBuildResult(
            title=title,
            subject=subject,
            sections=sections,
            source_entities=entities,
            evidence_references=evidence,
            source_notes=notes,
            issues=issues,
        )

    def _build_source_metadata(
        self,
        context: _CommunicationContext,
        *,
        selected_packet: PacketRecordModel | None,
        selected_workflow_run: WorkflowRunRecordModel | None,
        selected_workflow_pack_run: WorkflowPackRunModel | None,
        evidence_references: list[CommunicationDraftEvidenceReference],
        notes: list[str],
    ) -> CommunicationDraftSourceMetadata:
        missing_items = self._missing_required_items(context)
        latest_packet_id = selected_packet.packet_id if selected_packet is not None else (
            context.packets[0].packet_id if context.packets else None
        )
        return CommunicationDraftSourceMetadata(
            case_id=context.case.case_id,
            case_title=context.case.title,
            case_status=context.case.status,
            domain_pack_id=context.case.domain_pack_id,
            case_type_id=context.case.case_type_id,
            readiness_status=(
                context.readiness.readiness_status
                if context.readiness is not None
                else "not_evaluated"
            ),
            linked_document_count=len(context.linked_documents),
            extraction_run_count=len(context.extraction_runs),
            missing_required_item_count=len(missing_items),
            open_action_count=len(context.open_actions),
            latest_packet_id=latest_packet_id,
            workflow_run_id=selected_workflow_run.run_id if selected_workflow_run is not None else None,
            workflow_pack_run_id=(
                selected_workflow_pack_run.run_id if selected_workflow_pack_run is not None else None
            ),
            includes_document_evidence=any(
                reference.kind == "retrieved_document_chunk"
                for reference in evidence_references
            ),
            notes=notes,
        )

    def _load_context(self, case_id: str) -> _CommunicationContext:
        case = self._require_case(case_id)
        doc_links = list(
            self._session.exec(
                select(CaseDocumentLinkModel)
                .where(CaseDocumentLinkModel.case_id == case_id)
                .order_by(desc(CaseDocumentLinkModel.linked_at))
            ).all()
        )
        linked_documents: list[DocumentRecord] = []
        for link in doc_links:
            document = self._session.get(DocumentRecord, link.document_id)
            if document is not None:
                linked_documents.append(document)

        extraction_runs = list(
            self._session.exec(
                select(ExtractionRunModel)
                .where(ExtractionRunModel.case_id == case_id)
                .order_by(desc(ExtractionRunModel.created_at))
            ).all()
        )
        checklist_response = self._readiness.get_checklist(case_id)
        readiness_response = self._readiness.get_readiness(case_id)
        open_actions = list(
            self._session.exec(
                select(ActionItemModel)
                .where(ActionItemModel.case_id == case_id)
                .where(ActionItemModel.status == "open")
                .order_by(desc(ActionItemModel.updated_at), desc(ActionItemModel.created_at))
            ).all()
        )
        review_notes = list(
            self._session.exec(
                select(ReviewNoteModel)
                .where(ReviewNoteModel.case_id == case_id)
                .order_by(desc(ReviewNoteModel.created_at))
            ).all()
        )
        packets = list(
            self._session.exec(
                select(PacketRecordModel)
                .where(PacketRecordModel.case_id == case_id)
                .order_by(desc(PacketRecordModel.generated_at))
            ).all()
        )
        workflow_runs = list(
            self._session.exec(
                select(WorkflowRunRecordModel)
                .where(WorkflowRunRecordModel.case_id == case_id)
                .order_by(desc(WorkflowRunRecordModel.created_at))
            ).all()
        )
        workflow_pack_runs = list(
            self._session.exec(
                select(WorkflowPackRunModel)
                .where(WorkflowPackRunModel.case_id == case_id)
                .order_by(desc(WorkflowPackRunModel.created_at))
            ).all()
        )
        return _CommunicationContext(
            case=case,
            linked_documents=linked_documents,
            extraction_runs=extraction_runs,
            checklist=checklist_response.checklist if checklist_response is not None else None,
            readiness=readiness_response.readiness if readiness_response is not None else None,
            open_actions=open_actions,
            review_notes=review_notes,
            packets=packets,
            workflow_runs=workflow_runs,
            workflow_pack_runs=workflow_pack_runs,
        )

    def _resolve_packet(
        self,
        context: _CommunicationContext,
        packet_id: str | None,
    ) -> PacketRecordModel | None:
        if packet_id is None:
            return context.packets[0] if context.packets else None
        for packet in context.packets:
            if packet.packet_id == packet_id:
                return packet
        raise CommunicationDraftServiceError(
            f"Packet '{packet_id}' was not found for this case.",
            status_code=404,
        )

    def _resolve_workflow_run(
        self,
        context: _CommunicationContext,
        workflow_run_id: str | None,
    ) -> WorkflowRunRecordModel | None:
        if workflow_run_id is None:
            return context.workflow_runs[0] if context.workflow_runs else None
        for run in context.workflow_runs:
            if run.run_id == workflow_run_id:
                return run
        raise CommunicationDraftServiceError(
            f"Workflow run '{workflow_run_id}' was not found for this case.",
            status_code=404,
        )

    def _resolve_workflow_pack_run(
        self,
        context: _CommunicationContext,
        workflow_pack_run_id: str | None,
    ) -> WorkflowPackRunModel | None:
        if workflow_pack_run_id is None:
            return context.workflow_pack_runs[0] if context.workflow_pack_runs else None
        for run in context.workflow_pack_runs:
            if run.run_id == workflow_pack_run_id:
                return run
        raise CommunicationDraftServiceError(
            f"Workflow pack run '{workflow_pack_run_id}' was not found for this case.",
            status_code=404,
        )

    def _require_case(self, case_id: str) -> CaseRecordModel:
        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise CommunicationDraftServiceError(
                f"Case '{case_id}' was not found.",
                status_code=404,
            )
        return case

    def _require_draft(self, draft_id: str) -> CommunicationDraftModel:
        draft = self._session.get(CommunicationDraftModel, draft_id)
        if draft is None:
            raise CommunicationDraftServiceError(
                f"Communication draft '{draft_id}' was not found.",
                status_code=404,
            )
        return draft

    def _missing_required_items(self, context: _CommunicationContext) -> list[ChecklistItem]:
        if context.checklist is None:
            return []
        return [
            item
            for item in context.checklist.items
            if item.priority == "required" and item.status in {"missing", "needs_human_review"}
        ]

    def _workflow_pack_recommendation(
        self,
        model: WorkflowPackRunModel,
    ) -> OperatorReviewRecommendation:
        return OperatorReviewRecommendation.model_validate(model.review_recommendation_json or {})

    def _workflow_pack_record(self, model: WorkflowPackRunModel) -> WorkflowPackRunRecord:
        return WorkflowPackRunRecord(
            run_id=model.run_id,
            case_id=model.case_id,
            workflow_pack_id=model.workflow_pack_id,
            status=model.status,
            operator_id=model.operator_id,
            stage_results=[
                WorkflowPackStageResult.model_validate(item)
                for item in (model.stage_results_json or [])
            ],
            review_recommendation=self._workflow_pack_recommendation(model),
            created_at=isoformat_utc(model.created_at),
            started_at=isoformat_utc(model.started_at),
            completed_at=isoformat_utc(model.completed_at),
            notes=list(model.notes_json or []),
        )

    def _select_document_evidence(
        self,
        context: _CommunicationContext,
        *,
        include_document_evidence: bool,
        query: str,
    ) -> tuple[
        list[CommunicationDraftEvidenceReference],
        list[NormalizedResultIssue],
        list[str],
    ]:
        if not include_document_evidence:
            return [], [], []

        issues: list[NormalizedResultIssue] = []
        notes: list[str] = []
        if self._evidence_selector is None:
            issues.append(
                NormalizedResultIssue(
                    severity="warning",
                    code="document_evidence_unavailable",
                    message="Document evidence selection is unavailable in this environment.",
                )
            )
            return [], issues, notes

        document_ids = [document.document_id for document in context.linked_documents]
        if not document_ids:
            issues.append(
                NormalizedResultIssue(
                    severity="warning",
                    code="no_linked_documents",
                    message="No linked documents were available for document-evidence selection.",
                )
            )
            return [], issues, notes

        if len(document_ids) > 1:
            notes.append(
                "Document-evidence retrieval is currently limited to one linked document per query in the current vector-store path."
            )

        try:
            selection = self._evidence_selector.select(
                query,
                top_k=3,
                scope=RetrievalScope(kind="case", case_id=context.case.case_id),
                document_ids=document_ids,
            )
        except Exception as exc:
            issues.append(
                NormalizedResultIssue(
                    severity="warning",
                    code="document_evidence_lookup_failed",
                    message=f"Document evidence lookup failed: {exc}",
                )
            )
            return [], issues, notes

        references = [
            CommunicationDraftEvidenceReference(
                evidence_id=chunk.chunk_id,
                label=chunk.source_filename or f"Document {chunk.source_reference.document_id}",
                kind="retrieved_document_chunk",
                snippet_text=chunk.text,
                source_entity_type="document",
                source_entity_id=chunk.source_reference.document_id,
                source_reference=chunk.source_reference,
                notes=[
                    f"Retrieval score: {chunk.score.raw_score}",
                ],
            )
            for chunk in selection.chunks
        ]
        if not references:
            issues.append(
                NormalizedResultIssue(
                    severity="warning",
                    code="document_evidence_empty",
                    message="Document evidence was requested, but no retrieval chunks were selected.",
                )
            )
        return references, issues, notes

    async def _rewrite_with_provider(
        self,
        *,
        template: CommunicationTemplateMetadata,
        provider_selection,
        title: str,
        subject: str,
        sections: list[CommunicationDraftSection],
        source_metadata: CommunicationDraftSourceMetadata,
        source_entities: list[CommunicationDraftSourceEntityReference],
        evidence_references: list[CommunicationDraftEvidenceReference],
    ) -> dict[str, Any]:
        structured_output = StructuredOutputSchema(
            json_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "subject": {"type": "string"},
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "section_type": {
                                    "type": "string",
                                    "enum": [section.section_type for section in sections],
                                },
                                "title": {"type": "string"},
                                "body": {"type": "string"},
                                "bullet_items": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["section_type", "title", "body", "bullet_items"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["title", "subject", "sections"],
                "additionalProperties": False,
            },
            strict=True,
        )

        system_prompt = (
            "You rewrite communication drafts inside CaseGraph. Use only the grounded state provided. "
            "Do not invent recipient names, contact data, channels, deadlines, legal statements, medical claims, payer rules, tax guidance, or unsupported case facts. "
            "Preserve the same section types and order. If information is missing, omit it rather than guessing."
        )
        user_prompt = "\n\n".join(
            [
                f"Template: {template.display_name}",
                f"Audience: {template.audience_type}",
                "Rewrite the base draft for clarity only.",
                "SOURCE_METADATA:\n" + json.dumps(source_metadata.model_dump(mode="json"), indent=2),
                "SOURCE_ENTITIES:\n" + json.dumps(
                    [entity.model_dump(mode="json") for entity in source_entities],
                    indent=2,
                ),
                "EVIDENCE_REFERENCES:\n" + json.dumps(
                    [reference.model_dump(mode="json") for reference in evidence_references],
                    indent=2,
                ),
                "BASE_DRAFT:\n" + json.dumps(
                    {
                        "title": title,
                        "subject": subject,
                        "sections": [section.model_dump(mode="json") for section in sections],
                    },
                    indent=2,
                ),
            ]
        )

        result, _events = await self._task_service.execute_prepared_prompt(
            task_id="communication-draft-rewrite",
            provider_selection=provider_selection,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            structured_output=structured_output,
            max_tokens=900,
            temperature=0.2,
            trace_name="communication_draft.rewrite",
            trace_label="communication-draft.rewrite",
            trace_metadata={
                "template_id": template.template_id,
                "provider": provider_selection.provider,
                "model_id": provider_selection.model_id,
            },
            trace_input_data={"template_id": template.template_id},
        )

        generation = CommunicationDraftGenerationMetadata(
            strategy="deterministic_template_only",
            provider=result.provider,
            model_id=result.model_id,
            finish_reason=result.finish_reason,
            duration_ms=result.duration_ms,
            provider_request_id=result.provider_request_id or "",
            usage=result.usage,
            error=result.error,
            used_document_evidence=any(
                reference.kind == "retrieved_document_chunk"
                for reference in evidence_references
            ),
            notes=[],
        )

        if result.error is not None:
            generation.notes.append("Provider-assisted rewrite failed; deterministic draft preserved.")
            return {
                "rewritten": False,
                "title": title,
                "subject": subject,
                "sections": sections,
                "generation": generation,
                "issues": [
                    NormalizedResultIssue(
                        severity="warning",
                        code="provider_assist_failed",
                        message=result.error.message,
                    )
                ],
            }

        parsed = result.structured_output.parsed if result.structured_output is not None else None
        if not isinstance(parsed, dict):
            generation.notes.append("Provider-assisted rewrite returned no structured payload; deterministic draft preserved.")
            return {
                "rewritten": False,
                "title": title,
                "subject": subject,
                "sections": sections,
                "generation": generation,
                "issues": [
                    NormalizedResultIssue(
                        severity="warning",
                        code="provider_assist_invalid_output",
                        message="Provider-assisted rewrite returned an invalid structured payload.",
                    )
                ],
            }

        by_type = {
            item.get("section_type"): item
            for item in parsed.get("sections", [])
            if isinstance(item, dict) and isinstance(item.get("section_type"), str)
        }
        rewritten_sections: list[CommunicationDraftSection] = []
        rewritten_section_count = 0
        preserved_section_types: list[str] = []
        for base_section in sections:
            candidate = by_type.get(base_section.section_type)
            if candidate is None:
                preserved_section_types.append(base_section.section_type)
                rewritten_sections.append(base_section)
                continue
            body = str(candidate.get("body") or base_section.body).strip()
            bullet_items = [
                str(item).strip()
                for item in candidate.get("bullet_items", [])
                if str(item).strip()
            ]
            rewritten_sections.append(
                base_section.model_copy(
                    update={
                        "title": str(candidate.get("title") or base_section.title).strip() or base_section.title,
                        "body": body,
                        "bullet_items": bullet_items if bullet_items else base_section.bullet_items,
                    }
                )
            )
            rewritten_section_count += 1

        generation.notes.append(
            "Provider-assisted rewrite returned structured wording for "
            f"{rewritten_section_count}/{len(sections)} section(s)."
        )
        if preserved_section_types:
            generation.notes.append(
                "Deterministic wording was preserved for sections without valid provider rewrite output: "
                + ", ".join(preserved_section_types)
                + "."
            )

        return {
            "rewritten": True,
            "title": str(parsed.get("title") or title).strip() or title,
            "subject": str(parsed.get("subject") or subject).strip() or subject,
            "sections": rewritten_sections,
            "generation": generation,
            "issues": [],
        }

    def _append_source_entity(
        self,
        entities: list[CommunicationDraftSourceEntityReference],
        seen: set[tuple[str, str, str]],
        entity: CommunicationDraftSourceEntityReference,
    ) -> None:
        fingerprint = (entity.source_entity_type, entity.source_entity_id, entity.source_path)
        if fingerprint in seen:
            return
        seen.add(fingerprint)
        entities.append(entity)

    def _to_summary(self, model: CommunicationDraftModel) -> CommunicationDraftSummary:
        return CommunicationDraftSummary(
            draft_id=model.draft_id,
            case_id=model.case_id,
            template_id=model.template_id,
            draft_type=model.draft_type,
            status=model.status,
            audience_type=model.audience_type,
            strategy=model.strategy,
            packet_id=model.packet_id,
            workflow_run_id=model.workflow_run_id,
            workflow_pack_run_id=model.workflow_pack_run_id,
            title=model.title,
            subject=model.subject,
            created_at=isoformat_utc(model.created_at),
            updated_at=isoformat_utc(model.updated_at),
        )

    def _to_record(self, model: CommunicationDraftModel) -> CommunicationDraftRecord:
        try:
            return CommunicationDraftRecord(
                draft_id=model.draft_id,
                case_id=model.case_id,
                template_id=model.template_id,
                draft_type=model.draft_type,
                status=model.status,
                audience_type=model.audience_type,
                strategy=model.strategy,
                packet_id=model.packet_id,
                workflow_run_id=model.workflow_run_id,
                workflow_pack_run_id=model.workflow_pack_run_id,
                title=model.title,
                subject=model.subject,
                sections=[
                    CommunicationDraftSection.model_validate(item)
                    for item in (model.sections_json or [])
                ],
                source_metadata=CommunicationDraftSourceMetadata.model_validate(
                    model.source_metadata_json or {}
                ),
                source_entities=[
                    CommunicationDraftSourceEntityReference.model_validate(item)
                    for item in (model.source_entities_json or [])
                ],
                evidence_references=[
                    CommunicationDraftEvidenceReference.model_validate(item)
                    for item in (model.evidence_references_json or [])
                ],
                review=CommunicationDraftReviewMetadata.model_validate(model.review_json or {}),
                generation=CommunicationDraftGenerationMetadata.model_validate(model.generation_json or {}),
                created_at=isoformat_utc(model.created_at),
                updated_at=isoformat_utc(model.updated_at),
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise CommunicationDraftServiceError(
                f"Communication draft '{model.draft_id}' contains invalid persisted data and could not be loaded.",
                status_code=500,
            ) from exc

    def _build_copy_artifacts(
        self,
        draft: CommunicationDraftRecord,
    ) -> list[CommunicationCopyExportArtifact]:
        base_name = f"communication-draft-{draft.draft_id}"
        plain_lines = [f"Title: {draft.title}", f"Subject: {draft.subject}", ""]
        markdown_lines = [f"# {draft.title}", "", f"Subject: {draft.subject}", ""]

        for section in draft.sections:
            plain_lines.append(section.title)
            if section.body:
                plain_lines.append(section.body)
            for bullet in section.bullet_items:
                plain_lines.append(f"- {bullet}")
            plain_lines.append("")

            markdown_lines.append(f"## {section.title}")
            markdown_lines.append("")
            if section.body:
                markdown_lines.append(section.body)
                markdown_lines.append("")
            for bullet in section.bullet_items:
                markdown_lines.append(f"- {bullet}")
            markdown_lines.append("")

        generated_at = draft.updated_at or draft.created_at
        return [
            CommunicationCopyExportArtifact(
                format="plain_text",
                filename=f"{base_name}.txt",
                content_text="\n".join(plain_lines).strip() + "\n",
                generated_at=generated_at,
            ),
            CommunicationCopyExportArtifact(
                format="markdown_text",
                filename=f"{base_name}.md",
                content_text="\n".join(markdown_lines).strip() + "\n",
                generated_at=generated_at,
            ),
        ]