"""Helpers for building deterministic draft source metadata and mapping previews."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from casegraph_agent_sdk.extraction import ExtractedFieldResult
from casegraph_agent_sdk.packets import PacketManifest
from casegraph_agent_sdk.reviewed_handoff import ReviewedSnapshotRecord
from casegraph_agent_sdk.submissions import (
    SubmissionDraftSourceMetadata,
    SubmissionMappingFieldDefinition,
    SubmissionMappingSourceReference,
    SubmissionFieldValuePreview,
    SubmissionMappingTargetField,
    SubmissionTargetMetadata,
)
from casegraph_agent_sdk.target_packs import CaseTargetPackSelection

from app.cases.models import CaseRecordModel
from app.extraction.models import ExtractionRunModel


@dataclass(frozen=True)
class CandidateSource:
    reference: SubmissionMappingSourceReference
    raw_value: Any
    text_value: str


def build_source_metadata_and_mappings(
    case: CaseRecordModel,
    manifest: PacketManifest,
    extraction_runs: list[ExtractionRunModel],
    target: SubmissionTargetMetadata,
    reviewed_snapshot: ReviewedSnapshotRecord | None = None,
    *,
    target_fields: list[SubmissionMappingTargetField] | None = None,
    target_pack_selection: CaseTargetPackSelection | None = None,
) -> tuple[SubmissionDraftSourceMetadata, list[SubmissionMappingFieldDefinition]]:
    candidates = _collect_candidates(
        case,
        manifest,
        extraction_runs,
        reviewed_snapshot=reviewed_snapshot,
    )

    source_metadata = SubmissionDraftSourceMetadata(
        packet_id=manifest.packet_id,
        source_mode=manifest.source_mode,
        source_reviewed_snapshot_id=manifest.source_reviewed_snapshot_id,
        source_snapshot_signoff_status=manifest.source_snapshot_signoff_status,
        source_snapshot_signed_off_at=manifest.source_snapshot_signed_off_at,
        source_snapshot_signed_off_by=manifest.source_snapshot_signed_off_by,
        packet_generated_at=manifest.generated_at,
        domain_pack_id=manifest.domain_pack_id,
        case_type_id=manifest.case_type_id,
        readiness_status=manifest.readiness_status,
        linked_document_count=manifest.linked_document_count,
        extraction_count=manifest.extraction_count,
        candidate_source_count=len(candidates),
        source_sections=[section.section_type for section in manifest.sections],
        target_pack_selection=target_pack_selection,
    )

    mappings: list[SubmissionMappingFieldDefinition] = []
    for target_field in (target_fields or target.default_target_fields):
        matches = [
            candidate
            for candidate in candidates
            if candidate.reference.source_path in target_field.candidate_source_paths
        ]

        if not matches:
            status = "requires_human_input" if target_field.required else "unresolved"
            notes = [
                "No current case, packet, or extraction value matched this target field.",
            ]
            mappings.append(
                SubmissionMappingFieldDefinition(
                    mapping_id=str(uuid4()),
                    target_field=target_field,
                    status=status,
                    notes=notes,
                )
            )
            continue

        primary = matches[0]
        preview = SubmissionFieldValuePreview(
            value_present=True,
            text_value=primary.text_value,
            raw_value=primary.raw_value,
            source_reference=primary.reference,
            notes=[],
        )
        status = "mapped_preview"
        notes: list[str] = [
            "Preview is derived from explicit persisted source data only.",
        ]

        unique_values = {
            (candidate.text_value, _stable_value_key(candidate.raw_value))
            for candidate in matches
        }
        if len(matches) > 1 and len(unique_values) == 1:
            notes.append(
                "Matching sources agreed on the same preview value across current case and packet state."
            )
        elif len(matches) > 1:
            status = "candidate_available"
            notes.append(
                f"{len(matches)} candidate sources matched. Preview shows the first deterministic candidate."
            )
            notes.append(
                "Operator review is required before treating this field as confirmed."
            )

        mappings.append(
            SubmissionMappingFieldDefinition(
                mapping_id=str(uuid4()),
                target_field=target_field,
                status=status,
                source_reference=primary.reference,
                value_preview=preview,
                notes=notes,
            )
        )

    return source_metadata, mappings


def _collect_candidates(
    case: CaseRecordModel,
    manifest: PacketManifest,
    extraction_runs: list[ExtractionRunModel],
    reviewed_snapshot: ReviewedSnapshotRecord | None = None,
) -> list[CandidateSource]:
    candidates: list[CandidateSource] = []

    def add_candidate(
        entity_type: str,
        entity_id: str,
        source_path: str,
        raw_value: Any,
        display_label: str,
    ) -> None:
        if raw_value is None:
            return
        if isinstance(raw_value, str) and not raw_value.strip():
            return
        if isinstance(raw_value, (list, dict)) and len(raw_value) == 0:
            return

        candidates.append(
            CandidateSource(
                reference=SubmissionMappingSourceReference(
                    source_entity_type=entity_type,
                    source_entity_id=entity_id,
                    source_path=source_path,
                    display_label=display_label,
                ),
                raw_value=raw_value,
                text_value=_to_preview_text(raw_value),
            )
        )

    case_fields = [
        ("case.case_id", case.case_id, "Case ID"),
        ("case.title", case.title, "Case Title"),
        ("case.category", case.category, "Case Category"),
        ("case.status", case.status, "Case Status"),
        ("case.summary", case.summary, "Case Summary"),
        ("case.current_stage", case.current_stage, "Current Stage"),
        ("case.domain_pack_id", case.domain_pack_id, "Domain Pack ID"),
        ("case.case_type_id", case.case_type_id, "Case Type ID"),
        ("case.jurisdiction", case.jurisdiction, "Jurisdiction"),
        ("case.domain_category", case.domain_category, "Domain Category"),
    ]
    for source_path, raw_value, label in case_fields:
        add_candidate("case", case.case_id, source_path, raw_value, label)

    for key_path, raw_value in _flatten_scalars(case.case_metadata_json, prefix="case.metadata"):
        add_candidate("case_metadata", case.case_id, key_path, raw_value, key_path)

    manifest_fields = [
        ("packet.packet_id", manifest.packet_id, "Packet ID"),
        ("packet.case_id", manifest.case_id, "Packet Case ID"),
        ("packet.case_title", manifest.case_title, "Packet Case Title"),
        ("packet.case_status", manifest.case_status, "Packet Case Status"),
        ("packet.current_stage", manifest.current_stage, "Packet Current Stage"),
        ("packet.domain_pack_id", manifest.domain_pack_id, "Packet Domain Pack"),
        ("packet.case_type_id", manifest.case_type_id, "Packet Case Type"),
        ("packet.readiness_status", manifest.readiness_status, "Packet Readiness"),
        ("packet.generated_at", manifest.generated_at, "Packet Generated At"),
        ("packet.note", manifest.note, "Packet Note"),
    ]
    for source_path, raw_value, label in manifest_fields:
        add_candidate("packet_manifest", manifest.packet_id, source_path, raw_value, label)

    for section in manifest.sections:
        for key_path, raw_value in _flatten_scalars(section.data, prefix=f"packet.{section.section_type}"):
            add_candidate("packet_section", manifest.packet_id, key_path, raw_value, key_path)

    if manifest.source_mode == "reviewed_snapshot" and reviewed_snapshot is not None:
        for field in reviewed_snapshot.fields:
            if not field.included_in_snapshot or field.snapshot_value is None:
                continue
            add_candidate(
                "reviewed_snapshot",
                reviewed_snapshot.snapshot_id,
                f"extraction.{field.field_id}",
                field.snapshot_value,
                f"{field.field_id} (reviewed snapshot)",
            )
    else:
        for run in extraction_runs:
            for field_raw in run.fields_json:
                field = ExtractedFieldResult.model_validate(field_raw)
                if not field.is_present:
                    continue
                raw_value = field.value if field.value is not None else field.raw_value
                add_candidate(
                    "extraction",
                    run.extraction_id,
                    f"extraction.{field.field_id}",
                    raw_value,
                    f"{field.field_id} ({run.template_id})",
                )

    return candidates


def _flatten_scalars(value: Any, *, prefix: str) -> list[tuple[str, Any]]:
    flattened: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        if value:
            flattened.append((prefix, value))
        for key in sorted(value.keys()):
            next_prefix = f"{prefix}.{key}"
            flattened.extend(_flatten_scalars(value[key], prefix=next_prefix))
        return flattened

    if isinstance(value, list):
        if value:
            flattened.append((prefix, value))
        for index, item in enumerate(value):
            flattened.extend(_flatten_scalars(item, prefix=f"{prefix}[{index}]") )
        return flattened

    flattened.append((prefix, value))
    return flattened


def _to_preview_text(value: Any) -> str:
    if isinstance(value, str):
        text = value
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)

    if len(text) > 240:
        return text[:237] + "..."
    return text


def _stable_value_key(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return repr(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)