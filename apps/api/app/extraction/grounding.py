"""Grounding service — maps extraction results to source document artifacts.

This service bridges extracted field values back to the document's ingestion
artifacts: page records, text blocks, and geometry when genuinely available.
It does NOT fabricate bounding boxes or claim precision beyond what exists.
"""

from __future__ import annotations

from sqlmodel import Session, select

from casegraph_agent_sdk.extraction import (
    ExtractedFieldResult,
    GroundingReference,
)
from casegraph_agent_sdk.ingestion import (
    BoundingBoxArtifact,
    CoordinateSpace,
    GeometrySource,
    PolygonArtifact,
    PolygonPoint,
    TextBlockArtifact,
)

from app.review.models import PageRecord


class GroundingService:
    """Attach source evidence references to extracted field values.

    Grounding strategy:
    1. For each extracted field value, search page records for text overlap.
    2. If a matching text block is found, attach the block reference.
    3. If the matching block has genuine geometry (bbox/polygon), attach it.
    4. Never fabricate geometry — only attach what the extractor produced.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def attach_grounding(
        self,
        document_id: str,
        fields: list[ExtractedFieldResult],
    ) -> list[ExtractedFieldResult]:
        """Enrich extracted fields with grounding references from document artifacts."""
        page_records = self._get_page_records(document_id)
        if not page_records:
            return fields

        # Build a flat index of text blocks across all pages
        block_index = _build_block_index(document_id, page_records)

        for field in fields:
            if not field.is_present or field.value is None:
                continue

            search_text = _field_value_to_search_text(field.value)
            if not search_text:
                continue

            refs = _find_grounding_references(search_text, block_index)
            if refs:
                field.grounding = refs

        return fields

    def _get_page_records(self, document_id: str) -> list[PageRecord]:
        statement = (
            select(PageRecord)
            .where(PageRecord.document_id == document_id)
            .order_by(PageRecord.page_number)
        )
        return list(self._session.exec(statement).all())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _BlockEntry:
    """Pre-indexed text block for grounding lookup."""

    __slots__ = (
        "document_id",
        "page_number",
        "block_id",
        "text",
        "geometry_source",
        "coordinate_space",
        "bbox",
        "polygon",
    )

    def __init__(
        self,
        *,
        document_id: str,
        page_number: int,
        block_id: str,
        text: str,
        geometry_source: GeometrySource | None,
        coordinate_space: CoordinateSpace | None,
        bbox: BoundingBoxArtifact | None,
        polygon: PolygonArtifact | None,
    ) -> None:
        self.document_id = document_id
        self.page_number = page_number
        self.block_id = block_id
        self.text = text
        self.geometry_source = geometry_source
        self.coordinate_space = coordinate_space
        self.bbox = bbox
        self.polygon = polygon


def _build_block_index(
    document_id: str, page_records: list[PageRecord]
) -> list[_BlockEntry]:
    """Build a flat list of block entries from page records for text matching."""
    entries: list[_BlockEntry] = []
    for pr in page_records:
        geo_source: GeometrySource | None = None
        if pr.geometry_source:
            try:
                geo_source = GeometrySource(pr.geometry_source)
            except ValueError:
                pass

        coord_space: CoordinateSpace | None = None
        if pr.coordinate_space:
            try:
                coord_space = CoordinateSpace(pr.coordinate_space)
            except ValueError:
                pass

        for block_dict in pr.text_blocks_json:
            block_text = block_dict.get("text", "")
            if not block_text:
                continue

            bbox = _parse_bbox(block_dict.get("bbox"))
            polygon = _parse_polygon(block_dict.get("polygon"))

            block_geo = None
            if block_dict.get("geometry_source"):
                try:
                    block_geo = GeometrySource(block_dict["geometry_source"])
                except ValueError:
                    block_geo = geo_source
            else:
                block_geo = geo_source

            entries.append(
                _BlockEntry(
                    document_id=document_id,
                    page_number=pr.page_number,
                    block_id=block_dict.get("block_id", ""),
                    text=block_text,
                    geometry_source=block_geo,
                    coordinate_space=coord_space,
                    bbox=bbox,
                    polygon=polygon,
                )
            )

    return entries


def _parse_bbox(data: dict | None) -> BoundingBoxArtifact | None:
    if not data or "x0" not in data:
        return None
    try:
        return BoundingBoxArtifact(
            x0=float(data["x0"]),
            y0=float(data["y0"]),
            x1=float(data["x1"]),
            y1=float(data["y1"]),
            coordinate_space=CoordinateSpace(data["coordinate_space"]),
        )
    except (ValueError, KeyError, TypeError):
        return None


def _parse_polygon(data: dict | None) -> PolygonArtifact | None:
    if not data or "points" not in data:
        return None
    try:
        points = [PolygonPoint(x=float(p["x"]), y=float(p["y"])) for p in data["points"]]
        if len(points) < 3:
            return None
        return PolygonArtifact(
            points=points,
            coordinate_space=CoordinateSpace(data["coordinate_space"]),
        )
    except (ValueError, KeyError, TypeError):
        return None


def _field_value_to_search_text(value: object) -> str:
    """Convert a field value to a search string."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    # For complex types (lists, dicts), skip text-based grounding
    return ""


def _find_grounding_references(
    search_text: str,
    block_index: list[_BlockEntry],
) -> list[GroundingReference]:
    """Find text blocks that contain the extracted value text."""
    if not search_text or len(search_text) < 2:
        return []

    normalized = search_text.lower().strip()
    refs: list[GroundingReference] = []
    seen_blocks: set[str] = set()

    for entry in block_index:
        if normalized in entry.text.lower():
            if entry.block_id in seen_blocks:
                continue
            seen_blocks.add(entry.block_id)

            refs.append(
                GroundingReference(
                    document_id=entry.document_id,
                    page_number=entry.page_number,
                    block_id=entry.block_id if entry.block_id else None,
                    text_span=search_text,
                    geometry_source=entry.geometry_source,
                    coordinate_space=entry.coordinate_space,
                    bbox=entry.bbox,
                    polygon=entry.polygon,
                    grounding_method="text_block_match",
                )
            )

            # Limit to 3 references per field (first occurrences)
            if len(refs) >= 3:
                break

    return refs
