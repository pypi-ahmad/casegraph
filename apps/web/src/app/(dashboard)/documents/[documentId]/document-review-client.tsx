"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import type {
  DocumentReviewResponse,
  PageReviewDetail,
  PageReviewSummary,
  TextBlockArtifact,
} from "@casegraph/agent-sdk";

import {
  fetchDocumentReview,
  fetchPageDetail,
  getPageImageUrl,
} from "@/lib/review-api";

export default function DocumentReviewClient({
  documentId,
}: {
  documentId: string;
}) {
  const [review, setReview] = useState<DocumentReviewResponse | null>(null);
  const [page, setPage] = useState<PageReviewDetail | null>(null);
  const [currentPageNumber, setCurrentPageNumber] = useState(1);
  const [showOverlays, setShowOverlays] = useState(true);
  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchDocumentReview(documentId)
      .then((data) => {
        if (!cancelled) {
          setReview(data);
          setCurrentPageNumber(data.pages.length > 0 ? data.pages[0].page_number : 1);
        }
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Unable to load document.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [documentId]);

  useEffect(() => {
    if (!review || review.pages.length === 0) return;

    let cancelled = false;
    setPageLoading(true);

    fetchPageDetail(documentId, currentPageNumber)
      .then((data) => {
        if (!cancelled) setPage(data);
      })
      .catch(() => {
        if (!cancelled) setPage(null);
      })
      .finally(() => {
        if (!cancelled) setPageLoading(false);
      });

    return () => { cancelled = true; };
  }, [documentId, currentPageNumber, review]);

  if (loading) {
    return (
      <main style={pageStyle}>
        <section style={containerStyle}>
          <div style={panelStyle}>Loading document review...</div>
        </section>
      </main>
    );
  }

  if (error || !review) {
    return (
      <main style={pageStyle}>
        <section style={containerStyle}>
          <div style={errorPanelStyle}>{error ?? "Document not found."}</div>
        </section>
      </main>
    );
  }

  const doc = review.document;
  const caps = review.capabilities;

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <Link href="/documents" style={backLinkStyle}>
          Back to documents
        </Link>

        <header style={{ marginBottom: "1.5rem" }}>
          <p style={breadcrumbStyle}>Documents / Review</p>
          <h1 style={titleStyle}>{doc.source_file.filename}</h1>
          <p style={subtitleStyle}>
            Document review workspace — inspect pages, text blocks, and overlay
            geometry where available.
          </p>
        </header>

        {/* Document metadata */}
        <section style={cardStyle}>
          <h2 style={sectionTitleStyle}>Document Metadata</h2>
          <div style={metaGridStyle}>
            <MetaItem label="Document ID" value={doc.document_id} />
            <MetaItem label="Status" value={doc.status} />
            <MetaItem label="Ingestion Mode" value={doc.ingestion_mode} />
            <MetaItem label="Extractor" value={doc.extractor_name ?? "none"} />
            <MetaItem label="Pages" value={String(doc.page_count)} />
            <MetaItem label="Text Blocks" value={String(doc.text_block_count)} />
            <MetaItem
              label="Geometry"
              value={doc.geometry_available ? "available" : "none"}
            />
            <MetaItem
              label="Geometry Sources"
              value={
                doc.geometry_sources.length > 0
                  ? doc.geometry_sources.join(", ")
                  : "none"
              }
            />
            <MetaItem
              label="Page Images"
              value={doc.page_images_available ? "available" : "not available"}
            />
            <MetaItem
              label="Overlay Sources"
              value={
                caps.overlay_source_types.length > 0
                  ? caps.overlay_source_types.join(", ")
                  : "none"
              }
            />
            <MetaItem
              label="Linked Cases"
              value={
                doc.linked_case_ids.length > 0
                  ? doc.linked_case_ids.join(", ")
                  : "none"
              }
            />
            <MetaItem
              label="File"
              value={`${doc.source_file.content_type ?? "unknown"} · ${doc.source_file.size_bytes ?? "?"} bytes`}
            />
          </div>

          {caps.limitations.length > 0 && (
            <div style={limitationsPanelStyle}>
              <strong>Current limitations for this document:</strong>
              <ul style={limitationsListStyle}>
                {caps.limitations.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </div>
          )}
        </section>

        {/* Page viewer area */}
        {review.pages.length === 0 ? (
          <section style={{ ...cardStyle, marginTop: "1rem" }}>
            <p style={mutedTextStyle}>
              No page artifacts were produced during ingestion. There is nothing
              to review.
            </p>
          </section>
        ) : (
          <div style={viewerLayoutStyle}>
            {/* Page list sidebar */}
            <aside style={sidebarStyle}>
              <h3 style={sidebarTitleStyle}>Pages</h3>
              {review.pages.map((p) => (
                <PageListItem
                  key={p.page_number}
                  page={p}
                  active={p.page_number === currentPageNumber}
                  onClick={() => setCurrentPageNumber(p.page_number)}
                />
              ))}
            </aside>

            {/* Main viewer */}
            <section style={viewerMainStyle}>
              <header style={viewerHeaderStyle}>
                <span style={viewerPageLabelStyle}>
                  Page {currentPageNumber} of {review.pages.length}
                </span>
                {caps.can_show_geometry && (
                  <label style={toggleLabelStyle}>
                    <input
                      type="checkbox"
                      checked={showOverlays}
                      onChange={(e) => setShowOverlays(e.target.checked)}
                    />
                    Show overlays
                  </label>
                )}
              </header>

              {pageLoading ? (
                <div style={panelStyle}>Loading page...</div>
              ) : page ? (
                <>
                  <PageViewer
                    documentId={documentId}
                    page={page}
                    showOverlays={showOverlays}
                  />
                  <TextBlockInspector blocks={page.text_blocks} />
                </>
              ) : (
                <div style={panelStyle}>
                  Page {currentPageNumber} could not be loaded.
                </div>
              )}
            </section>
          </div>
        )}
      </section>
    </main>
  );
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                      */
/* ------------------------------------------------------------------ */

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div style={metaItemStyle}>
      <span style={metaLabelStyle}>{label}</span>
      <span style={metaValueStyle}>{value}</span>
    </div>
  );
}

