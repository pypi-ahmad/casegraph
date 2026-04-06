"""Domain pack registry — in-memory registry of domain packs and case type templates.

Domain packs are the first-class organizational unit for regulated/operational
domains. Each pack groups case type templates, workflow bindings, extraction
bindings, and document requirement definitions for a specific domain + jurisdiction.

This is a structured metadata layer. It does not implement regulatory logic,
payer policies, compliance engines, or automated decisions.
"""

from __future__ import annotations

from casegraph_agent_sdk.domains import (
    CaseTypeTemplateId,
    CaseTypeTemplateMetadata,
    DomainPackCapabilities,
    DomainPackDetail,
    DomainPackId,
    DomainPackListResponse,
    DomainPackMetadata,
)


class DomainPackRegistry:
    """In-memory registry of domain packs."""

    def __init__(self) -> None:
        self._packs: dict[DomainPackId, DomainPackDetail] = {}

    def register(self, pack: DomainPackDetail) -> None:
        self._packs[pack.metadata.pack_id] = pack

    def get(self, pack_id: DomainPackId) -> DomainPackDetail | None:
        return self._packs.get(pack_id)

    def list_packs(self) -> list[DomainPackDetail]:
        return list(self._packs.values())

    def list_metadata(self) -> DomainPackListResponse:
        return DomainPackListResponse(
            packs=[p.metadata for p in self._packs.values()]
        )

    def get_case_type(
        self, case_type_id: CaseTypeTemplateId
    ) -> tuple[CaseTypeTemplateMetadata, DomainPackMetadata] | None:
        """Look up a case type by ID across all packs."""
        for pack in self._packs.values():
            for ct in pack.case_types:
                if ct.case_type_id == case_type_id:
                    return ct, pack.metadata
        return None

    def list_case_types_for_pack(
        self, pack_id: DomainPackId
    ) -> list[CaseTypeTemplateMetadata]:
        pack = self._packs.get(pack_id)
        if pack is None:
            return []
        return list(pack.case_types)


def _build_capabilities(case_types: list[CaseTypeTemplateMetadata]) -> DomainPackCapabilities:
    """Derive capabilities from case type definitions."""
    has_workflows = any(len(ct.workflow_bindings) > 0 for ct in case_types)
    has_extractions = any(len(ct.extraction_bindings) > 0 for ct in case_types)
    has_requirements = any(len(ct.document_requirements) > 0 for ct in case_types)

    limitations = [
        "Domain packs provide operational metadata only — not regulatory logic, compliance engines, or automated decisions.",
        "Workflow and extraction bindings reference existing generic templates. Domain-specific templates are not implemented yet.",
        "Document requirements are structured metadata checklists. They do not enforce filing rules or payer policies.",
    ]

    return DomainPackCapabilities(
        has_case_types=len(case_types) > 0,
        has_workflow_bindings=has_workflows,
        has_extraction_bindings=has_extractions,
        has_document_requirements=has_requirements,
        limitations=limitations,
    )
