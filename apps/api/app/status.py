"""Authoritative module maturity registry.

This is the single source of truth for every module's release label.
STATUS.md and the ``GET /status/modules`` endpoint both derive from
this registry.  To change a label, update the entry here and the
regression test will tell you if the change is valid.

Labels
------
- **stable** — regression-gated, cross-layer tested, hardened.
- **implemented** — working logic + endpoints + tests, not yet hardened.
- **scaffolded** — router exists, logic is thin/proxy/stub.
- **planned** — directory or placeholder only.
"""

from __future__ import annotations

from casegraph_agent_sdk.platform import (
    ModuleStatusEntry,
    PlatformStatusResponse,
)

# ───────────────────────────────────────────────────────────────────
# Registry entries  (alphabetical by module_id)
#
# When you add a new module, add an entry here.  The regression test
# in test_module_maturity.py will fail if the module is mounted in
# main.py but missing from this table (or vice-versa).
# ───────────────────────────────────────────────────────────────────

MODULE_REGISTRY: list[ModuleStatusEntry] = [
    ModuleStatusEntry(
        module_id="audit",
        display_name="Audit Trail",
        maturity="implemented",
        route_count=4,
        has_db_models=True,
        has_tests=True,
        notes="Read-only timeline, decisions, lineage queries.",
    ),
    ModuleStatusEntry(
        module_id="automation",
        display_name="Automation Proxy",
        maturity="scaffolded",
        route_count=2,
        has_tests=True,
        notes="Thin proxy to agent-runtime /tools. No local logic.",
    ),
    ModuleStatusEntry(
        module_id="cases",
        display_name="Cases",
        maturity="stable",
        route_count=9,
        has_db_models=True,
        has_tests=True,
        has_regression_gate=True,
        notes="Central entity. Cross-layer contract + integration tested.",
    ),
    ModuleStatusEntry(
        module_id="communications",
        display_name="Communications",
        maturity="implemented",
        route_count=6,
        has_db_models=True,
        has_tests=True,
        notes="Template registry, draft generation, provider fallback.",
    ),
    ModuleStatusEntry(
        module_id="domains",
        display_name="Domain Packs",
        maturity="stable",
        route_count=5,
        has_tests=True,
        has_regression_gate=True,
        notes="In-memory pack registry. All 8 packs regression-gated.",
    ),
    ModuleStatusEntry(
        module_id="evals",
        display_name="Evaluation Suites",
        maturity="implemented",
        route_count=6,
        has_db_models=True,
        has_tests=True,
        notes="Fixture/suite registry, regression runner.",
    ),
    ModuleStatusEntry(
        module_id="execution",
        display_name="Execution Lifecycle",
        maturity="implemented",
        route_count=13,
        has_db_models=True,
        has_tests=True,
        notes="Gating, checkpoints, resume/block/skip.",
    ),
    ModuleStatusEntry(
        module_id="extraction",
        display_name="Extraction",
        maturity="implemented",
        route_count=5,
        has_db_models=True,
        has_tests=True,
        notes="Template registry, schema conversion, grounding, LLM extraction.",
    ),
    ModuleStatusEntry(
        module_id="human_validation",
        display_name="Human Validation",
        maturity="implemented",
        route_count=5,
        has_db_models=True,
        has_tests=True,
        notes="Field validation, requirement review, state tracking.",
    ),
    ModuleStatusEntry(
        module_id="ingestion",
        display_name="Document Ingestion",
        maturity="stable",
        route_count=5,
        has_db_models=True,
        has_tests=True,
        has_regression_gate=True,
        notes="PDF/OCR routing, text extraction, page geometry. Persisted output + source file.",
    ),
    ModuleStatusEntry(
        module_id="knowledge",
        display_name="Knowledge & Retrieval",
        maturity="implemented",
        route_count=3,
        has_tests=True,
        notes="Chunking, embedding, vector indexing, search.",
    ),
    ModuleStatusEntry(
        module_id="observability",
        display_name="Observability",
        maturity="implemented",
        route_count=0,
        has_tests=True,
        notes="Request logging middleware, Langfuse client, trace_span. No routes.",
    ),
    ModuleStatusEntry(
        module_id="operator_review",
        display_name="Operator Review",
        maturity="implemented",
        route_count=9,
        has_db_models=True,
        has_tests=True,
        notes="Stage machine, actions, queue, notes.",
    ),
    ModuleStatusEntry(
        module_id="packets",
        display_name="Packet Assembly",
        maturity="stable",
        route_count=6,
        has_db_models=True,
        has_tests=True,
        has_regression_gate=True,
        notes="Assembly, manifests, artifacts, export. Cross-layer tested.",
    ),
    ModuleStatusEntry(
        module_id="providers",
        display_name="BYOK Providers",
        maturity="stable",
        route_count=3,
        has_tests=True,
        has_regression_gate=True,
        notes="Adapter registry, key validation, model discovery. Integration tested.",
    ),
    ModuleStatusEntry(
        module_id="rag",
        display_name="RAG",
        maturity="implemented",
        route_count=2,
        has_tests=True,
        notes="Task registry, evidence selection, citations.",
    ),
    ModuleStatusEntry(
        module_id="readiness",
        display_name="Readiness",
        maturity="stable",
        route_count=5,
        has_db_models=True,
        has_tests=True,
        has_regression_gate=True,
        notes="Checklist generation, evaluation, overrides. Pack-aligned regression gates.",
    ),
    ModuleStatusEntry(
        module_id="review",
        display_name="Document Review",
        maturity="implemented",
        route_count=12,
        has_db_models=True,
        has_tests=True,
        notes="Page viewer, geometry, OCR results, annotations CRUD, word-level extraction.",
    ),
    ModuleStatusEntry(
        module_id="reviewed_handoff",
        display_name="Reviewed Handoff",
        maturity="implemented",
        route_count=6,
        has_db_models=True,
        has_tests=True,
        notes="Snapshot, signoff, eligibility governance.",
    ),
    ModuleStatusEntry(
        module_id="reviewed_release",
        display_name="Reviewed Release",
        maturity="implemented",
        route_count=5,
        has_db_models=True,
        has_tests=True,
        notes="Bundle creation, provenance, audit trail.",
    ),
    ModuleStatusEntry(
        module_id="runtime",
        display_name="Runtime Proxy",
        maturity="scaffolded",
        route_count=4,
        has_tests=True,
        notes="Thin pass-through to agent-runtime. No local logic.",
    ),
    ModuleStatusEntry(
        module_id="submissions",
        display_name="Submissions",
        maturity="stable",
        route_count=7,
        has_db_models=True,
        has_tests=True,
        has_regression_gate=True,
        notes="Targets, drafts, field mapping, approval gating. Cross-layer tested.",
    ),
    ModuleStatusEntry(
        module_id="target_packs",
        display_name="Target Packs",
        maturity="implemented",
        route_count=7,
        has_tests=True,
        notes="Registry, domain filtering, case selection.",
    ),
    ModuleStatusEntry(
        module_id="tasks",
        display_name="Task Execution",
        maturity="implemented",
        route_count=2,
        has_tests=True,
        notes="Registry lookup, prompt building, LLM execution.",
    ),
    ModuleStatusEntry(
        module_id="topology",
        display_name="Topology",
        maturity="scaffolded",
        route_count=1,
        has_tests=True,
        notes="Pure graph builder. Depends on agent-runtime for input.",
    ),
    ModuleStatusEntry(
        module_id="workflow_packs",
        display_name="Workflow Packs",
        maturity="stable",
        route_count=5,
        has_db_models=True,
        has_tests=True,
        has_regression_gate=True,
        notes="Built-in domain workflow orchestration. All 10 packs regression-gated.",
    ),
    ModuleStatusEntry(
        module_id="work_management",
        display_name="Work Management",
        maturity="implemented",
        route_count=6,
        has_db_models=True,
        has_tests=True,
        notes="Assignment, SLA, queue, summary.",
    ),
]


def get_platform_status() -> PlatformStatusResponse:
    """Build the platform status summary from the registry."""
    stable = sum(1 for m in MODULE_REGISTRY if m.maturity == "stable")
    implemented = sum(1 for m in MODULE_REGISTRY if m.maturity == "implemented")
    scaffolded = sum(1 for m in MODULE_REGISTRY if m.maturity == "scaffolded")
    planned = sum(1 for m in MODULE_REGISTRY if m.maturity == "planned")
    return PlatformStatusResponse(
        modules=MODULE_REGISTRY,
        total_modules=len(MODULE_REGISTRY),
        stable_count=stable,
        implemented_count=implemented,
        scaffolded_count=scaffolded,
        planned_count=planned,
    )
