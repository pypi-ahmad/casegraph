"""Helpers for reading and writing target-pack selection metadata."""

from __future__ import annotations

from typing import Any

from casegraph_agent_sdk.submissions import SubmissionMappingTargetField
from casegraph_agent_sdk.target_packs import (
    CaseTargetPackSelection,
    TargetPackDetail,
)


TARGET_PACK_SELECTION_METADATA_KEY = "target_pack_selection"


def get_case_target_pack_selection(metadata: dict[str, Any]) -> CaseTargetPackSelection | None:
    raw = metadata.get(TARGET_PACK_SELECTION_METADATA_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        return CaseTargetPackSelection.model_validate(raw)
    except Exception:
        return None


def set_case_target_pack_selection(
    metadata: dict[str, Any],
    selection: CaseTargetPackSelection | None,
) -> dict[str, Any]:
    next_metadata = dict(metadata)
    if selection is None:
        next_metadata.pop(TARGET_PACK_SELECTION_METADATA_KEY, None)
        return next_metadata
    next_metadata[TARGET_PACK_SELECTION_METADATA_KEY] = selection.model_dump(mode="json")
    return next_metadata


def build_case_target_pack_selection(
    pack: TargetPackDetail,
    *,
    selected_at: str,
) -> CaseTargetPackSelection:
    return CaseTargetPackSelection(
        pack_id=pack.metadata.pack_id,
        version=pack.metadata.version,
        display_name=pack.metadata.display_name,
        category=pack.metadata.category,
        selected_at=selected_at,
    )


def build_submission_target_fields(pack: TargetPackDetail) -> list[SubmissionMappingTargetField]:
    fields: list[SubmissionMappingTargetField] = []
    for section in pack.field_schema.sections:
        for field in section.fields:
            fields.append(
                SubmissionMappingTargetField(
                    field_name=field.field_id,
                    target_section=section.section_id,
                    display_label=field.display_name,
                    field_type=field.field_type,
                    required=field.required,
                    candidate_source_paths=list(field.candidate_source_paths),
                    notes=list(field.notes),
                )
            )
    return fields


def merge_submission_target_fields(
    base_fields: list[SubmissionMappingTargetField],
    overlay_fields: list[SubmissionMappingTargetField],
) -> list[SubmissionMappingTargetField]:
    merged: list[SubmissionMappingTargetField] = []
    seen: set[tuple[str, str]] = set()
    for field in [*base_fields, *overlay_fields]:
        key = (field.field_name, field.target_section)
        if key in seen:
            continue
        seen.add(key)
        merged.append(field)
    return merged