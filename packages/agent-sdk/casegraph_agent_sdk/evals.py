"""Evaluation and observability contracts.

Shared typed schemas for:
  - eval/observability capabilities endpoint (existing)
  - workflow evaluation suites, cases, assertions, and runs (new)
  - fixture metadata
  - provider comparison metadata
  - domain-specific eval result summaries

These contracts describe evaluation infrastructure — not benchmark
results, scorecards, or production quality claims.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Integration / capabilities (existing)
# ---------------------------------------------------------------------------

IntegrationStatus = Literal["configured", "available", "not_configured"]
BenchmarkCategory = Literal["provider_comparison", "retrieval", "agent_workflow", "custom"]


class IntegrationInfo(BaseModel):
    id: str
    display_name: str
    status: IntegrationStatus
    notes: list[str] = Field(default_factory=list)


class BenchmarkSuiteMeta(BaseModel):
    id: str
    display_name: str
    category: BenchmarkCategory
    description: str
    config_path: str


class EvalCapabilitiesResponse(BaseModel):
    integrations: list[IntegrationInfo]
    benchmark_suites: list[BenchmarkSuiteMeta]
    limitations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Eval identifiers
# ---------------------------------------------------------------------------

EvalSuiteId = str
EvalCaseId = str
EvalRunId = str

# ---------------------------------------------------------------------------
# Eval target and assertion type literals
# ---------------------------------------------------------------------------

EvalTargetType = Literal[
    "workflow_pack",
    "extraction_template",
    "communication_draft_template",
    "provider_task",
    "readiness_evaluation",
]

EvalSuiteCategory = Literal[
    "workflow_regression",
    "extraction_quality",
    "provider_comparison",
    "readiness_assertion",
    "communication_draft",
    "packet_assertion",
    "composite",
]

AssertionType = Literal[
    "status_equals",
    "field_present",
    "field_absent",
    "minimum_item_count",
    "required_reference_present",
    "requirement_status_expected",
    "section_generated",
    "blocked_state_expected",
]

AssertionResultStatus = Literal["pass", "fail", "error", "skipped"]

EvalRunStatus = Literal[
    "created",
    "running",
    "completed",
    "completed_partial",
    "failed",
]

# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------


class EvalAssertion(BaseModel):
    """A single deterministic assertion within an eval case."""

    assertion_id: str = ""
    assertion_type: AssertionType
    target_path: str = ""
    expected_value: Any = None
    description: str = ""


class EvalAssertionResult(BaseModel):
    """Result of evaluating a single assertion."""

    assertion_id: str = ""
    assertion_type: AssertionType
    status: AssertionResultStatus = "skipped"
    actual_value: Any = None
    expected_value: Any = None
    message: str = ""


# ---------------------------------------------------------------------------
# Fixture metadata
# ---------------------------------------------------------------------------


class EvalFixtureMeta(BaseModel):
    """Metadata for a seed fixture used in an eval case."""

    fixture_id: str
    display_name: str
    description: str = ""
    domain_pack_id: str = ""
    case_type_id: str = ""
    document_filenames: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Eval case
# ---------------------------------------------------------------------------


class EvalCaseDefinition(BaseModel):
    """A single eval case within a suite."""

    case_id: EvalCaseId
    display_name: str
    description: str = ""
    fixture: EvalFixtureMeta
    assertions: list[EvalAssertion] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Eval suite definition
# ---------------------------------------------------------------------------


class EvalSuiteDefinition(BaseModel):
    """Full definition of an eval suite."""

    suite_id: EvalSuiteId
    display_name: str
    description: str = ""
    category: EvalSuiteCategory
    target_type: EvalTargetType
    target_ids: list[str] = Field(default_factory=list)
    cases: list[EvalCaseDefinition] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Eval run results
# ---------------------------------------------------------------------------


class EvalCaseResult(BaseModel):
    """Result of running a single eval case."""

    case_id: EvalCaseId
    display_name: str = ""
    status: AssertionResultStatus = "skipped"
    assertion_results: list[EvalAssertionResult] = Field(default_factory=list)
    duration_ms: float = 0.0
    error_message: str = ""
    notes: list[str] = Field(default_factory=list)


class EvalRunRecord(BaseModel):
    """Full record of an eval suite run."""

    run_id: EvalRunId
    suite_id: EvalSuiteId
    status: EvalRunStatus = "created"
    case_results: list[EvalCaseResult] = Field(default_factory=list)
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    error_cases: int = 0
    skipped_cases: int = 0
    started_at: str = ""
    completed_at: str = ""
    duration_ms: float = 0.0
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Provider comparison metadata
# ---------------------------------------------------------------------------


class ProviderComparisonEntry(BaseModel):
    """Single provider result in a comparison run."""

    provider_id: str
    model_id: str = ""
    completed: bool = False
    error_message: str = ""
    latency_ms: float = 0.0
    output_summary: str = ""
    notes: list[str] = Field(default_factory=list)


class ProviderComparisonResult(BaseModel):
    """Comparison of multiple providers on a single task."""

    task_description: str
    entries: list[ProviderComparisonEntry] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Domain-scoped eval summaries (workflow / extraction / readiness / etc.)
# ---------------------------------------------------------------------------


class WorkflowEvalSummary(BaseModel):
    """Summary of workflow-level eval results."""

    workflow_pack_id: str
    total_assertions: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    notes: list[str] = Field(default_factory=list)


class ExtractionEvalSummary(BaseModel):
    """Summary of extraction eval results."""

    template_id: str = ""
    total_assertions: int = 0
    passed: int = 0
    failed: int = 0
    notes: list[str] = Field(default_factory=list)


class ReadinessEvalSummary(BaseModel):
    """Summary of readiness assertion results."""

    total_assertions: int = 0
    passed: int = 0
    failed: int = 0
    notes: list[str] = Field(default_factory=list)


class CommunicationDraftEvalSummary(BaseModel):
    """Summary of communication draft eval results."""

    total_assertions: int = 0
    passed: int = 0
    failed: int = 0
    notes: list[str] = Field(default_factory=list)


class PacketEvalSummary(BaseModel):
    """Summary of packet assembly eval results."""

    total_assertions: int = 0
    passed: int = 0
    failed: int = 0
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API responses
# ---------------------------------------------------------------------------


class EvalSuiteListResponse(BaseModel):
    """Response listing available eval suites."""

    suites: list[EvalSuiteDefinition] = Field(default_factory=list)


class EvalSuiteDetailResponse(BaseModel):
    """Detailed response for a single eval suite."""

    definition: EvalSuiteDefinition


class EvalRunResponse(BaseModel):
    """Response after running an eval suite."""

    success: bool = False
    message: str = ""
    run: EvalRunRecord


class EvalRunDetailResponse(BaseModel):
    """Detailed run with assertion breakdown."""

    run: EvalRunRecord
    suite_display_name: str = ""
