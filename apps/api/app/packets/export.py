"""Export artifact generation from assembled packet manifests.

Produces deterministic export artifacts (JSON manifest, markdown summary)
from a PacketManifest. Does not fabricate content or produce fake files.
"""

from __future__ import annotations

import json
from uuid import uuid4

from casegraph_agent_sdk.packets import ExportArtifact, PacketManifest, PacketSection


class GeneratedArtifact:
    """An ExportArtifact with its raw text content attached."""

    __slots__ = (
        "artifact_id", "packet_id", "format", "filename",
        "size_bytes", "content_type", "created_at", "_content_text",
    )

    def __init__(
        self,
        *,
        artifact_id: str,
        packet_id: str,
        format: str,
        filename: str,
        size_bytes: int,
        content_type: str,
        created_at: str,
        content_text: str,
    ) -> None:
        self.artifact_id = artifact_id
        self.packet_id = packet_id
        self.format = format
        self.filename = filename
        self.size_bytes = size_bytes
        self.content_type = content_type
        self.created_at = created_at
        self._content_text = content_text

    @property
    def content_text(self) -> str:
        return self._content_text

    def to_export_artifact(self) -> ExportArtifact:
        return ExportArtifact(
            artifact_id=self.artifact_id,
            packet_id=self.packet_id,
            format=self.format,
            filename=self.filename,
            size_bytes=self.size_bytes,
            content_type=self.content_type,
            created_at=self.created_at,
        )


def generate_artifacts(manifest: PacketManifest) -> list[GeneratedArtifact]:
    artifacts: list[GeneratedArtifact] = []
    artifacts.append(_generate_json_manifest(manifest))
    artifacts.append(_generate_markdown_summary(manifest))
    return artifacts


def _generate_json_manifest(manifest: PacketManifest) -> GeneratedArtifact:
    content = json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False)
    return GeneratedArtifact(
        artifact_id=str(uuid4()),
        packet_id=manifest.packet_id,
        format="json_manifest",
        filename=f"packet-{manifest.packet_id[:8]}-manifest.json",
        size_bytes=len(content.encode("utf-8")),
        content_type="application/json",
        created_at=manifest.generated_at,
        content_text=content,
    )


def _generate_markdown_summary(manifest: PacketManifest) -> GeneratedArtifact:
    lines: list[str] = []
    source_scope = (
        "explicit case state and an explicitly selected reviewed snapshot"
        if manifest.source_mode == "reviewed_snapshot"
        else "explicit case state"
    )
    lines.append(f"# Case Packet: {manifest.case_title}")
    lines.append("")
    lines.append(f"**Packet ID:** {manifest.packet_id}  ")
    lines.append(f"**Case ID:** {manifest.case_id}  ")
    lines.append(f"**Generated:** {manifest.generated_at}  ")
    if manifest.note:
        lines.append(f"**Note:** {manifest.note}  ")
    lines.append("")

    lines.append("## Overview")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Status | {manifest.case_status} |")
    lines.append(f"| Current stage | {manifest.current_stage.replace('_', ' ')} |")
    lines.append(f"| Source mode | {manifest.source_mode.replace('_', ' ')} |")
    lines.append(f"| Reviewed snapshot | {manifest.source_reviewed_snapshot_id or 'None'} |")
    lines.append(f"| Domain pack | {manifest.domain_pack_id or 'None'} |")
    lines.append(f"| Case type | {manifest.case_type_id or 'None'} |")
    lines.append(f"| Readiness | {manifest.readiness_status or 'Not evaluated'} |")
    lines.append(f"| Linked documents | {manifest.linked_document_count} |")
    lines.append(f"| Extraction runs | {manifest.extraction_count} |")
    lines.append(f"| Open actions | {manifest.open_action_count} |")
    lines.append(f"| Review notes | {manifest.review_note_count} |")
    lines.append(f"| Workflow runs | {manifest.run_count} |")
    lines.append("")

    for section in manifest.sections:
        lines.append(f"## {section.title}")
        lines.append("")
        if section.empty:
            lines.append("_No data available for this section._")
            lines.append("")
            continue
        _render_section(lines, section)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        f"_This packet was assembled from {source_scope}. "
        "It does not constitute a regulatory filing, compliance certificate, "
        "or guaranteed-complete submission package._"
    )

    content = "\n".join(lines)
    return GeneratedArtifact(
        artifact_id=str(uuid4()),
        packet_id=manifest.packet_id,
        format="markdown_summary",
        filename=f"packet-{manifest.packet_id[:8]}-summary.md",
        size_bytes=len(content.encode("utf-8")),
        content_type="text/markdown",
        created_at=manifest.generated_at,
        content_text=content,
    )


