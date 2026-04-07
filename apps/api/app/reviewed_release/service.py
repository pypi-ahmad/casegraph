"""Reviewed release bundle service.

Creates release bundles from signed-off reviewed snapshots and generates
frozen downstream artifacts (packets, submission drafts, communication
drafts, automation plan metadata) using the snapshot as the sole source
of truth.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import ChangeSummary, FieldChangeRecord
from casegraph_agent_sdk.communications import CommunicationDraftGenerateRequest
from casegraph_agent_sdk.reviewed_release import (
    CreateReleaseBundleRequest,
    ReleaseArtifactEntry,
    ReleaseBlockingReason,
    ReleaseBundleCreateResponse,
    ReleaseBundleListResponse,
    ReleaseBundleRecord,
    ReleaseBundleResponse,
    ReleaseBundleSourceMetadata,
    ReleaseBundleSummary,
    ReleaseEligibilityResponse,
    ReleaseEligibilitySummary,
    ReleaseIssue,
    ReleaseOperationResult,
    ReleaseArtifactListResponse,
)

from app.audit.service import AuditTrailService, audit_actor, derived_ref, entity_ref, source_ref
from app.cases.models import CaseRecordModel
from app.persistence.database import isoformat_utc, utcnow
from app.reviewed_handoff.service import ReviewedHandoffService, ReviewedHandoffServiceError
from app.reviewed_release.models import ReleaseBundleModel
from app.target_packs.context import get_case_target_pack_selection


class ReviewedReleaseServiceError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class ReviewedReleaseService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_releases(self, case_id: str) -> ReleaseBundleListResponse:
        self._require_case(case_id)
        rows = list(self._session.exec(
            select(ReleaseBundleModel)
            .where(ReleaseBundleModel.case_id == case_id)
            .order_by(desc(ReleaseBundleModel.created_at), desc(ReleaseBundleModel.release_id))
        ).all())
        return ReleaseBundleListResponse(
            case_id=case_id,
            releases=[self._to_record(row) for row in rows],
        )

    def get_release(self, release_id: str) -> ReleaseBundleResponse:
        return ReleaseBundleResponse(release=self._to_record(self._require_release(release_id)))

    def get_release_artifacts(self, release_id: str) -> ReleaseArtifactListResponse:
        row = self._require_release(release_id)
        record = self._to_record(row)
        return ReleaseArtifactListResponse(
            release_id=release_id,
            artifacts=record.artifacts,
        )

    def get_release_eligibility(self, case_id: str, snapshot_id: str = "") -> ReleaseEligibilityResponse:
        self._require_case(case_id)
        return ReleaseEligibilityResponse(
            eligibility=self._build_eligibility(case_id, snapshot_id=snapshot_id),
        )

    async def create_release(
        self,
        case_id: str,
        request: CreateReleaseBundleRequest,
    ) -> ReleaseBundleCreateResponse:
        case = self._require_case(case_id)
        handoff = ReviewedHandoffService(self._session)

        # Resolve snapshot: use requested, selected, or latest
        snapshot_id = request.snapshot_id.strip() if request.snapshot_id else ""
        try:
            snapshot = handoff.resolve_snapshot_for_handoff(case_id, snapshot_id)
        except ReviewedHandoffServiceError as exc:
            raise ReviewedReleaseServiceError(exc.detail, status_code=exc.status_code) from exc

        # Build source metadata from the resolved snapshot
        signoff = snapshot.signoff
        source = ReleaseBundleSourceMetadata(
            case_id=case_id,
            snapshot_id=snapshot.snapshot_id,
            signoff_id=signoff.signoff_id if signoff is not None else "",
            signoff_status=signoff.status if signoff is not None else "not_signed_off",
            signed_off_by=(
                (signoff.actor.display_name or signoff.actor.actor_id)
                if signoff is not None else ""
            ),
            signed_off_at=signoff.created_at if signoff is not None else "",
            snapshot_created_at=snapshot.created_at,
            snapshot_included_fields=snapshot.summary.included_fields,
            snapshot_corrected_fields=snapshot.summary.corrected_fields,
            snapshot_reviewed_requirements=snapshot.summary.reviewed_requirements,
            snapshot_unresolved_item_count=snapshot.summary.unresolved_item_count,
            target_pack_selection=get_case_target_pack_selection(case.case_metadata_json),
        )

        artifacts: list[ReleaseArtifactEntry] = []
        issues: list[ReleaseIssue] = []
        now = utcnow()
        release_id = str(uuid4())

        # Generate reviewed packet
        if request.generate_packet:
            art, art_issues = self._generate_reviewed_packet(
                case_id, snapshot.snapshot_id, now,
            )
            artifacts.append(art)
            issues.extend(art_issues)

        # Generate reviewed submission draft (requires a packet)
        reviewed_packet_id = ""
        for art in artifacts:
            if art.artifact_type == "reviewed_packet" and art.status == "generated":
                reviewed_packet_id = art.downstream_artifact_id
                break

        if request.generate_submission_draft:
            if reviewed_packet_id:
                art, art_issues = self._generate_reviewed_submission_draft(
                    case_id, snapshot.snapshot_id, reviewed_packet_id, now,
                )
                artifacts.append(art)
                issues.extend(art_issues)
            else:
                artifacts.append(ReleaseArtifactEntry(
                    artifact_ref_id=str(uuid4()),
                    artifact_type="reviewed_submission_draft",
                    status="skipped_missing_data",
                    display_label="Reviewed submission draft",
                    source_mode="reviewed_snapshot",
                    source_snapshot_id=snapshot.snapshot_id,
                    notes=["Skipped: no reviewed packet was generated to source this draft from."],
                    created_at=isoformat_utc(now),
                ))

        # Generate reviewed communication draft
        if request.generate_communication_draft:
            if reviewed_packet_id:
                art, art_issues = await self._generate_reviewed_communication_draft(
                    case_id, snapshot.snapshot_id, reviewed_packet_id, now,
                )
                artifacts.append(art)
                issues.extend(art_issues)
            else:
                artifacts.append(ReleaseArtifactEntry(
                    artifact_ref_id=str(uuid4()),
                    artifact_type="reviewed_communication_draft",
                    status="skipped_missing_data",
                    display_label="Reviewed communication draft",
                    source_mode="reviewed_snapshot",
                    source_snapshot_id=snapshot.snapshot_id,
                    notes=["Skipped: no reviewed packet was generated to source this draft from."],
                    created_at=isoformat_utc(now),
                ))

        # Record automation plan metadata reference
        if request.include_automation_plan_metadata:
            art = self._record_automation_plan_metadata(
                case_id, snapshot.snapshot_id, reviewed_packet_id, now,
            )
            artifacts.append(art)

        for artifact in artifacts:
            artifact.release_bundle_id = release_id

        # Compute summary
        summary = ReleaseBundleSummary(
            total_artifacts=len(artifacts),
            generated_artifacts=sum(1 for a in artifacts if a.status == "generated"),
            skipped_artifacts=sum(1 for a in artifacts if a.status == "skipped_missing_data"),
            blocked_artifacts=sum(1 for a in artifacts if a.status == "blocked"),
            failed_artifacts=sum(1 for a in artifacts if a.status == "failed"),
        )

        status = "created" if summary.generated_artifacts > 0 else "incomplete"

        release = ReleaseBundleModel(
            release_id=release_id,
            case_id=case_id,
            snapshot_id=snapshot.snapshot_id,
            signoff_id=source.signoff_id,
            status=status,
            note=request.note.strip(),
            created_by=request.operator_id.strip(),
            created_by_display_name=request.operator_display_name.strip(),
            source_metadata_json=source.model_dump(mode="json"),
            summary_json=summary.model_dump(mode="json"),
            artifacts_json=[art.model_dump(mode="json") for art in artifacts],
            created_at=now,
        )
        self._session.add(release)

        # Audit
        actor = (
            audit_actor(
                "operator",
                actor_id=request.operator_id.strip(),
                display_name=request.operator_display_name.strip() or request.operator_id.strip(),
            )
            if request.operator_id.strip()
            else audit_actor("service", actor_id="reviewed_release.service", display_name="Reviewed Release Service")
        )
        audit = AuditTrailService(self._session)
        audit.append_event(
            case_id=case_id,
            category="reviewed_release",
            event_type="release_bundle_created",
            actor=actor,
            entity=entity_ref("release_bundle", release.release_id, case_id=case_id, display_label=case.title),
            change_summary=ChangeSummary(
                message="Release bundle created from signed-off reviewed snapshot.",
                field_changes=[
                    FieldChangeRecord(field_path="status", new_value=status),
                    FieldChangeRecord(field_path="summary.total_artifacts", new_value=summary.total_artifacts),
                    FieldChangeRecord(field_path="summary.generated_artifacts", new_value=summary.generated_artifacts),
                ],
            ),
            metadata={
                "snapshot_id": snapshot.snapshot_id,
                "source_mode": "reviewed_snapshot",
                "generated_artifact_count": summary.generated_artifacts,
                "skipped_artifact_count": summary.skipped_artifacts,
            },
        )
        audit.append_decision(
            case_id=case_id,
            decision_type="release_bundle_created",
            actor=actor,
            source_entity=entity_ref("release_bundle", release.release_id, case_id=case_id, display_label=case.title),
            outcome=status,
            note=request.note.strip(),
        )

        # Lineage
        lineage_edges = [
            (
                "case_context",
                source_ref("case", case_id, case_id=case_id, display_label=case.title, source_path="case"),
                None,
            ),
            (
                "snapshot_source",
                source_ref(
                    "reviewed_snapshot", snapshot.snapshot_id,
                    case_id=case_id, display_label=snapshot.snapshot_id,
                    source_path="reviewed_snapshot",
                ),
                {"signoff_status": source.signoff_status},
            ),
        ]
        for art in artifacts:
            if art.status == "generated" and art.downstream_artifact_id:
                lineage_edges.append(
                    (
                        "release_bundle_source",
                        source_ref(
                            _artifact_type_to_lineage_type(art.artifact_type),
                            art.downstream_artifact_id,
                            case_id=case_id,
                            display_label=art.display_label,
                            source_path=f"release.{art.artifact_type}",
                        ),
                        None,
                    )
                )
        audit.record_lineage(
            case_id=case_id,
            artifact=derived_ref("release_bundle", release.release_id, case_id=case_id, display_label=case.title),
            edges=lineage_edges,
            notes=[
                "Release bundle lineage shows the reviewed snapshot and all downstream artifacts generated from it.",
            ],
            metadata={"total_artifacts": summary.total_artifacts},
        )

        self._session.commit()

        release_record = self._to_record(release)
        success_msg = (
            f"Release bundle created with {summary.generated_artifacts} artifact(s)."
            if summary.generated_artifacts > 0
            else "Release bundle created but no downstream artifacts could be generated."
        )
        return ReleaseBundleCreateResponse(
            result=ReleaseOperationResult(
                success=True,
                message=success_msg,
                issues=issues,
            ),
            release=release_record,
        )

    # ------------------------------------------------------------------
    # Downstream artifact generation
    # ------------------------------------------------------------------

    def _generate_reviewed_packet(
        self,
        case_id: str,
        snapshot_id: str,
        now: datetime,
    ) -> tuple[ReleaseArtifactEntry, list[ReleaseIssue]]:
        from app.packets.service import PacketAssemblyService
        from app.packets.errors import PacketServiceError

        issues: list[ReleaseIssue] = []
        try:
            result = PacketAssemblyService(self._session).generate_packet(
                case_id,
                note="Generated as part of a reviewed release bundle.",
                source_mode="reviewed_snapshot",
                reviewed_snapshot_id=snapshot_id,
            )
            packet_id = result.packet.packet_id if result.packet else ""
            return (
                ReleaseArtifactEntry(
                    artifact_ref_id=str(uuid4()),
                    artifact_type="reviewed_packet",
                    downstream_artifact_id=packet_id,
                    status="generated",
                    display_label="Reviewed packet",
                    source_mode="reviewed_snapshot",
                    source_snapshot_id=snapshot_id,
                    notes=["Packet generated from reviewed snapshot."],
                    created_at=isoformat_utc(now),
                ),
                issues,
            )
        except PacketServiceError as exc:
            issues.append(ReleaseIssue(
                severity="error",
                code="packet_generation_failed",
                message=exc.detail,
                related_artifact_type="reviewed_packet",
            ))
            return (
                ReleaseArtifactEntry(
                    artifact_ref_id=str(uuid4()),
                    artifact_type="reviewed_packet",
                    status="failed",
                    display_label="Reviewed packet",
                    source_mode="reviewed_snapshot",
                    source_snapshot_id=snapshot_id,
                    notes=[f"Failed: {exc.detail}"],
                    created_at=isoformat_utc(now),
                ),
                issues,
            )

    def _generate_reviewed_submission_draft(
        self,
        case_id: str,
        snapshot_id: str,
        packet_id: str,
        now: datetime,
    ) -> tuple[ReleaseArtifactEntry, list[ReleaseIssue]]:
        from app.submissions.service import SubmissionDraftService
        from app.submissions.errors import SubmissionDraftServiceError
        from casegraph_agent_sdk.submissions import CreateSubmissionDraftRequest

        issues: list[ReleaseIssue] = []
        try:
            result = SubmissionDraftService(self._session).create_draft(
                case_id,
                CreateSubmissionDraftRequest(
                    packet_id=packet_id,
                    submission_target_id="portal_submission",
                    note="Generated as part of a reviewed release bundle.",
                ),
            )
            draft_id = result.draft.draft_id
            return (
                ReleaseArtifactEntry(
                    artifact_ref_id=str(uuid4()),
                    artifact_type="reviewed_submission_draft",
                    downstream_artifact_id=draft_id,
                    status="generated",
                    display_label="Reviewed submission draft",
                    source_mode="reviewed_snapshot",
                    source_snapshot_id=snapshot_id,
                    notes=["Submission draft generated from reviewed snapshot packet."],
                    created_at=isoformat_utc(now),
                ),
                issues,
            )
        except SubmissionDraftServiceError as exc:
            issues.append(ReleaseIssue(
                severity="warning",
                code="submission_draft_generation_failed",
                message=exc.detail,
                related_artifact_type="reviewed_submission_draft",
            ))
            return (
                ReleaseArtifactEntry(
                    artifact_ref_id=str(uuid4()),
                    artifact_type="reviewed_submission_draft",
                    status="failed",
                    display_label="Reviewed submission draft",
                    source_mode="reviewed_snapshot",
                    source_snapshot_id=snapshot_id,
                    notes=[f"Failed: {exc.detail}"],
                    created_at=isoformat_utc(now),
                ),
                issues,
            )

    async def _generate_reviewed_communication_draft(
        self,
        case_id: str,
        snapshot_id: str,
        packet_id: str,
        now: datetime,
    ) -> tuple[ReleaseArtifactEntry, list[ReleaseIssue]]:
        from app.communications.service import CommunicationDraftService
        from app.communications.errors import CommunicationDraftServiceError

        issues: list[ReleaseIssue] = []
        try:
            result = await CommunicationDraftService(self._session).generate_draft(
                case_id,
                CommunicationDraftGenerateRequest(
                    template_id="packet_cover_note",
                    strategy="deterministic_template_only",
                    packet_id=packet_id,
                    note="Generated as part of a reviewed release bundle.",
                ),
            )
            draft_id = result.draft.draft_id
            return (
                ReleaseArtifactEntry(
                    artifact_ref_id=str(uuid4()),
                    artifact_type="reviewed_communication_draft",
                    downstream_artifact_id=draft_id,
                    status="generated",
                    display_label="Reviewed communication draft (packet cover note)",
                    source_mode="reviewed_snapshot",
                    source_snapshot_id=snapshot_id,
                    notes=["Communication draft generated from reviewed snapshot packet."],
                    created_at=isoformat_utc(now),
                ),
                issues,
            )
        except CommunicationDraftServiceError as exc:
            issues.append(ReleaseIssue(
                severity="warning",
                code="communication_draft_generation_failed",
                message=exc.detail,
                related_artifact_type="reviewed_communication_draft",
            ))
            return (
                ReleaseArtifactEntry(
                    artifact_ref_id=str(uuid4()),
                    artifact_type="reviewed_communication_draft",
                    status="failed",
                    display_label="Reviewed communication draft",
                    source_mode="reviewed_snapshot",
                    source_snapshot_id=snapshot_id,
                    notes=[f"Failed: {exc.detail}"],
                    created_at=isoformat_utc(now),
                ),
                issues,
            )

    def _record_automation_plan_metadata(
        self,
        case_id: str,
        snapshot_id: str,
        packet_id: str,
        now: datetime,
    ) -> ReleaseArtifactEntry:
        """Record a metadata entry indicating automation plan derivation is available.

        Actual automation plan generation requires a submission draft and
        capabilities loader, so this entry serves as a provenance marker
        rather than a generated artifact.
        """
        notes = ["Automation plan metadata marker: actual plan generation requires an existing submission draft and dry-run capabilities."]
        if not packet_id:
            notes.append("No reviewed packet was available, so automation plan generation is not possible for this release.")
        return ReleaseArtifactEntry(
            artifact_ref_id=str(uuid4()),
            artifact_type="reviewed_automation_plan",
            status="skipped_missing_data",
            display_label="Reviewed automation plan metadata",
            source_mode="reviewed_snapshot",
            source_snapshot_id=snapshot_id,
            notes=notes,
            created_at=isoformat_utc(now),
        )

    # ------------------------------------------------------------------
    # Eligibility
    # ------------------------------------------------------------------

    def _build_eligibility(self, case_id: str, *, snapshot_id: str = "") -> ReleaseEligibilitySummary:
        handoff = ReviewedHandoffService(self._session)
        try:
            eligibility = handoff.get_handoff_eligibility(case_id).eligibility
        except ReviewedHandoffServiceError:
            return ReleaseEligibilitySummary(
                case_id=case_id,
                eligible=False,
                reasons=[ReleaseBlockingReason(
                    code="no_reviewed_snapshot",
                    message="Case not found or has no reviewed state.",
                    blocking=True,
                )],
            )

        # Use specific snapshot if requested
        if snapshot_id:
            try:
                handoff.resolve_snapshot_for_handoff(case_id, snapshot_id)
                return ReleaseEligibilitySummary(
                    case_id=case_id,
                    snapshot_id=snapshot_id,
                    signoff_status=eligibility.signoff_status,
                    eligible=True,
                    reasons=[],
                )
            except ReviewedHandoffServiceError as exc:
                return ReleaseEligibilitySummary(
                    case_id=case_id,
                    snapshot_id=snapshot_id,
                    signoff_status=eligibility.signoff_status,
                    eligible=False,
                    reasons=[ReleaseBlockingReason(
                        code="missing_signoff",
                        message=exc.detail,
                        blocking=True,
                    )],
                )

        reasons: list[ReleaseBlockingReason] = []
        for reason in eligibility.reasons:
            if reason.blocking:
                code = reason.code
                if code in ("no_reviewed_snapshot", "missing_signoff", "unresolved_review_items", "required_requirement_reviews_incomplete"):
                    reasons.append(ReleaseBlockingReason(
                        code=code,
                        message=reason.message,
                        blocking=True,
                    ))

        return ReleaseEligibilitySummary(
            case_id=case_id,
            snapshot_id=eligibility.snapshot_id,
            signoff_status=eligibility.signoff_status,
            eligible=eligibility.eligible,
            reasons=reasons,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_case(self, case_id: str) -> CaseRecordModel:
        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise ReviewedReleaseServiceError(f"Case '{case_id}' not found.", status_code=404)
        return case

    def _require_release(self, release_id: str) -> ReleaseBundleModel:
        release = self._session.get(ReleaseBundleModel, release_id)
        if release is None:
            raise ReviewedReleaseServiceError(f"Release bundle '{release_id}' not found.", status_code=404)
        return release

    def _to_record(self, row: ReleaseBundleModel) -> ReleaseBundleRecord:
        return ReleaseBundleRecord(
            release_id=row.release_id,
            case_id=row.case_id,
            status=row.status,
            source=ReleaseBundleSourceMetadata.model_validate(row.source_metadata_json),
            summary=ReleaseBundleSummary.model_validate(row.summary_json),
            artifacts=[ReleaseArtifactEntry.model_validate(a) for a in row.artifacts_json],
            note=row.note,
            created_by=row.created_by,
            created_at=isoformat_utc(row.created_at),
        )


def _artifact_type_to_lineage_type(artifact_type: str) -> str:
    mapping = {
        "reviewed_packet": "packet",
        "reviewed_submission_draft": "submission_draft",
        "reviewed_communication_draft": "communication_draft",
        "reviewed_automation_plan": "automation_plan",
    }
    return mapping.get(artifact_type, artifact_type)
