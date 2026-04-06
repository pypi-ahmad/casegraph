"""Response schemas for document ingestion endpoints.

All contracts are imported from the shared SDK.
"""

from casegraph_agent_sdk import (
    DocumentDetailResponse,
    DocumentPageSummary,
    DocumentPagesResponse,
    DocumentRegistryListResponse,
    DocumentsCapabilitiesResponse,
    IngestionModeCapability,
)

__all__ = [
    "DocumentDetailResponse",
    "DocumentPageSummary",
    "DocumentPagesResponse",
    "DocumentRegistryListResponse",
    "DocumentsCapabilitiesResponse",
    "IngestionModeCapability",
]