def _render_section(lines: list[str], section: PacketSection) -> None:
    st = section.section_type
    data = section.data

    if st == "case_summary":
        for key in ("case_id", "title", "category", "status", "current_stage", "summary", "created_at", "updated_at"):
            value = data.get(key)
            if value is not None:
                lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        return

    if st == "domain_metadata":
        for key in ("domain_pack_id", "case_type_id", "jurisdiction", "domain_category"):
            value = data.get(key)
            if value is not None:
                lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        return

    if st == "linked_documents":
        docs = data.get("documents", [])
        if not docs:
            lines.append("_No linked documents._")
            return
        lines.append("| Filename | Pages | Content Type | Linked At |")
        lines.append("|----------|-------|--------------|-----------|")
        for doc in docs:
            lines.append(
                f"| {doc.get('filename', '?')} "
                f"| {doc.get('page_count', 0)} "
                f"| {doc.get('content_type', '?')} "
                f"| {doc.get('linked_at', '')} |"
            )
        return

    if st == "extraction_results":
        exts = data.get("extractions", [])
        if not exts:
            lines.append("_No extraction results._")
            return
        lines.append("| Extraction ID | Status | Fields | Grounded | Strategy |")
        lines.append("|---------------|--------|--------|----------|----------|")
        for ext in exts:
            eid = ext.get("extraction_id", "?")[:12]
            lines.append(
                f"| {eid}… "
                f"| {ext.get('status', '?')} "
                f"| {ext.get('fields_extracted', 0)}/{ext.get('field_count', 0)} "
                f"| {'Yes' if ext.get('grounding_available') else 'No'} "
                f"| {ext.get('strategy_used', '?')} |"
            )
        return

    if st == "readiness_summary":
        if not data.get("checklist_available"):
            lines.append("_No checklist has been generated for this case._")
            return
        rs = data.get("readiness_status", "not_evaluated")
        lines.append(f"**Readiness status:** {rs}")
        for key in ("total_items", "supported_items", "missing_items", "partially_supported_items", "needs_review_items"):
            value = data.get(key)
            if value is not None:
                lines.append(f"- {key.replace('_', ' ').title()}: {value}")
        items = data.get("items", [])
        if items:
            lines.append("")
            lines.append("| Requirement | Priority | Status | Docs | Extractions |")
            lines.append("|-------------|----------|--------|------|-------------|")
            for item in items:
                lines.append(
                    f"| {item.get('display_name', '?')} "
                    f"| {item.get('priority', '?')} "
                    f"| {item.get('status', '?')} "
                    f"| {item.get('linked_document_count', 0)} "
                    f"| {item.get('linked_extraction_count', 0)} |"
                )
        return

    if st == "open_actions":
        actions = data.get("actions", [])
        if not actions:
            lines.append("_No open action items._")
            return
        for action in actions:
            lines.append(f"- **{action.get('title', '?')}** ({action.get('category', '?')}, {action.get('priority', 'normal')})")
            reason = action.get("source_reason", "")
            if reason:
                lines.append(f"  {reason}")
        return

    if st == "review_notes":
        notes = data.get("notes", [])
        if not notes:
            lines.append("_No review notes._")
            return
        for note in notes:
            lines.append(f"- [{note.get('decision', 'note_only')}] {note.get('body', '')}")
            lines.append(f"  Stage: {note.get('stage_snapshot', '?')} | {note.get('created_at', '')}")
        return

    if st == "run_history":
        runs = data.get("runs", [])
        if not runs:
            lines.append("_No workflow runs._")
            return
        lines.append("| Run ID | Workflow | Status | Created |")
        lines.append("|--------|----------|--------|---------|")
        for run in runs:
            rid = run.get("run_id", "?")[:12]
            lines.append(
                f"| {rid}… "
                f"| {run.get('workflow_id', '?')} "
                f"| {run.get('status', '?')} "
                f"| {run.get('created_at', '')} |"
            )
        return

    if st == "reviewed_snapshot":
        lines.append(f"- **Snapshot ID:** {data.get('snapshot_id', '')}")
        lines.append(f"- **Snapshot Status:** {data.get('status', '')}")
        lines.append(f"- **Sign-off Status:** {data.get('signoff_status', '')}")
        signed_off_by = data.get("signed_off_by")
        if signed_off_by:
            lines.append(f"- **Signed Off By:** {signed_off_by}")
        signed_off_at = data.get("signed_off_at")
        if signed_off_at:
            lines.append(f"- **Signed Off At:** {signed_off_at}")

        summary = data.get("summary", {})
        if summary:
            lines.append("")
            lines.append("| Summary | Value |")
            lines.append("|---------|-------|")
            lines.append(f"| Included fields | {summary.get('included_fields', 0)} |")
            lines.append(f"| Reviewed requirements | {summary.get('reviewed_requirements', 0)} |")
            lines.append(f"| Unresolved items | {summary.get('unresolved_item_count', 0)} |")

        fields = data.get("fields", [])
        if fields:
            lines.append("")
            lines.append("| Field | Value | Validation |")
            lines.append("|-------|-------|------------|")
            for field in fields:
                lines.append(
                    f"| {field.get('field_id', '?')} "
                    f"| {field.get('snapshot_value', '')} "
                    f"| {field.get('validation_status', '')} |"
                )

        requirements = data.get("requirements", [])
        if requirements:
            lines.append("")
            lines.append("| Requirement | Priority | Review Status |")
            lines.append("|-------------|----------|---------------|")
            for requirement in requirements:
                lines.append(
                    f"| {requirement.get('display_name', '?')} "
                    f"| {requirement.get('priority', '')} "
                    f"| {requirement.get('review_status', '')} |"
                )
        return

    lines.append(f"_{section.item_count} item(s)_")
