"""Deterministic packet assembly from explicit case state."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import ChangeSummary
from casegraph_agent_sdk.packets import (
    ExportArtifact,
    PacketActionEntry,
    PacketArtifactListResponse,
    PacketDetailResponse,
    PacketDocumentEntry,
    PacketExtractionEntry,
    PacketGenerateResponse,
    PacketGenerationResult,
    PacketListResponse,
    PacketManifest,
    PacketManifestResponse,
    PacketReadinessEntry,
    PacketReviewNoteEntry,
    PacketRunSummaryEntry,
    PacketSection,
    PacketSummary,
)
from casegraph_agent_sdk.reviewed_handoff import ReviewedSnapshotRecord

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel, WorkflowRunRecordModel
from app.audit.service import AuditTrailService, audit_actor, derived_ref, entity_ref, source_ref
from app.extraction.models import ExtractionRunModel
from app.ingestion.models import DocumentRecord
from app.operator_review.models import ActionItemModel, ReviewNoteModel
from app.packets.errors import PacketServiceError
from app.packets.export import generate_artifacts
from app.packets.models import ExportArtifactModel, PacketRecordModel
from app.readiness.models import (
    ChecklistItemDocumentLinkModel,
    ChecklistItemExtractionLinkModel,
    ChecklistItemModel,
    ChecklistModel,
)
from app.readiness.service import ReadinessService
from app.reviewed_handoff.service import ReviewedHandoffService, ReviewedHandoffServiceError
from app.persistence.database import isoformat_utc


class PacketAssemblyService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._readiness = ReadinessService(session)

    def generate_packet(
        self,
        case_id: str,
        *,
        note: str = "",
        source_mode: str = "live_case_state",
        reviewed_snapshot_id: str = "",
    ) -> PacketGenerateResponse:
        case = self._require_case(case_id)
        now = datetime.now(UTC)
        packet_id = str(uuid4())
        reviewed_snapshot: ReviewedSnapshotRecord | None = None
        if source_mode == "reviewed_snapshot":
            try:
                reviewed_snapshot = ReviewedHandoffService(self._session).resolve_snapshot_for_handoff(
                    case_id,
                    reviewed_snapshot_id.strip(),
                )
            except ReviewedHandoffServiceError as exc:
                raise PacketServiceError(exc.detail, status_code=exc.status_code) from exc

        manifest = self._assemble_manifest(
            case,
            packet_id=packet_id,
            note=note,
            now=now,
            source_mode=source_mode,
            reviewed_snapshot=reviewed_snapshot,
        )
        section_count = len(manifest.sections)

        artifacts = generate_artifacts(manifest)
        artifact_models: list[ExportArtifactModel] = []
        for art in artifacts:
            model = ExportArtifactModel(
                artifact_id=art.artifact_id,
                packet_id=packet_id,
                format=art.format,
                filename=art.filename,
                size_bytes=art.size_bytes,
                content_type=art.content_type,
                content_text=art.content_text,
                created_at=now,
            )
            artifact_models.append(model)

        record = PacketRecordModel(
            packet_id=packet_id,
            case_id=case_id,
            source_mode=manifest.source_mode,
            source_reviewed_snapshot_id=manifest.source_reviewed_snapshot_id,
            case_title=case.title,
            current_stage=case.current_stage or "intake",
            readiness_status=manifest.readiness_status,
            section_count=section_count,
            artifact_count=len(artifacts),
            manifest_json=manifest.model_dump(mode="json"),
            note=note.strip(),
            generated_at=now,
        )
        self._session.add(record)
        for model in artifact_models:
            self._session.add(model)

        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=case_id,
            category="packet",
            event_type="packet_generated",
            actor=audit_actor("service", actor_id="packets.service", display_name="Packet Assembly Service"),
            entity=entity_ref("packet", packet_id, case_id=case_id, display_label=case.title),
            change_summary=ChangeSummary(
                message=(
                    "Packet assembled from reviewed snapshot and explicit case context."
                    if manifest.source_mode == "reviewed_snapshot"
                    else "Packet assembled from current case state."
                )
            ),
            metadata={
                "section_count": section_count,
                "artifact_count": len(artifacts),
                "readiness_status": manifest.readiness_status or "",
                "source_mode": manifest.source_mode,
                "source_reviewed_snapshot_id": manifest.source_reviewed_snapshot_id,
            },
        )
        decision = audit.append_decision(
            case_id=case_id,
            decision_type="packet_generated",
            actor=audit_actor("service", actor_id="packets.service", display_name="Packet Assembly Service"),
            source_entity=entity_ref("packet", packet_id, case_id=case_id, display_label=case.title),
            outcome=manifest.readiness_status or "",
            note=note.strip(),
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)

        lineage_edges: list[tuple[LineageRelationshipType, SourceArtifactReference, dict | None]] = [
            (
                "case_context",
                source_ref("case", case.case_id, case_id=case.case_id, display_label=case.title, source_path="case"),
                None,
            ),
        ]
        checklist = self._session.exec(
            select(ChecklistModel).where(ChecklistModel.case_id == case_id)
        ).first()
        if checklist is not None:
            lineage_edges.append(
                (
                    "checklist_reference",
                    source_ref("checklist", checklist.checklist_id, case_id=case.case_id, display_label="Case checklist", source_path="readiness.checklist"),
                    None,
                )
            )
        if reviewed_snapshot is not None:
            lineage_edges.append(
                (
                    "snapshot_source",
                    source_ref(
                        "reviewed_snapshot",
                        reviewed_snapshot.snapshot_id,
                        case_id=case.case_id,
                        display_label=reviewed_snapshot.snapshot_id,
                        source_path="reviewed_snapshot",
                    ),
                    {
                        "signoff_status": reviewed_snapshot.signoff_status,
                        "selected_at": reviewed_snapshot.selected_at,
                    },
                )
            )
        doc_links = list(self._session.exec(
            select(CaseDocumentLinkModel).where(CaseDocumentLinkModel.case_id == case_id)
        ).all())
        for link in doc_links:
            document = self._session.get(DocumentRecord, link.document_id)
            if document is None:
                continue
            lineage_edges.append(
                (
                    "document_source",
                    source_ref("document", document.document_id, case_id=case.case_id, display_label=document.filename, source_path="case.documents"),
                    None,
                )
            )
        extraction_runs = list(self._session.exec(
            select(ExtractionRunModel).where(ExtractionRunModel.case_id == case_id)
        ).all())
        for extraction in extraction_runs:
            lineage_edges.append(
                (
                    "extraction_source",
                    source_ref("extraction_run", extraction.extraction_id, case_id=case.case_id, display_label=extraction.template_id, source_path="case.extractions"),
                    {"document_id": extraction.document_id},
                )
            )
        workflow_runs = list(self._session.exec(
            select(WorkflowRunRecordModel).where(WorkflowRunRecordModel.case_id == case_id)
        ).all())
        for run in workflow_runs:
            lineage_edges.append(
                (
                    "workflow_reference",
                    source_ref("workflow_run", run.run_id, case_id=case.case_id, display_label=run.workflow_id, source_path="case.runs"),
                    None,
                )
            )
        audit.record_lineage(
            case_id=case_id,
            artifact=derived_ref("packet", packet_id, case_id=case_id, display_label=case.title),
            edges=lineage_edges,
            notes=[
                "Packet lineage reflects current case-linked documents, checklists, extraction runs, and workflow runs at generation time.",
                "When source mode is reviewed_snapshot, the snapshot lineage edge marks the reviewed handoff artifact used for downstream consumption.",
            ],
            metadata={
                "artifact_count": len(artifacts),
                "section_count": section_count,
                "source_mode": manifest.source_mode,
            },
        )

        self._session.commit()
        self._session.refresh(record)

        summary = self._to_summary(record)
        return PacketGenerateResponse(
            result=PacketGenerationResult(
                success=True,
                message=(
                    "Packet assembled from reviewed snapshot and explicit case context."
                    if manifest.source_mode == "reviewed_snapshot"
                    else "Packet assembled from current case state."
                ),
                packet=summary,
            ),
            packet=summary,
            artifacts=[self._to_artifact(m) for m in artifact_models],
        )

    def list_packets(self, case_id: str) -> PacketListResponse:
        self._require_case(case_id)
        records = list(self._session.exec(
            select(PacketRecordModel)
            .where(PacketRecordModel.case_id == case_id)
            .order_by(desc(PacketRecordModel.generated_at), desc(PacketRecordModel.packet_id))
        ).all())
        return PacketListResponse(packets=[self._to_summary(r) for r in records])

    def get_packet(self, packet_id: str) -> PacketDetailResponse:
        record = self._require_packet(packet_id)
        manifest = PacketManifest.model_validate(record.manifest_json)
        return PacketDetailResponse(
            packet=self._to_summary(record),
            manifest=manifest,
        )

    def get_manifest(self, packet_id: str) -> PacketManifestResponse:
        record = self._require_packet(packet_id)
        manifest = PacketManifest.model_validate(record.manifest_json)
        return PacketManifestResponse(manifest=manifest)

    def list_artifacts(self, packet_id: str) -> PacketArtifactListResponse:
        self._require_packet(packet_id)
        models = list(self._session.exec(
            select(ExportArtifactModel)
            .where(ExportArtifactModel.packet_id == packet_id)
            .order_by(
                ExportArtifactModel.created_at,
                ExportArtifactModel.filename,
                ExportArtifactModel.artifact_id,
            )
        ).all())
        return PacketArtifactListResponse(
            artifacts=[self._to_artifact(m) for m in models],
        )

    def get_artifact_content(self, packet_id: str, artifact_id: str) -> tuple[ExportArtifactModel, str]:
        self._require_packet(packet_id)
        model = self._session.get(ExportArtifactModel, artifact_id)
        if model is None or model.packet_id != packet_id:
            raise PacketServiceError(
                "Export artifact not found for this packet.",
                status_code=404,
            )
        return model, model.content_text or ""

    # ------------------------------------------------------------------
    # Manifest assembly
    # ------------------------------------------------------------------

    def _assemble_manifest(
        self,
        case: CaseRecordModel,
        *,
        packet_id: str,
        note: str,
        now: datetime,
        source_mode: str,
        reviewed_snapshot: ReviewedSnapshotRecord | None,
    ) -> PacketManifest:
        sections: list[PacketSection] = []

        sections.append(self._section_case_summary(case))
        sections.append(self._section_domain_metadata(case))

        docs_section, doc_entries = self._section_linked_documents(case)
        sections.append(docs_section)

        ext_section, ext_entries = self._section_extraction_results(case)
        sections.append(ext_section)

        readiness_section = self._section_readiness_summary(case)
        sections.append(readiness_section)

        actions_section, open_action_count = self._section_open_actions(case)
        sections.append(actions_section)

        notes_section, note_count = self._section_review_notes(case)
        sections.append(notes_section)

        runs_section, run_entries = self._section_run_history(case)
        sections.append(runs_section)

        review_state_section = self._section_human_review_state(case)
        sections.append(review_state_section)
        if reviewed_snapshot is not None:
            sections.append(self._section_reviewed_snapshot(reviewed_snapshot))

        # Derive readiness_status from the already-assembled section data
        # to avoid a redundant ReadinessService query.
        readiness_status = readiness_section.data.get("readiness_status")

        return PacketManifest(
            packet_id=packet_id,
            case_id=case.case_id,
            source_mode=source_mode,
            source_reviewed_snapshot_id=reviewed_snapshot.snapshot_id if reviewed_snapshot is not None else "",
            source_snapshot_signoff_status=reviewed_snapshot.signoff_status if reviewed_snapshot is not None else "not_signed_off",
            source_snapshot_signed_off_at=(
                reviewed_snapshot.signoff.created_at
                if reviewed_snapshot is not None and reviewed_snapshot.signoff is not None
                else ""
            ),
            source_snapshot_signed_off_by=(
                (reviewed_snapshot.signoff.actor.display_name or reviewed_snapshot.signoff.actor.actor_id)
                if reviewed_snapshot is not None and reviewed_snapshot.signoff is not None
                else ""
            ),
            case_title=case.title,
            case_status=case.status,
            current_stage=case.current_stage or "intake",
            domain_pack_id=case.domain_pack_id,
            case_type_id=case.case_type_id,
            readiness_status=readiness_status,
            linked_document_count=len(doc_entries),
            extraction_count=len(ext_entries),
            open_action_count=open_action_count,
            review_note_count=note_count,
            run_count=len(run_entries),
            sections=sections,
            generated_at=isoformat_utc(now),
            note=note.strip(),
        )

    def _section_reviewed_snapshot(self, reviewed_snapshot: ReviewedSnapshotRecord) -> PacketSection:
        return PacketSection(
            section_type="reviewed_snapshot",
            title="Reviewed Snapshot",
            item_count=reviewed_snapshot.summary.included_fields + sum(
                1 for requirement in reviewed_snapshot.requirements if requirement.included_in_snapshot
            ),
            data={
                "snapshot_id": reviewed_snapshot.snapshot_id,
                "status": reviewed_snapshot.status,
                "signoff_status": reviewed_snapshot.signoff_status,
                "signed_off_at": reviewed_snapshot.signoff.created_at if reviewed_snapshot.signoff is not None else "",
                "signed_off_by": (
                    reviewed_snapshot.signoff.actor.display_name or reviewed_snapshot.signoff.actor.actor_id
                    if reviewed_snapshot.signoff is not None
                    else ""
                ),
                "summary": reviewed_snapshot.summary.model_dump(mode="json"),
                "fields": [
                    field.model_dump(mode="json")
                    for field in reviewed_snapshot.fields
                    if field.included_in_snapshot
                ],
                "requirements": [
                    requirement.model_dump(mode="json")
                    for requirement in reviewed_snapshot.requirements
                    if requirement.included_in_snapshot
                ],
                "unresolved_items": [
                    item.model_dump(mode="json")
                    for item in reviewed_snapshot.unresolved_items
                ],
            },
            empty=False,
        )

    def _section_case_summary(self, case: CaseRecordModel) -> PacketSection:
        return PacketSection(
            section_type="case_summary",
            title="Case Summary",
            item_count=1,
            data={
                "case_id": case.case_id,
                "title": case.title,
                "category": case.category,
                "status": case.status,
                "current_stage": case.current_stage or "intake",
                "summary": case.summary,
                "created_at": isoformat_utc(case.created_at),
                "updated_at": isoformat_utc(case.updated_at),
            },
            empty=False,
        )

    def _section_domain_metadata(self, case: CaseRecordModel) -> PacketSection:
        has_domain = bool(case.domain_pack_id)
        data: dict = {}
        if has_domain:
            data = {
                "domain_pack_id": case.domain_pack_id,
                "case_type_id": case.case_type_id,
                "jurisdiction": case.jurisdiction,
                "domain_category": case.domain_category,
            }
        return PacketSection(
            section_type="domain_metadata",
            title="Domain Metadata",
            item_count=1 if has_domain else 0,
            data=data,
            empty=not has_domain,
        )

    def _section_linked_documents(
        self, case: CaseRecordModel,
    ) -> tuple[PacketSection, list[PacketDocumentEntry]]:
        links = list(self._session.exec(
            select(CaseDocumentLinkModel)
            .where(CaseDocumentLinkModel.case_id == case.case_id)
            .order_by(CaseDocumentLinkModel.linked_at, CaseDocumentLinkModel.document_id)
        ).all())
        entries: list[PacketDocumentEntry] = []
        for link in links:
            doc = self._session.get(DocumentRecord, link.document_id)
            if doc is None:
                continue
            entries.append(PacketDocumentEntry(
                document_id=doc.document_id,
                filename=doc.filename,
                content_type=doc.content_type,
                page_count=doc.page_count,
                linked_at=isoformat_utc(link.linked_at),
            ))
        return (
            PacketSection(
                section_type="linked_documents",
                title="Linked Documents",
                item_count=len(entries),
                data={"documents": [e.model_dump(mode="json") for e in entries]},
                empty=len(entries) == 0,
            ),
            entries,
        )

    def _section_extraction_results(
        self, case: CaseRecordModel,
    ) -> tuple[PacketSection, list[PacketExtractionEntry]]:
        runs = list(self._session.exec(
            select(ExtractionRunModel)
            .where(ExtractionRunModel.case_id == case.case_id)
            .order_by(desc(ExtractionRunModel.created_at), desc(ExtractionRunModel.extraction_id))
        ).all())
        entries: list[PacketExtractionEntry] = []
        for run in runs:
            entries.append(PacketExtractionEntry(
                extraction_id=run.extraction_id,
                document_id=run.document_id or None,
                template_id=run.template_id or None,
                strategy_used=run.strategy_used or None,
                status=run.status,
                field_count=run.field_count,
                fields_extracted=run.fields_extracted,
                grounding_available=run.grounding_available,
                created_at=isoformat_utc(run.created_at),
            ))
        return (
            PacketSection(
                section_type="extraction_results",
                title="Extraction Results",
                item_count=len(entries),
                data={"extractions": [e.model_dump(mode="json") for e in entries]},
                empty=len(entries) == 0,
            ),
            entries,
        )

    def _section_readiness_summary(self, case: CaseRecordModel) -> PacketSection:
        checklist = self._session.exec(
            select(ChecklistModel).where(ChecklistModel.case_id == case.case_id)
        ).first()
        if checklist is None:
            return PacketSection(
                section_type="readiness_summary",
                title="Readiness Summary",
                item_count=0,
                data={"checklist_available": False},
                empty=True,
            )

        items = list(self._session.exec(
            select(ChecklistItemModel)
            .where(ChecklistItemModel.checklist_id == checklist.checklist_id)
            .order_by(
                ChecklistItemModel.created_at,
                ChecklistItemModel.requirement_id,
                ChecklistItemModel.item_id,
            )
        ).all())

        item_ids = [item.item_id for item in items]
        doc_links = list(self._session.exec(
            select(ChecklistItemDocumentLinkModel)
            .where(ChecklistItemDocumentLinkModel.item_id.in_(item_ids))
        ).all()) if item_ids else []
        ext_links = list(self._session.exec(
            select(ChecklistItemExtractionLinkModel)
            .where(ChecklistItemExtractionLinkModel.item_id.in_(item_ids))
        ).all()) if item_ids else []

        doc_counts: dict[str, int] = {}
        for link in doc_links:
            doc_counts[link.item_id] = doc_counts.get(link.item_id, 0) + 1
        ext_counts: dict[str, int] = {}
        for link in ext_links:
            ext_counts[link.item_id] = ext_counts.get(link.item_id, 0) + 1

        entries: list[PacketReadinessEntry] = []
        for item in items:
            entries.append(PacketReadinessEntry(
                checklist_item_id=item.item_id,
                requirement_id=item.requirement_id,
                display_name=item.display_name,
                priority=item.priority,
                status=item.status,
                linked_document_count=doc_counts.get(item.item_id, 0),
                linked_extraction_count=ext_counts.get(item.item_id, 0),
            ))

        readiness_result = self._readiness.get_readiness(case.case_id)
        summary_data: dict = {
            "checklist_available": True,
            "checklist_id": checklist.checklist_id,
            "items": [e.model_dump(mode="json") for e in entries],
        }
        if readiness_result is not None:
            rs = readiness_result.readiness
            summary_data["readiness_status"] = rs.readiness_status
            summary_data["total_items"] = rs.total_items
            summary_data["supported_items"] = rs.supported_items
            summary_data["missing_items"] = rs.missing_items
            summary_data["partially_supported_items"] = rs.partially_supported_items
            summary_data["needs_review_items"] = rs.needs_review_items

        return PacketSection(
            section_type="readiness_summary",
            title="Readiness Summary",
            item_count=len(entries),
            data=summary_data,
            empty=False,
        )

    def _section_open_actions(
        self, case: CaseRecordModel,
    ) -> tuple[PacketSection, int]:
        actions = list(self._session.exec(
            select(ActionItemModel)
            .where(ActionItemModel.case_id == case.case_id)
            .where(ActionItemModel.status == "open")
            .order_by(desc(ActionItemModel.updated_at), desc(ActionItemModel.action_item_id))
        ).all())
        entries = [
            PacketActionEntry(
                action_item_id=a.action_item_id,
                category=a.category,
                priority=a.priority,
                status=a.status,
                title=a.title,
                source_reason=a.source_reason,
            )
            for a in actions
        ]
        return (
            PacketSection(
                section_type="open_actions",
                title="Open Action Items",
                item_count=len(entries),
                data={"actions": [e.model_dump(mode="json") for e in entries]},
                empty=len(entries) == 0,
            ),
            len(entries),
        )

    def _section_review_notes(
        self, case: CaseRecordModel,
    ) -> tuple[PacketSection, int]:
        notes = list(self._session.exec(
            select(ReviewNoteModel)
            .where(ReviewNoteModel.case_id == case.case_id)
            .order_by(desc(ReviewNoteModel.created_at), desc(ReviewNoteModel.note_id))
        ).all())
        entries = [
            PacketReviewNoteEntry(
                note_id=n.note_id,
                body=n.body,
                decision=n.decision,
                stage_snapshot=n.stage_snapshot,
                created_at=isoformat_utc(n.created_at),
            )
            for n in notes
        ]
        return (
            PacketSection(
                section_type="review_notes",
                title="Review Notes",
                item_count=len(entries),
                data={"notes": [e.model_dump(mode="json") for e in entries]},
                empty=len(entries) == 0,
            ),
            len(entries),
        )

    def _section_run_history(
        self, case: CaseRecordModel,
    ) -> tuple[PacketSection, list[PacketRunSummaryEntry]]:
        runs = list(self._session.exec(
            select(WorkflowRunRecordModel)
            .where(WorkflowRunRecordModel.case_id == case.case_id)
            .order_by(desc(WorkflowRunRecordModel.created_at), desc(WorkflowRunRecordModel.run_id))
        ).all())
        entries = [
            PacketRunSummaryEntry(
                run_id=r.run_id,
                workflow_id=r.workflow_id,
                status=r.status,
                created_at=isoformat_utc(r.created_at),
                updated_at=isoformat_utc(r.updated_at),
            )
            for r in runs
        ]
        return (
            PacketSection(
                section_type="run_history",
                title="Workflow Run History",
                item_count=len(entries),
                data={"runs": [e.model_dump(mode="json") for e in entries]},
                empty=len(entries) == 0,
            ),
            entries,
        )

    # ------------------------------------------------------------------
    # Human review state section
    # ------------------------------------------------------------------

    def _section_human_review_state(self, case: CaseRecordModel) -> PacketSection:
        from app.human_validation.service import HumanValidationService

        svc = HumanValidationService(self._session)
        try:
            result = svc.get_reviewed_state(case.case_id)
        except Exception:
            return PacketSection(
                section_type="human_review_state",
                title="Human Review State",
                item_count=0,
                data={"available": False},
                empty=True,
            )

        state = result.state
        return PacketSection(
            section_type="human_review_state",
            title="Human Review State",
            item_count=state.field_validation.reviewed_fields + state.requirement_review.reviewed_items,
            data={
                "available": state.has_reviewed_state,
                "field_validation": state.field_validation.model_dump(mode="json"),
                "requirement_review": state.requirement_review.model_dump(mode="json"),
                "unresolved_count": len(state.unresolved_items),
                "reviewed_at": state.reviewed_at,
            },
            empty=not state.has_reviewed_state,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_case(self, case_id: str) -> CaseRecordModel:
        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise PacketServiceError(
                f"Case '{case_id}' not found.",
                status_code=404,
            )
        return case

    def _require_packet(self, packet_id: str) -> PacketRecordModel:
        record = self._session.get(PacketRecordModel, packet_id)
        if record is None:
            raise PacketServiceError(
                f"Packet '{packet_id}' not found.",
                status_code=404,
            )
        return record

    def _to_summary(self, record: PacketRecordModel) -> PacketSummary:
        return PacketSummary(
            packet_id=record.packet_id,
            case_id=record.case_id,
            source_mode=record.source_mode,
            source_reviewed_snapshot_id=record.source_reviewed_snapshot_id,
            case_title=record.case_title,
            current_stage=record.current_stage,
            readiness_status=record.readiness_status,
            section_count=record.section_count,
            artifact_count=record.artifact_count,
            generated_at=isoformat_utc(record.generated_at),
            note=record.note,
        )

    def _to_artifact(self, model: ExportArtifactModel) -> ExportArtifact:
        return ExportArtifact(
            artifact_id=model.artifact_id,
            packet_id=model.packet_id,
            format=model.format,
            filename=model.filename,
            size_bytes=model.size_bytes,
            content_type=model.content_type,
            created_at=isoformat_utc(model.created_at),
        )
