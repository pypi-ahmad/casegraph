"""Route handlers for packet assembly, manifest, and export artifacts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlmodel import Session

from casegraph_agent_sdk.packets import (
    PacketArtifactListResponse,
    PacketDetailResponse,
    PacketGenerateRequest,
    PacketGenerateResponse,
    PacketListResponse,
    PacketManifestResponse,
)

from app.packets.errors import PacketServiceError
from app.packets.service import PacketAssemblyService
from app.persistence.database import get_session

router = APIRouter(tags=["packets"])


def _handle(exc: PacketServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _get_service(session: Session = Depends(get_session)) -> PacketAssemblyService:
    return PacketAssemblyService(session)


@router.post("/cases/{case_id}/packets/generate", response_model=PacketGenerateResponse)
async def generate_packet(
    case_id: str,
    body: PacketGenerateRequest | None = None,
    service: PacketAssemblyService = Depends(_get_service),
) -> PacketGenerateResponse:
    try:
        request = body or PacketGenerateRequest()
        return service.generate_packet(
            case_id,
            note=request.note,
            source_mode=request.source_mode,
            reviewed_snapshot_id=request.reviewed_snapshot_id,
        )
    except PacketServiceError as exc:
        raise _handle(exc) from exc


@router.get("/cases/{case_id}/packets", response_model=PacketListResponse)
async def list_packets(
    case_id: str,
    service: PacketAssemblyService = Depends(_get_service),
) -> PacketListResponse:
    try:
        return service.list_packets(case_id)
    except PacketServiceError as exc:
        raise _handle(exc) from exc


@router.get("/packets/{packet_id}", response_model=PacketDetailResponse)
async def get_packet(
    packet_id: str,
    service: PacketAssemblyService = Depends(_get_service),
) -> PacketDetailResponse:
    try:
        return service.get_packet(packet_id)
    except PacketServiceError as exc:
        raise _handle(exc) from exc


@router.get("/packets/{packet_id}/manifest", response_model=PacketManifestResponse)
async def get_manifest(
    packet_id: str,
    service: PacketAssemblyService = Depends(_get_service),
) -> PacketManifestResponse:
    try:
        return service.get_manifest(packet_id)
    except PacketServiceError as exc:
        raise _handle(exc) from exc


@router.get("/packets/{packet_id}/artifacts", response_model=PacketArtifactListResponse)
async def list_artifacts(
    packet_id: str,
    service: PacketAssemblyService = Depends(_get_service),
) -> PacketArtifactListResponse:
    try:
        return service.list_artifacts(packet_id)
    except PacketServiceError as exc:
        raise _handle(exc) from exc


@router.get("/packets/{packet_id}/download/{artifact_id}")
async def download_artifact(
    packet_id: str,
    artifact_id: str,
    service: PacketAssemblyService = Depends(_get_service),
) -> PlainTextResponse:
    try:
        model, content = service.get_artifact_content(packet_id, artifact_id)
        return PlainTextResponse(
            content=content,
            media_type=model.content_type or "text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="{model.filename}"',
            },
        )
    except PacketServiceError as exc:
        raise _handle(exc) from exc