function PageListItem({
  page,
  active,
  onClick,
}: {
  page: PageReviewSummary;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        ...pageListItemStyle,
        backgroundColor: active ? "#e0e7ff" : "#ffffff",
        borderColor: active ? "#6366f1" : "#d7dee8",
      }}
    >
      <span style={pageListItemTitleStyle}>Page {page.page_number}</span>
      <span style={pageListItemMetaStyle}>
        {page.text_block_count} blocks
        {page.has_geometry ? " · geometry" : ""}
        {page.has_page_image ? " · image" : ""}
      </span>
    </button>
  );
}

function PageViewer({
  documentId,
  page,
  showOverlays,
}: {
  documentId: string;
  page: PageReviewDetail;
  showOverlays: boolean;
}) {
  const hasImage = page.has_page_image;
  const hasGeometry =
    showOverlays &&
    page.text_blocks.some((b) => b.bbox !== null || b.polygon !== null);

  if (hasImage) {
    return (
      <div style={imageContainerStyle}>
        <img
          src={getPageImageUrl(documentId, page.page_number)}
          alt={`Page ${page.page_number}`}
          style={pageImageStyle}
        />
        {hasGeometry && page.dimensions.width && page.dimensions.height && (
          <svg
            viewBox={`0 0 ${page.dimensions.width} ${page.dimensions.height}`}
            style={svgOverlayStyle}
            preserveAspectRatio="none"
          >
            {page.text_blocks.map((block) => (
              <BlockOverlay key={block.block_id} block={block} />
            ))}
          </svg>
        )}
      </div>
    );
  }

  // No page image — show text-based view
  return (
    <div style={textViewerStyle}>
      <div style={textViewerHeaderStyle}>
        <span style={mutedTextStyle}>
          No page image available —{" "}
          {page.geometry_source ?? "no geometry source"}
        </span>
        {page.dimensions.width && page.dimensions.height && (
          <span style={mutedTextStyle}>
            {page.dimensions.width} × {page.dimensions.height}{" "}
            {page.dimensions.coordinate_space ?? ""}
          </span>
        )}
      </div>
      <pre style={textContentStyle}>
        {page.text || "No extracted text on this page."}
      </pre>
    </div>
  );
}

function BlockOverlay({ block }: { block: TextBlockArtifact }) {
  if (block.polygon && block.polygon.points.length >= 3) {
    const pointsStr = block.polygon.points
      .map((p) => `${p.x},${p.y}`)
      .join(" ");
    return (
      <polygon
        points={pointsStr}
        fill="rgba(59, 130, 246, 0.08)"
        stroke="rgba(59, 130, 246, 0.6)"
        strokeWidth="1"
      >
        <title>
          {block.block_id}
          {block.confidence != null
            ? ` (confidence: ${(block.confidence * 100).toFixed(1)}%)`
            : ""}
        </title>
      </polygon>
    );
  }

  if (block.bbox) {
    const w = block.bbox.x1 - block.bbox.x0;
    const h = block.bbox.y1 - block.bbox.y0;
    return (
      <rect
        x={block.bbox.x0}
        y={block.bbox.y0}
        width={w}
        height={h}
        fill="rgba(59, 130, 246, 0.08)"
        stroke="rgba(59, 130, 246, 0.6)"
        strokeWidth="1"
      >
        <title>
          {block.block_id}
          {block.confidence != null
            ? ` (confidence: ${(block.confidence * 100).toFixed(1)}%)`
            : ""}
        </title>
      </rect>
    );
  }

  return null;
}

