"""Shared case/workspace contracts for the CaseGraph platform."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from casegraph_agent_sdk.domains import CaseDomainContext, CaseTypeTemplateId, DomainPackId
from casegraph_agent_sdk.ingestion import (
    DocumentId,
    DocumentProcessingStatus,
    IngestionMode,
    IngestionModePreference,
    SourceFileMetadata,
)
from casegraph_agent_sdk.rag import RagTaskExecutionRequest, RagTaskExecutionResult
from casegraph_agent_sdk.tasks import TaskExecutionEvent, TaskExecutionRequest, TaskExecutionResult
from casegraph_agent_sdk.target_packs import CaseTargetPackSelection

CaseId = str
CaseTitle = str
CaseCategory = str
WorkflowRunId = str
CaseMetadata = dict[str, Any]

CaseStatus = Literal["open", "active", "on_hold", "closed", "archived"]

CaseRunStatus = Literal[
    "created",
    "running",
    "completed",
    "failed",
    "queued_placeholder",
    "not_started",
    "failed_validation",
    "completed_placeholder",
]

RunInputReferenceType = Literal["case_document", "document", "case", "custom"]


class TimestampMetadata(BaseModel):
    created_at: str
    updated_at: str


class NormalizedOperationError(BaseModel):
    error_code: str
    message: str
    recoverable: bool = False


class CaseWorkflowBindingMetadata(BaseModel):
    workflow_id: str
    bound_at: str


class CaseRecord(BaseModel):
    case_id: CaseId
    title: CaseTitle
    category: CaseCategory | None = None
    status: CaseStatus = "open"
    summary: str | None = None
    metadata: CaseMetadata = Field(default_factory=dict)
    domain_context: CaseDomainContext | None = None
    workflow_binding: CaseWorkflowBindingMetadata | None = None
    target_pack_selection: CaseTargetPackSelection | None = None
    timestamps: TimestampMetadata


class CaseDocumentReference(BaseModel):
    link_id: str
    case_id: CaseId
    document_id: DocumentId
    source_file: SourceFileMetadata
    requested_mode: IngestionModePreference | None = None
    resolved_mode: IngestionMode | None = None
    document_status: DocumentProcessingStatus | None = None
    linked_at: str


class RunInputReference(BaseModel):
    reference_type: RunInputReferenceType
    reference_id: str
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunOutputPlaceholderMetadata(BaseModel):
    output_available: bool = False
    summary: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    task_execution_id: str | None = None
    task_execution: TaskExecutionResult | None = None
    rag_task_execution: RagTaskExecutionResult | None = None
    events: list[TaskExecutionEvent] = Field(default_factory=list)


class WorkflowRunRequest(BaseModel):
    workflow_id: str
    input_references: list[RunInputReference] = Field(default_factory=list)
    linked_document_ids: list[DocumentId] = Field(default_factory=list)
    notes: str | None = None
    task_execution: TaskExecutionRequest | None = None
    rag_task_execution: RagTaskExecutionRequest | None = None


class WorkflowRunRecord(BaseModel):
    run_id: WorkflowRunId
    case_id: CaseId
    workflow_id: str
    status: CaseRunStatus = "created"
    input_references: list[RunInputReference] = Field(default_factory=list)
    linked_document_ids: list[DocumentId] = Field(default_factory=list)
    output: WorkflowRunOutputPlaceholderMetadata | None = None
    events: list[TaskExecutionEvent] = Field(default_factory=list)
    error: NormalizedOperationError | None = None
    notes: str | None = None
    timestamps: TimestampMetadata


class CreateCaseRequest(BaseModel):
    title: CaseTitle
    category: CaseCategory | None = None
    summary: str | None = None
    metadata: CaseMetadata = Field(default_factory=dict)
    workflow_id: str | None = None
    domain_pack_id: DomainPackId | None = None
    case_type_id: CaseTypeTemplateId | None = None


class UpdateCaseRequest(BaseModel):
    title: CaseTitle | None = None
    category: CaseCategory | None = None
    status: CaseStatus | None = None
    summary: str | None = None
    metadata: CaseMetadata | None = None
    workflow_id: str | None = None


class LinkCaseDocumentRequest(BaseModel):
    document_id: DocumentId


class CaseListResponse(BaseModel):
    cases: list[CaseRecord] = Field(default_factory=list)


class CaseDocumentListResponse(BaseModel):
    documents: list[CaseDocumentReference] = Field(default_factory=list)


class WorkflowRunListResponse(BaseModel):
    runs: list[WorkflowRunRecord] = Field(default_factory=list)


class CaseDetailResponse(BaseModel):
    case: CaseRecord
    documents: list[CaseDocumentReference] = Field(default_factory=list)
    runs: list[WorkflowRunRecord] = Field(default_factory=list)