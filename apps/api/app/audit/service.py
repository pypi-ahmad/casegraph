"""Append-oriented audit, decision-ledger, and lineage services."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlmodel import Session, desc, select

from casegraph_agent_sdk.audit import (
    ArtifactLineageResponse,
    AuditableEntityReference,
    AuditActorMetadata,
    AuditEventRecord,
    AuditFilterMetadata,
    AuditTimelineResponse,
    ChangeSummary,
    DecisionLedgerEntry,
    DecisionLedgerResponse,
    DerivedArtifactReference,
    LineageEdge,
    LineageRecord,
    LineageRelationshipType,
    LineageResponse,
    SourceArtifactReference,
)

from app.audit.models import (
    ArtifactLineageEdgeModel,
    ArtifactLineageRecordModel,
    AuditEventModel,
    DecisionLedgerEntryModel,
)
from app.persistence.database import isoformat_utc, utcnow


def audit_actor(
    actor_type,
    *,
    actor_id: str = "",
    display_name: str = "",
    metadata: dict | None = None,
) -> AuditActorMetadata:
    return AuditActorMetadata(
        actor_type=actor_type,
        actor_id=actor_id,
        display_name=display_name or actor_id,
        metadata=metadata or {},
    )


def entity_ref(
    entity_type: str,
    entity_id: str,
    *,
    case_id: str = "",
    display_label: str = "",
    source_path: str = "",
) -> AuditableEntityReference:
    return AuditableEntityReference(
        entity_type=entity_type,
        entity_id=entity_id,
        case_id=case_id,
        display_label=display_label,
        source_path=source_path,
    )


def source_ref(
    artifact_type,
    artifact_id: str,
    *,
    case_id: str = "",
    display_label: str = "",
    source_path: str = "",
) -> SourceArtifactReference:
    return SourceArtifactReference(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        case_id=case_id,
        display_label=display_label,
        source_path=source_path,
    )


def derived_ref(
    artifact_type,
    artifact_id: str,
    *,
    case_id: str = "",
    display_label: str = "",
) -> DerivedArtifactReference:
    return DerivedArtifactReference(
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        case_id=case_id,
        display_label=display_label,
    )


class AuditServiceError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class AuditTrailService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append_event(
        self,
        *,
        case_id: str,
        category,
        event_type,
        actor: AuditActorMetadata,
        entity: AuditableEntityReference,
        change_summary: ChangeSummary | None = None,
        related_entities: list[AuditableEntityReference] | None = None,
        metadata: dict | None = None,
        created_at: datetime | None = None,
    ) -> AuditEventModel:
        event = AuditEventModel(
            event_id=str(uuid4()),
            case_id=case_id,
            category=category,
            event_type=event_type,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            actor_display_name=actor.display_name,
            actor_metadata_json=dict(actor.metadata),
            entity_type=entity.entity_type,
            entity_id=entity.entity_id,
            entity_label=entity.display_label,
            change_summary_json=(change_summary or ChangeSummary()).model_dump(mode="json"),
            decision_ids_json=[],
            related_entities_json=[
                ref.model_dump(mode="json") for ref in (related_entities or [])
            ],
            metadata_json=dict(metadata or {}),
            created_at=created_at or utcnow(),
        )
        self._session.add(event)
        return event

    def append_decision(
        self,
        *,
        case_id: str,
        decision_type,
        actor: AuditActorMetadata,
        source_entity: AuditableEntityReference,
        outcome: str = "",
        reason: str = "",
        note: str = "",
        related_event_id: str = "",
        metadata: dict | None = None,
        created_at: datetime | None = None,
    ) -> DecisionLedgerEntryModel:
        entry = DecisionLedgerEntryModel(
            decision_id=str(uuid4()),
            case_id=case_id,
            decision_type=decision_type,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            actor_display_name=actor.display_name,
            actor_metadata_json=dict(actor.metadata),
            source_entity_type=source_entity.entity_type,
            source_entity_id=source_entity.entity_id,
            source_entity_label=source_entity.display_label,
            related_event_id=related_event_id,
            outcome=outcome,
            reason=reason,
            note=note,
            metadata_json=dict(metadata or {}),
            created_at=created_at or utcnow(),
        )
        self._session.add(entry)
        return entry

    def link_event_to_decision(
        self,
        event: AuditEventModel,
        decision: DecisionLedgerEntryModel,
    ) -> None:
        event.decision_ids_json = [*event.decision_ids_json, decision.decision_id]
        self._session.add(event)

    def record_lineage(
        self,
        *,
        case_id: str,
        artifact: DerivedArtifactReference,
        edges: list[tuple[LineageRelationshipType, SourceArtifactReference, dict | None]],
        notes: list[str] | None = None,
        metadata: dict | None = None,
        created_at: datetime | None = None,
    ) -> ArtifactLineageRecordModel:
        existing = self._session.exec(
            select(ArtifactLineageRecordModel).where(
                ArtifactLineageRecordModel.artifact_type == artifact.artifact_type,
                ArtifactLineageRecordModel.artifact_id == artifact.artifact_id,
            )
        ).first()
        if existing is not None:
            return existing

        now = created_at or utcnow()
        record = ArtifactLineageRecordModel(
            record_id=str(uuid4()),
            case_id=case_id,
            artifact_type=artifact.artifact_type,
            artifact_id=artifact.artifact_id,
            artifact_label=artifact.display_label,
            notes_json=list(notes or []),
            metadata_json=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)
        self._session.flush()

        for relationship_type, source, edge_metadata in edges:
            self._session.add(
                ArtifactLineageEdgeModel(
                    edge_id=str(uuid4()),
                    record_id=record.record_id,
                    case_id=case_id,
                    relationship_type=relationship_type,
                    source_artifact_type=source.artifact_type,
                    source_artifact_id=source.artifact_id,
                    source_label=source.display_label,
                    source_path=source.source_path,
                    metadata_json=dict(edge_metadata or {}),
                    created_at=now,
                )
            )

        return record

    def get_case_timeline(
        self,
        case_id: str,
        *,
        category: str | None = None,
        event_type: str | None = None,
    ) -> AuditTimelineResponse:
        self._require_case(case_id)
        query = select(AuditEventModel).where(AuditEventModel.case_id == case_id)
        if category:
            query = query.where(AuditEventModel.category == category)
        if event_type:
            query = query.where(AuditEventModel.event_type == event_type)
        rows = list(self._session.exec(query.order_by(desc(AuditEventModel.created_at))).all())
        all_rows = list(self._session.exec(
            select(AuditEventModel).where(AuditEventModel.case_id == case_id)
        ).all())
        return AuditTimelineResponse(
            case_id=case_id,
            events=[self._to_event_record(row) for row in rows],
            filters=AuditFilterMetadata(
                categories=sorted({row.category for row in all_rows}),
                event_types=sorted({row.event_type for row in all_rows}),
                actor_types=sorted({row.actor_type for row in all_rows}),
            ),
        )

    def get_case_decisions(self, case_id: str) -> DecisionLedgerResponse:
        self._require_case(case_id)
        rows = list(self._session.exec(
            select(DecisionLedgerEntryModel)
            .where(DecisionLedgerEntryModel.case_id == case_id)
            .order_by(desc(DecisionLedgerEntryModel.created_at))
        ).all())
        return DecisionLedgerResponse(
            case_id=case_id,
            decisions=[self._to_decision_record(row) for row in rows],
        )

    def get_case_lineage(self, case_id: str) -> LineageResponse:
        self._require_case(case_id)
        rows = list(self._session.exec(
            select(ArtifactLineageRecordModel)
            .where(ArtifactLineageRecordModel.case_id == case_id)
            .order_by(desc(ArtifactLineageRecordModel.created_at))
        ).all())
        return LineageResponse(
            case_id=case_id,
            records=[self._to_lineage_record(row) for row in rows],
        )

    def get_artifact_lineage(self, artifact_type: str, artifact_id: str) -> ArtifactLineageResponse:
        row = self._session.exec(
            select(ArtifactLineageRecordModel).where(
                ArtifactLineageRecordModel.artifact_type == artifact_type,
                ArtifactLineageRecordModel.artifact_id == artifact_id,
            )
        ).first()
        return ArtifactLineageResponse(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            record=self._to_lineage_record(row) if row is not None else None,
        )

    def _require_case(self, case_id: str) -> CaseRecordModel:
        from app.cases.models import CaseRecordModel

        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise AuditServiceError(f"Case '{case_id}' not found.", status_code=404)
        return case

    def _to_event_record(self, row: AuditEventModel) -> AuditEventRecord:
        return AuditEventRecord(
            event_id=row.event_id,
            case_id=row.case_id,
            category=row.category,
            event_type=row.event_type,
            actor=AuditActorMetadata(
                actor_type=row.actor_type,
                actor_id=row.actor_id,
                display_name=row.actor_display_name,
                metadata=dict(row.actor_metadata_json),
            ),
            entity=AuditableEntityReference(
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                case_id=row.case_id,
                display_label=row.entity_label,
            ),
            change_summary=ChangeSummary.model_validate(row.change_summary_json),
            decision_ids=list(row.decision_ids_json),
            related_entities=[
                AuditableEntityReference.model_validate(item)
                for item in row.related_entities_json
            ],
            metadata=dict(row.metadata_json),
            created_at=isoformat_utc(row.created_at),
        )

    def _to_decision_record(self, row: DecisionLedgerEntryModel) -> DecisionLedgerEntry:
        return DecisionLedgerEntry(
            decision_id=row.decision_id,
            case_id=row.case_id,
            decision_type=row.decision_type,
            actor=AuditActorMetadata(
                actor_type=row.actor_type,
                actor_id=row.actor_id,
                display_name=row.actor_display_name,
                metadata=dict(row.actor_metadata_json),
            ),
            source_entity=AuditableEntityReference(
                entity_type=row.source_entity_type,
                entity_id=row.source_entity_id,
                case_id=row.case_id,
                display_label=row.source_entity_label,
            ),
            outcome=row.outcome,
            reason=row.reason,
            note=row.note,
            related_event_id=row.related_event_id,
            metadata=dict(row.metadata_json),
            created_at=isoformat_utc(row.created_at),
        )

    def _to_lineage_record(self, row: ArtifactLineageRecordModel) -> LineageRecord:
        edge_rows = list(self._session.exec(
            select(ArtifactLineageEdgeModel)
            .where(ArtifactLineageEdgeModel.record_id == row.record_id)
            .order_by(ArtifactLineageEdgeModel.created_at)
        ).all())
        artifact = DerivedArtifactReference(
            artifact_type=row.artifact_type,
            artifact_id=row.artifact_id,
            case_id=row.case_id,
            display_label=row.artifact_label,
        )
        return LineageRecord(
            record_id=row.record_id,
            case_id=row.case_id,
            artifact=artifact,
            edges=[
                LineageEdge(
                    edge_id=edge.edge_id,
                    relationship_type=edge.relationship_type,
                    source=SourceArtifactReference(
                        artifact_type=edge.source_artifact_type,
                        artifact_id=edge.source_artifact_id,
                        case_id=edge.case_id,
                        display_label=edge.source_label,
                        source_path=edge.source_path,
                    ),
                    derived=artifact,
                    metadata=dict(edge.metadata_json),
                    created_at=isoformat_utc(edge.created_at),
                )
                for edge in edge_rows
            ],
            notes=list(row.notes_json),
            created_at=isoformat_utc(row.created_at),
            updated_at=isoformat_utc(row.updated_at),
        )