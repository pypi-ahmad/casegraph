"""Deterministic follow-up action generation and review note service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Session, desc, select

from app.audit.service import AuditTrailService, audit_actor, entity_ref
from casegraph_agent_sdk.audit import ChangeSummary
from casegraph_agent_sdk.operator_review import (
    ActionGenerationResponse,
    ActionItem,
    ActionItemCategory,
    ActionItemPriority,
    ActionItemSource,
    CaseActionListResponse,
    CreateReviewNoteRequest,
    OperatorActionSummary,
    OperatorOperationResult,
    ReviewNote,
    ReviewNoteListResponse,
    ReviewNoteResponse,
)

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel, WorkflowRunRecordModel
from app.extraction.models import ExtractionRunModel
from app.operator_review.errors import OperatorReviewServiceError
from app.operator_review.models import ActionItemModel, ReviewNoteModel
from app.readiness.models import (
    ChecklistItemDocumentLinkModel,
    ChecklistItemExtractionLinkModel,
    ChecklistItemModel,
    ChecklistModel,
)
from app.persistence.database import isoformat_utc


FAILED_RUN_STATUSES = {"failed", "failed_validation", "not_started", "queued_placeholder"}


@dataclass(frozen=True)
class _DerivedActionCandidate:
    fingerprint: str
    category: ActionItemCategory
    source: ActionItemSource
    priority: ActionItemPriority
    title: str
    description: str
    source_reason: str
    checklist_item_id: str | None = None
    document_id: str | None = None
    extraction_id: str | None = None
    run_id: str | None = None


class ActionItemService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_actions(self, case_id: str) -> CaseActionListResponse:
        self._require_case(case_id)
        actions = list(self._session.exec(
            select(ActionItemModel)
            .where(ActionItemModel.case_id == case_id)
            .order_by(ActionItemModel.status.asc(), desc(ActionItemModel.updated_at))
        ).all())
        return CaseActionListResponse(actions=[self._to_action_item(item) for item in actions])

    def preview_candidates(self, case_id: str) -> list[_DerivedActionCandidate]:
        case = self._require_case(case_id)
        return self._derive_candidates(case)

    def generate_actions(self, case_id: str) -> ActionGenerationResponse:
        case = self._require_case(case_id)
        candidates = self._derive_candidates(case)
        existing_items = list(self._session.exec(
            select(ActionItemModel).where(ActionItemModel.case_id == case_id)
        ).all())
        existing_by_fingerprint = {item.fingerprint: item for item in existing_items}
        active_fingerprints = {candidate.fingerprint for candidate in candidates}

        now = datetime.now(UTC)
        generated_count = 0
        reopened_count = 0
        resolved_count = 0

        for candidate in candidates:
            existing = existing_by_fingerprint.get(candidate.fingerprint)
            if existing is None:
                self._session.add(ActionItemModel(
                    action_item_id=str(uuid4()),
                    case_id=case_id,
                    fingerprint=candidate.fingerprint,
                    category=candidate.category,
                    source=candidate.source,
                    priority=candidate.priority,
                    status="open",
                    title=candidate.title,
                    description=candidate.description,
                    source_reason=candidate.source_reason,
                    checklist_item_id=candidate.checklist_item_id,
                    document_id=candidate.document_id,
                    extraction_id=candidate.extraction_id,
                    run_id=candidate.run_id,
                    created_at=now,
                    updated_at=now,
                    resolved_at=None,
                ))
                generated_count += 1
                continue

            if existing.status != "open":
                reopened_count += 1
            existing.category = candidate.category
            existing.source = candidate.source
            existing.priority = candidate.priority
            existing.status = "open"
            existing.title = candidate.title
            existing.description = candidate.description
            existing.source_reason = candidate.source_reason
            existing.checklist_item_id = candidate.checklist_item_id
            existing.document_id = candidate.document_id
            existing.extraction_id = candidate.extraction_id
            existing.run_id = candidate.run_id
            existing.updated_at = now
            existing.resolved_at = None
            self._session.add(existing)

        for item in existing_items:
            if item.status == "open" and item.fingerprint not in active_fingerprints:
                item.status = "resolved"
                item.updated_at = now
                item.resolved_at = now
                self._session.add(item)
                resolved_count += 1

        self._session.commit()

        open_count = self._session.exec(
            select(ActionItemModel)
            .where(ActionItemModel.case_id == case_id)
            .where(ActionItemModel.status == "open")
        ).all()
        actions = self.list_actions(case_id).actions
        return ActionGenerationResponse(
            result=OperatorOperationResult(
                success=True,
                message="Deterministic follow-up actions generated from current case state.",
            ),
            summary=OperatorActionSummary(
                case_id=case_id,
                detected_count=len(candidates),
                generated_count=generated_count,
                reopened_count=reopened_count,
                resolved_count=resolved_count,
                open_count=len(open_count),
            ),
            actions=actions,
        )

    def create_review_note(
        self,
        case_id: str,
        request: CreateReviewNoteRequest,
    ) -> ReviewNoteResponse:
        case = self._require_case(case_id)
        body = request.body.strip()
        if not body:
            raise OperatorReviewServiceError(
                "Review note body is required.",
                status_code=400,
            )

        if request.related_action_item_id is not None:
            action = self._session.get(ActionItemModel, request.related_action_item_id)
            if action is None or action.case_id != case_id:
                raise OperatorReviewServiceError(
                    "Related action item was not found for this case.",
                    status_code=404,
                )

        note = ReviewNoteModel(
            note_id=str(uuid4()),
            case_id=case_id,
            body=body,
            decision=request.decision,
            related_action_item_id=request.related_action_item_id,
            stage_snapshot=case.current_stage or "intake",
        )
        self._session.add(note)

        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=case_id,
            category="review",
            event_type="review_note_added",
            actor=audit_actor("service", actor_id="operator_review.actions", display_name="Action Item Service"),
            entity=entity_ref(
                "review_note",
                note.note_id,
                case_id=case_id,
                display_label=body[:80],
            ),
            change_summary=ChangeSummary(message="Review note recorded."),
            metadata={"decision": request.decision, "related_action_item_id": request.related_action_item_id or ""},
        )
        decision = audit.append_decision(
            case_id=case_id,
            decision_type="review_note_added",
            actor=audit_actor("service", actor_id="operator_review.actions", display_name="Action Item Service"),
            source_entity=entity_ref("review_note", note.note_id, case_id=case_id, display_label=body[:80]),
            outcome=request.decision,
            note=body,
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)

        self._session.commit()
        self._session.refresh(note)

        return ReviewNoteResponse(
            result=OperatorOperationResult(
                success=True,
                message="Review note recorded.",
            ),
            note=self._to_review_note(note),
        )

    def list_review_notes(self, case_id: str) -> ReviewNoteListResponse:
        self._require_case(case_id)
        notes = list(self._session.exec(
            select(ReviewNoteModel)
            .where(ReviewNoteModel.case_id == case_id)
            .order_by(desc(ReviewNoteModel.created_at))
        ).all())
        return ReviewNoteListResponse(notes=[self._to_review_note(item) for item in notes])

    def _require_case(self, case_id: str) -> CaseRecordModel:
        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise OperatorReviewServiceError(
                f"Case '{case_id}' not found.",
                status_code=404,
            )
        return case

    def _derive_candidates(self, case: CaseRecordModel) -> list[_DerivedActionCandidate]:
        if (case.current_stage or "intake") == "closed_placeholder":
            return []

        case_doc_links = list(self._session.exec(
            select(CaseDocumentLinkModel).where(CaseDocumentLinkModel.case_id == case.case_id)
        ).all())
        workflow_runs = list(self._session.exec(
            select(WorkflowRunRecordModel).where(WorkflowRunRecordModel.case_id == case.case_id)
        ).all())
        extraction_runs = list(self._session.exec(
            select(ExtractionRunModel).where(ExtractionRunModel.case_id == case.case_id)
        ).all())

        candidates: list[_DerivedActionCandidate] = []

        if not case_doc_links:
            candidates.append(_DerivedActionCandidate(
                fingerprint="case:document_linking_needed:no-linked-documents",
                category="document_linking_needed",
                source="case",
                priority="high",
                title="Link documents to the case",
                description="No case-linked documents are available for operator review.",
                source_reason="No document records are currently linked to this case.",
            ))

        if case.selected_workflow_id and not workflow_runs:
            candidates.append(_DerivedActionCandidate(
                fingerprint=f"case:run_followup:workflow-not-started:{case.selected_workflow_id}",
                category="run_followup",
                source="case",
                priority="normal",
                title="Start or review the selected workflow",
                description="A workflow is bound to this case, but no run has been started yet.",
                source_reason=f"No workflow runs exist for the selected workflow '{case.selected_workflow_id}'.",
            ))

        for run in workflow_runs:
            if run.status in FAILED_RUN_STATUSES:
                priority: ActionItemPriority = "high" if run.status in {"failed", "failed_validation"} else "normal"
                candidates.append(_DerivedActionCandidate(
                    fingerprint=f"workflow-run:run_followup:{run.run_id}:{run.status}",
                    category="run_followup",
                    source="workflow_run",
                    priority=priority,
                    title="Review workflow run outcome",
                    description=f"Workflow run '{run.workflow_id}' is in status '{run.status}'.",
                    source_reason=f"Workflow run '{run.run_id}' requires operator follow-up.",
                    run_id=run.run_id,
                ))

        for extraction in extraction_runs:
            if extraction.status == "completed" and not extraction.grounding_available:
                candidates.append(_DerivedActionCandidate(
                    fingerprint=f"extraction-run:evidence_gap:{extraction.extraction_id}",
                    category="evidence_gap",
                    source="extraction_run",
                    priority="normal",
                    title="Review extraction without grounding",
                    description="A completed extraction result exists without grounding references.",
                    source_reason=f"Extraction '{extraction.extraction_id}' completed without grounding metadata.",
                    document_id=extraction.document_id or None,
                    extraction_id=extraction.extraction_id,
                ))

        checklist = self._session.exec(
            select(ChecklistModel).where(ChecklistModel.case_id == case.case_id)
        ).first()
        if case.domain_pack_id and case.case_type_id and checklist is None:
            candidates.append(_DerivedActionCandidate(
                fingerprint=f"case:needs_review:generate-checklist:{case.case_id}",
                category="needs_review",
                source="case",
                priority="normal",
                title="Generate the case checklist",
                description="This domain-scoped case does not yet have a generated requirement checklist.",
                source_reason="Domain pack context exists, but no checklist has been generated.",
            ))
            return candidates

        if checklist is None:
            return candidates

        items = list(self._session.exec(
            select(ChecklistItemModel).where(ChecklistItemModel.checklist_id == checklist.checklist_id)
        ).all())
        latest_evaluated_at = max((item.last_evaluated_at for item in items if item.last_evaluated_at), default=None)
        latest_artifact_change = max(
            [link.linked_at for link in case_doc_links] + [run.created_at for run in extraction_runs],
            default=None,
        )

        if latest_evaluated_at is None:
            candidates.append(_DerivedActionCandidate(
                fingerprint=f"case:needs_review:evaluate-checklist:{checklist.checklist_id}",
                category="needs_review",
                source="case",
                priority="normal",
                title="Evaluate checklist coverage",
                description="A checklist exists for this case, but coverage has not been evaluated yet.",
                source_reason="Checklist items do not yet have evaluated support state.",
            ))
            return candidates

        if latest_artifact_change is not None and latest_artifact_change > latest_evaluated_at:
            candidates.append(_DerivedActionCandidate(
                fingerprint=f"case:needs_review:reevaluate-checklist:{checklist.checklist_id}",
                category="needs_review",
                source="case",
                priority="normal",
                title="Re-evaluate checklist coverage",
                description="Case-linked artifacts changed after the last readiness evaluation.",
                source_reason="Documents or extraction runs were updated after the last readiness evaluation.",
            ))
            return candidates

        doc_links_by_item = self._group_document_links(checklist.checklist_id)
        extraction_links_by_item = self._group_extraction_links(checklist.checklist_id)

        for item in items:
            doc_links = doc_links_by_item.get(item.item_id, [])
            extraction_links = extraction_links_by_item.get(item.item_id, [])

            if item.status == "missing" and item.priority != "optional":
                priority: ActionItemPriority = "high" if item.priority == "required" else "normal"
                candidates.append(_DerivedActionCandidate(
                    fingerprint=f"checklist-item:missing_document:{item.item_id}",
                    category="missing_document",
                    source="checklist_item",
                    priority=priority,
                    title=f"Collect {item.display_name}",
                    description="The last readiness evaluation did not find supporting case artifacts for this requirement.",
                    source_reason=f"Checklist item '{item.requirement_id}' remains missing.",
                    checklist_item_id=item.item_id,
                ))
                continue

            if item.status == "partially_supported":
                document_id = doc_links[0].document_id if doc_links else None
                candidates.append(_DerivedActionCandidate(
                    fingerprint=f"checklist-item:extraction_followup:{item.item_id}",
                    category="extraction_followup",
                    source="checklist_item",
                    priority="normal",
                    title=f"Review extraction follow-up for {item.display_name}",
                    description="A supporting document is linked, but no supporting extraction result is linked yet.",
                    source_reason=f"Checklist item '{item.requirement_id}' is only partially supported.",
                    checklist_item_id=item.item_id,
                    document_id=document_id,
                ))
                continue

            if item.status == "needs_human_review":
                extraction_link = extraction_links[0] if extraction_links else None
                document_id = extraction_link.document_id if extraction_link else None
                extraction_id = extraction_link.extraction_id if extraction_link else None
                category: ActionItemCategory = (
                    "document_linking_needed" if extraction_links and not doc_links else "needs_review"
                )
                title = (
                    f"Link supporting document for {item.display_name}"
                    if category == "document_linking_needed"
                    else f"Review support for {item.display_name}"
                )
                description = (
                    "Extraction support was detected without a linked case document."
                    if category == "document_linking_needed"
                    else "The last readiness evaluation flagged this requirement for human review."
                )
                candidates.append(_DerivedActionCandidate(
                    fingerprint=f"checklist-item:{category}:{item.item_id}",
                    category=category,
                    source="checklist_item",
                    priority="high" if item.priority == "required" else "normal",
                    title=title,
                    description=description,
                    source_reason=f"Checklist item '{item.requirement_id}' requires operator review.",
                    checklist_item_id=item.item_id,
                    document_id=document_id,
                    extraction_id=extraction_id,
                ))

        return candidates

    def _group_document_links(
        self,
        checklist_id: str,
    ) -> dict[str, list[ChecklistItemDocumentLinkModel]]:
        items = list(self._session.exec(
            select(ChecklistItemModel.item_id).where(ChecklistItemModel.checklist_id == checklist_id)
        ).all())
        if not items:
            return {}
        links = list(self._session.exec(
            select(ChecklistItemDocumentLinkModel).where(
                ChecklistItemDocumentLinkModel.item_id.in_(items)
            )
        ).all())
        grouped: dict[str, list[ChecklistItemDocumentLinkModel]] = {}
        for link in links:
            grouped.setdefault(link.item_id, []).append(link)
        return grouped

    def _group_extraction_links(
        self,
        checklist_id: str,
    ) -> dict[str, list[ChecklistItemExtractionLinkModel]]:
        items = list(self._session.exec(
            select(ChecklistItemModel.item_id).where(ChecklistItemModel.checklist_id == checklist_id)
        ).all())
        if not items:
            return {}
        links = list(self._session.exec(
            select(ChecklistItemExtractionLinkModel).where(
                ChecklistItemExtractionLinkModel.item_id.in_(items)
            )
        ).all())
        grouped: dict[str, list[ChecklistItemExtractionLinkModel]] = {}
        for link in links:
            grouped.setdefault(link.item_id, []).append(link)
        return grouped

    def _to_action_item(self, item: ActionItemModel) -> ActionItem:
        return ActionItem(
            action_item_id=item.action_item_id,
            case_id=item.case_id,
            category=item.category,
            source=item.source,
            priority=item.priority,
            status=item.status,
            title=item.title,
            description=item.description,
            source_reason=item.source_reason,
            checklist_item_id=item.checklist_item_id,
            document_id=item.document_id,
            extraction_id=item.extraction_id,
            run_id=item.run_id,
            created_at=isoformat_utc(item.created_at),
            updated_at=isoformat_utc(item.updated_at),
            resolved_at=isoformat_utc(item.resolved_at) if item.resolved_at else None,
        )

    def _to_review_note(self, note: ReviewNoteModel) -> ReviewNote:
        return ReviewNote(
            note_id=note.note_id,
            case_id=note.case_id,
            body=note.body,
            decision=note.decision,
            related_action_item_id=note.related_action_item_id,
            stage_snapshot=note.stage_snapshot,
            created_at=isoformat_utc(note.created_at),
        )