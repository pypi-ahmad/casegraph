"""Workflow pack orchestration service.

Executes a domain workflow pack against a case by composing existing
services (readiness, packets, submissions, extraction, operator review)
in an explicit stage sequence.  Each stage consumes real persisted state
and produces normalized summaries.  Outputs are deterministic reflections
of explicit case data — no fabricated facts or domain intelligence.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import ChangeSummary, FieldChangeRecord
from casegraph_agent_sdk.workflow_packs import (
    ActionGenerationSummary,
    ChecklistRefreshSummary,
    ExtractionPassSummary,
    HumanReviewCheckSummary,
    IntakeDocumentCheckSummary,
    OperatorReviewRecommendation,
    PacketAssemblySummary,
    ReadinessEvaluationSummary,
    SubmissionDraftPreparationSummary,
    WorkflowPackDefinition,
    WorkflowPackExecutionRequest,
    WorkflowPackRunRecord,
    WorkflowPackRunResponse,
    WorkflowPackRunSummaryResponse,
    WorkflowPackStageResult,
)
from casegraph_agent_sdk.submissions import (
    CreateSubmissionDraftRequest,
    GenerateAutomationPlanRequest,
)

from app.cases.models import CaseDocumentLinkModel, CaseRecordModel
from app.audit.service import AuditTrailService, audit_actor, entity_ref
from app.domains.packs import domain_pack_registry
from app.extraction.models import ExtractionRunModel
from app.ingestion.models import DocumentRecord
from app.operator_review.actions import ActionItemService
from app.operator_review.models import ActionItemModel
from app.packets.service import PacketAssemblyService
from app.persistence.database import isoformat_utc, utcnow
from app.readiness.service import ReadinessService
from app.submissions.service import SubmissionDraftService
from app.workflow_packs.errors import WorkflowPackError
from app.workflow_packs.models import WorkflowPackRunModel
from app.workflow_packs.registry import get_workflow_pack_registry

logger = logging.getLogger(__name__)


class WorkflowPackOrchestrationService:
    """Executes domain workflow packs by composing existing services."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(self, request: WorkflowPackExecutionRequest) -> WorkflowPackRunResponse:
        """Execute a workflow pack against a case."""
        registry = get_workflow_pack_registry()
        definition = registry.get(request.workflow_pack_id)
        if definition is None:
            raise WorkflowPackError(
                f"Workflow pack '{request.workflow_pack_id}' not found.",
                status_code=404,
            )

        case = self._require_case(request.case_id)
        self._validate_compatibility(case, definition)

        now = utcnow()
        run = WorkflowPackRunModel(
            run_id=str(uuid4()),
            case_id=case.case_id,
            workflow_pack_id=request.workflow_pack_id,
            status="running",
            operator_id=request.operator_id.strip() if request.operator_id else "",
            stage_results_json=[],
            review_recommendation_json={},
            notes_json=list(request.notes),
            created_at=now,
            started_at=now,
        )
        self._session.add(run)
        self._session.flush()

        stage_results: list[WorkflowPackStageResult] = []

        for stage_def in definition.stages:
            if request.skip_optional_stages and stage_def.optional:
                stage_results.append(WorkflowPackStageResult(
                    stage_id=stage_def.stage_id,
                    status="skipped",
                    display_name=stage_def.display_name,
                    notes=["Skipped — optional stage excluded by request."],
                ))
                continue

            # Check dependency failures
            failed_deps = [
                sr.stage_id for sr in stage_results
                if sr.stage_id in stage_def.depends_on
                and sr.status in ("failed", "blocked")
            ]
            if failed_deps:
                stage_results.append(WorkflowPackStageResult(
                    stage_id=stage_def.stage_id,
                    status="blocked",
                    display_name=stage_def.display_name,
                    notes=[f"Blocked by failed/blocked dependency: {', '.join(failed_deps)}."],
                ))
                continue

            result = self._execute_stage(case, stage_def.stage_id, stage_def.display_name, stage_results)
            stage_results.append(result)

        recommendation = self._build_recommendation(stage_results)
        final_status = self._derive_final_status(stage_results)

        completed_at = utcnow()
        run.status = final_status
        run.stage_results_json = [sr.model_dump(mode="json") for sr in stage_results]
        run.review_recommendation_json = recommendation.model_dump(mode="json")
        run.completed_at = completed_at
        self._session.add(run)

        completion_actor = (
            audit_actor("operator", actor_id=request.operator_id.strip(), display_name=request.operator_id.strip())
            if request.operator_id.strip()
            else audit_actor("workflow_pack", actor_id=request.workflow_pack_id, display_name=request.workflow_pack_id)
        )
        audit = AuditTrailService(self._session)
        event = audit.append_event(
            case_id=case.case_id,
            category="workflow_run",
            event_type="workflow_pack_run_completed",
            actor=completion_actor,
            entity=entity_ref("workflow_pack_run", run.run_id, case_id=case.case_id, display_label=request.workflow_pack_id),
            change_summary=ChangeSummary(
                message="Workflow pack execution completed.",
                field_changes=[
                    FieldChangeRecord(field_path="status", old_value="running", new_value=final_status),
                    FieldChangeRecord(field_path="stage_count", new_value=len(stage_results)),
                ],
            ),
            metadata={"suggested_next_stage": recommendation.suggested_next_stage},
        )
        decision = audit.append_decision(
            case_id=case.case_id,
            decision_type="workflow_pack_completed",
            actor=completion_actor,
            source_entity=entity_ref("workflow_pack_run", run.run_id, case_id=case.case_id, display_label=request.workflow_pack_id),
            outcome=final_status,
            note=" ".join(recommendation.notes).strip(),
            related_event_id=event.event_id,
        )
        audit.link_event_to_decision(event, decision)
        self._session.commit()

        return WorkflowPackRunResponse(
            success=final_status not in ("failed", "blocked"),
            message=self._status_message(final_status),
            run=self._to_run_record(run),
        )

    def get_run(self, run_id: str) -> WorkflowPackRunSummaryResponse:
        """Load a workflow pack run with case context."""
        run = self._session.get(WorkflowPackRunModel, run_id)
        if run is None:
            raise WorkflowPackError(
                f"Workflow pack run '{run_id}' not found.",
                status_code=404,
            )
        case = self._session.get(CaseRecordModel, run.case_id)
        pack = get_workflow_pack_registry().get(run.workflow_pack_id)
        return WorkflowPackRunSummaryResponse(
            run=self._to_run_record(run),
            case_title=case.title if case else "",
            domain_pack_display_name=pack.metadata.display_name if pack else "",
        )

    def list_runs(self, case_id: str) -> list[WorkflowPackRunRecord]:
        """List workflow pack runs for a case."""
        rows = list(self._session.exec(
            select(WorkflowPackRunModel)
            .where(WorkflowPackRunModel.case_id == case_id)
            .order_by(desc(WorkflowPackRunModel.created_at))
        ).all())
        return [self._to_run_record(row) for row in rows]

    # ------------------------------------------------------------------
    # Stage execution
    # ------------------------------------------------------------------

    def _execute_stage(
        self,
        case: CaseRecordModel,
        stage_id: str,
        display_name: str,
        previous_results: list[WorkflowPackStageResult],
    ) -> WorkflowPackStageResult:
        started_at = isoformat_utc(utcnow())
        try:
            if stage_id == "intake_document_check":
                summary = self._stage_intake_document_check(case)
            elif stage_id == "extraction_pass":
                summary = self._stage_extraction_pass(case)
            elif stage_id == "checklist_refresh":
                summary = self._stage_checklist_refresh(case)
            elif stage_id == "readiness_evaluation":
                summary = self._stage_readiness_evaluation(case)
            elif stage_id == "action_generation":
                summary = self._stage_action_generation(case)
            elif stage_id == "packet_assembly":
                summary = self._stage_packet_assembly(case, previous_results)
            elif stage_id == "submission_draft_preparation":
                summary = self._stage_submission_draft_preparation(case, previous_results)
            elif stage_id == "human_review_check":
                summary = self._stage_human_review_check(case)
            else:
                return WorkflowPackStageResult(
                    stage_id=stage_id,
                    status="skipped",
                    display_name=display_name,
                    started_at=started_at,
                    completed_at=isoformat_utc(utcnow()),
                    notes=[f"Unknown stage '{stage_id}' — skipped."],
                )

            status = summary.pop("_status", "completed")
            return WorkflowPackStageResult(
                stage_id=stage_id,
                status=status,
                display_name=display_name,
                started_at=started_at,
                completed_at=isoformat_utc(utcnow()),
                summary=summary,
                notes=summary.get("notes", []),
            )
        except Exception as exc:
            logger.warning("Workflow pack stage '%s' failed.", stage_id, exc_info=True)
            return WorkflowPackStageResult(
                stage_id=stage_id,
                status="failed",
                display_name=display_name,
                started_at=started_at,
                completed_at=isoformat_utc(utcnow()),
                error_message=str(exc)[:1000],
                notes=["Stage execution failed with an exception."],
            )

    # ------------------------------------------------------------------
    # Individual stage implementations
    # ------------------------------------------------------------------

    def _stage_intake_document_check(self, case: CaseRecordModel) -> dict:
        links = list(self._session.exec(
            select(CaseDocumentLinkModel)
            .where(CaseDocumentLinkModel.case_id == case.case_id)
        ).all())
        linked_doc_ids = [link.document_id for link in links]
        linked_docs = [
            self._session.get(DocumentRecord, doc_id)
            for doc_id in linked_doc_ids
        ]
        linked_docs = [d for d in linked_docs if d is not None]
        linked_categories = {getattr(d, "document_category", None) or "" for d in linked_docs}

        # Check requirements from domain pack
        required_categories: list[str] = []
        if case.domain_pack_id and case.case_type_id:
            result = domain_pack_registry.get_case_type(case.case_type_id)
            if result:
                case_type, _ = result
                required_categories = [
                    req.document_category
                    for req in case_type.document_requirements
                    if req.priority == "required"
                ]

        missing = [cat for cat in required_categories if cat not in linked_categories]
        summary = IntakeDocumentCheckSummary(
            linked_document_count=len(linked_docs),
            required_document_count=len(required_categories),
            missing_categories=missing,
            notes=[
                f"{len(linked_docs)} document(s) linked to case.",
                *(
                    [f"{len(missing)} required document category(ies) not yet linked: {', '.join(missing)}."]
                    if missing else ["All required document categories have at least one linked document."]
                ),
            ],
        )
        result = summary.model_dump(mode="json")
        result["_status"] = "completed" if not missing else "completed_partial"
        return result

    def _stage_extraction_pass(self, case: CaseRecordModel) -> dict:
        # Find existing extraction runs for this case's documents
        links = list(self._session.exec(
            select(CaseDocumentLinkModel)
            .where(CaseDocumentLinkModel.case_id == case.case_id)
        ).all())
        linked_doc_ids = {link.document_id for link in links}

        existing_runs: list[ExtractionRunModel] = []
        if linked_doc_ids:
            existing_runs = list(self._session.exec(
                select(ExtractionRunModel)
                .where(ExtractionRunModel.case_id == case.case_id)
                .where(ExtractionRunModel.document_id.in_(linked_doc_ids))
            ).all())

        completed = [r for r in existing_runs if r.status == "completed"]
        failed = [r for r in existing_runs if r.status in ("failed", "failed_validation")]

        total_fields = 0
        for run in completed:
            total_fields += run.fields_extracted or len(run.fields_json or [])

        summary = ExtractionPassSummary(
            total_runs=len(existing_runs),
            completed_runs=len(completed),
            failed_runs=len(failed),
            skipped_runs=0,
            extracted_field_count=total_fields,
            extraction_run_ids=[r.extraction_id for r in existing_runs],
            notes=[
                f"{len(existing_runs)} extraction run(s) found for case documents.",
                f"{len(completed)} completed, {len(failed)} failed.",
                f"{total_fields} total field(s) extracted across completed runs.",
                *(
                    ["No extraction runs exist yet. Run extraction on linked documents to populate this stage."]
                    if not existing_runs else []
                ),
            ],
        )
        result = summary.model_dump(mode="json")
        result["_status"] = "completed" if existing_runs else "completed_partial"
        return result

    def _stage_checklist_refresh(self, case: CaseRecordModel) -> dict:
        if not case.domain_pack_id or not case.case_type_id:
            summary = ChecklistRefreshSummary(
                checklist_generated=False,
                notes=["Case does not have a domain pack binding. Checklist generation skipped."],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "skipped"
            return result

        service = ReadinessService(self._session)
        try:
            response = service.generate_checklist(case.case_id, force=False)
            checklist = response.checklist
            summary = ChecklistRefreshSummary(
                checklist_generated=True,
                checklist_id=checklist.checklist_id,
                total_items=len(checklist.items),
                notes=[
                    f"Checklist with {len(checklist.items)} item(s) is current.",
                ],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "completed"
            return result
        except Exception as exc:
            summary = ChecklistRefreshSummary(
                checklist_generated=False,
                notes=[f"Checklist generation failed: {str(exc)[:300]}"],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "failed"
            return result

    def _stage_readiness_evaluation(self, case: CaseRecordModel) -> dict:
        if not case.domain_pack_id or not case.case_type_id:
            summary = ReadinessEvaluationSummary(
                notes=["No domain pack binding. Readiness evaluation skipped."],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "skipped"
            return result

        service = ReadinessService(self._session)
        try:
            response = service.evaluate(case.case_id)
            readiness = response.readiness
            summary = ReadinessEvaluationSummary(
                readiness_status=readiness.readiness_status,
                total_items=readiness.total_items,
                supported_items=readiness.supported_items,
                missing_items=readiness.missing_items,
                partially_supported_items=readiness.partially_supported_items,
                missing_required_names=[
                    item.display_name for item in readiness.missing_required
                ],
                notes=[
                    f"Readiness status: {readiness.readiness_status}.",
                    f"{readiness.supported_items}/{readiness.total_items} item(s) supported.",
                    *(
                        [f"{readiness.missing_items} item(s) still missing."]
                        if readiness.missing_items > 0 else []
                    ),
                ],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "completed"
            return result
        except Exception as exc:
            summary = ReadinessEvaluationSummary(
                notes=[f"Readiness evaluation failed: {str(exc)[:300]}"],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "failed"
            return result

    def _stage_action_generation(self, case: CaseRecordModel) -> dict:
        service = ActionItemService(self._session)
        try:
            response = service.generate_actions(case.case_id)
            all_actions = list(self._session.exec(
                select(ActionItemModel)
                .where(ActionItemModel.case_id == case.case_id)
            ).all())
            open_actions = [a for a in all_actions if a.status == "open"]
            high_priority = [a for a in open_actions if a.priority == "high"]
            categories = list({a.category for a in open_actions})

            summary = ActionGenerationSummary(
                total_actions=len(all_actions),
                open_actions=len(open_actions),
                high_priority_actions=len(high_priority),
                action_categories=sorted(categories),
                notes=[
                    f"{response.summary.generated_count} action(s) generated, "
                    f"{response.summary.reopened_count} reopened, "
                    f"{response.summary.resolved_count} resolved.",
                    f"{len(open_actions)} open action(s), {len(high_priority)} high priority.",
                ],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "completed"
            return result
        except Exception as exc:
            summary = ActionGenerationSummary(
                notes=[f"Action generation failed: {str(exc)[:300]}"],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "failed"
            return result

    def _stage_packet_assembly(
        self,
        case: CaseRecordModel,
        previous_results: list[WorkflowPackStageResult],
    ) -> dict:
        # Check if there are any linked documents
        links = list(self._session.exec(
            select(CaseDocumentLinkModel)
            .where(CaseDocumentLinkModel.case_id == case.case_id)
        ).all())
        if not links:
            summary = PacketAssemblySummary(
                packet_generated=False,
                skipped_reason="No documents linked to case. Packet assembly skipped.",
                notes=["Packet assembly requires at least one linked document."],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "skipped"
            return result

        service = PacketAssemblyService(self._session)
        try:
            response = service.generate_packet(
                case.case_id,
                note="Generated by workflow pack orchestration.",
            )
            summary = PacketAssemblySummary(
                packet_generated=True,
                packet_id=response.packet.packet_id,
                artifact_count=response.packet.artifact_count,
                notes=[
                    f"Packet '{response.packet.packet_id}' assembled with "
                    f"{response.packet.artifact_count} artifact(s).",
                ],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "completed"
            return result
        except Exception as exc:
            summary = PacketAssemblySummary(
                packet_generated=False,
                skipped_reason=f"Packet assembly failed: {str(exc)[:300]}",
                notes=[f"Packet assembly failed: {str(exc)[:300]}"],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "failed"
            return result

    def _stage_submission_draft_preparation(
        self,
        case: CaseRecordModel,
        previous_results: list[WorkflowPackStageResult],
    ) -> dict:
        # Check if packet assembly produced a packet
        packet_result = next(
            (sr for sr in previous_results if sr.stage_id == "packet_assembly"),
            None,
        )
        if packet_result is None or packet_result.status in ("skipped", "failed", "blocked"):
            summary = SubmissionDraftPreparationSummary(
                draft_generated=False,
                skipped_reason="No packet available. Submission draft preparation skipped.",
                notes=["Submission draft requires a successfully assembled packet."],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "skipped"
            return result

        packet_id = packet_result.summary.get("packet_id", "")
        if not packet_id:
            summary = SubmissionDraftPreparationSummary(
                draft_generated=False,
                skipped_reason="Packet ID not found in assembly result.",
                notes=["Cannot create submission draft without a valid packet."],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "skipped"
            return result

        service = SubmissionDraftService(self._session)
        try:
            draft_response = service.create_draft(
                case.case_id,
                CreateSubmissionDraftRequest(
                    packet_id=packet_id,
                    submission_target_id="portal_submission",
                    note="Created by workflow pack orchestration.",
                ),
            )
            draft = draft_response.draft
            plan_id = ""
            plan_generated = False

            # Attempt plan generation only if draft was created
            if draft.draft_id:
                try:
                    try:
                        asyncio.get_running_loop()
                    except RuntimeError:
                        plan_response = asyncio.run(service.generate_plan(
                            draft.draft_id,
                            GenerateAutomationPlanRequest(dry_run=True),
                        ))
                        plan_id = plan_response.plan.plan_id if plan_response.plan else ""
                        plan_generated = bool(plan_id)
                    else:
                        logger.info(
                            "Skipping dry-run automation plan generation during workflow pack execution because an event loop is already running.",
                        )
                except Exception:
                    logger.warning("Automation plan generation skipped or failed.", exc_info=True)

            summary = SubmissionDraftPreparationSummary(
                draft_generated=True,
                draft_id=draft.draft_id,
                plan_generated=plan_generated,
                plan_id=plan_id,
                notes=[
                    f"Submission draft '{draft.draft_id}' created.",
                    *(
                        [f"Dry-run automation plan '{plan_id}' generated."]
                        if plan_generated
                        else ["Automation plan generation was not possible at this stage."]
                    ),
                ],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "completed" if draft.draft_id else "failed"
            return result
        except Exception as exc:
            summary = SubmissionDraftPreparationSummary(
                draft_generated=False,
                skipped_reason=f"Submission draft creation failed: {str(exc)[:300]}",
                notes=[f"Submission draft creation failed: {str(exc)[:300]}"],
            )
            result = summary.model_dump(mode="json")
            result["_status"] = "failed"
            return result

    # ------------------------------------------------------------------
    # Recommendation
    # ------------------------------------------------------------------

    def _build_recommendation(
        self,
        stage_results: list[WorkflowPackStageResult],
    ) -> OperatorReviewRecommendation:
        intake = next((sr for sr in stage_results if sr.stage_id == "intake_document_check"), None)
        readiness = next((sr for sr in stage_results if sr.stage_id == "readiness_evaluation"), None)
        actions = next((sr for sr in stage_results if sr.stage_id == "action_generation"), None)

        has_missing_docs = False
        if intake and intake.summary.get("missing_categories"):
            has_missing_docs = True

        readiness_status = "not_evaluated"
        if readiness and readiness.summary.get("readiness_status"):
            readiness_status = readiness.summary["readiness_status"]

        has_high_priority = False
        if actions and actions.summary.get("high_priority_actions", 0) > 0:
            has_high_priority = True

        has_failures = any(sr.status == "failed" for sr in stage_results)

        # Suggest next stage based on state
        if has_failures:
            suggested = "document_review"
        elif has_missing_docs:
            suggested = "awaiting_documents"
        elif readiness_status in ("incomplete", "needs_review"):
            suggested = "readiness_review"
        elif has_high_priority:
            suggested = "document_review"
        else:
            suggested = "ready_for_next_step"

        notes: list[str] = []
        if has_missing_docs:
            notes.append("Required document categories are missing. Collect documents before proceeding.")
        if readiness_status == "incomplete":
            notes.append("Readiness evaluation found gaps. Review checklist items.")
        if has_high_priority:
            notes.append("High-priority follow-up actions require operator attention.")
        if has_failures:
            notes.append("One or more stages failed. Review errors before proceeding.")
        if not notes:
            notes.append("All stages completed. Review results before advancing the case.")

        return OperatorReviewRecommendation(
            has_missing_required_documents=has_missing_docs,
            has_open_high_priority_actions=has_high_priority,
            has_failed_stages=has_failures,
            readiness_status=readiness_status,
            suggested_next_stage=suggested,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Human review check stage
    # ------------------------------------------------------------------

    def _stage_human_review_check(self, case: CaseRecordModel) -> dict:
        from app.human_validation.service import HumanValidationService

        svc = HumanValidationService(self._session)
        result = svc.get_reviewed_state(case.case_id)
        state = result.state
        fv = state.field_validation
        rr = state.requirement_review

        notes: list[str] = []
        if not state.has_reviewed_state:
            notes.append("No human review decisions have been recorded for this case yet.")
        else:
            notes.append(f"{fv.reviewed_fields}/{fv.total_fields} extracted field(s) reviewed.")
            notes.append(f"{rr.reviewed_items}/{rr.total_items} requirement item(s) reviewed.")
            if len(state.unresolved_items) > 0:
                notes.append(f"{len(state.unresolved_items)} unresolved item(s) require operator attention.")

        summary = HumanReviewCheckSummary(
            has_reviewed_state=state.has_reviewed_state,
            reviewed_fields=fv.reviewed_fields,
            total_fields=fv.total_fields,
            reviewed_requirements=rr.reviewed_items,
            total_requirements=rr.total_items,
            unresolved_count=len(state.unresolved_items),
            notes=notes,
        )
        return {**summary.model_dump(mode="json"), "_status": "completed"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_compatibility(
        self,
        case: CaseRecordModel,
        definition: WorkflowPackDefinition,
    ) -> None:
        if not case.case_type_id:
            raise WorkflowPackError(
                "Case does not have a case type binding. "
                "Workflow packs require a domain-scoped case.",
            )
        if case.case_type_id not in definition.metadata.compatible_case_type_ids:
            raise WorkflowPackError(
                f"Case type '{case.case_type_id}' is not compatible with "
                f"workflow pack '{definition.metadata.workflow_pack_id}'. "
                f"Compatible types: {', '.join(definition.metadata.compatible_case_type_ids)}.",
            )

    def _derive_final_status(
        self,
        stage_results: list[WorkflowPackStageResult],
    ) -> str:
        statuses = {sr.status for sr in stage_results}
        if "failed" in statuses:
            return "failed"
        if "blocked" in statuses:
            return "blocked"
        if "completed_partial" in statuses or "skipped" in statuses:
            return "completed_partial"
        return "completed"

    def _status_message(self, status: str) -> str:
        messages = {
            "completed": "Workflow pack run completed successfully.",
            "completed_partial": "Workflow pack run completed with some stages skipped or partial.",
            "blocked": "Workflow pack run blocked — prerequisite stages did not succeed.",
            "failed": "Workflow pack run completed with failures in one or more stages.",
        }
        return messages.get(status, f"Workflow pack run status: {status}.")

    def _require_case(self, case_id: str) -> CaseRecordModel:
        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise WorkflowPackError(
                f"Case '{case_id}' not found.",
                status_code=404,
            )
        return case

    def _to_run_record(self, row: WorkflowPackRunModel) -> WorkflowPackRunRecord:
        return WorkflowPackRunRecord(
            run_id=row.run_id,
            case_id=row.case_id,
            workflow_pack_id=row.workflow_pack_id,
            status=row.status,
            operator_id=row.operator_id,
            stage_results=[
                WorkflowPackStageResult.model_validate(sr)
                for sr in row.stage_results_json
            ],
            review_recommendation=OperatorReviewRecommendation.model_validate(
                row.review_recommendation_json
            ) if row.review_recommendation_json else OperatorReviewRecommendation(),
            created_at=isoformat_utc(row.created_at),
            started_at=isoformat_utc(row.started_at) if row.started_at else "",
            completed_at=isoformat_utc(row.completed_at) if row.completed_at else "",
            notes=list(row.notes_json),
        )
