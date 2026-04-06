"""Checklist generation, linkage, and readiness evaluation service.

This service connects domain pack requirement definitions to real case
data (linked documents, extraction results) and produces honest
readiness metadata.  It does not implement rules engines, compliance
validators, adjudication logic, or filing decision systems.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Session, select

from casegraph_agent_sdk.audit import ChangeSummary, FieldChangeRecord
from casegraph_agent_sdk.readiness import (
    CaseChecklist,
    ChecklistGenerationMetadata,
    ChecklistItem,
    ChecklistItemStatus,
    ChecklistResponse,
    LinkedDocumentReference,
    LinkedExtractionReference,
    MissingItemSummary,
    ReadinessResponse,
    ReadinessStatus,
    ReadinessSummary,
    UpdateChecklistItemRequest,
)

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel
from app.audit.service import AuditTrailService, audit_actor, derived_ref, entity_ref, source_ref
from app.extraction.models import ExtractionRunModel
from app.ingestion.models import DocumentRecord
from app.readiness.models import (
    ChecklistItemDocumentLinkModel,
    ChecklistItemExtractionLinkModel,
    ChecklistItemModel,
    ChecklistModel,
)
from app.persistence.database import isoformat_utc


class ReadinessServiceError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class ReadinessService:
    """Generates checklists, links evidence, and evaluates readiness."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Checklist generation
    # ------------------------------------------------------------------

    def generate_checklist(
        self, case_id: str, *, force: bool = False,
    ) -> ChecklistResponse:
        """Generate a checklist from the case's domain pack case type."""

        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise ReadinessServiceError(
                f"Case '{case_id}' not found.", status_code=404,
            )

        if not case.domain_pack_id or not case.case_type_id:
            raise ReadinessServiceError(
                "Case does not have a domain pack or case type. "
                "Checklists can only be generated for domain-scoped cases.",
            )

        # Look up the case type from the domain pack registry.
        from app.domains.packs import domain_pack_registry

        result = domain_pack_registry.get_case_type(case.case_type_id)
        if result is None:
            raise ReadinessServiceError(
                f"Case type '{case.case_type_id}' not found in any registered "
                "domain pack.",
            )

        case_type, _pack_meta = result

        # Check for existing checklist.
        existing = self._session.exec(
            select(ChecklistModel).where(ChecklistModel.case_id == case_id)
        ).first()

        if existing is not None and not force:
            return self._load_checklist(existing)

        # Delete old checklist if regenerating.
        if existing is not None:
            self._delete_checklist(existing)

        now = datetime.now(UTC)
        checklist_id = str(uuid4())

        checklist_model = ChecklistModel(
            checklist_id=checklist_id,
            case_id=case_id,
            domain_pack_id=case.domain_pack_id,
            case_type_id=case.case_type_id,
            requirement_count=len(case_type.document_requirements),
            generated_at=now,
        )
        self._session.add(checklist_model)

        for req in case_type.document_requirements:
            item = ChecklistItemModel(
                item_id=str(uuid4()),
                checklist_id=checklist_id,
                requirement_id=req.requirement_id,
                display_name=req.display_name,
                description=req.description,
                document_category=req.document_category,
                priority=req.priority,
                status="missing" if req.priority != "optional" else "optional_unfilled",
                created_at=now,
                updated_at=now,
            )
            self._session.add(item)

        audit = AuditTrailService(self._session)
        audit.append_event(
            case_id=case_id,
            category="checklist",
            event_type="checklist_generated",
            actor=audit_actor("service", actor_id="readiness.service", display_name="Readiness Service"),
            entity=entity_ref(
                "checklist",
                checklist_id,
                case_id=case_id,
                display_label="Case checklist",
            ),
            change_summary=ChangeSummary(
                message="Checklist generated from case type requirements.",
                field_changes=[
                    FieldChangeRecord(field_path="requirement_count", new_value=len(case_type.document_requirements)),
                    FieldChangeRecord(field_path="domain_pack_id", new_value=case.domain_pack_id),
                    FieldChangeRecord(field_path="case_type_id", new_value=case.case_type_id),
                ],
            ),
        )
        audit.record_lineage(
            case_id=case_id,
            artifact=derived_ref("checklist", checklist_id, case_id=case_id, display_label="Case checklist"),
            edges=[
                (
                    "case_context",
                    source_ref("case", case.case_id, case_id=case.case_id, display_label=case.title, source_path="case"),
                    {"domain_pack_id": case.domain_pack_id, "case_type_id": case.case_type_id},
                ),
            ],
            notes=["Checklist generated from registered domain-pack requirements."],
        )

        self._session.commit()
        self._session.refresh(checklist_model)
        return self._load_checklist(checklist_model)

    # ------------------------------------------------------------------
    # Get existing checklist
    # ------------------------------------------------------------------

    def get_checklist(self, case_id: str) -> ChecklistResponse | None:
        """Return the current checklist for a case, or None."""
        checklist = self._session.exec(
            select(ChecklistModel).where(ChecklistModel.case_id == case_id)
        ).first()
        if checklist is None:
            return None
        return self._load_checklist(checklist)

    # ------------------------------------------------------------------
    # Evaluate coverage
    # ------------------------------------------------------------------

    def evaluate(self, case_id: str) -> ReadinessResponse:
        """Evaluate checklist coverage from real linked artifacts."""

        checklist_model = self._session.exec(
            select(ChecklistModel).where(ChecklistModel.case_id == case_id)
        ).first()
        if checklist_model is None:
            raise ReadinessServiceError(
                "No checklist exists for this case. Generate one first.",
            )

        items = list(self._session.exec(
            select(ChecklistItemModel).where(
                ChecklistItemModel.checklist_id == checklist_model.checklist_id,
            )
        ).all())

        # Gather case documents.
        case_doc_links = list(self._session.exec(
            select(CaseDocumentLinkModel).where(
                CaseDocumentLinkModel.case_id == case_id,
            )
        ).all())
        # Gather extraction runs scoped to this case.
        extraction_runs = list(self._session.exec(
            select(ExtractionRunModel).where(
                ExtractionRunModel.case_id == case_id,
            )
        ).all())

        now = datetime.now(UTC)

        for item in items:
            # Delete old linkage and re-derive.
            self._delete_item_links(item.item_id)
            doc_links_added = self._link_documents(item, case_doc_links)
            extraction_links_added = self._link_extractions(item, extraction_runs)

            # Determine status from real linkage.
            new_status = self._derive_status(
                item, doc_links_added, extraction_links_added,
            )
            item.status = new_status
            item.last_evaluated_at = now
            item.updated_at = now
            self._session.add(item)

        readiness = self._build_readiness(case_id, checklist_model, items)
        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=case_id,
            category="checklist",
            event_type="checklist_evaluated",
            actor=audit_actor("service", actor_id="readiness.service", display_name="Readiness Service"),
            entity=entity_ref(
                "checklist",
                checklist_model.checklist_id,
                case_id=case_id,
                display_label="Case checklist",
            ),
            change_summary=ChangeSummary(
                message="Checklist evaluated from linked documents and extraction runs.",
                field_changes=[
                    FieldChangeRecord(field_path="readiness_status", new_value=readiness.readiness.readiness_status),
                    FieldChangeRecord(field_path="supported_items", new_value=readiness.readiness.supported_items),
                    FieldChangeRecord(field_path="missing_items", new_value=readiness.readiness.missing_items),
                    FieldChangeRecord(field_path="needs_review_items", new_value=readiness.readiness.needs_review_items),
                ],
            ),
        )
        decision = audit.append_decision(
            case_id=case_id,
            decision_type="checklist_evaluated",
            actor=audit_actor("service", actor_id="readiness.service", display_name="Readiness Service"),
            source_entity=entity_ref(
                "checklist",
                checklist_model.checklist_id,
                case_id=case_id,
                display_label="Case checklist",
            ),
            outcome=readiness.readiness.readiness_status,
            note=f"Missing required items: {len(readiness.readiness.missing_required)}.",
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)

        self._session.commit()
        return readiness

    # ------------------------------------------------------------------
    # Manual item update (operator notes / status override)
    # ------------------------------------------------------------------

    def update_item(
        self,
        case_id: str,
        item_id: str,
        request: UpdateChecklistItemRequest,
    ) -> ChecklistItem:
        """Apply operator notes or a manual status override."""

        item = self._session.get(ChecklistItemModel, item_id)
        if item is None:
            raise ReadinessServiceError(
                f"Checklist item '{item_id}' not found.", status_code=404,
            )

        # Verify item belongs to a checklist for this case.
        checklist = self._session.get(ChecklistModel, item.checklist_id)
        if checklist is None or checklist.case_id != case_id:
            raise ReadinessServiceError(
                "Item does not belong to a checklist for this case.",
                status_code=404,
            )

        if request.operator_notes is not None:
            item.operator_notes = request.operator_notes
        if request.status_override is not None:
            allowed_overrides = {"missing", "needs_human_review", "waived"}
            if item.priority == "optional":
                allowed_overrides.add("optional_unfilled")
            if request.status_override not in allowed_overrides:
                raise ReadinessServiceError(
                    "Manual overrides cannot mark an item as supported or "
                    "partially supported. Re-run evaluation or link real "
                    "supporting artifacts instead.",
                )
            item.status = request.status_override
        item.updated_at = datetime.now(UTC)
        self._session.add(item)
        self._session.commit()
        self._session.refresh(item)
        return self._to_checklist_item(item)

    # ------------------------------------------------------------------
    # Readiness summary (read-only)
    # ------------------------------------------------------------------

    def get_readiness(self, case_id: str) -> ReadinessResponse | None:
        """Return the last-computed readiness without re-evaluating."""
        checklist_model = self._session.exec(
            select(ChecklistModel).where(ChecklistModel.case_id == case_id)
        ).first()
        if checklist_model is None:
            return None
        items = list(self._session.exec(
            select(ChecklistItemModel).where(
                ChecklistItemModel.checklist_id == checklist_model.checklist_id,
            )
        ).all())
        return self._build_readiness(case_id, checklist_model, items)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _link_documents(
        self,
        item: ChecklistItemModel,
        case_doc_links: list[CaseDocumentLinkModel],
    ) -> int:
        """Link case documents to a checklist item by document category match."""
        count = 0
        for caselink in case_doc_links:
            doc = self._session.get(DocumentRecord, caselink.document_id)
            if doc is None:
                continue
            # Coarse matching: document filename/content_type vs requirement category.
            # This is intentionally simple — no deep semantic matching.
            if self._document_matches_category(doc, item.document_category):
                link = ChecklistItemDocumentLinkModel(
                    link_id=str(uuid4()),
                    item_id=item.item_id,
                    document_id=doc.document_id,
                    filename=doc.filename,
                    content_type=doc.content_type,
                    linked_at=datetime.now(UTC),
                )
                self._session.add(link)
                count += 1
        return count

    def _link_extractions(
        self,
        item: ChecklistItemModel,
        extraction_runs: list[ExtractionRunModel],
    ) -> int:
        """Link extraction results to a checklist item."""
        count = 0
        for run in extraction_runs:
            if run.status != "completed":
                continue
            # Link extractions that were performed on documents matching category.
            doc = self._session.get(DocumentRecord, run.document_id)
            if doc is None:
                continue
            if self._document_matches_category(doc, item.document_category):
                link = ChecklistItemExtractionLinkModel(
                    link_id=str(uuid4()),
                    item_id=item.item_id,
                    extraction_id=run.extraction_id,
                    template_id=run.template_id,
                    document_id=run.document_id,
                    field_count=run.fields_extracted,
                    grounding_available=run.grounding_available,
                    linked_at=datetime.now(UTC),
                )
                self._session.add(link)
                count += 1
        return count

    @staticmethod
    def _document_matches_category(doc: DocumentRecord, category: str) -> bool:
        """Coarse document-to-category matching.

        Uses document metadata (category field stored during ingestion) if
        available, or falls back to a best-effort filename heuristic.
        This is intentionally imprecise — the system does not claim
        semantic classification.
        """
        # If the document has an explicit category stored, compare directly.
        if hasattr(doc, "category") and doc.category:
            return doc.category == category

        # Fallback: very basic keyword matching on filename.
        # This is honestly coarse and will miss many edge cases.
        fn = (doc.filename or "").lower()
        category_keywords: dict[str, list[str]] = {
            "identity": ["identity", "passport", "license", "dl", "id_card", "photo_id"],
            "clinical_notes": ["clinical", "notes", "physician", "doctor"],
            "diagnostic_report": ["diagnostic", "lab", "radiology", "pathology", "imaging"],
            "referral_order": ["referral", "order", "authorization"],
            "claim_form": ["claim", "form"],
            "invoice_bill": ["invoice", "bill", "receipt"],
            "policy_document": ["policy"],
            "tax_notice": ["tax_notice", "irs_notice", "gst_notice", "irs", "gst"],
            "income_document": ["income", "w2", "1099", "salary", "form16"],
            "prescription": ["prescription", "rx"],
            "proof_of_loss": ["loss", "proof"],
            "government_form": ["government", "tax_form", "gov_form"],
            "supporting_attachment": [],
            "insurer_payer_correspondence": ["insurer", "payer", "eob"],
            "prior_records": ["prior", "record", "history"],
            "other": [],
        }
        keywords = category_keywords.get(category, [])
        return any(kw in fn for kw in keywords) if keywords else False

    @staticmethod
    def _derive_status(
        item: ChecklistItemModel,
        doc_count: int,
        extraction_count: int,
    ) -> ChecklistItemStatus:
        """Derive item status from explicit linkage counts."""
        is_optional = item.priority == "optional"

        if doc_count == 0 and extraction_count == 0:
            return "optional_unfilled" if is_optional else "missing"

        if doc_count > 0 and extraction_count > 0:
            return "supported"

        if doc_count > 0:
            # Document present but no extraction — partial support.
            return "partially_supported"

        # Extraction exists but no document link — unusual, flag for review.
        return "needs_human_review"

    def _build_readiness(
        self,
        case_id: str,
        checklist: ChecklistModel,
        items: list[ChecklistItemModel],
    ) -> ReadinessResponse:
        """Build an honest readiness summary from item statuses."""
        total = len(items)
        required = sum(1 for i in items if i.priority == "required")
        supported = sum(1 for i in items if i.status == "supported")
        partially = sum(1 for i in items if i.status == "partially_supported")
        missing = sum(1 for i in items if i.status == "missing")
        review = sum(1 for i in items if i.status == "needs_human_review")
        optional_unfilled = sum(1 for i in items if i.status == "optional_unfilled")
        waived = sum(1 for i in items if i.status == "waived")

        required_missing = [
            i for i in items
            if i.priority == "required" and i.status in ("missing", "needs_human_review")
        ]

        evaluated_at = ""
        dates = [i.last_evaluated_at for i in items if i.last_evaluated_at]
        if dates:
            evaluated_at = isoformat_utc(max(dates))

        # Determine overall status honestly.
        if not items:
            status: ReadinessStatus = "not_evaluated"
        elif not dates:
            status = "not_evaluated"
        elif required_missing:
            status = "incomplete"
        elif review > 0 or partially > 0:
            status = "needs_review"
        else:
            status = "ready"

        return ReadinessResponse(
            readiness=ReadinessSummary(
                case_id=case_id,
                checklist_id=checklist.checklist_id,
                readiness_status=status,
                total_items=total,
                required_items=required,
                supported_items=supported,
                partially_supported_items=partially,
                missing_items=missing,
                needs_review_items=review,
                optional_unfilled_items=optional_unfilled,
                waived_items=waived,
                missing_required=[
                    MissingItemSummary(
                        item_id=i.item_id,
                        requirement_id=i.requirement_id,
                        display_name=i.display_name,
                        priority=i.priority,
                        status=i.status,
                    )
                    for i in required_missing
                ],
                evaluated_at=evaluated_at,
            ),
        )

    def _load_checklist(self, checklist: ChecklistModel) -> ChecklistResponse:
        """Load a full checklist from persistence."""
        items = list(self._session.exec(
            select(ChecklistItemModel).where(
                ChecklistItemModel.checklist_id == checklist.checklist_id,
            )
        ).all())

        return ChecklistResponse(
            checklist=CaseChecklist(
                checklist_id=checklist.checklist_id,
                case_id=checklist.case_id,
                generation=ChecklistGenerationMetadata(
                    generated_at=isoformat_utc(checklist.generated_at),
                    domain_pack_id=checklist.domain_pack_id,
                    case_type_id=checklist.case_type_id,
                    requirement_count=checklist.requirement_count,
                ),
                items=[self._to_checklist_item(i) for i in items],
            ),
        )

    def _to_checklist_item(self, item: ChecklistItemModel) -> ChecklistItem:
        """Convert a persisted item to the SDK contract."""
        doc_links = list(self._session.exec(
            select(ChecklistItemDocumentLinkModel).where(
                ChecklistItemDocumentLinkModel.item_id == item.item_id,
            )
        ).all())
        extraction_links = list(self._session.exec(
            select(ChecklistItemExtractionLinkModel).where(
                ChecklistItemExtractionLinkModel.item_id == item.item_id,
            )
        ).all())

        return ChecklistItem(
            item_id=item.item_id,
            checklist_id=item.checklist_id,
            requirement_id=item.requirement_id,
            display_name=item.display_name,
            description=item.description,
            document_category=item.document_category,
            priority=item.priority,
            status=item.status,
            operator_notes=item.operator_notes,
            linked_documents=[
                LinkedDocumentReference(
                    document_id=dl.document_id,
                    filename=dl.filename,
                    content_type=dl.content_type,
                    linked_at=isoformat_utc(dl.linked_at),
                )
                for dl in doc_links
            ],
            linked_extractions=[
                LinkedExtractionReference(
                    extraction_id=el.extraction_id,
                    template_id=el.template_id,
                    document_id=el.document_id,
                    field_count=el.field_count,
                    grounding_available=el.grounding_available,
                )
                for el in extraction_links
            ],
            linked_evidence=[],
            last_evaluated_at=isoformat_utc(item.last_evaluated_at) if item.last_evaluated_at else None,
        )

    def _delete_checklist(self, checklist: ChecklistModel) -> None:
        """Delete a checklist and all its items + links."""
        items = list(self._session.exec(
            select(ChecklistItemModel).where(
                ChecklistItemModel.checklist_id == checklist.checklist_id,
            )
        ).all())
        for item in items:
            self._delete_item_links(item.item_id)
            self._session.delete(item)
        self._session.delete(checklist)
        self._session.flush()

    def _delete_item_links(self, item_id: str) -> None:
        """Delete all document and extraction links for an item."""
        for dl in self._session.exec(
            select(ChecklistItemDocumentLinkModel).where(
                ChecklistItemDocumentLinkModel.item_id == item_id,
            )
        ).all():
            self._session.delete(dl)
        for el in self._session.exec(
            select(ChecklistItemExtractionLinkModel).where(
                ChecklistItemExtractionLinkModel.item_id == item_id,
            )
        ).all():
            self._session.delete(el)
