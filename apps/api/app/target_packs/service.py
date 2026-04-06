"""Service layer for target-pack registry lookup and case selection."""

from __future__ import annotations

from casegraph_agent_sdk.audit import ChangeSummary, FieldChangeRecord
from casegraph_agent_sdk.target_packs import (
    CaseTargetPackResponse,
    CaseTargetPackUpdateResponse,
    TargetPackCompatibilityResponse,
    TargetPackDetailResponse,
    TargetPackFieldSchemaResponse,
    TargetPackListFilters,
    TargetPackListResponse,
    TargetPackOperationResult,
    TargetPackRequirementsResponse,
    UpdateCaseTargetPackRequest,
)

from app.audit.service import AuditTrailService, audit_actor, entity_ref
from app.cases.models import CaseRecordModel
from app.persistence.database import utcnow
from app.target_packs.context import (
    build_case_target_pack_selection,
    get_case_target_pack_selection,
    set_case_target_pack_selection,
)
from app.target_packs.packs import target_pack_registry


class TargetPackServiceError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class TargetPackService:
    def __init__(self, session) -> None:
        self._session = session

    def list_packs(self, filters: TargetPackListFilters) -> TargetPackListResponse:
        return target_pack_registry.list_summaries(filters)

    def get_pack(self, pack_id: str) -> TargetPackDetailResponse:
        pack = self._require_pack(pack_id)
        return TargetPackDetailResponse(pack=pack)

    def get_compatibility(self, pack_id: str) -> TargetPackCompatibilityResponse:
        pack = self._require_pack(pack_id)
        return TargetPackCompatibilityResponse(
            pack_id=pack.metadata.pack_id,
            compatibility=pack.compatibility,
        )

    def get_field_schema(self, pack_id: str) -> TargetPackFieldSchemaResponse:
        pack = self._require_pack(pack_id)
        return TargetPackFieldSchemaResponse(
            pack_id=pack.metadata.pack_id,
            field_schema=pack.field_schema,
        )

    def get_requirements(self, pack_id: str) -> TargetPackRequirementsResponse:
        pack = self._require_pack(pack_id)
        return TargetPackRequirementsResponse(
            pack_id=pack.metadata.pack_id,
            requirement_overrides=pack.requirement_overrides,
        )

    def get_case_target_pack(self, case_id: str) -> CaseTargetPackResponse:
        case = self._require_case(case_id)
        return CaseTargetPackResponse(
            case_id=case.case_id,
            selection=get_case_target_pack_selection(case.case_metadata_json),
        )

    def update_case_target_pack(
        self,
        case_id: str,
        request: UpdateCaseTargetPackRequest,
    ) -> CaseTargetPackUpdateResponse:
        case = self._require_case(case_id)
        current = get_case_target_pack_selection(case.case_metadata_json)

        if request.clear_selection and request.pack_id:
            raise TargetPackServiceError(
                "Provide either pack_id or clear_selection, not both.",
                status_code=400,
            )
        if not request.clear_selection and not (request.pack_id or "").strip():
            raise TargetPackServiceError(
                "pack_id is required unless clear_selection is true.",
                status_code=400,
            )

        if request.clear_selection:
            if current is None:
                return CaseTargetPackUpdateResponse(
                    result=TargetPackOperationResult(success=True, message="Case target pack already clear."),
                    case_id=case.case_id,
                    selection=None,
                )
            next_selection = None
        else:
            pack = self._require_pack((request.pack_id or "").strip())
            self._require_case_compatibility(case, pack)
            selected_at = utcnow().isoformat().replace("+00:00", "Z")
            next_selection = build_case_target_pack_selection(pack, selected_at=selected_at)
            if current is not None and current.pack_id == next_selection.pack_id and current.version == next_selection.version:
                return CaseTargetPackUpdateResponse(
                    result=TargetPackOperationResult(success=True, message="Case target pack unchanged."),
                    case_id=case.case_id,
                    selection=current,
                )

        previous_value = current.model_dump(mode="json") if current else None
        next_value = next_selection.model_dump(mode="json") if next_selection else None

        case.case_metadata_json = set_case_target_pack_selection(case.case_metadata_json, next_selection)
        case.updated_at = utcnow()
        self._session.add(case)

        AuditTrailService(self._session).append_event(
            case_id=case.case_id,
            category="case",
            event_type="case_updated",
            actor=audit_actor("service", actor_id="target_packs.service", display_name="Target Pack Service"),
            entity=entity_ref("case", case.case_id, case_id=case.case_id, display_label=case.title),
            change_summary=ChangeSummary(
                message="Case target-pack selection updated.",
                field_changes=[
                    FieldChangeRecord(
                        field_path="target_pack_selection",
                        old_value=previous_value,
                        new_value=next_value,
                    )
                ],
            ),
        )

        self._session.commit()
        return CaseTargetPackUpdateResponse(
            result=TargetPackOperationResult(success=True, message="Case target pack updated."),
            case_id=case.case_id,
            selection=next_selection,
        )

    def _require_pack(self, pack_id: str):
        pack = target_pack_registry.get(pack_id)
        if pack is None:
            raise TargetPackServiceError(f"Target pack '{pack_id}' not found.", status_code=404)
        return pack

    def _require_case(self, case_id: str) -> CaseRecordModel:
        case = self._session.get(CaseRecordModel, case_id)
        if case is None:
            raise TargetPackServiceError(f"Case '{case_id}' not found.", status_code=404)
        return case

    def _require_case_compatibility(self, case: CaseRecordModel, pack) -> None:
        if pack.compatibility.compatible_domain_pack_ids:
            if not case.domain_pack_id:
                raise TargetPackServiceError(
                    "Case must have domain pack context before a target pack can be selected.",
                    status_code=400,
                )
            if case.domain_pack_id not in pack.compatibility.compatible_domain_pack_ids:
                raise TargetPackServiceError(
                    "Selected target pack is not compatible with this case's domain pack.",
                    status_code=400,
                )
        if pack.compatibility.compatible_case_type_ids:
            if not case.case_type_id:
                raise TargetPackServiceError(
                    "Case must have case-type context before a target pack can be selected.",
                    status_code=400,
                )
            if case.case_type_id not in pack.compatibility.compatible_case_type_ids:
                raise TargetPackServiceError(
                    "Selected target pack is not compatible with this case's case type.",
                    status_code=400,
                )