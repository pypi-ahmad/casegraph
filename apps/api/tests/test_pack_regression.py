"""Regression gates for the three core domain areas.

These tests pin the exact pack inventories, case-type IDs, requirement
contracts, workflow-pack bindings, and stage sequences so that any
structural drift (renamed IDs, dropped requirements, added packs) causes
a clear, deliberate failure.

If you need to change a pack, update the snapshot constant here first.
If you want to add a new pack, increase the count constant first.

Domains gated:
  1. Medical Insurance  (medical_insurance_us, medical_insurance_india)
  2. General Insurance   (insurance_us, insurance_india)
  3. Taxation            (tax_us, tax_india)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from casegraph_agent_sdk.readiness import ChecklistResponse

from app.domains.packs import build_default_domain_pack_registry, domain_pack_registry
from app.workflow_packs.registry import (
    build_default_workflow_pack_registry,
    get_workflow_pack_registry,
)


# ═══════════════════════════════════════════════════════════════════════════
# Freeze constants — update these intentionally when packs change
# ═══════════════════════════════════════════════════════════════════════════

EXPECTED_DOMAIN_PACK_COUNT = 8
EXPECTED_WORKFLOW_PACK_COUNT = 10

EXPECTED_DOMAIN_PACK_IDS = frozenset({
    "medical_us",
    "medical_india",
    "medical_insurance_us",
    "medical_insurance_india",
    "insurance_us",
    "insurance_india",
    "tax_us",
    "tax_india",
})

EXPECTED_WORKFLOW_PACK_IDS = frozenset({
    "prior_auth_packet_review",
    "pre_claim_packet_review",
    "insurance_claim_intake_review",
    "insurance_claim_intake_review_india",
    "coverage_correspondence_review",
    "coverage_correspondence_review_india",
    "tax_intake_packet_review",
    "tax_intake_packet_review_india",
    "tax_notice_review",
    "tax_notice_review_india",
})

EXPECTED_STAGE_IDS = [
    "intake_document_check",
    "extraction_pass",
    "checklist_refresh",
    "readiness_evaluation",
    "action_generation",
    "packet_assembly",
    "submission_draft_preparation",
]


# ═══════════════════════════════════════════════════════════════════════════
# Per-case-type requirement snapshots
#
# Format: case_type_id → [(requirement_id, priority)]
# Order matters — it's the declared order in the pack definition.
# ═══════════════════════════════════════════════════════════════════════════

REQUIREMENT_SNAPSHOTS: dict[str, list[tuple[str, str]]] = {
    # ── Medical Insurance US ──────────────────────────────────────────
    "medical_insurance_us:prior_auth_review": [
        ("identity", "required"),
        ("clinical_notes", "required"),
        ("referral_order", "required"),
        ("insurer_correspondence", "recommended"),
        ("supporting_attachment", "optional"),
    ],
    "medical_insurance_us:claim_intake": [
        ("identity", "required"),
        ("claim_form", "required"),
        ("invoice_bill", "required"),
        ("clinical_notes", "recommended"),
        ("supporting_attachment", "optional"),
    ],
    # ── Medical Insurance India ───────────────────────────────────────
    "medical_insurance_india:pre_claim_review": [
        ("identity", "required"),
        ("clinical_notes", "required"),
        ("insurer_correspondence", "recommended"),
        ("supporting_attachment", "optional"),
    ],
    "medical_insurance_india:claim_intake": [
        ("identity", "required"),
        ("claim_form", "required"),
        ("invoice_bill", "required"),
        ("diagnostic_reports", "recommended"),
        ("supporting_attachment", "optional"),
    ],
    # ── Insurance US ──────────────────────────────────────────────────
    "insurance_us:policy_review": [
        ("identity", "required"),
        ("policy_document", "required"),
        ("insurer_correspondence", "recommended"),
        ("supporting_attachment", "optional"),
    ],
    "insurance_us:coverage_review": [
        ("identity", "required"),
        ("policy_document", "required"),
        ("proof_of_loss", "required"),
        ("insurer_correspondence", "recommended"),
        ("supporting_attachment", "optional"),
    ],
    # ── Insurance India ───────────────────────────────────────────────
    "insurance_india:policy_review": [
        ("identity", "required"),
        ("policy_document", "required"),
        ("insurer_correspondence", "recommended"),
        ("supporting_attachment", "optional"),
    ],
    "insurance_india:coverage_review": [
        ("identity", "required"),
        ("policy_document", "required"),
        ("proof_of_loss", "required"),
        ("insurer_correspondence", "recommended"),
        ("supporting_attachment", "optional"),
    ],
    # ── Tax US ────────────────────────────────────────────────────────
    "tax_us:intake_review": [
        ("identity", "required"),
        ("income_document", "required"),
        ("government_form", "recommended"),
        ("supporting_attachment", "optional"),
    ],
    "tax_us:notice_review": [
        ("identity", "required"),
        ("tax_notice", "required"),
        ("supporting_attachment", "optional"),
    ],
    # ── Tax India ─────────────────────────────────────────────────────
    "tax_india:intake_review": [
        ("identity", "required"),
        ("income_document", "required"),
        ("government_form", "recommended"),
        ("supporting_attachment", "optional"),
    ],
    "tax_india:notice_review": [
        ("identity", "required"),
        ("tax_notice", "required"),
        ("supporting_attachment", "optional"),
    ],
}

# Workflow pack → domain_pack_id mapping
WORKFLOW_DOMAIN_BINDINGS: dict[str, str] = {
    "prior_auth_packet_review": "medical_insurance_us",
    "pre_claim_packet_review": "medical_insurance_india",
    "insurance_claim_intake_review": "insurance_us",
    "insurance_claim_intake_review_india": "insurance_india",
    "coverage_correspondence_review": "insurance_us",
    "coverage_correspondence_review_india": "insurance_india",
    "tax_intake_packet_review": "tax_us",
    "tax_intake_packet_review_india": "tax_india",
    "tax_notice_review": "tax_us",
    "tax_notice_review_india": "tax_india",
}

# Workflow pack → compatible case type IDs
WORKFLOW_CASE_TYPE_COMPAT: dict[str, frozenset[str]] = {
    "prior_auth_packet_review": frozenset({
        "medical_insurance_us:prior_auth_review",
        "medical_insurance_us:claim_intake",
    }),
    "pre_claim_packet_review": frozenset({
        "medical_insurance_india:pre_claim_review",
        "medical_insurance_india:claim_intake",
    }),
    "insurance_claim_intake_review": frozenset({
        "insurance_us:policy_review",
        "insurance_us:coverage_review",
    }),
    "insurance_claim_intake_review_india": frozenset({
        "insurance_india:policy_review",
        "insurance_india:coverage_review",
    }),
    "coverage_correspondence_review": frozenset({
        "insurance_us:coverage_review",
    }),
    "coverage_correspondence_review_india": frozenset({
        "insurance_india:coverage_review",
    }),
    "tax_intake_packet_review": frozenset({
        "tax_us:intake_review",
    }),
    "tax_intake_packet_review_india": frozenset({
        "tax_india:intake_review",
    }),
    "tax_notice_review": frozenset({
        "tax_us:notice_review",
    }),
    "tax_notice_review_india": frozenset({
        "tax_india:notice_review",
    }),
}


# ═══════════════════════════════════════════════════════════════════════════
# Freeze guards — fail loudly if pack inventory changes
# ═══════════════════════════════════════════════════════════════════════════


class TestPackInventoryFreeze:
    """Prevents adding / removing packs without updating snapshot constants."""

    def test_domain_pack_count_frozen(self) -> None:
        packs = domain_pack_registry.list_packs()
        assert len(packs) == EXPECTED_DOMAIN_PACK_COUNT, (
            f"Domain pack count changed: {len(packs)} != {EXPECTED_DOMAIN_PACK_COUNT}. "
            "Update EXPECTED_DOMAIN_PACK_COUNT if this is intentional."
        )

    def test_domain_pack_ids_frozen(self) -> None:
        actual = frozenset(p.metadata.pack_id for p in domain_pack_registry.list_packs())
        assert actual == EXPECTED_DOMAIN_PACK_IDS, (
            f"Domain pack IDs changed.\n"
            f"  Added:   {actual - EXPECTED_DOMAIN_PACK_IDS}\n"
            f"  Removed: {EXPECTED_DOMAIN_PACK_IDS - actual}\n"
            "Update EXPECTED_DOMAIN_PACK_IDS if this is intentional."
        )

    def test_workflow_pack_count_frozen(self) -> None:
        registry = get_workflow_pack_registry()
        packs = registry.list_packs()
        assert len(packs) == EXPECTED_WORKFLOW_PACK_COUNT, (
            f"Workflow pack count changed: {len(packs)} != {EXPECTED_WORKFLOW_PACK_COUNT}. "
            "Update EXPECTED_WORKFLOW_PACK_COUNT if this is intentional."
        )

    def test_workflow_pack_ids_frozen(self) -> None:
        registry = get_workflow_pack_registry()
        actual = frozenset(p.metadata.workflow_pack_id for p in registry.list_packs())
        assert actual == EXPECTED_WORKFLOW_PACK_IDS, (
            f"Workflow pack IDs changed.\n"
            f"  Added:   {actual - EXPECTED_WORKFLOW_PACK_IDS}\n"
            f"  Removed: {EXPECTED_WORKFLOW_PACK_IDS - actual}\n"
            "Update EXPECTED_WORKFLOW_PACK_IDS if this is intentional."
        )

    def test_case_type_count_frozen(self) -> None:
        actual_ct_ids: set[str] = set()
        for pack in domain_pack_registry.list_packs():
            for ct in pack.case_types:
                actual_ct_ids.add(ct.case_type_id)
        expected = set(REQUIREMENT_SNAPSHOTS.keys())
        # Also include the medical packs (not in gated domains but still counted)
        medical_ids = {
            "medical_us:record_review",
            "medical_us:referral_review",
            "medical_india:record_review",
            "medical_india:referral_review",
        }
        assert actual_ct_ids == expected | medical_ids, (
            f"Case type IDs changed.\n"
            f"  Added:   {actual_ct_ids - (expected | medical_ids)}\n"
            f"  Removed: {(expected | medical_ids) - actual_ct_ids}\n"
            "Update REQUIREMENT_SNAPSHOTS if this is intentional."
        )


# ═══════════════════════════════════════════════════════════════════════════
# Requirement contract snapshots — per case type
# ═══════════════════════════════════════════════════════════════════════════


class TestRequirementContracts:
    """Pin the exact (requirement_id, priority) tuples for every gated case type."""

    @pytest.mark.parametrize(
        "case_type_id",
        sorted(REQUIREMENT_SNAPSHOTS.keys()),
        ids=lambda ct: ct.replace(":", "_"),
    )
    def test_requirement_snapshot(self, case_type_id: str) -> None:
        result = domain_pack_registry.get_case_type(case_type_id)
        assert result is not None, f"Case type {case_type_id} not found in registry"
        case_type, _pack_meta = result

        actual = [
            (r.requirement_id, r.priority)
            for r in case_type.document_requirements
        ]
        expected = REQUIREMENT_SNAPSHOTS[case_type_id]
        assert actual == expected, (
            f"Requirement contract for {case_type_id} changed.\n"
            f"  Expected: {expected}\n"
            f"  Actual:   {actual}\n"
            "Update REQUIREMENT_SNAPSHOTS if this is intentional."
        )

    @pytest.mark.parametrize(
        "case_type_id",
        sorted(REQUIREMENT_SNAPSHOTS.keys()),
        ids=lambda ct: ct.replace(":", "_"),
    )
    def test_every_requirement_has_category(self, case_type_id: str) -> None:
        result = domain_pack_registry.get_case_type(case_type_id)
        assert result is not None
        case_type, _ = result
        for req in case_type.document_requirements:
            assert req.document_category, (
                f"{case_type_id}:{req.requirement_id} has no document_category"
            )

    def test_required_items_per_case_type_minimum(self) -> None:
        """Every case type must have at least 1 required document requirement."""
        for case_type_id, reqs in REQUIREMENT_SNAPSHOTS.items():
            required_count = sum(1 for _, p in reqs if p == "required")
            assert required_count >= 1, (
                f"{case_type_id} has no required document requirements"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Workflow pack contract snapshots
# ═══════════════════════════════════════════════════════════════════════════


class TestWorkflowPackContracts:
    """Pin workflow stage sequences, domain bindings, and compatibility."""

    def test_all_packs_use_standard_stage_sequence(self) -> None:
        registry = get_workflow_pack_registry()
        for pack in registry.list_packs():
            actual_ids = [s.stage_id for s in pack.stages]
            assert actual_ids == EXPECTED_STAGE_IDS, (
                f"Workflow pack {pack.metadata.workflow_pack_id} stage sequence changed.\n"
                f"  Expected: {EXPECTED_STAGE_IDS}\n"
                f"  Actual:   {actual_ids}"
            )

    def test_stage_count_matches_metadata(self) -> None:
        registry = get_workflow_pack_registry()
        for pack in registry.list_packs():
            assert pack.metadata.stage_count == len(pack.stages), (
                f"{pack.metadata.workflow_pack_id}: metadata.stage_count "
                f"({pack.metadata.stage_count}) != len(stages) ({len(pack.stages)})"
            )

    @pytest.mark.parametrize(
        "pack_id",
        sorted(WORKFLOW_DOMAIN_BINDINGS.keys()),
    )
    def test_domain_binding(self, pack_id: str) -> None:
        registry = get_workflow_pack_registry()
        pack = registry.get(pack_id)
        assert pack is not None
        assert pack.metadata.domain_pack_id == WORKFLOW_DOMAIN_BINDINGS[pack_id], (
            f"{pack_id} domain binding changed: "
            f"{pack.metadata.domain_pack_id} != {WORKFLOW_DOMAIN_BINDINGS[pack_id]}"
        )

    @pytest.mark.parametrize(
        "pack_id",
        sorted(WORKFLOW_CASE_TYPE_COMPAT.keys()),
    )
    def test_case_type_compatibility(self, pack_id: str) -> None:
        registry = get_workflow_pack_registry()
        pack = registry.get(pack_id)
        assert pack is not None
        actual = frozenset(pack.metadata.compatible_case_type_ids)
        expected = WORKFLOW_CASE_TYPE_COMPAT[pack_id]
        assert actual == expected, (
            f"{pack_id} compatible case types changed.\n"
            f"  Added:   {actual - expected}\n"
            f"  Removed: {expected - actual}"
        )

    def test_optional_stages_are_last_two(self) -> None:
        """packet_assembly and submission_draft_preparation must stay optional."""
        registry = get_workflow_pack_registry()
        for pack in registry.list_packs():
            optional_ids = [s.stage_id for s in pack.stages if s.optional]
            assert optional_ids == ["packet_assembly", "submission_draft_preparation"], (
                f"{pack.metadata.workflow_pack_id} optional stage contract broken: {optional_ids}"
            )

    def test_stage_dependency_chain_intact(self) -> None:
        """Each stage depends on the previous stage (linear pipeline)."""
        registry = get_workflow_pack_registry()
        for pack in registry.list_packs():
            stages = pack.stages
            # First stage has no dependencies
            assert stages[0].depends_on is None or stages[0].depends_on == [], (
                f"{pack.metadata.workflow_pack_id}: first stage has unexpected deps"
            )
            # Subsequent stages depend on their predecessor
            for i in range(1, len(stages)):
                deps = stages[i].depends_on or []
                assert stages[i - 1].stage_id in deps, (
                    f"{pack.metadata.workflow_pack_id}: stage {stages[i].stage_id} "
                    f"does not depend on {stages[i - 1].stage_id}"
                )

    def test_every_workflow_pack_has_limitations(self) -> None:
        registry = get_workflow_pack_registry()
        for pack in registry.list_packs():
            assert len(pack.metadata.limitations) >= 5, (
                f"{pack.metadata.workflow_pack_id} has too few limitations: "
                f"{len(pack.metadata.limitations)}"
            )

    def test_workflow_domain_packs_exist_in_domain_registry(self) -> None:
        """Every workflow pack's domain_pack_id must resolve in the domain registry."""
        registry = get_workflow_pack_registry()
        for pack in registry.list_packs():
            domain_pack = domain_pack_registry.get(pack.metadata.domain_pack_id)
            assert domain_pack is not None, (
                f"Workflow pack {pack.metadata.workflow_pack_id} references "
                f"nonexistent domain pack: {pack.metadata.domain_pack_id}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Cross-layer: checklist items match pack requirements exactly
# ═══════════════════════════════════════════════════════════════════════════


class TestChecklistRequirementAlignment:
    """Verify checklist generation produces items 1:1 with pack requirements."""

    @pytest.mark.parametrize(
        "case_type_id,domain_pack_id",
        [
            ("medical_insurance_us:prior_auth_review", "medical_insurance_us"),
            ("medical_insurance_us:claim_intake", "medical_insurance_us"),
            ("insurance_us:policy_review", "insurance_us"),
            ("insurance_us:coverage_review", "insurance_us"),
            ("tax_us:intake_review", "tax_us"),
            ("tax_us:notice_review", "tax_us"),
        ],
        ids=lambda x: x.split(":")[-1] if ":" in x else x,
    )
    def test_checklist_items_match_requirements(
        self,
        client: TestClient,
        case_type_id: str,
        domain_pack_id: str,
    ) -> None:
        """Create a case, generate checklist, verify items match pack requirements exactly."""
        # Create case
        case_resp = client.post(
            "/cases",
            json={
                "title": f"Regression — {case_type_id}",
                "category": "test",
                "domain_pack_id": domain_pack_id,
                "case_type_id": case_type_id,
            },
        )
        assert case_resp.status_code == 200
        case_id = case_resp.json()["case_id"]

        # Generate checklist
        gen_resp = client.post(f"/cases/{case_id}/checklist/generate")
        assert gen_resp.status_code == 200

        # Fetch checklist
        cl_resp = client.get(f"/cases/{case_id}/checklist")
        assert cl_resp.status_code == 200
        checklist = ChecklistResponse.model_validate(cl_resp.json())
        assert checklist.checklist is not None

        # Compare requirement IDs
        actual_req_ids = [item.requirement_id for item in checklist.checklist.items]
        expected_req_ids = [rid for rid, _ in REQUIREMENT_SNAPSHOTS[case_type_id]]

        assert actual_req_ids == expected_req_ids, (
            f"Checklist for {case_type_id} does not match pack requirements.\n"
            f"  Expected requirement_ids: {expected_req_ids}\n"
            f"  Actual requirement_ids:   {actual_req_ids}"
        )

    @pytest.mark.parametrize(
        "case_type_id,domain_pack_id",
        [
            ("medical_insurance_india:pre_claim_review", "medical_insurance_india"),
            ("insurance_india:coverage_review", "insurance_india"),
            ("tax_india:notice_review", "tax_india"),
        ],
        ids=lambda x: x.split(":")[-1] if ":" in x else x,
    )
    def test_india_variant_checklist_matches(
        self,
        client: TestClient,
        case_type_id: str,
        domain_pack_id: str,
    ) -> None:
        """India pack variants also produce checklists aligned with their requirements."""
        case_resp = client.post(
            "/cases",
            json={
                "title": f"Regression — {case_type_id}",
                "category": "test",
                "domain_pack_id": domain_pack_id,
                "case_type_id": case_type_id,
            },
        )
        assert case_resp.status_code == 200
        case_id = case_resp.json()["case_id"]

        client.post(f"/cases/{case_id}/checklist/generate")
        cl_resp = client.get(f"/cases/{case_id}/checklist")
        assert cl_resp.status_code == 200
        checklist = ChecklistResponse.model_validate(cl_resp.json())
        assert checklist.checklist is not None

        actual_req_ids = [item.requirement_id for item in checklist.checklist.items]
        expected_req_ids = [rid for rid, _ in REQUIREMENT_SNAPSHOTS[case_type_id]]
        assert actual_req_ids == expected_req_ids


# ═══════════════════════════════════════════════════════════════════════════
# Cross-layer: readiness → packet → draft data threading per domain
# ═══════════════════════════════════════════════════════════════════════════


class TestDomainDataThreading:
    """Verify readiness status threads through packet and draft for each domain."""

    def _run_domain_flow(
        self, client: TestClient, domain_pack_id: str, case_type_id: str
    ) -> dict:
        """Run full lifecycle and return key data points."""
        # Create case
        case_resp = client.post(
            "/cases",
            json={
                "title": f"Threading — {case_type_id}",
                "category": "test",
                "domain_pack_id": domain_pack_id,
                "case_type_id": case_type_id,
            },
        )
        assert case_resp.status_code == 200
        case_id = case_resp.json()["case_id"]

        # Generate checklist and evaluate
        client.post(f"/cases/{case_id}/checklist/generate")
        client.post(f"/cases/{case_id}/checklist/evaluate")

        # Get readiness
        readiness_resp = client.get(f"/cases/{case_id}/readiness")
        assert readiness_resp.status_code == 200
        readiness = readiness_resp.json()["readiness"]

        # Generate packet
        packet_resp = client.post(f"/cases/{case_id}/packets/generate")
        assert packet_resp.status_code == 200
        packet = packet_resp.json()["packet"]

        return {
            "case_id": case_id,
            "readiness_status": readiness["readiness_status"],
            "readiness_total_items": readiness["total_items"],
            "packet_id": packet["packet_id"],
            "packet_readiness_status": packet["readiness_status"],
            "packet_section_count": packet["section_count"],
        }

    @pytest.mark.parametrize(
        "domain_pack_id,case_type_id",
        [
            ("medical_insurance_us", "medical_insurance_us:prior_auth_review"),
            ("insurance_us", "insurance_us:policy_review"),
            ("tax_us", "tax_us:intake_review"),
        ],
        ids=["medical_insurance", "insurance", "tax"],
    )
    def test_readiness_threads_to_packet(
        self,
        client: TestClient,
        domain_pack_id: str,
        case_type_id: str,
    ) -> None:
        data = self._run_domain_flow(client, domain_pack_id, case_type_id)

        # Readiness status must propagate to packet
        assert data["packet_readiness_status"] == data["readiness_status"]

        # Packet must have content sections
        assert data["packet_section_count"] > 0

        # Readiness must reflect the actual requirement count
        expected_count = len(REQUIREMENT_SNAPSHOTS[case_type_id])
        assert data["readiness_total_items"] == expected_count, (
            f"Readiness total_items ({data['readiness_total_items']}) != "
            f"requirement count ({expected_count}) for {case_type_id}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Blocked / incomplete / error-path regression
# ═══════════════════════════════════════════════════════════════════════════


class TestWorkflowPackBlockedStates:
    """Verify workflow pack execution produces correct statuses for
    non-happy-path scenarios: no documents, incompatible case types,
    dependency-blocked stages, and skipped optional stages."""

    def _execute_pack(
        self,
        client: TestClient,
        case_id: str,
        pack_id: str,
        *,
        skip_optional: bool = False,
    ) -> dict:
        resp = client.post(
            f"/cases/{case_id}/workflow-packs/{pack_id}/execute",
            json={
                "case_id": case_id,
                "workflow_pack_id": pack_id,
                "operator_id": "regression-operator",
                "skip_optional_stages": skip_optional,
                "notes": [],
            },
        )
        assert resp.status_code == 200, f"Execute failed: {resp.text}"
        return resp.json()

    def test_no_documents_yields_completed_partial(self, client: TestClient) -> None:
        """A case with no linked documents should produce completed_partial,
        not completed — the intake stage should report missing docs."""
        case_resp = client.post(
            "/cases",
            json={
                "title": "Blocked: no docs",
                "category": "test",
                "domain_pack_id": "medical_insurance_us",
                "case_type_id": "medical_insurance_us:prior_auth_review",
            },
        )
        assert case_resp.status_code == 200
        case_id = case_resp.json()["case_id"]

        payload = self._execute_pack(client, case_id, "prior_auth_packet_review")
        run = payload["run"]
        assert run["status"] in ("completed_partial", "blocked"), (
            f"Expected partial/blocked without docs, got: {run['status']}"
        )

        # intake_document_check must reflect missing documents
        stages = {s["stage_id"]: s for s in run["stage_results"]}
        intake = stages["intake_document_check"]
        assert intake["status"] == "completed_partial"

    def test_skip_optional_stages_marks_them_skipped(self, client: TestClient) -> None:
        """When skip_optional_stages=True, the last two stages should be skipped."""
        case_resp = client.post(
            "/cases",
            json={
                "title": "Blocked: skip optional",
                "category": "test",
                "domain_pack_id": "insurance_us",
                "case_type_id": "insurance_us:policy_review",
            },
        )
        assert case_resp.status_code == 200
        case_id = case_resp.json()["case_id"]

        payload = self._execute_pack(
            client, case_id, "insurance_claim_intake_review", skip_optional=True,
        )
        stages = {s["stage_id"]: s for s in payload["run"]["stage_results"]}
        assert stages["packet_assembly"]["status"] == "skipped"
        assert stages["submission_draft_preparation"]["status"] == "skipped"

    def test_incompatible_case_type_rejected(self, client: TestClient) -> None:
        """Executing a pack against an incompatible case type returns 400."""
        case_resp = client.post(
            "/cases",
            json={
                "title": "Blocked: incompatible",
                "category": "test",
                "domain_pack_id": "tax_us",
                "case_type_id": "tax_us:intake_review",
            },
        )
        assert case_resp.status_code == 200
        case_id = case_resp.json()["case_id"]

        # prior_auth_packet_review is for medical_insurance_us only
        resp = client.post(
            f"/cases/{case_id}/workflow-packs/prior_auth_packet_review/execute",
            json={
                "case_id": case_id,
                "workflow_pack_id": "prior_auth_packet_review",
                "operator_id": "regression-operator",
                "skip_optional_stages": False,
                "notes": [],
            },
        )
        assert resp.status_code == 400

    def test_recommendation_awaiting_documents_without_docs(
        self, client: TestClient
    ) -> None:
        """Without linked documents, recommendation should suggest awaiting_documents."""
        case_resp = client.post(
            "/cases",
            json={
                "title": "Recommendation: no docs",
                "category": "test",
                "domain_pack_id": "medical_insurance_us",
                "case_type_id": "medical_insurance_us:prior_auth_review",
            },
        )
        assert case_resp.status_code == 200
        case_id = case_resp.json()["case_id"]

        payload = self._execute_pack(client, case_id, "prior_auth_packet_review")
        rec = payload["run"]["review_recommendation"]
        assert rec["suggested_next_stage"] == "awaiting_documents"
        assert rec["has_missing_required_documents"] is True

    def test_all_stages_report_status_field(self, client: TestClient) -> None:
        """Every stage result must have a status — no None or missing values."""
        case_resp = client.post(
            "/cases",
            json={
                "title": "All stages status",
                "category": "test",
                "domain_pack_id": "tax_us",
                "case_type_id": "tax_us:notice_review",
            },
        )
        assert case_resp.status_code == 200
        case_id = case_resp.json()["case_id"]

        payload = self._execute_pack(client, case_id, "tax_notice_review")
        for stage in payload["run"]["stage_results"]:
            assert stage["status"] in (
                "completed", "completed_partial", "skipped", "blocked", "failed",
            ), f"Stage {stage['stage_id']} has unexpected status: {stage['status']}"

    @pytest.mark.parametrize(
        "pack_id,domain_pack_id,case_type_id",
        [
            ("prior_auth_packet_review", "medical_insurance_us", "medical_insurance_us:prior_auth_review"),
            ("insurance_claim_intake_review", "insurance_us", "insurance_us:policy_review"),
            ("tax_intake_packet_review", "tax_us", "tax_us:intake_review"),
        ],
        ids=["medical", "insurance", "tax"],
    )
    def test_run_without_docs_never_reports_completed(
        self,
        client: TestClient,
        pack_id: str,
        domain_pack_id: str,
        case_type_id: str,
    ) -> None:
        """No-doc execution must never claim fully 'completed' — it's dishonest."""
        case_resp = client.post(
            "/cases",
            json={
                "title": f"No-doc guard — {pack_id}",
                "category": "test",
                "domain_pack_id": domain_pack_id,
                "case_type_id": case_type_id,
            },
        )
        assert case_resp.status_code == 200
        case_id = case_resp.json()["case_id"]

        payload = self._execute_pack(client, case_id, pack_id)
        assert payload["run"]["status"] != "completed", (
            f"Pack {pack_id} reported 'completed' with no linked documents"
        )
