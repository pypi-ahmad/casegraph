"""Human validation service — field validation, requirement review, and reviewed state projection."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import (
    AuditableEntityReference,
    AuditActorMetadata,
    ChangeSummary,
    FieldChangeRecord,
)
from casegraph_agent_sdk.extraction import ExtractedFieldResult
from casegraph_agent_sdk.human_validation import (
    ExtractionValidationsResponse,
    FieldValidationRecord,
    FieldValidationResponse,
    FieldValidationSummary,
    OriginalValueReference,
    RequirementReviewRecord,
    RequirementReviewResponse,
    RequirementReviewsResponse,
    RequirementReviewSummary,
    ReviewedCaseState,
    ReviewedCaseStateResponse,
    ReviewerMetadata,
    UnresolvedReviewItem,
    ValidateFieldRequest,
    ReviewRequirementRequest,
)

from app.audit.service import AuditTrailService, audit_actor, entity_ref
from app.human_validation.models import FieldValidationModel, RequirementReviewModel
from app.persistence.database import isoformat_utc, utcnow


class HumanValidationServiceError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class HumanValidationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Field validation
    # ------------------------------------------------------------------

    def validate_field(
        self,
        extraction_id: str,
        field_id: str,
        request: ValidateFieldRequest,
    ) -> FieldValidationResponse:
        """Record or update a human validation decision for an extracted field."""
        from app.extraction.models import ExtractionRunModel

        run = self._session.get(ExtractionRunModel, extraction_id)
        if run is None:
            raise HumanValidationServiceError(
                f"Extraction run '{extraction_id}' not found.", status_code=404,
            )
        if not run.case_id:
            raise HumanValidationServiceError(
                "Extraction run is not linked to a case.", status_code=400,
            )

        # Find the field in the extraction result
        original_field = self._find_extracted_field(run, field_id)
        if original_field is None:
            raise HumanValidationServiceError(
                f"Field '{field_id}' not found in extraction '{extraction_id}'.",
                status_code=404,
            )

        now = utcnow()

        # Check for existing validation (upsert)
        existing = self._session.exec(
            select(FieldValidationModel).where(
                FieldValidationModel.extraction_id == extraction_id,
                FieldValidationModel.field_id == field_id,
            )
        ).first()

        previous_status = existing.status if existing is not None else "unreviewed"

        if existing is not None:
            model = existing
            model.status = request.status
            model.reviewed_value_json = {"value": request.reviewed_value}
            model.note = request.note or ""
            model.reviewer_id = request.reviewer_id or model.reviewer_id
            model.reviewer_display_name = request.reviewer_display_name or model.reviewer_display_name
            model.updated_at = now
            self._session.add(model)
        else:
            model = FieldValidationModel(
                validation_id=str(uuid4()),
                extraction_id=extraction_id,
                field_id=field_id,
                case_id=run.case_id,
                status=request.status,
                original_value_json={
                    "value": original_field.value,
                    "raw_value": original_field.raw_value,
                    "is_present": original_field.is_present,
                    "grounding": [g.model_dump(mode="json") for g in original_field.grounding],
                },
                reviewed_value_json={"value": request.reviewed_value},
                reviewer_id=request.reviewer_id or "",
                reviewer_display_name=request.reviewer_display_name or "",
                note=request.note or "",
                created_at=now,
                updated_at=now,
            )
            self._session.add(model)

        self._session.flush()

        # Audit event + decision
        audit = AuditTrailService(self._session)
        actor = audit_actor(
            "operator",
            actor_id=request.reviewer_id or "",
            display_name=request.reviewer_display_name or request.reviewer_id or "operator",
        )
        event = audit.append_event(
            case_id=run.case_id,
            category="human_validation",
            event_type="field_validation_recorded",
            actor=actor,
            entity=entity_ref(
                "field_validation",
                model.validation_id,
                case_id=run.case_id,
                display_label=f"{extraction_id}/{field_id}",
            ),
            change_summary=ChangeSummary(
                message=f"Field '{field_id}' validation: {request.status}.",
                field_changes=[
                    FieldChangeRecord(field_path="status", old_value=previous_status, new_value=request.status),
                    *(
                        [FieldChangeRecord(field_path="reviewed_value", old_value=None, new_value=request.reviewed_value)]
                        if request.status == "corrected" and request.reviewed_value is not None
                        else []
                    ),
                ],
            ),
            metadata={"extraction_id": extraction_id, "field_id": field_id},
        )
        decision = audit.append_decision(
            case_id=run.case_id,
            decision_type="field_validated",
            actor=actor,
            source_entity=entity_ref(
                "extraction_run",
                extraction_id,
                case_id=run.case_id,
                display_label=field_id,
            ),
            outcome=request.status,
            reason=f"Operator validated field '{field_id}' as {request.status}.",
            note=request.note or "",
        )
        audit.link_event_to_decision(event, decision)

        self._session.commit()
        return FieldValidationResponse(validation=self._to_field_validation_record(model))

    def get_extraction_validations(self, case_id: str) -> ExtractionValidationsResponse:
        """Return all field validation records for a case."""
        self._require_case(case_id)
        rows = list(self._session.exec(
            select(FieldValidationModel)
            .where(FieldValidationModel.case_id == case_id)
            .order_by(FieldValidationModel.extraction_id, FieldValidationModel.field_id)
        ).all())
        return ExtractionValidationsResponse(
            case_id=case_id,
            validations=[self._to_field_validation_record(r) for r in rows],
        )

    # ------------------------------------------------------------------
    # Requirement review
    # ------------------------------------------------------------------

    def review_requirement(
        self,
        case_id: str,
        item_id: str,
        request: ReviewRequirementRequest,
    ) -> RequirementReviewResponse:
        """Record or update a human review decision for a checklist requirement item."""
        from app.readiness.models import ChecklistModel, ChecklistItemModel

        self._require_case(case_id)
        checklist = self._session.exec(
            select(ChecklistModel).where(ChecklistModel.case_id == case_id)
        ).first()
        if checklist is None:
            raise HumanValidationServiceError(
                f"No checklist found for case '{case_id}'.", status_code=404,
            )

        item = self._session.get(ChecklistItemModel, item_id)
        if item is None or item.checklist_id != checklist.checklist_id:
            raise HumanValidationServiceError(
                f"Checklist item '{item_id}' not found for case '{case_id}'.",
                status_code=404,
            )

        now = utcnow()

        existing = self._session.exec(
            select(RequirementReviewModel).where(
                RequirementReviewModel.case_id == case_id,
                RequirementReviewModel.checklist_id == checklist.checklist_id,
                RequirementReviewModel.item_id == item_id,
            )
        ).first()

        previous_status = existing.status if existing is not None else "unreviewed"

        if existing is not None:
            model = existing
            model.status = request.status
            model.note = request.note or ""
            model.reviewer_id = request.reviewer_id or model.reviewer_id
            model.reviewer_display_name = request.reviewer_display_name or model.reviewer_display_name
            model.linked_document_ids_json = list(request.linked_document_ids or [])
            model.linked_extraction_ids_json = list(request.linked_extraction_ids or [])
            model.linked_evidence_notes_json = list(request.linked_evidence_notes or [])
            model.updated_at = now
            self._session.add(model)
        else:
            model = RequirementReviewModel(
                review_id=str(uuid4()),
                case_id=case_id,
                checklist_id=checklist.checklist_id,
                item_id=item_id,
                status=request.status,
                original_machine_status=item.status,
                reviewer_id=request.reviewer_id or "",
                reviewer_display_name=request.reviewer_display_name or "",
                note=request.note or "",
                linked_document_ids_json=list(request.linked_document_ids or []),
                linked_extraction_ids_json=list(request.linked_extraction_ids or []),
                linked_evidence_notes_json=list(request.linked_evidence_notes or []),
                created_at=now,
                updated_at=now,
            )
            self._session.add(model)

        self._session.flush()

        # Audit event + decision
        audit = AuditTrailService(self._session)
        actor = audit_actor(
            "operator",
            actor_id=request.reviewer_id or "",
            display_name=request.reviewer_display_name or request.reviewer_id or "operator",
        )
        event = audit.append_event(
            case_id=case_id,
            category="human_validation",
            event_type="requirement_review_recorded",
            actor=actor,
            entity=entity_ref(
                "requirement_review",
                model.review_id,
                case_id=case_id,
                display_label=item.display_name,
            ),
            change_summary=ChangeSummary(
                message=f"Requirement '{item.display_name}' reviewed: {request.status}.",
                field_changes=[
                    FieldChangeRecord(field_path="status", old_value=previous_status, new_value=request.status),
                ],
            ),
            metadata={"checklist_id": checklist.checklist_id, "item_id": item_id},
        )
        decision = audit.append_decision(
            case_id=case_id,
            decision_type="requirement_reviewed",
            actor=actor,
            source_entity=entity_ref(
                "checklist_item",
                item_id,
                case_id=case_id,
                display_label=item.display_name,
            ),
            outcome=request.status,
            reason=f"Operator reviewed requirement '{item.display_name}' as {request.status}.",
            note=request.note or "",
        )
        audit.link_event_to_decision(event, decision)

        self._session.commit()
        return RequirementReviewResponse(review=self._to_requirement_review_record(model))

    def get_requirement_reviews(self, case_id: str) -> RequirementReviewsResponse:
        """Return all requirement review records for a case."""
        self._require_case(case_id)
        rows = list(self._session.exec(
            select(RequirementReviewModel)
            .where(RequirementReviewModel.case_id == case_id)
            .order_by(RequirementReviewModel.item_id)
        ).all())
        return RequirementReviewsResponse(
            case_id=case_id,
            reviews=[self._to_requirement_review_record(r) for r in rows],
        )

    # ------------------------------------------------------------------
    # Reviewed case state projection
    # ------------------------------------------------------------------

    def get_reviewed_state(self, case_id: str) -> ReviewedCaseStateResponse:
        """Project the reviewed case state from raw outputs + validation records."""
        from app.extraction.models import ExtractionRunModel
        from app.readiness.models import ChecklistModel, ChecklistItemModel

        self._require_case(case_id)

        # --- Field validation summary ---
        validations = list(self._session.exec(
            select(FieldValidationModel).where(FieldValidationModel.case_id == case_id)
        ).all())

        extraction_rows = list(self._session.exec(
            select(ExtractionRunModel).where(ExtractionRunModel.case_id == case_id)
        ).all())

        total_fields = sum(len(r.fields_json) for r in extraction_rows)
        reviewed_fields = sum(1 for v in validations if v.status != "unreviewed")

        field_summary = FieldValidationSummary(
            total_fields=total_fields,
            reviewed_fields=reviewed_fields,
            accepted_fields=sum(1 for v in validations if v.status == "accepted"),
            corrected_fields=sum(1 for v in validations if v.status == "corrected"),
            rejected_fields=sum(1 for v in validations if v.status == "rejected"),
            needs_followup_fields=sum(1 for v in validations if v.status == "needs_followup"),
            extraction_count=len(extraction_rows),
        )

        # --- Requirement review summary ---
        checklist = self._session.exec(
            select(ChecklistModel).where(ChecklistModel.case_id == case_id)
        ).first()

        reviews = list(self._session.exec(
            select(RequirementReviewModel).where(RequirementReviewModel.case_id == case_id)
        ).all())

        total_items = 0
        if checklist is not None:
            items = list(self._session.exec(
                select(ChecklistItemModel).where(
                    ChecklistItemModel.checklist_id == checklist.checklist_id,
                )
            ).all())
            total_items = len(items)

        reviewed_items = sum(1 for r in reviews if r.status != "unreviewed")
        req_summary = RequirementReviewSummary(
            total_items=total_items,
            reviewed_items=reviewed_items,
            confirmed_supported=sum(1 for r in reviews if r.status == "confirmed_supported"),
            confirmed_missing=sum(1 for r in reviews if r.status == "confirmed_missing"),
            requires_more_information=sum(1 for r in reviews if r.status == "requires_more_information"),
            manually_overridden=sum(1 for r in reviews if r.status == "manually_overridden"),
            unresolved_count=total_items - reviewed_items,
        )

        # --- Unresolved items ---
        unresolved: list[UnresolvedReviewItem] = []

        # Fields needing follow-up
        for v in validations:
            if v.status == "needs_followup":
                unresolved.append(UnresolvedReviewItem(
                    item_type="field_validation",
                    entity_id=v.validation_id,
                    display_label=f"{v.extraction_id}/{v.field_id}",
                    current_status=v.status,
                    note=v.note,
                ))

        # Requirements needing more info
        for r in reviews:
            if r.status == "requires_more_information":
                unresolved.append(UnresolvedReviewItem(
                    item_type="requirement_review",
                    entity_id=r.review_id,
                    display_label=r.item_id,
                    current_status=r.status,
                    note=r.note,
                ))

        has_reviewed = reviewed_fields > 0 or reviewed_items > 0
        latest_update = ""
        all_timestamps = [v.updated_at for v in validations] + [r.updated_at for r in reviews]
        if all_timestamps:
            latest_update = isoformat_utc(max(all_timestamps))

        return ReviewedCaseStateResponse(
            state=ReviewedCaseState(
                case_id=case_id,
                field_validation=field_summary,
                requirement_review=req_summary,
                unresolved_items=unresolved,
                has_reviewed_state=has_reviewed,
                reviewed_at=latest_update,
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_case(self, case_id: str) -> object:
        from app.cases.models import CaseRecordModel

        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise HumanValidationServiceError(
                f"Case '{case_id}' not found.", status_code=404,
            )
        return case

    def _find_extracted_field(
        self, run: object, field_id: str,
    ) -> ExtractedFieldResult | None:
        for field_json in run.fields_json:  # type: ignore[attr-defined]
            field = ExtractedFieldResult.model_validate(field_json)
            if field.field_id == field_id:
                return field
        return None

    def _to_field_validation_record(self, row: FieldValidationModel) -> FieldValidationRecord:
        from casegraph_agent_sdk.extraction import GroundingReference

        original_json = dict(row.original_value_json)
        grounding_data = original_json.get("grounding", [])
        return FieldValidationRecord(
            validation_id=row.validation_id,
            extraction_id=row.extraction_id,
            field_id=row.field_id,
            case_id=row.case_id,
            status=row.status,
            original=OriginalValueReference(
                value=original_json.get("value"),
                raw_value=original_json.get("raw_value"),
                is_present=original_json.get("is_present", False),
                grounding=[
                    GroundingReference.model_validate(g) for g in grounding_data
                ],
            ),
            reviewed_value=row.reviewed_value_json.get("value"),
            reviewer=ReviewerMetadata(
                reviewer_id=row.reviewer_id,
                display_name=row.reviewer_display_name,
                metadata=dict(row.reviewer_metadata_json),
            ),
            note=row.note,
            created_at=isoformat_utc(row.created_at),
            updated_at=isoformat_utc(row.updated_at),
        )

    def _to_requirement_review_record(self, row: RequirementReviewModel) -> RequirementReviewRecord:
        return RequirementReviewRecord(
            review_id=row.review_id,
            case_id=row.case_id,
            checklist_id=row.checklist_id,
            item_id=row.item_id,
            status=row.status,
            original_machine_status=row.original_machine_status,
            reviewer=ReviewerMetadata(
                reviewer_id=row.reviewer_id,
                display_name=row.reviewer_display_name,
                metadata=dict(row.reviewer_metadata_json),
            ),
            note=row.note,
            linked_document_ids=list(row.linked_document_ids_json),
            linked_extraction_ids=list(row.linked_extraction_ids_json),
            linked_evidence_notes=list(row.linked_evidence_notes_json),
            created_at=isoformat_utc(row.created_at),
            updated_at=isoformat_utc(row.updated_at),
        )
