"""Cross-layer contract tests.

Every test in this module hits a real FastAPI endpoint through the full app
(all routers mounted) and validates the JSON response against the corresponding
SDK Pydantic model.  This catches the class of bugs that individual module tests
miss: field renames, missing keys, type drift between the Python service layer,
the API response_model, and the SDK contract that the TypeScript frontend imports.

Tests are organised in two groups:

1. **Zero-state registry endpoints** — GET endpoints that return valid (often
   empty-list) responses on a freshly-initialised database.  These are cheap
   and cover the widest surface.

2. **Stateful integration flows** — Multi-step flows that create real persisted
   objects and then validate every response in the chain.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from casegraph_agent_sdk import (
    # -- agents / runtime ---------------------------------------------------
    AgentsResponse,
    # -- automation ---------------------------------------------------------
    AutomationCapabilitiesResponse,
    # -- cases --------------------------------------------------------------
    CaseDetailResponse,
    CaseListResponse,
    CaseRecord,
    # -- communications -----------------------------------------------------
    CommunicationTemplateListResponse,
    # -- domains ------------------------------------------------------------
    DomainPackListResponse,
    # -- evals --------------------------------------------------------------
    EvalCapabilitiesResponse,
    EvalSuiteListResponse,
    # -- extraction ---------------------------------------------------------
    ExtractionTemplateListResponse,
    # -- ingestion / documents ----------------------------------------------
    DocumentRegistryListResponse,
    DocumentsCapabilitiesResponse,
    # -- knowledge ----------------------------------------------------------
    KnowledgeCapabilitiesResponse,
    # -- providers ----------------------------------------------------------
    ProvidersResponse,
    # -- rag ----------------------------------------------------------------
    RagTaskRegistryResponse,
    # -- readiness ----------------------------------------------------------
    ChecklistResponse,
    ReadinessResponse,
    # -- submissions --------------------------------------------------------
    SubmissionTargetListResponse,
    # -- target packs -------------------------------------------------------
    TargetPackListResponse,
    # -- tasks --------------------------------------------------------------
    TaskRegistryResponse,
    # -- topology -----------------------------------------------------------
    TopologyResponse,
    # -- work management ----------------------------------------------------
    WorkQueueResponse,
    WorkSummaryResponse,
    # -- workflow packs -----------------------------------------------------
    WorkflowPackListResponse,
    # -- audit --------------------------------------------------------------
    AuditTimelineResponse,
    DecisionLedgerResponse,
    LineageResponse,
    # -- packets ------------------------------------------------------------
    PacketListResponse,
    # -- human validation ---------------------------------------------------
    ExtractionValidationsResponse,
    ReviewedCaseStateResponse,
    RequirementReviewsResponse,
    # -- reviewed handoff ---------------------------------------------------
    ReviewedSnapshotListResponse,
    HandoffEligibilityResponse,
    # -- reviewed release ---------------------------------------------------
    ReleaseBundleListResponse,
    ReleaseEligibilityResponse,
    # -- operator review ----------------------------------------------------
    ReviewQueueResponse,
    QueueSummaryResponse,
    CaseStageResponse,
    StageHistoryResponse,
    CaseActionListResponse,
    ReviewNoteListResponse,
    # -- case documents / runs ----------------------------------------------
    CaseDocumentListResponse,
    WorkflowRunListResponse,
    # -- communication drafts -----------------------------------------------
    CommunicationDraftListResponse,
    # -- submission drafts --------------------------------------------------
    SubmissionDraftListResponse,
    # -- execution ----------------------------------------------------------
    AutomationRunListResponse,
    # -- work management per-case -------------------------------------------
    AssignmentHistoryResponse,
    CaseAssignmentResponse,
    CaseSLAResponse,
    CaseWorkStatusResponse,
    # -- case target pack ---------------------------------------------------
    CaseTargetPackResponse,
    # -- workflow pack runs -------------------------------------------------
    WorkflowPackRunSummaryResponse,
    WorkflowPackRunResponse,
)


# ---------------------------------------------------------------------------
# 1. Zero-state registry / capability / list endpoints
#
# These endpoints return valid responses on an empty DB.  We validate every
# response against its SDK model.
# ---------------------------------------------------------------------------


class TestZeroStateRegistries:
    """GET endpoints that return structured responses on a fresh database."""

    @pytest.mark.parametrize(
        "path, model",
        [
            # Registries and capabilities
            ("/providers", ProvidersResponse),
            ("/automation/capabilities", AutomationCapabilitiesResponse),
            ("/evals/capabilities", EvalCapabilitiesResponse),
            ("/evals/suites", EvalSuiteListResponse),
            ("/tasks", TaskRegistryResponse),
            ("/rag/tasks", RagTaskRegistryResponse),
            ("/extraction/templates", ExtractionTemplateListResponse),
            ("/communication/templates", CommunicationTemplateListResponse),
            ("/submission/targets", SubmissionTargetListResponse),
            ("/domain-packs", DomainPackListResponse),
            ("/target-packs", TargetPackListResponse),
            ("/workflow-packs", WorkflowPackListResponse),
            ("/documents/capabilities", DocumentsCapabilitiesResponse),
            # Lists (empty on fresh DB)
            ("/cases", CaseListResponse),
            ("/documents", DocumentRegistryListResponse),
            ("/queue", ReviewQueueResponse),
            ("/queue/summary", QueueSummaryResponse),
            ("/work/queue", WorkQueueResponse),
            ("/work/summary", WorkSummaryResponse),
        ],
    )
    def test_registry_endpoint_conforms_to_sdk(
        self, client: TestClient, path: str, model: type
    ) -> None:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}: {resp.text}"
        validated = model.model_validate(resp.json())
        assert validated is not None


class TestZeroStateTopology:
    """Topology derives from runtime metadata — may fail if runtime is down."""

    def test_topology_response_conforms_to_sdk(self, client: TestClient) -> None:
        resp = client.get("/topology")
        if resp.status_code == 502:
            pytest.skip("Agent-runtime not reachable in test environment")
        assert resp.status_code == 200
        validated = TopologyResponse.model_validate(resp.json())
        assert isinstance(validated.nodes, list)
        assert isinstance(validated.edges, list)


# ---------------------------------------------------------------------------
# 2. Case-scoped integration flow
#
# Create a case → hit every case-scoped endpoint → validate each response
# against its SDK model.  This catches cross-layer contract drift in the
# stateful paths that matter most.
# ---------------------------------------------------------------------------


class TestCaseLifecycleContracts:
    """Create a real case and validate every case-scoped response."""

    @pytest.fixture(autouse=True)
    def _setup_case(self, client: TestClient) -> None:
        """Create a case to use across all tests in this class."""
        resp = client.post(
            "/cases",
            json={
                "title": "Contract test case",
                "category": "general",
                "summary": "Cross-layer contract validation.",
            },
        )
        assert resp.status_code == 200, resp.text
        self.case = CaseRecord.model_validate(resp.json())
        self.case_id = self.case.case_id
        self.client = client

    def test_case_create_conforms(self) -> None:
        assert self.case.title == "Contract test case"

    def test_case_list_conforms(self) -> None:
        resp = self.client.get("/cases")
        validated = CaseListResponse.model_validate(resp.json())
        assert len(validated.cases) >= 1

    def test_case_detail_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}")
        assert resp.status_code == 200
        validated = CaseDetailResponse.model_validate(resp.json())
        assert validated.case.case_id == self.case_id

    def test_case_update_conforms(self) -> None:
        resp = self.client.patch(
            f"/cases/{self.case_id}",
            json={"summary": "Updated summary."},
        )
        assert resp.status_code == 200
        validated = CaseRecord.model_validate(resp.json())
        assert validated.summary == "Updated summary."

    def test_case_documents_list_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/documents")
        assert resp.status_code == 200
        CaseDocumentListResponse.model_validate(resp.json())

    def test_case_runs_list_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/runs")
        assert resp.status_code == 200
        WorkflowRunListResponse.model_validate(resp.json())

    def test_audit_timeline_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/audit")
        assert resp.status_code == 200
        AuditTimelineResponse.model_validate(resp.json())

    def test_decision_ledger_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/decisions")
        assert resp.status_code == 200
        DecisionLedgerResponse.model_validate(resp.json())

    def test_lineage_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/lineage")
        assert resp.status_code == 200
        LineageResponse.model_validate(resp.json())

    def test_checklist_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/checklist")
        if resp.status_code == 404:
            return  # No checklist generated yet — expected for generic cases
        assert resp.status_code == 200
        ChecklistResponse.model_validate(resp.json())

    def test_readiness_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/readiness")
        if resp.status_code == 404:
            return  # No readiness data yet — expected for generic cases
        assert resp.status_code == 200
        ReadinessResponse.model_validate(resp.json())

    def test_packets_list_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/packets")
        assert resp.status_code == 200
        PacketListResponse.model_validate(resp.json())

    def test_extraction_validations_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/extraction-validations")
        assert resp.status_code == 200
        ExtractionValidationsResponse.model_validate(resp.json())

    def test_reviewed_case_state_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/reviewed-state")
        if resp.status_code == 404:
            return  # No review data yet — expected for fresh cases
        assert resp.status_code == 200
        ReviewedCaseStateResponse.model_validate(resp.json())

    def test_requirement_reviews_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/requirement-reviews")
        assert resp.status_code == 200
        RequirementReviewsResponse.model_validate(resp.json())

    def test_reviewed_snapshots_list_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/reviewed-snapshots")
        assert resp.status_code == 200
        ReviewedSnapshotListResponse.model_validate(resp.json())

    def test_handoff_eligibility_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/handoff-eligibility")
        assert resp.status_code == 200
        HandoffEligibilityResponse.model_validate(resp.json())

    def test_release_bundles_list_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/release-bundles")
        if resp.status_code == 404:
            return  # No release bundles — expected for fresh cases
        assert resp.status_code == 200
        ReleaseBundleListResponse.model_validate(resp.json())

    def test_release_eligibility_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/release-eligibility")
        assert resp.status_code == 200
        ReleaseEligibilityResponse.model_validate(resp.json())

    def test_communication_drafts_list_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/communication-drafts")
        assert resp.status_code == 200
        CommunicationDraftListResponse.model_validate(resp.json())

    def test_submission_drafts_list_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/submission-drafts")
        assert resp.status_code == 200
        SubmissionDraftListResponse.model_validate(resp.json())

    def test_automation_runs_list_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/automation-runs")
        assert resp.status_code == 200
        AutomationRunListResponse.model_validate(resp.json())

    def test_case_stage_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/stage")
        assert resp.status_code == 200
        CaseStageResponse.model_validate(resp.json())

    def test_stage_history_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/stage-history")
        assert resp.status_code == 200
        StageHistoryResponse.model_validate(resp.json())

    def test_actions_list_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/actions")
        assert resp.status_code == 200
        CaseActionListResponse.model_validate(resp.json())

    def test_review_notes_list_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/review-notes")
        assert resp.status_code == 200
        ReviewNoteListResponse.model_validate(resp.json())

    def test_assignment_history_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/assignment-history")
        assert resp.status_code == 200
        AssignmentHistoryResponse.model_validate(resp.json())

    def test_work_status_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/work-status")
        assert resp.status_code == 200
        CaseWorkStatusResponse.model_validate(resp.json())

    def test_target_pack_selection_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/target-pack")
        assert resp.status_code == 200
        CaseTargetPackResponse.model_validate(resp.json())

    def test_workflow_pack_runs_list_conforms(self) -> None:
        resp = self.client.get(f"/cases/{self.case_id}/workflow-pack-runs")
        assert resp.status_code == 200
        runs = resp.json()
        assert isinstance(runs, list)
        for item in runs:
            WorkflowPackRunResponse.model_validate(item)


# ---------------------------------------------------------------------------
# 3. SDK barrel integrity
#
# Validates that every name in the Python SDK __all__ actually resolves at
# import time.  Catches typos in the barrel or missing types in submodules.
# ---------------------------------------------------------------------------


class TestSDKBarrelIntegrity:
    """Validates the Python SDK barrel export is complete and importable."""

    def test_all_exports_resolve(self) -> None:
        import casegraph_agent_sdk as sdk

        missing = []
        for name in sdk.__all__:
            obj = getattr(sdk, name, None)
            if obj is None:
                missing.append(name)
        assert missing == [], f"SDK __all__ contains unresolvable names: {missing}"

    def test_export_count_minimum(self) -> None:
        import casegraph_agent_sdk as sdk

        assert len(sdk.__all__) >= 570, (
            f"SDK __all__ has {len(sdk.__all__)} exports; expected >= 570"
        )
