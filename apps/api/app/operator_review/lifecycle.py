"""Case lifecycle service for explicit operator-controlled stage transitions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import ChangeSummary, FieldChangeRecord
from casegraph_agent_sdk.operator_review import (
    CaseStage,
    CaseStageResponse,
    CaseStageState,
    OperatorOperationResult,
    StageHistoryResponse,
    StageTransitionMetadata,
    StageTransitionRecord,
    StageTransitionResponse,
    UpdateCaseStageRequest,
)

from app.cases.models import CaseRecordModel
from app.audit.service import AuditTrailService, audit_actor, entity_ref
from app.operator_review.errors import OperatorReviewServiceError
from app.operator_review.models import StageTransitionModel

ALLOWED_STAGE_TRANSITIONS: dict[CaseStage, tuple[CaseStage, ...]] = {
    "intake": ("document_review", "awaiting_documents", "closed_placeholder"),
    "document_review": (
        "readiness_review",
        "awaiting_documents",
        "closed_placeholder",
    ),
    "readiness_review": (
        "awaiting_documents",
        "ready_for_next_step",
        "closed_placeholder",
    ),
    "awaiting_documents": (
        "document_review",
        "readiness_review",
        "closed_placeholder",
    ),
    "ready_for_next_step": ("document_review", "closed_placeholder"),
    "closed_placeholder": (),
}

from app.persistence.database import isoformat_utc


class CaseLifecycleService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_stage(self, case_id: str) -> CaseStageResponse:
        case = self._require_case(case_id)
        return CaseStageResponse(stage=self._to_stage_state(case))

    def transition_stage(
        self,
        case_id: str,
        request: UpdateCaseStageRequest,
    ) -> StageTransitionResponse:
        case = self._require_case(case_id)
        current_stage = self._current_stage(case)

        if request.new_stage == current_stage:
            raise OperatorReviewServiceError(
                f"Case is already in stage '{current_stage}'.",
                status_code=400,
            )

        allowed = ALLOWED_STAGE_TRANSITIONS.get(current_stage, ())
        if request.new_stage not in allowed:
            raise OperatorReviewServiceError(
                f"Stage transition from '{current_stage}' to '{request.new_stage}' is not allowed.",
                status_code=400,
            )

        now = datetime.now(UTC)
        case.current_stage = request.new_stage
        case.updated_at = now
        self._session.add(case)

        transition = StageTransitionModel(
            transition_id=str(uuid4()),
            case_id=case_id,
            from_stage=current_stage,
            to_stage=request.new_stage,
            transition_type="manual",
            reason=(request.reason or "").strip(),
            note=(request.note or "").strip(),
            created_at=now,
        )
        self._session.add(transition)

        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=case_id,
            category="case",
            event_type="case_stage_transitioned",
            actor=audit_actor("service", actor_id="operator_review.lifecycle", display_name="Case Lifecycle Service"),
            entity=entity_ref(
                "stage_transition",
                transition.transition_id,
                case_id=case_id,
                display_label=f"{current_stage} -> {request.new_stage}",
            ),
            change_summary=ChangeSummary(
                message="Case stage transitioned.",
                field_changes=[
                    FieldChangeRecord(field_path="current_stage", old_value=current_stage, new_value=request.new_stage),
                ],
            ),
            metadata={"reason": transition.reason, "note": transition.note},
        )
        decision = audit.append_decision(
            case_id=case_id,
            decision_type="stage_transition",
            actor=audit_actor("service", actor_id="operator_review.lifecycle", display_name="Case Lifecycle Service"),
            source_entity=entity_ref(
                "stage_transition",
                transition.transition_id,
                case_id=case_id,
                display_label=f"{current_stage} -> {request.new_stage}",
            ),
            outcome=request.new_stage,
            reason=transition.reason,
            note=transition.note,
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)

        self._session.commit()
        self._session.refresh(case)
        self._session.refresh(transition)

        return StageTransitionResponse(
            result=OperatorOperationResult(
                success=True,
                message=f"Case stage updated to '{request.new_stage}'.",
            ),
            stage=self._to_stage_state(case),
            transition=self._to_transition_record(transition),
        )

    def list_stage_history(self, case_id: str) -> StageHistoryResponse:
        self._require_case(case_id)
        transitions = list(self._session.exec(
            select(StageTransitionModel)
            .where(StageTransitionModel.case_id == case_id)
            .order_by(desc(StageTransitionModel.created_at))
        ).all())
        return StageHistoryResponse(
            transitions=[self._to_transition_record(item) for item in transitions]
        )

    def _require_case(self, case_id: str) -> CaseRecordModel:
        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise OperatorReviewServiceError(
                f"Case '{case_id}' not found.",
                status_code=404,
            )
        return case

    def _current_stage(self, case: CaseRecordModel) -> CaseStage:
        return (case.current_stage or "intake")  # type: ignore[return-value]

    def _to_stage_state(self, case: CaseRecordModel) -> CaseStageState:
        current_stage = self._current_stage(case)
        return CaseStageState(
            case_id=case.case_id,
            current_stage=current_stage,
            allowed_transitions=list(ALLOWED_STAGE_TRANSITIONS.get(current_stage, ())),
            updated_at=isoformat_utc(case.updated_at),
        )

    def _to_transition_record(
        self,
        transition: StageTransitionModel,
    ) -> StageTransitionRecord:
        return StageTransitionRecord(
            transition_id=transition.transition_id,
            case_id=transition.case_id,
            from_stage=transition.from_stage,
            to_stage=transition.to_stage,
            metadata=StageTransitionMetadata(
                transition_type=transition.transition_type,
                reason=transition.reason,
                note=transition.note,
            ),
            created_at=isoformat_utc(transition.created_at),
        )