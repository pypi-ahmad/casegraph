"""Case-centric operator review queue service."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.operator_review import (
    ActionItemCategory,
    QueueFilterMetadata,
    QueueStageCount,
    QueueSummary,
    QueueSummaryResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
)

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel, WorkflowRunRecordModel
from app.operator_review.actions import ActionItemService, _DerivedActionCandidate
from app.operator_review.errors import OperatorReviewServiceError
from app.operator_review.models import ActionItemModel, ReviewNoteModel, StageTransitionModel
from app.readiness.service import ReadinessService
from app.persistence.database import isoformat_utc


class ReviewQueueService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._action_service = ActionItemService(session)
        self._readiness_service = ReadinessService(session)

    def list_queue(self, filters: QueueFilterMetadata) -> ReviewQueueResponse:
        items = self._collect_items(filters, apply_limit=True)
        return ReviewQueueResponse(filters=filters, items=items)

    def get_summary(self, filters: QueueFilterMetadata) -> QueueSummaryResponse:
        items = self._collect_items(filters, apply_limit=False)
        stage_counts = Counter(item.current_stage for item in items)
        summary = QueueSummary(
            total_cases=len(items),
            cases_with_open_actions=sum(1 for item in items if item.has_open_actions),
            cases_with_missing_items=sum(1 for item in items if item.has_missing_items),
            cases_needing_attention=sum(1 for item in items if item.detected_action_count > 0 or item.open_action_count > 0),
            stage_counts=[
                QueueStageCount(stage=stage, case_count=count)
                for stage, count in sorted(stage_counts.items())
            ],
        )
        return QueueSummaryResponse(filters=filters, summary=summary)

    def _collect_items(
        self,
        filters: QueueFilterMetadata,
        *,
        apply_limit: bool,
    ) -> list[ReviewQueueItem]:
        limit = max(1, min(filters.limit, 200))
        cases = list(self._session.exec(
            select(CaseRecordModel).order_by(desc(CaseRecordModel.updated_at))
        ).all())

        queue_items: list[ReviewQueueItem] = []
        for case in cases:
            item = self._build_queue_item(case)
            if item.detected_action_count == 0 and item.open_action_count == 0:
                continue
            if filters.stage is not None and item.current_stage != filters.stage:
                continue
            if filters.has_missing_items is not None and item.has_missing_items != filters.has_missing_items:
                continue
            if filters.has_open_actions is not None and item.has_open_actions != filters.has_open_actions:
                continue
            if filters.domain_pack_id is not None and item.domain_pack_id != filters.domain_pack_id:
                continue
            if filters.case_type_id is not None and item.case_type_id != filters.case_type_id:
                continue
            queue_items.append(item)

        queue_items.sort(
            key=lambda item: (
                item.detected_action_count,
                item.open_action_count,
                item.last_activity_at,
            ),
            reverse=True,
        )
        return queue_items[:limit] if apply_limit else queue_items

    def _build_queue_item(self, case: CaseRecordModel) -> ReviewQueueItem:
        detected_candidates = self._action_service.preview_candidates(case.case_id)
        open_actions = list(self._session.exec(
            select(ActionItemModel)
            .where(ActionItemModel.case_id == case.case_id)
            .where(ActionItemModel.status == "open")
        ).all())
        case_doc_links = list(self._session.exec(
            select(CaseDocumentLinkModel).where(CaseDocumentLinkModel.case_id == case.case_id)
        ).all())
        workflow_runs = list(self._session.exec(
            select(WorkflowRunRecordModel).where(WorkflowRunRecordModel.case_id == case.case_id)
        ).all())
        latest_transition = self._session.exec(
            select(StageTransitionModel)
            .where(StageTransitionModel.case_id == case.case_id)
            .order_by(desc(StageTransitionModel.created_at))
        ).first()
        latest_note = self._session.exec(
            select(ReviewNoteModel)
            .where(ReviewNoteModel.case_id == case.case_id)
            .order_by(desc(ReviewNoteModel.created_at))
        ).first()

        readiness = self._readiness_service.get_readiness(case.case_id)
        readiness_summary = readiness.readiness if readiness is not None else None
        missing_required_count = len(readiness_summary.missing_required) if readiness_summary else 0
        needs_review_count = 0
        if readiness_summary is not None:
            needs_review_count = (
                readiness_summary.needs_review_items + readiness_summary.partially_supported_items
            )

        failed_run_count = sum(1 for run in workflow_runs if run.status in {"failed", "failed_validation"})
        attention_categories = sorted(self._merge_attention_categories(detected_candidates, open_actions))
        last_activity_values = [case.updated_at]
        if open_actions:
            last_activity_values.extend(item.updated_at for item in open_actions)
        if latest_transition is not None:
            last_activity_values.append(latest_transition.created_at)
        if latest_note is not None:
            last_activity_values.append(latest_note.created_at)

        return ReviewQueueItem(
            case_id=case.case_id,
            title=case.title,
            case_status=case.status,
            current_stage=case.current_stage or "intake",
            domain_pack_id=case.domain_pack_id,
            case_type_id=case.case_type_id,
            readiness_status=readiness_summary.readiness_status if readiness_summary else None,
            linked_document_count=len(case_doc_links),
            open_action_count=len(open_actions),
            detected_action_count=len(detected_candidates),
            missing_required_count=missing_required_count,
            needs_review_count=needs_review_count,
            failed_run_count=failed_run_count,
            has_open_actions=len(open_actions) > 0,
            has_missing_items=missing_required_count > 0,
            attention_categories=attention_categories,
            last_activity_at=isoformat_utc(max(last_activity_values)),
        )

    @staticmethod
    def _merge_attention_categories(
        detected_candidates: list[_DerivedActionCandidate],
        open_actions: list[ActionItemModel],
    ) -> list[ActionItemCategory]:
        categories = {candidate.category for candidate in detected_candidates}
        categories.update(action.category for action in open_actions)
        return list(categories)