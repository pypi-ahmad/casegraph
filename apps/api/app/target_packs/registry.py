"""In-memory registry of versioned target-pack metadata."""

from __future__ import annotations

from casegraph_agent_sdk.target_packs import (
    CaseTargetPackSelection,
    TargetPackDetail,
    TargetPackListFilters,
    TargetPackListResponse,
    TargetPackSummary,
)


class TargetPackRegistry:
    def __init__(self) -> None:
        self._packs: dict[str, TargetPackDetail] = {}

    def register(self, pack: TargetPackDetail) -> None:
        if pack.metadata.pack_id in self._packs:
            raise ValueError(
                f"Target pack '{pack.metadata.pack_id}' is already registered."
            )
        self._packs[pack.metadata.pack_id] = pack

    def get(self, pack_id: str) -> TargetPackDetail | None:
        return self._packs.get(pack_id)

    def resolve_selection(
        self,
        selection: CaseTargetPackSelection | None,
    ) -> TargetPackDetail | None:
        if selection is None:
            return None
        pack = self._packs.get(selection.pack_id)
        if pack is None:
            return None
        if pack.metadata.version != selection.version:
            return None
        return pack

    def list_packs(self, filters: TargetPackListFilters | None = None) -> list[TargetPackDetail]:
        filters = filters or TargetPackListFilters()
        packs = list(self._packs.values())
        if filters.category:
            packs = [pack for pack in packs if pack.metadata.category == filters.category]
        if filters.status:
            packs = [pack for pack in packs if pack.metadata.status == filters.status]
        if filters.domain_pack_id:
            packs = [
                pack
                for pack in packs
                if filters.domain_pack_id in pack.compatibility.compatible_domain_pack_ids
            ]
        if filters.case_type_id:
            packs = [
                pack
                for pack in packs
                if filters.case_type_id in pack.compatibility.compatible_case_type_ids
            ]
        packs.sort(key=lambda pack: (pack.metadata.category, pack.metadata.display_name, pack.metadata.version))
        return packs

    def list_summaries(self, filters: TargetPackListFilters | None = None) -> TargetPackListResponse:
        filters = filters or TargetPackListFilters()
        return TargetPackListResponse(
            filters=filters,
            packs=[self._to_summary(pack) for pack in self.list_packs(filters)],
        )

    @staticmethod
    def _to_summary(pack: TargetPackDetail) -> TargetPackSummary:
        return TargetPackSummary(
            metadata=pack.metadata,
            compatibility=pack.compatibility,
            field_section_count=len(pack.field_schema.sections),
            field_count=sum(len(section.fields) for section in pack.field_schema.sections),
            requirement_override_count=len(pack.requirement_overrides),
            template_binding_count=len(pack.template_bindings),
            submission_target_count=len(pack.submission_compatibility.submission_target_ids),
        )