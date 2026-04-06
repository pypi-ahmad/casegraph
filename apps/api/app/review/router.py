"""Route handlers for the document review surface."""

from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from casegraph_agent_sdk.annotations import (
    AnnotationListResponse,
    AnnotationRecord,
    CreateAnnotationRequest,
    PageAnnotationListResponse,
    PageWordsResponse,
    UpdateAnnotationRequest,
)
from casegraph_agent_sdk.review import (
    DocumentPageListResponse,
    DocumentReviewResponse,
    PageReviewDetail,
)

from app.persistence.database import get_session
from app.review.annotation_service import AnnotationService
from app.review.service import DocumentReviewService

router = APIRouter(tags=["review"])


def get_review_service(
    session: Session = Depends(get_session),
) -> DocumentReviewService:
    return DocumentReviewService(session)


def get_annotation_service(
    session: Session = Depends(get_session),
) -> AnnotationService:
    return AnnotationService(session)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentReviewResponse,
)
async def get_document(
    document_id: str,
    service: DocumentReviewService = Depends(get_review_service),
) -> DocumentReviewResponse:
    result = service.get_document(document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


@router.get(
    "/documents/{document_id}/review",
    response_model=DocumentReviewResponse,
)
async def get_document_review(
    document_id: str,
    service: DocumentReviewService = Depends(get_review_service),
) -> DocumentReviewResponse:
    result = service.get_document_review(document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


@router.get(
    "/documents/{document_id}/pages",
    response_model=DocumentPageListResponse,
)
async def list_document_pages(
    document_id: str,
    service: DocumentReviewService = Depends(get_review_service),
) -> DocumentPageListResponse:
    result = service.list_document_pages(document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


@router.get(
    "/documents/{document_id}/pages/{page_number}",
    response_model=PageReviewDetail,
)
async def get_page_detail(
    document_id: str,
    page_number: int,
    service: DocumentReviewService = Depends(get_review_service),
) -> PageReviewDetail:
    result = service.get_page_detail(document_id, page_number)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page_number} not found for document {document_id}.",
        )
    return result


@router.get("/documents/{document_id}/pages/{page_number}/image")
async def get_page_image(
    document_id: str,
    page_number: int,
    service: DocumentReviewService = Depends(get_review_service),
) -> FileResponse:
    image_path = service.get_page_image_path(document_id, page_number)
    if image_path is None:
        raise HTTPException(
            status_code=404,
            detail="Page image not available for this page.",
        )
    media_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    return FileResponse(
        path=str(image_path),
        media_type=media_type,
        filename=image_path.name,
    )


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------


@router.post(
    "/documents/{document_id}/annotations",
    response_model=AnnotationRecord,
    status_code=201,
)
async def create_annotation(
    document_id: str,
    request: CreateAnnotationRequest,
    service: AnnotationService = Depends(get_annotation_service),
) -> AnnotationRecord:
    if request.document_id != document_id:
        raise HTTPException(
            status_code=400,
            detail="document_id in body must match URL path.",
        )
    result = service.create_annotation(request)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


@router.get(
    "/documents/{document_id}/annotations",
    response_model=AnnotationListResponse,
)
async def list_document_annotations(
    document_id: str,
    service: AnnotationService = Depends(get_annotation_service),
) -> AnnotationListResponse:
    result = service.list_document_annotations(document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


@router.get(
    "/documents/{document_id}/pages/{page_number}/annotations",
    response_model=PageAnnotationListResponse,
)
async def list_page_annotations(
    document_id: str,
    page_number: int,
    service: AnnotationService = Depends(get_annotation_service),
) -> PageAnnotationListResponse:
    result = service.list_page_annotations(document_id, page_number)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


@router.get(
    "/annotations/{annotation_id}",
    response_model=AnnotationRecord,
)
async def get_annotation(
    annotation_id: str,
    service: AnnotationService = Depends(get_annotation_service),
) -> AnnotationRecord:
    result = service.get_annotation(annotation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Annotation not found.")
    return result


@router.patch(
    "/annotations/{annotation_id}",
    response_model=AnnotationRecord,
)
async def update_annotation(
    annotation_id: str,
    request: UpdateAnnotationRequest,
    service: AnnotationService = Depends(get_annotation_service),
) -> AnnotationRecord:
    result = service.update_annotation(annotation_id, request)
    if result is None:
        raise HTTPException(status_code=404, detail="Annotation not found.")
    return result


@router.delete(
    "/annotations/{annotation_id}",
    status_code=204,
)
async def delete_annotation(
    annotation_id: str,
    service: AnnotationService = Depends(get_annotation_service),
) -> None:
    if not service.delete_annotation(annotation_id):
        raise HTTPException(status_code=404, detail="Annotation not found.")


# ---------------------------------------------------------------------------
# Word-level extraction
# ---------------------------------------------------------------------------


@router.get(
    "/documents/{document_id}/pages/{page_number}/words",
    response_model=PageWordsResponse,
)
async def get_page_words(
    document_id: str,
    page_number: int,
    service: AnnotationService = Depends(get_annotation_service),
) -> PageWordsResponse:
    result = service.get_page_words(document_id, page_number)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page_number} not found for document {document_id}.",
        )
    return result
