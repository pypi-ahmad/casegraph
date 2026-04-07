"""RAG execution service — orchestrates retrieval, evidence, and task execution.

This service connects:
1. Knowledge search (via EvidenceSelector)
2. Evidence formatting (via format_evidence_context)
3. Provider-backed task execution (via existing adapters)
4. Citation extraction from model output

It does NOT duplicate retrieval or provider logic.
"""

from __future__ import annotations

import re
from typing import Any

from casegraph_agent_sdk.rag import (
    CitationReference,
    EvidenceChunkReference,
    RagTaskExecutionRequest,
    RagTaskExecutionResult,
    ResultGroundingMetadata,
)
from casegraph_agent_sdk.tasks import (
    FinishReason,
    StructuredOutputSchema,
    TaskExecutionError,
    TaskExecutionEvent,
)

from app.rag.evidence import EvidenceSelector, EvidenceSelectionResult, format_evidence_context
from app.rag.registry import RagTaskDefinition, rag_task_registry
from app.tasks.service import TaskExecutionService, TaskExecutionServiceError


class RagExecutionServiceError(Exception):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code

from app.persistence.database import isoformat_utc, utcnow


def _event(kind: str, **metadata: Any) -> TaskExecutionEvent:
    return TaskExecutionEvent(kind=kind, timestamp=isoformat_utc(utcnow()), metadata=metadata)


