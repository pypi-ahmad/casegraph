"""Route handlers for schema-driven extraction."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from casegraph_agent_sdk.extraction import (
    DocumentExtractionListResponse,
    ExtractionRequest,
    ExtractionResult,
    ExtractionTemplateDetail,
    ExtractionTemplateListResponse,
)

from app.extraction.registry import extraction_template_registry
from app.extraction.schemas import ExtractionExecuteRequestBody, ExtractionExecuteResponseBody
from app.extraction.service import ExtractionService, ExtractionServiceError, langextract_available
from app.persistence.database import get_session

router = APIRouter(tags=["extraction"])


def get_extraction_service(
    session: Session = Depends(get_session),
) -> ExtractionService:
    return ExtractionService(session)


@router.get(
    "/extraction/templates",
    response_model=ExtractionTemplateListResponse,
)
async def list_extraction_templates() -> ExtractionTemplateListResponse:
    available_strategies = ["auto", "provider_structured"]
    limitations: list[str] = []
    if langextract_available():
        available_strategies.append("langextract_grounded")
    else:
        limitations.append(
            "LangExtract strategy is scaffolded and unavailable in this build. Only provider-backed extraction is executable right now."
        )

    response = extraction_template_registry.list_metadata()
    response.available_strategies = available_strategies
    response.limitations = limitations
    return response


@router.get(
    "/extraction/templates/{template_id}",
    response_model=ExtractionTemplateDetail,
)
async def get_extraction_template(template_id: str) -> ExtractionTemplateDetail:
    template = extraction_template_registry.get(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Extraction template not found.")
    return template.detail


@router.post(
    "/extraction/execute",
    response_model=ExtractionExecuteResponseBody,
)
async def execute_extraction(
    body: ExtractionExecuteRequestBody,
    service: ExtractionService = Depends(get_extraction_service),
) -> ExtractionExecuteResponseBody:
    request = ExtractionRequest(
        template_id=body.template_id,
        document_id=body.document_id,
        case_id=body.case_id,
        strategy=body.strategy,
        provider=body.provider,
        model_id=body.model_id,
        api_key=body.api_key.get_secret_value() if body.api_key else None,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
    )
    try:
        result = await service.execute(request)
    except ExtractionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return ExtractionExecuteResponseBody(result=result)


@router.get(
    "/documents/{document_id}/extractions",
    response_model=DocumentExtractionListResponse,
)
async def list_document_extractions(
    document_id: str,
    service: ExtractionService = Depends(get_extraction_service),
) -> DocumentExtractionListResponse:
    try:
        return service.list_document_extractions(document_id)
    except ExtractionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get(
    "/extractions/{extraction_id}",
    response_model=ExtractionResult,
)
async def get_extraction(
    extraction_id: str,
    service: ExtractionService = Depends(get_extraction_service),
) -> ExtractionResult:
    result = service.get_extraction(extraction_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Extraction not found.")
    return result
