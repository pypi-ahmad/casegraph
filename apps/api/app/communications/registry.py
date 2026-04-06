"""Static registry of reviewable communication draft templates."""

from __future__ import annotations

from dataclasses import dataclass

from casegraph_agent_sdk.communications import (
    CommunicationTemplateInputRequirement,
    CommunicationTemplateListResponse,
    CommunicationTemplateMetadata,
)


@dataclass(frozen=True)
class CommunicationTemplateDefinition:
    metadata: CommunicationTemplateMetadata


class CommunicationTemplateRegistry:
    def __init__(self) -> None:
        self._definitions = {
            definition.metadata.template_id: definition
            for definition in self._build_definitions()
        }

    def list_metadata(self) -> CommunicationTemplateListResponse:
        return CommunicationTemplateListResponse(
            templates=[
                definition.metadata
                for definition in self._definitions.values()
            ]
        )

    def get(self, template_id: str) -> CommunicationTemplateDefinition | None:
        return self._definitions.get(template_id)

    @staticmethod
    def _build_definitions() -> list[CommunicationTemplateDefinition]:
        return [
            CommunicationTemplateDefinition(
                metadata=CommunicationTemplateMetadata(
                    template_id="missing_document_request",
                    draft_type="missing_document_request",
                    display_name="Missing Document Request",
                    audience_type="external_party",
                    description=(
                        "Drafts a grounded request for currently unresolved required checklist items."
                    ),
                    required_source_inputs=[
                        CommunicationTemplateInputRequirement(
                            input_id="case",
                            display_name="Case",
                            description="Current persisted case title, status, and domain metadata.",
                            required=True,
                        ),
                        CommunicationTemplateInputRequirement(
                            input_id="readiness",
                            display_name="Readiness",
                            description="Current checklist and readiness summary for the case.",
                            required=True,
                        ),
                        CommunicationTemplateInputRequirement(
                            input_id="checklist_missing_items",
                            display_name="Missing Required Items",
                            description="Explicit required checklist items still marked missing or unresolved.",
                            required=True,
                        ),
                    ],
                    provider_assisted_available=True,
                    uses_deterministic_sections=True,
                    notes=[
                        "Does not populate recipient identity, channel, or contact information.",
                        "Human review is always required before use.",
                    ],
                )
            ),
            CommunicationTemplateDefinition(
                metadata=CommunicationTemplateMetadata(
                    template_id="internal_handoff_note",
                    draft_type="internal_handoff_note",
                    display_name="Internal Handoff Note",
                    audience_type="internal_operator",
                    description=(
                        "Summarizes case state, follow-up items, and recent review context for operator handoff."
                    ),
                    required_source_inputs=[
                        CommunicationTemplateInputRequirement(
                            input_id="case",
                            display_name="Case",
                            description="Current persisted case summary and stage.",
                            required=True,
                        ),
                        CommunicationTemplateInputRequirement(
                            input_id="open_actions",
                            display_name="Open Actions",
                            description="Persisted follow-up items currently open for the case.",
                            required=False,
                        ),
                        CommunicationTemplateInputRequirement(
                            input_id="workflow_pack_run",
                            display_name="Workflow Pack Run",
                            description="Optional latest workflow-pack recommendation and stage results.",
                            required=False,
                        ),
                    ],
                    provider_assisted_available=True,
                    uses_deterministic_sections=True,
                    notes=[
                        "Summaries are grounded in persisted actions, review notes, and readiness state.",
                        "No routing, escalation, or messaging handoff is performed automatically.",
                    ],
                )
            ),
            CommunicationTemplateDefinition(
                metadata=CommunicationTemplateMetadata(
                    template_id="packet_cover_note",
                    draft_type="packet_cover_note",
                    display_name="Packet Cover Note",
                    audience_type="packet_consumer",
                    description=(
                        "Summarizes the latest generated packet using its stored manifest and linked case state."
                    ),
                    required_source_inputs=[
                        CommunicationTemplateInputRequirement(
                            input_id="case",
                            display_name="Case",
                            description="Current persisted case summary and status.",
                            required=True,
                        ),
                        CommunicationTemplateInputRequirement(
                            input_id="packet",
                            display_name="Packet",
                            description="A real generated packet manifest for the case.",
                            required=True,
                        ),
                    ],
                    provider_assisted_available=True,
                    uses_deterministic_sections=True,
                    notes=[
                        "Requires a real packet record; does not generate a packet on demand.",
                        "Human review is required before copying or exporting the note.",
                    ],
                )
            ),
        ]


_registry = CommunicationTemplateRegistry()


def get_communication_template_registry() -> CommunicationTemplateRegistry:
    return _registry