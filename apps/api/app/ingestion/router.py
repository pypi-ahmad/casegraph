"""Route handlers for document ingestion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlmodel import Session

from casegraph_agent_sdk.ingestion import (
    DocumentProcessingStatus,
    IngestionModePreference,
    IngestionRequest,
    IngestionResult,
)

from app.ingestion.registry import DocumentRegistryService
from app.ingestion.schemas import (
    DocumentDetailResponse,
    DocumentPageSummary,
    DocumentPagesResponse,
    DocumentRegistryListResponse,
    DocumentsCapabilitiesResponse,
)
from app.ingestion.service import DocumentIngestionService
from app.persistence.database import get_session


router = APIRouter(tags=["documents"])


def get_document_registry_service(
    session: Session = Depends(get_session),
) -> DocumentRegistryService:
    return DocumentRegistryService(session)


def get_ingestion_service(
    document_registry: DocumentRegistryService = Depends(get_document_registry_service),
) -> DocumentIngestionService:
    return DocumentIngestionService(document_registry=document_registry)


@router.get("/documents/capabilities", response_model=DocumentsCapabilitiesResponse)
async def document_capabilities(
    service: DocumentIngestionService = Depends(get_ingestion_service),
) -> DocumentsCapabilitiesResponse:
    return service.capabilities()


@router.get("/documents", response_model=DocumentRegistryListResponse)
async def list_documents(
    status: DocumentProcessingStatus | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=250),
    document_registry: DocumentRegistryService = Depends(get_document_registry_service),
) -> DocumentRegistryListResponse:
    return DocumentRegistryListResponse(
        documents=document_registry.list_documents(status=status, limit=limit)
    )


@router.post("/documents/ingest", response_model=IngestionResult)
async def ingest_document(
    file: UploadFile = File(...),
    mode: IngestionModePreference = Form(default=IngestionModePreference.AUTO),
    ocr_enabled: bool = Form(default=False),
    service: DocumentIngestionService = Depends(get_ingestion_service),
) -> IngestionResult:
    request = IngestionRequest(requested_mode=mode, ocr_enabled=ocr_enabled)
    return await service.ingest_upload(upload_file=file, request=request)


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document_detail(
    document_id: str,
    document_registry: DocumentRegistryService = Depends(get_document_registry_service),
) -> DocumentDetailResponse:
    summary = document_registry.get_document(document_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    output = document_registry.get_document_output(document_id)
    source_file_path = document_registry.get_source_file_path(document_id)
    page_records = document_registry.get_page_records(document_id)
    pages = [
        DocumentPageSummary(
            page_number=p.page_number,
            width=p.width,
            height=p.height,
            coordinate_space=p.coordinate_space,
            geometry_source=p.geometry_source,
            text=p.text,
            text_blocks=p.text_blocks_json,
            has_page_image=p.has_page_image,
            page_image_path=p.page_image_path,
        )
        for p in page_records
    ]
    return DocumentDetailResponse(
        summary=summary,
        output=output,
        source_file_path=source_file_path,
        pages=pages,
    )


@router.get("/documents/{document_id}/pages", response_model=DocumentPagesResponse)
async def get_document_pages(
    document_id: str,
    document_registry: DocumentRegistryService = Depends(get_document_registry_service),
) -> DocumentPagesResponse:
    summary = document_registry.get_document(document_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    page_records = document_registry.get_page_records(document_id)
    pages = [
        DocumentPageSummary(
            page_number=p.page_number,
            width=p.width,
            height=p.height,
            coordinate_space=p.coordinate_space,
            geometry_source=p.geometry_source,
            text=p.text,
            text_blocks=p.text_blocks_json,
            has_page_image=p.has_page_image,
            page_image_path=p.page_image_path,
        )
        for p in page_records
    ]
    return DocumentPagesResponse(document_id=document_id, pages=pages)