class RagExecutionService:
    """Orchestrates evidence-backed task execution."""

    def __init__(
        self,
        evidence_selector: EvidenceSelector,
        *,
        timeout_seconds: float = 120.0,
        task_execution_service: TaskExecutionService | None = None,
    ) -> None:
        self._evidence = evidence_selector
        self._task_execution = task_execution_service or TaskExecutionService(
            timeout_seconds=timeout_seconds,
        )

    async def execute(
        self,
        request: RagTaskExecutionRequest,
        *,
        case_document_ids: list[str] | None = None,
    ) -> tuple[RagTaskExecutionResult, list[TaskExecutionEvent]]:
        """Execute a RAG task: retrieve → assemble context → generate → cite."""
        events: list[TaskExecutionEvent] = []

        # --- Resolve task definition ---
        task_def = rag_task_registry.get(request.task_id)
        if task_def is None:
            raise RagExecutionServiceError(
                f"RAG task '{request.task_id}' is not registered.",
                status_code=404,
            )

        # --- Retrieve evidence ---
        events.append(_event("retrieval_started", query=request.query, top_k=request.top_k))

        try:
            evidence_result = self._evidence.select(
                request.query,
                top_k=request.top_k,
                scope=request.retrieval_scope,
                document_ids=case_document_ids,
            )
        except Exception as exc:
            events.append(_event("retrieval_failed", error=str(exc)))
            raise RagExecutionServiceError(
                f"Evidence retrieval failed: {exc}",
                status_code=503,
            ) from exc

        events.append(_event(
            "retrieval_completed",
            total_retrieved=evidence_result.summary.total_retrieved,
            embedding_model=evidence_result.summary.embedding_model,
            vector_store=evidence_result.summary.vector_store,
        ))

        # --- Select evidence ---
        evidence_chunks = evidence_result.chunks
        events.append(_event(
            "evidence_selected",
            total_selected=len(evidence_chunks),
            total_retrieved=evidence_result.summary.total_retrieved,
        ))

        if task_def.meta.requires_evidence and not evidence_chunks:
            return self._empty_evidence_result(request, evidence_result, events)

        # --- Assemble context ---
        evidence_context = format_evidence_context(evidence_chunks)
        user_prompt = task_def.build_user_prompt(request.query, evidence_context)
        system_prompt = task_def.system_prompt
        events.append(_event("context_assembled", evidence_chars=len(evidence_context)))

        # --- Resolve structured output ---
        structured_output = self._resolve_structured_output(request, task_def)

        try:
            base_result, execution_events = await self._task_execution.execute_prepared_prompt(
                task_id=request.task_id,
                provider_selection=request.provider_selection,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                structured_output=structured_output,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                trace_name="rag.execute",
                trace_label=f"rag.{request.task_id}",
                trace_metadata={
                    "task_id": request.task_id,
                    "provider": request.provider_selection.provider,
                    "model_id": request.provider_selection.model_id,
                    "evidence_count": len(evidence_chunks),
                },
                trace_input_data={"query": request.query},
            )
        except TaskExecutionServiceError as exc:
            raise RagExecutionServiceError(exc.detail, status_code=exc.status_code) from exc

        events.extend(execution_events)

        citations = self._extract_citations(
            base_result.output_text,
            evidence_chunks,
        ) if task_def.meta.returns_citations and base_result.output_text else []

        if citations:
            events.append(_event(
                "citations_attached",
                citation_count=len(citations),
                cited_chunk_ids=[c.chunk_id for c in citations],
            ))

        return RagTaskExecutionResult(
            task_id=request.task_id,
            provider=base_result.provider,
            model_id=base_result.model_id,
            finish_reason=base_result.finish_reason,
            output_text=base_result.output_text,
            structured_output=base_result.structured_output,
            citations=citations,
            evidence=evidence_chunks,
            evidence_summary=evidence_result.summary,
            grounding=ResultGroundingMetadata(
                evidence_provided=bool(evidence_chunks),
                evidence_chunk_count=len(evidence_chunks),
                citation_count=len(citations),
                grounding_method="chunk_reference",
            ),
            usage=base_result.usage,
            error=base_result.error,
            duration_ms=base_result.duration_ms,
            provider_request_id=base_result.provider_request_id,
        ), events

    def _empty_evidence_result(
        self,
        request: RagTaskExecutionRequest,
        evidence_result: EvidenceSelectionResult,
        events: list[TaskExecutionEvent],
    ) -> tuple[RagTaskExecutionResult, list[TaskExecutionEvent]]:
        """Return an honest result when no evidence was found."""
        return RagTaskExecutionResult(
            task_id=request.task_id,
            provider=request.provider_selection.provider,
            model_id=request.provider_selection.model_id,
            finish_reason=FinishReason.ERROR,
            output_text=None,
            error=TaskExecutionError(
                error_code="no_evidence",
                message="No relevant evidence was found for the query.",
                provider=request.provider_selection.provider,
                model_id=request.provider_selection.model_id,
                recoverable=True,
            ),
            evidence=[],
            evidence_summary=evidence_result.summary,
            grounding=ResultGroundingMetadata(
                evidence_provided=False,
                evidence_chunk_count=0,
            ),
        ), events

    def _resolve_structured_output(
        self,
        request: RagTaskExecutionRequest,
        task_def: RagTaskDefinition,
    ) -> StructuredOutputSchema | None:
        if request.structured_output is not None:
            return request.structured_output
        if task_def.meta.supports_structured_output and task_def.meta.output_schema:
            return StructuredOutputSchema(
                json_schema=task_def.meta.output_schema,
                strict=False,
            )
        return None

    @staticmethod
    def _extract_citations(
        output_text: str | None,
        evidence_chunks: list[EvidenceChunkReference],
    ) -> list[CitationReference]:
        """Extract citation references from model output.

        Looks for [1], [2], etc. patterns and maps them to evidence chunks.
        This is an honest extraction — only references that appear in the
        output AND correspond to a real evidence chunk are included.
        """
        if not output_text or not evidence_chunks:
            return []

        # Find all [N] references in the output
        found_indices = set(int(m) for m in re.findall(r"\[(\d+)\]", output_text))

        citations: list[CitationReference] = []
        for idx in sorted(found_indices):
            if 1 <= idx <= len(evidence_chunks):
                chunk = evidence_chunks[idx - 1]
                citations.append(CitationReference(
                    citation_index=idx,
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.source_reference.document_id,
                    page_number=chunk.page_number,
                    source_filename=chunk.source_filename,
                ))

        return citations
