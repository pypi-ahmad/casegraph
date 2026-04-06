"""Helpers for safe local upload handling."""

from __future__ import annotations

import hashlib
import mimetypes
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkdtemp

from fastapi import UploadFile

from casegraph_agent_sdk.ingestion import FileTypeClassification, SourceFileMetadata


_SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
_CHUNK_SIZE = 1024 * 1024


@dataclass(slots=True)
class PersistedUpload:
    path: Path
    temp_dir: Path
    metadata: SourceFileMetadata


def _sanitize_filename(filename: str | None) -> str:
    raw_name = Path(filename or "upload.bin").name.strip() or "upload.bin"
    sanitized = _SAFE_FILENAME_PATTERN.sub("_", raw_name)
    return sanitized[:255] or "upload.bin"


def classify_file_type(content_type: str | None, filename: str) -> FileTypeClassification:
    extension = Path(filename).suffix.lower()
    guessed_type = content_type or mimetypes.guess_type(filename)[0] or ""

    if guessed_type == "application/pdf" or extension == ".pdf":
        return FileTypeClassification.PDF

    if guessed_type.startswith("image/") or extension in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
        return FileTypeClassification.IMAGE

    return FileTypeClassification.UNSUPPORTED


async def persist_upload(upload_file: UploadFile) -> PersistedUpload:
    temp_dir = Path(mkdtemp(prefix="casegraph-ingest-"))
    safe_name = _sanitize_filename(upload_file.filename)
    target_path = temp_dir / safe_name
    sha256 = hashlib.sha256()
    size_bytes = 0

    try:
        with target_path.open("wb") as target:
            while True:
                chunk = await upload_file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                target.write(chunk)
                sha256.update(chunk)
                size_bytes += len(chunk)
    finally:
        await upload_file.close()

    content_type = upload_file.content_type or mimetypes.guess_type(safe_name)[0]
    metadata = SourceFileMetadata(
        filename=safe_name,
        content_type=content_type,
        extension=target_path.suffix.lower() or None,
        size_bytes=size_bytes,
        sha256=sha256.hexdigest(),
        classification=classify_file_type(content_type, safe_name),
    )

    return PersistedUpload(path=target_path, temp_dir=temp_dir, metadata=metadata)


def cleanup_upload(persisted: PersistedUpload) -> None:
    shutil.rmtree(persisted.temp_dir, ignore_errors=True)