function TextBlockInspector({ blocks }: { blocks: TextBlockArtifact[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (blocks.length === 0) {
    return (
      <div style={{ ...panelStyle, marginTop: "1rem" }}>
        No text blocks on this page.
      </div>
    );
  }

  return (
    <section style={{ ...cardStyle, marginTop: "1rem" }}>
      <h3 style={sectionTitleStyle}>
        Text Blocks ({blocks.length})
      </h3>
      <div style={blockListStyle}>
        {blocks.map((block) => {
          const isExpanded = expanded === block.block_id;
          return (
            <article key={block.block_id} style={blockItemStyle}>
              <button
                type="button"
                onClick={() =>
                  setExpanded(isExpanded ? null : block.block_id)
                }
                style={blockHeaderButtonStyle}
              >
                <span style={blockIdStyle}>{block.block_id}</span>
                <span style={blockMetaBadgeStyle}>
                  {block.geometry_source}
                  {block.confidence != null &&
                    ` · ${(block.confidence * 100).toFixed(1)}%`}
                </span>
              </button>
              {isExpanded && (
                <div style={blockDetailStyle}>
                  <p style={blockTextStyle}>
                    {block.text || "(empty)"}
                  </p>
                  {block.bbox && (
                    <p style={blockCoordStyle}>
                      bbox: ({block.bbox.x0.toFixed(1)},{" "}
                      {block.bbox.y0.toFixed(1)}) → ({block.bbox.x1.toFixed(1)},{" "}
                      {block.bbox.y1.toFixed(1)}) [{block.bbox.coordinate_space}]
                    </p>
                  )}
                  {block.polygon && (
                    <p style={blockCoordStyle}>
                      polygon: {block.polygon.points.length} points [
                      {block.polygon.coordinate_space}]
                    </p>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Styles                                                              */
/* ------------------------------------------------------------------ */

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2.5rem 1.25rem 3rem",
  backgroundColor: "#f5f7fa",
};

const containerStyle: CSSProperties = {
  maxWidth: "1280px",
  margin: "0 auto",
};

const backLinkStyle: CSSProperties = {
  display: "inline-flex",
  marginBottom: "1rem",
  color: "#102033",
  textDecoration: "none",
  fontWeight: 600,
};

const breadcrumbStyle: CSSProperties = {
  margin: 0,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  fontSize: "0.8rem",
  color: "#64748b",
};

const titleStyle: CSSProperties = {
  margin: "0.5rem 0 0",
  fontSize: "2.2rem",
  color: "#102033",
};

const subtitleStyle: CSSProperties = {
  maxWidth: "780px",
  color: "#55657a",
  lineHeight: 1.6,
};

const cardStyle: CSSProperties = {
  padding: "1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  backgroundColor: "#ffffff",
};

const panelStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  border: "1px solid #d7dee8",
  borderRadius: "12px",
  backgroundColor: "#f8fafc",
  color: "#334155",
};

const errorPanelStyle: CSSProperties = {
  ...panelStyle,
  borderColor: "#ef4444",
  backgroundColor: "#fff1f2",
  color: "#991b1b",
};

const sectionTitleStyle: CSSProperties = {
  margin: "0 0 1rem",
  fontSize: "1.05rem",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "#475569",
};

const metaGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  gap: "0.75rem",
};

const metaItemStyle: CSSProperties = {
  padding: "0.7rem 0.85rem",
  border: "1px solid #d7dee8",
  borderRadius: "12px",
  backgroundColor: "#f8fafc",
  display: "grid",
  gap: "0.2rem",
};

const metaLabelStyle: CSSProperties = {
  fontSize: "0.72rem",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "#64748b",
};

const metaValueStyle: CSSProperties = {
  color: "#102033",
  fontWeight: 600,
  wordBreak: "break-word",
  fontSize: "0.88rem",
};

const limitationsPanelStyle: CSSProperties = {
  marginTop: "1rem",
  padding: "0.9rem 1rem",
  border: "1px solid #fde68a",
  borderRadius: "12px",
  backgroundColor: "#fffbeb",
  color: "#92400e",
  fontSize: "0.88rem",
};

const limitationsListStyle: CSSProperties = {
  margin: "0.5rem 0 0 1.2rem",
  padding: 0,
  lineHeight: 1.7,
};

const mutedTextStyle: CSSProperties = {
  color: "#64748b",
  fontSize: "0.85rem",
};

/* Viewer layout */

const viewerLayoutStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "220px 1fr",
  gap: "1rem",
  marginTop: "1rem",
  alignItems: "start",
};

const sidebarStyle: CSSProperties = {
  ...cardStyle,
  padding: "0.75rem",
  position: "sticky",
  top: "1rem",
};

const sidebarTitleStyle: CSSProperties = {
  margin: "0 0 0.75rem",
  fontSize: "0.9rem",
  fontWeight: 600,
  color: "#334155",
};

const viewerMainStyle: CSSProperties = {
  minWidth: 0,
};

const viewerHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "0.75rem",
};

const viewerPageLabelStyle: CSSProperties = {
  fontWeight: 600,
  color: "#102033",
};

const toggleLabelStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.5rem",
  fontSize: "0.88rem",
  color: "#334155",
  cursor: "pointer",
};

/* Page list sidebar items */

const pageListItemStyle: CSSProperties = {
  display: "block",
  width: "100%",
  padding: "0.55rem 0.65rem",
  marginBottom: "0.35rem",
  border: "1px solid #d7dee8",
  borderRadius: "10px",
  cursor: "pointer",
  textAlign: "left",
  background: "none",
  fontFamily: "inherit",
};

const pageListItemTitleStyle: CSSProperties = {
  display: "block",
  fontWeight: 600,
  fontSize: "0.85rem",
  color: "#102033",
};

const pageListItemMetaStyle: CSSProperties = {
  display: "block",
  fontSize: "0.72rem",
  color: "#64748b",
  marginTop: "0.15rem",
};

/* Page image viewer */

const imageContainerStyle: CSSProperties = {
  position: "relative",
  border: "1px solid #d7dee8",
  borderRadius: "12px",
  overflow: "hidden",
  backgroundColor: "#1e293b",
};

const pageImageStyle: CSSProperties = {
  display: "block",
  width: "100%",
  height: "auto",
};

const svgOverlayStyle: CSSProperties = {
  position: "absolute",
  top: 0,
  left: 0,
  width: "100%",
  height: "100%",
  pointerEvents: "none",
};

/* Text-based viewer (no page image) */

const textViewerStyle: CSSProperties = {
  border: "1px solid #d7dee8",
  borderRadius: "12px",
  overflow: "hidden",
};

const textViewerHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  padding: "0.65rem 0.85rem",
  backgroundColor: "#f8fafc",
  borderBottom: "1px solid #d7dee8",
};

const textContentStyle: CSSProperties = {
  margin: 0,
  padding: "1rem",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
  fontSize: "0.85rem",
  color: "#334155",
  lineHeight: 1.7,
  maxHeight: "600px",
  overflow: "auto",
};

/* Text block inspector */

const blockListStyle: CSSProperties = {
  display: "grid",
  gap: "0.5rem",
  maxHeight: "400px",
  overflow: "auto",
};

const blockItemStyle: CSSProperties = {
  border: "1px solid #d7dee8",
  borderRadius: "10px",
  overflow: "hidden",
};

const blockHeaderButtonStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  width: "100%",
  padding: "0.55rem 0.75rem",
  border: "none",
  background: "none",
  cursor: "pointer",
  fontFamily: "inherit",
  textAlign: "left",
};

const blockIdStyle: CSSProperties = {
  fontFamily: "monospace",
  fontSize: "0.8rem",
  color: "#102033",
  fontWeight: 600,
};

const blockMetaBadgeStyle: CSSProperties = {
  fontSize: "0.72rem",
  color: "#64748b",
  fontFamily: "monospace",
};

const blockDetailStyle: CSSProperties = {
  padding: "0.5rem 0.75rem 0.65rem",
  borderTop: "1px solid #e2e8f0",
  backgroundColor: "#f8fafc",
};

const blockTextStyle: CSSProperties = {
  margin: 0,
  fontSize: "0.82rem",
  color: "#334155",
  lineHeight: 1.6,
  whiteSpace: "pre-wrap",
};

const blockCoordStyle: CSSProperties = {
  margin: "0.35rem 0 0",
  fontSize: "0.75rem",
  fontFamily: "monospace",
  color: "#64748b",
};
