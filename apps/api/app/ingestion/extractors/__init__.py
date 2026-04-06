"""Extraction adapters for document ingestion."""

from app.ingestion.extractors.ocr import (
    OcrExtractionAdapter,
    ocr_runtime_available,
    scanned_pdf_ocr_runtime_available,
)
from app.ingestion.extractors.readable_pdf import (
    ReadablePdfExtractor,
    readable_pdf_runtime_available,
)

__all__ = [
    "OcrExtractionAdapter",
    "ReadablePdfExtractor",
    "ocr_runtime_available",
    "readable_pdf_runtime_available",
    "scanned_pdf_ocr_runtime_available",
]
