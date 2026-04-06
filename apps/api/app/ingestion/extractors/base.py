"""Base types for extraction adapters."""

from __future__ import annotations

from abc import ABC


class ExtractorError(Exception):
    """Runtime exception for extraction adapters (not an SDK contract type)."""

    def __init__(self, *, code: str, message: str, recoverable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.recoverable = recoverable


class ExtractorDependencyError(ExtractorError):
    pass


class ExtractorExecutionError(ExtractorError):
    pass


class ExtractionAdapter(ABC):
    extractor_name: str
