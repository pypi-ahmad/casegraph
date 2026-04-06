"""Reviewed snapshot, sign-off, and release-gate services."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import ChangeSummary, FieldChangeRecord
from casegraph_agent_sdk.extraction import ExtractedFieldResult
from casegraph_agent_sdk.human_validation import OriginalValueReference
from casegraph_agent_sdk.reviewed_handoff import (
    CreateReviewedSnapshotRequest,
    HandoffEligibilityResponse,
    HandoffEligibilitySummary,
    ReleaseGateReason,
    ReviewedFieldEntry,
    ReviewedHandoffOperationResult,
    ReviewedRequirementEntry,
    ReviewedSnapshotCreateResponse,
    ReviewedSnapshotListResponse,
    ReviewedSnapshotRecord,
    ReviewedSnapshotResponse,
    ReviewedSnapshotSelectResponse,
    ReviewedSnapshotSignOffResponse,
    ReviewedSnapshotSourceMetadata,
    ReviewedSnapshotSummary,
    SignOffActorMetadata,
    SignOffReviewedSnapshotRequest,
    SnapshotSignOffRecord,
    UnresolvedReviewItemSummary,
)

from app.audit.service import AuditTrailService, audit_actor, derived_ref, entity_ref, source_ref
from app.human_validation.models import FieldValidationModel, RequirementReviewModel
from app.human_validation.service import HumanValidationService
from app.persistence.database import isoformat_utc, utcnow
from app.reviewed_handoff.models import ReviewedSnapshotModel, ReviewedSnapshotSignOffModel


class ReviewedHandoffServiceError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class ReviewedHandoffService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_snapshots(self, case_id: str) -> ReviewedSnapshotListResponse:
        self._require_case(case_id)
        rows = list(self._session.exec(
            select(ReviewedSnapshotModel)
            .where(ReviewedSnapshotModel.case_id == case_id)
            .order_by(desc(ReviewedSnapshotModel.created_at), desc(ReviewedSnapshotModel.snapshot_id))
        ).all())
        return ReviewedSnapshotListResponse(
            case_id=case_id,
            snapshots=[self._to_snapshot_record(row) for row in rows],
        )

    def get_snapshot(self, snapshot_id: str) -> ReviewedSnapshotResponse:
        return ReviewedSnapshotResponse(snapshot=self._to_snapshot_record(self._require_snapshot(snapshot_id)))

    def create_snapshot(
        self,
        case_id: str,
        request: CreateReviewedSnapshotRequest,
    ) -> ReviewedSnapshotCreateResponse:
        from app.cases.models import CaseDocumentLinkModel
        from app.extraction.models import ExtractionRunModel
        from app.readiness.models import ChecklistItemModel, ChecklistModel

        case = self._require_case(case_id)
        reviewed = HumanValidationService(self._session).get_reviewed_state(case_id).state

        validations = list(self._session.exec(
            select(FieldValidationModel)
            .where(FieldValidationModel.case_id == case_id)
            .order_by(FieldValidationModel.extraction_id, FieldValidationModel.field_id)
        ).all())
        validation_by_key = {
            (row.extraction_id, row.field_id): row
            for row in validations
        }

        extraction_runs = list(self._session.exec(
            select(ExtractionRunModel)
            .where(ExtractionRunModel.case_id == case_id)
            .order_by(ExtractionRunModel.created_at, ExtractionRunModel.extraction_id)
        ).all())

        checklist = self._session.exec(
            select(ChecklistModel).where(ChecklistModel.case_id == case_id)
        ).first()
        checklist_items: list[ChecklistItemModel] = []
        if checklist is not None:
            checklist_items = list(self._session.exec(
                select(ChecklistItemModel)
                .where(ChecklistItemModel.checklist_id == checklist.checklist_id)
                .order_by(ChecklistItemModel.created_at, ChecklistItemModel.requirement_id, ChecklistItemModel.item_id)
            ).all())

        requirement_reviews = list(self._session.exec(
            select(RequirementReviewModel)
            .where(RequirementReviewModel.case_id == case_id)
            .order_by(RequirementReviewModel.item_id)
        ).all())
        review_by_item = {row.item_id: row for row in requirement_reviews}

        linked_document_ids = list(self._session.exec(
            select(CaseDocumentLinkModel.document_id)
            .where(CaseDocumentLinkModel.case_id == case_id)
            .order_by(CaseDocumentLinkModel.linked_at)
        ).all())

        field_entries: list[ReviewedFieldEntry] = []
        accepted_fields = 0
        corrected_fields = 0
        for run in extraction_runs:
            for field_raw in run.fields_json:
                field = ExtractedFieldResult.model_validate(field_raw)
                validation = validation_by_key.get((run.extraction_id, field.field_id))
                if validation is not None:
                    original = OriginalValueReference.model_validate(validation.original_value_json)
                    validation_status = validation.status
                    validation_id = validation.validation_id
                    reviewed_value = validation.reviewed_value_json.get("value")
                    note = validation.note
                else:
                    original = OriginalValueReference(
                        value=field.value,
                        raw_value=field.raw_value,
                        is_present=field.is_present,
                        grounding=list(field.grounding),
                    )
                    validation_status = "unreviewed"
                    validation_id = ""
                    reviewed_value = None
                    note = ""

                included_in_snapshot = validation_status == "accepted" or (
                    validation_status == "corrected" and reviewed_value is not None
                )
                snapshot_value = None
                if validation_status == "accepted":
                    snapshot_value = original.value
                    accepted_fields += 1
                elif validation_status == "corrected" and reviewed_value is not None:
                    snapshot_value = reviewed_value
                    corrected_fields += 1

                field_entries.append(
                    ReviewedFieldEntry(
                        extraction_id=run.extraction_id,
                        document_id=run.document_id,
                        field_id=field.field_id,
                        field_type=field.field_type,
                        validation_id=validation_id,
                        validation_status=validation_status,
                        original=original,
                        reviewed_value=reviewed_value,
                        snapshot_value=snapshot_value,
                        included_in_snapshot=included_in_snapshot,
                        note=note,
                    )
                )

        requirement_entries: list[ReviewedRequirementEntry] = []
        required_reviews_complete = True
        reviewed_requirements = 0
        for item in checklist_items:
            review = review_by_item.get(item.item_id)
            review_status = review.status if review is not None else "unreviewed"
            included_in_snapshot = review_status in {
                "confirmed_supported",
                "confirmed_missing",
                "manually_overridden",
            }
            if review_status != "unreviewed":
                reviewed_requirements += 1
            if item.priority == "required" and review_status == "unreviewed":
                required_reviews_complete = False
            requirement_entries.append(
                ReviewedRequirementEntry(
                    checklist_id=item.checklist_id,
                    item_id=item.item_id,
                    requirement_id=item.requirement_id,
                    display_name=item.display_name,
                    priority=item.priority,
                    machine_status=item.status,
                    review_id=review.review_id if review is not None else "",
                    review_status=review_status,
                    included_in_snapshot=included_in_snapshot,
                    note=review.note if review is not None else "",
                    linked_document_ids=list(review.linked_document_ids_json) if review is not None else [],
                    linked_extraction_ids=list(review.linked_extraction_ids_json) if review is not None else [],
                )
            )

        unresolved_items = [
            UnresolvedReviewItemSummary(
                item_type=item.item_type,
                entity_id=item.entity_id,
                display_label=item.display_label,
                current_status=item.current_status,
                note=item.note,
            )
            for item in reviewed.unresolved_items
        ]

        source_metadata = ReviewedSnapshotSourceMetadata(
            case_id=case_id,
            linked_document_ids=linked_document_ids,
            extraction_ids=[run.extraction_id for run in extraction_runs],
            validation_record_ids=[row.validation_id for row in validations],
            checklist_id=checklist.checklist_id if checklist is not None else None,
            requirement_review_ids=[row.review_id for row in requirement_reviews],
            reviewed_state_timestamp=reviewed.reviewed_at,
        )
        summary = ReviewedSnapshotSummary(
            total_fields=len(field_entries),
            included_fields=sum(1 for entry in field_entries if entry.included_in_snapshot),
            accepted_fields=accepted_fields,
            corrected_fields=corrected_fields,
            total_requirements=len(requirement_entries),
            reviewed_requirements=reviewed_requirements,
            required_requirement_reviews_complete=required_reviews_complete,
            unresolved_item_count=len(unresolved_items),
        )

        now = utcnow()
        snapshot = ReviewedSnapshotModel(
            snapshot_id=str(uuid4()),
            case_id=case.case_id,
            status="created",
            note=request.note.strip(),
            created_by=request.operator_id.strip(),
            created_by_display_name=request.operator_display_name.strip(),
            created_by_metadata_json={},
            source_metadata_json=source_metadata.model_dump(mode="json"),
            summary_json=summary.model_dump(mode="json"),
            field_entries_json=[entry.model_dump(mode="json") for entry in field_entries],
            requirement_entries_json=[entry.model_dump(mode="json") for entry in requirement_entries],
            unresolved_items_json=[entry.model_dump(mode="json") for entry in unresolved_items],
            created_at=now,
        )
        self._session.add(snapshot)

        actor = (
            audit_actor(
                "operator",
                actor_id=request.operator_id.strip(),
                display_name=request.operator_display_name.strip() or request.operator_id.strip(),
            )
            if request.operator_id.strip() or request.operator_display_name.strip()
            else audit_actor("service", actor_id="reviewed_handoff.service", display_name="Reviewed Handoff Service")
        )
        audit = AuditTrailService(self._session)
        audit.append_event(
            case_id=case.case_id,
            category="reviewed_handoff",
            event_type="reviewed_snapshot_created",
            actor=actor,
            entity=entity_ref("reviewed_snapshot", snapshot.snapshot_id, case_id=case.case_id, display_label=case.title),
            change_summary=ChangeSummary(
                message="Reviewed snapshot created from current reviewed field and requirement state.",
                field_changes=[
                    FieldChangeRecord(field_path="summary.included_fields", new_value=summary.included_fields),
                    FieldChangeRecord(field_path="summary.reviewed_requirements", new_value=summary.reviewed_requirements),
                    FieldChangeRecord(field_path="summary.unresolved_item_count", new_value=summary.unresolved_item_count),
                ],
            ),
            metadata={
                "snapshot_status": snapshot.status,
                "extraction_count": len(source_metadata.extraction_ids),
                "validation_record_count": len(source_metadata.validation_record_ids),
                "requirement_review_count": len(source_metadata.requirement_review_ids),
            },
        )

        lineage_edges = [
            (
                "case_context",
                source_ref("case", case.case_id, case_id=case.case_id, display_label=case.title, source_path="case"),
                None,
            ),
        ]
        if checklist is not None:
            lineage_edges.append(
                (
                    "checklist_reference",
                    source_ref("checklist", checklist.checklist_id, case_id=case.case_id, display_label="Case checklist", source_path="reviewed_snapshot.checklist"),
                    None,
                )
            )
        for document_id in linked_document_ids:
            lineage_edges.append(
                (
                    "document_source",
                    source_ref("document", document_id, case_id=case.case_id, display_label=document_id, source_path="reviewed_snapshot.documents"),
                    None,
                )
            )
        for extraction_id in source_metadata.extraction_ids:
            lineage_edges.append(
                (
                    "extraction_source",
                    source_ref("extraction_run", extraction_id, case_id=case.case_id, display_label=extraction_id, source_path="reviewed_snapshot.extractions"),
                    None,
                )
            )
        audit.record_lineage(
            case_id=case.case_id,
            artifact=derived_ref("reviewed_snapshot", snapshot.snapshot_id, case_id=case.case_id, display_label=case.title),
            edges=lineage_edges,
            notes=[
                "Reviewed snapshot lineage reflects the case, linked documents, checklist reference, and extraction runs used when the immutable snapshot was created.",
                "Validation and requirement review record ids are preserved inside the snapshot content.",
            ],
            metadata={
                "included_fields": summary.included_fields,
                "reviewed_requirements": summary.reviewed_requirements,
            },
        )

        self._session.commit()
        snapshot_record = self._to_snapshot_record(snapshot)
        return ReviewedSnapshotCreateResponse(
            result=ReviewedHandoffOperationResult(
                success=True,
                message="Reviewed snapshot created from current reviewed state.",
                issues=[],
            ),
            snapshot=snapshot_record,
        )

    def signoff_snapshot(
        self,
        snapshot_id: str,
        request: SignOffReviewedSnapshotRequest,
    ) -> ReviewedSnapshotSignOffResponse:
        snapshot = self._require_snapshot(snapshot_id)
        if not request.operator_id.strip():
            raise ReviewedHandoffServiceError(
                "operator_id is required to sign off a reviewed snapshot.",
                status_code=400,
            )

        existing = self._signoff_model(snapshot.snapshot_id)
        if existing is not None and existing.status == "signed_off":
            raise ReviewedHandoffServiceError(
                "Reviewed snapshot is already signed off.",
                status_code=400,
            )

        now = utcnow()
        signoff = ReviewedSnapshotSignOffModel(
            signoff_id=str(uuid4()),
            snapshot_id=snapshot.snapshot_id,
            case_id=snapshot.case_id,
            status="signed_off",
            actor_id=request.operator_id.strip(),
            actor_display_name=request.operator_display_name.strip(),
            actor_metadata_json={},
            note=request.note.strip(),
            created_at=now,
        )
        self._session.add(signoff)

        actor = audit_actor(
            "operator",
            actor_id=signoff.actor_id,
            display_name=signoff.actor_display_name or signoff.actor_id,
        )
        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=snapshot.case_id,
            category="reviewed_handoff",
            event_type="reviewed_snapshot_signed_off",
            actor=actor,
            entity=entity_ref("reviewed_snapshot", snapshot.snapshot_id, case_id=snapshot.case_id, display_label=snapshot.snapshot_id),
            change_summary=ChangeSummary(
                message="Reviewed snapshot explicitly signed off by an operator.",
                field_changes=[
                    FieldChangeRecord(field_path="signoff_status", old_value="not_signed_off", new_value="signed_off"),
                ],
            ),
            metadata={"signoff_id": signoff.signoff_id},
        )
        decision = audit.append_decision(
            case_id=snapshot.case_id,
            decision_type="reviewed_snapshot_signed_off",
            actor=actor,
            source_entity=entity_ref("reviewed_snapshot", snapshot.snapshot_id, case_id=snapshot.case_id, display_label=snapshot.snapshot_id),
            outcome="signed_off",
            reason=request.note.strip(),
            note=request.note.strip(),
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)

        self._session.commit()
        return ReviewedSnapshotSignOffResponse(
            result=ReviewedHandoffOperationResult(
                success=True,
                message="Reviewed snapshot signed off.",
                issues=[],
            ),
            snapshot=self._to_snapshot_record(snapshot),
            signoff=self._to_signoff_record(signoff),
        )

    def select_snapshot(
        self,
        case_id: str,
        snapshot_id: str,
    ) -> ReviewedSnapshotSelectResponse:
        self._require_case(case_id)
        snapshot = self._require_snapshot(snapshot_id)
        if snapshot.case_id != case_id:
            raise ReviewedHandoffServiceError(
                "Reviewed snapshot does not belong to this case.",
                status_code=400,
            )

        eligibility = self._build_handoff_eligibility(
            case_id,
            preferred_snapshot_id=snapshot.snapshot_id,
        )
        if not eligibility.eligible:
            message = "; ".join(
                reason.message for reason in eligibility.reasons if reason.blocking
            ) or "Reviewed snapshot is not eligible for downstream handoff."
            raise ReviewedHandoffServiceError(
                f"Reviewed snapshot must satisfy current handoff rules before it can be selected: {message}",
                status_code=400,
            )

        if snapshot.status == "selected_for_handoff":
            return ReviewedSnapshotSelectResponse(
                result=ReviewedHandoffOperationResult(
                    success=True,
                    message="Reviewed snapshot is already selected for handoff.",
                    issues=[],
                ),
                snapshot=self._to_snapshot_record(snapshot),
            )

        now = utcnow()
        existing_selected = list(self._session.exec(
            select(ReviewedSnapshotModel)
            .where(ReviewedSnapshotModel.case_id == case_id)
            .where(ReviewedSnapshotModel.status == "selected_for_handoff")
        ).all())
        for row in existing_selected:
            if row.snapshot_id == snapshot.snapshot_id:
                continue
            row.status = "created"
            row.selected_at = None
            self._session.add(row)

        previous_status = snapshot.status
        snapshot.status = "selected_for_handoff"
        snapshot.selected_at = now
        self._session.add(snapshot)

        AuditTrailService(self._session).append_event(
            case_id=case_id,
            category="reviewed_handoff",
            event_type="reviewed_snapshot_selected_for_handoff",
            actor=audit_actor("service", actor_id="reviewed_handoff.service", display_name="Reviewed Handoff Service"),
            entity=entity_ref("reviewed_snapshot", snapshot.snapshot_id, case_id=case_id, display_label=snapshot.snapshot_id),
            change_summary=ChangeSummary(
                message="Reviewed snapshot marked as the current eligible handoff selection.",
                field_changes=[
                    FieldChangeRecord(field_path="status", old_value=previous_status, new_value="selected_for_handoff"),
                ],
            ),
            metadata={},
        )

        self._session.commit()
        return ReviewedSnapshotSelectResponse(
            result=ReviewedHandoffOperationResult(
                success=True,
                message="Reviewed snapshot selected for handoff.",
                issues=[],
            ),
            snapshot=self._to_snapshot_record(snapshot),
        )

    def get_handoff_eligibility(self, case_id: str) -> HandoffEligibilityResponse:
        self._require_case(case_id)
        return HandoffEligibilityResponse(eligibility=self._build_handoff_eligibility(case_id))

    def resolve_snapshot_for_handoff(self, case_id: str, snapshot_id: str = "") -> ReviewedSnapshotRecord:
        self._require_case(case_id)
        snapshot = self._resolve_candidate_snapshot(case_id, preferred_snapshot_id=snapshot_id)
        if snapshot is None:
            raise ReviewedHandoffServiceError(
                "No reviewed snapshot is available for handoff.",
                status_code=400,
            )
        eligibility = self._build_handoff_eligibility(case_id, preferred_snapshot_id=snapshot.snapshot_id)
        if not eligibility.eligible:
            message = "; ".join(reason.message for reason in eligibility.reasons if reason.blocking) or "Reviewed snapshot is not eligible for downstream handoff."
            raise ReviewedHandoffServiceError(message, status_code=400)
        return self._to_snapshot_record(snapshot)

    def _build_handoff_eligibility(
        self,
        case_id: str,
        *,
        preferred_snapshot_id: str | None = None,
    ) -> HandoffEligibilitySummary:
        selected = self._selected_snapshot(case_id)
        snapshot = self._resolve_candidate_snapshot(case_id, preferred_snapshot_id=preferred_snapshot_id)
        if snapshot is None:
            return HandoffEligibilitySummary(
                case_id=case_id,
                snapshot_id="",
                selected_snapshot_id=selected.snapshot_id if selected is not None else "",
                has_reviewed_snapshot=False,
                release_gate_status="blocked_no_reviewed_snapshot",
                eligible=False,
                reasons=[
                    ReleaseGateReason(
                        code="no_reviewed_snapshot",
                        message="No reviewed snapshot has been created for this case yet.",
                        blocking=True,
                    )
                ],
            )

        summary = ReviewedSnapshotSummary.model_validate(snapshot.summary_json)
        signoff = self._signoff_model(snapshot.snapshot_id)
        reasons: list[ReleaseGateReason] = []

        if summary.unresolved_item_count > 0:
            reasons.append(
                ReleaseGateReason(
                    code="unresolved_review_items",
                    message=f"{summary.unresolved_item_count} unresolved review item(s) remain in the reviewed snapshot.",
                    blocking=True,
                )
            )
        if not summary.required_requirement_reviews_complete:
            reasons.append(
                ReleaseGateReason(
                    code="required_requirement_reviews_incomplete",
                    message="At least one required checklist item has not been explicitly reviewed.",
                    blocking=True,
                )
            )
        if signoff is None or signoff.status != "signed_off":
            reasons.append(
                ReleaseGateReason(
                    code="missing_signoff",
                    message="The reviewed snapshot has not been explicitly signed off by an operator.",
                    blocking=True,
                )
            )

        _CODE_TO_STATUS = {
            "unresolved_review_items": "blocked_unresolved_review_items",
            "required_requirement_reviews_incomplete": "blocked_required_requirement_reviews_incomplete",
            "missing_signoff": "blocked_missing_signoff",
        }
        eligible = not any(reason.blocking for reason in reasons)
        if eligible:
            status = "eligible_with_current_rules"
            reasons.append(
                ReleaseGateReason(
                    code="eligible_with_current_rules",
                    message="Current reviewed-snapshot handoff rules are satisfied.",
                    blocking=False,
                )
            )
        else:
            first_blocking = next(reason for reason in reasons if reason.blocking)
            status = _CODE_TO_STATUS.get(first_blocking.code, "blocked_missing_signoff")

        return HandoffEligibilitySummary(
            case_id=case_id,
            snapshot_id=snapshot.snapshot_id,
            selected_snapshot_id=selected.snapshot_id if selected is not None else "",
            has_reviewed_snapshot=True,
            snapshot_status=snapshot.status,
            signoff_status=signoff.status if signoff is not None else "not_signed_off",
            unresolved_review_item_count=summary.unresolved_item_count,
            required_requirement_reviews_complete=summary.required_requirement_reviews_complete,
            release_gate_status=status,
            eligible=eligible,
            reasons=reasons,
        )

    def _selected_snapshot(self, case_id: str) -> ReviewedSnapshotModel | None:
        return self._session.exec(
            select(ReviewedSnapshotModel)
            .where(ReviewedSnapshotModel.case_id == case_id)
            .where(ReviewedSnapshotModel.status == "selected_for_handoff")
            .order_by(desc(ReviewedSnapshotModel.selected_at), desc(ReviewedSnapshotModel.created_at))
        ).first()

    def _latest_snapshot(self, case_id: str) -> ReviewedSnapshotModel | None:
        return self._session.exec(
            select(ReviewedSnapshotModel)
            .where(ReviewedSnapshotModel.case_id == case_id)
            .order_by(desc(ReviewedSnapshotModel.created_at), desc(ReviewedSnapshotModel.snapshot_id))
        ).first()

    def _resolve_candidate_snapshot(
        self,
        case_id: str,
        *,
        preferred_snapshot_id: str | None = None,
    ) -> ReviewedSnapshotModel | None:
        if preferred_snapshot_id:
            snapshot = self._require_snapshot(preferred_snapshot_id)
            if snapshot.case_id != case_id:
                raise ReviewedHandoffServiceError(
                    "Reviewed snapshot does not belong to this case.",
                    status_code=400,
                )
            return snapshot

        selected = self._selected_snapshot(case_id)
        if selected is not None:
            return selected
        return self._latest_snapshot(case_id)

    def _signoff_model(self, snapshot_id: str) -> ReviewedSnapshotSignOffModel | None:
        return self._session.exec(
            select(ReviewedSnapshotSignOffModel)
            .where(ReviewedSnapshotSignOffModel.snapshot_id == snapshot_id)
        ).first()

    def _require_case(self, case_id: str) -> object:
        from app.cases.models import CaseRecordModel

        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise ReviewedHandoffServiceError(
                f"Case '{case_id}' not found.",
                status_code=404,
            )
        return case

    def _require_snapshot(self, snapshot_id: str) -> ReviewedSnapshotModel:
        snapshot = self._session.get(ReviewedSnapshotModel, snapshot_id)
        if snapshot is None:
            raise ReviewedHandoffServiceError(
                f"Reviewed snapshot '{snapshot_id}' not found.",
                status_code=404,
            )
        return snapshot

    def _to_snapshot_record(self, row: ReviewedSnapshotModel) -> ReviewedSnapshotRecord:
        signoff_model = self._signoff_model(row.snapshot_id)
        signoff = self._to_signoff_record(signoff_model) if signoff_model is not None else None
        return ReviewedSnapshotRecord(
            snapshot_id=row.snapshot_id,
            case_id=row.case_id,
            status=row.status,
            summary=ReviewedSnapshotSummary.model_validate(row.summary_json),
            source_metadata=ReviewedSnapshotSourceMetadata.model_validate(row.source_metadata_json),
            fields=[ReviewedFieldEntry.model_validate(entry) for entry in row.field_entries_json],
            requirements=[ReviewedRequirementEntry.model_validate(entry) for entry in row.requirement_entries_json],
            unresolved_items=[UnresolvedReviewItemSummary.model_validate(entry) for entry in row.unresolved_items_json],
            signoff_status=signoff.status if signoff is not None else "not_signed_off",
            signoff=signoff,
            note=row.note,
            created_at=isoformat_utc(row.created_at),
            selected_at=isoformat_utc(row.selected_at) if row.selected_at is not None else "",
        )

    def _to_signoff_record(self, row: ReviewedSnapshotSignOffModel) -> SnapshotSignOffRecord:
        return SnapshotSignOffRecord(
            signoff_id=row.signoff_id,
            snapshot_id=row.snapshot_id,
            case_id=row.case_id,
            status=row.status,
            actor=SignOffActorMetadata(
                actor_id=row.actor_id,
                display_name=row.actor_display_name,
                metadata=dict(row.actor_metadata_json),
            ),
            note=row.note,
            created_at=isoformat_utc(row.created_at),
        )