"""Case/workspace foundation module."""

from app.cases.service import CaseService, CaseServiceError

__all__ = ["CaseService", "CaseServiceError"]