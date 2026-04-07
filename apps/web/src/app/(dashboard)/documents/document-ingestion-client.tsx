"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  DocumentsCapabilitiesResponse,
  IngestionModePreference,
  IngestionResult,
  IngestionResultSummary,
  PageArtifact,
} from "@casegraph/agent-sdk";

import {
  fetchDocumentCapabilities,
  ingestDocument,
} from "@/lib/documents-api";
import { fetchDocumentsList } from "@/lib/review-api";

const MODE_OPTIONS: Array<{ value: IngestionModePreference; label: string }> = [
  { value: "auto", label: "Auto" },
  { value: "readable_pdf", label: "Readable PDF" },
  { value: "scanned_pdf", label: "Scanned PDF" },
  { value: "image", label: "Image" },
];

export default function DocumentIngestionClient() {
  const [capabilities, setCapabilities] =
    useState<DocumentsCapabilitiesResponse | null>(null);
  const [capabilitiesError, setCapabilitiesError] = useState<string | null>(null);
  const [capabilitiesLoading, setCapabilitiesLoading] = useState(true);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [mode, setMode] = useState<IngestionModePreference>("auto");
  const [ocrEnabled, setOcrEnabled] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestionResult | null>(null);

  const [documents, setDocuments] = useState<IngestionResultSummary[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [showCapabilities, setShowCapabilities] = useState(false);

  function loadDocuments() {
    setDocumentsLoading(true);
    fetchDocumentsList({ limit: 100 })
      .then((res) => setDocuments(res.documents))
      .catch(() => setDocuments([]))
      .finally(() => setDocumentsLoading(false));
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadCapabilities() {
      setCapabilitiesLoading(true);
      setCapabilitiesError(null);

      try {
        const response = await fetchDocumentCapabilities();
        if (!cancelled) {
          setCapabilities(response);
        }
      } catch (error) {
        if (!cancelled) {
          setCapabilitiesError(
            error instanceof Error
              ? error.message
              : "Unable to load capabilities.",
          );
        }
      } finally {
        if (!cancelled) {
          setCapabilitiesLoading(false);
        }
      }
    }

    void loadCapabilities();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setSubmitError("Choose a local PDF or image file before submitting.");
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      const response = await ingestDocument(selectedFile, {
        mode,
        ocrEnabled,
      });
      setResult(response);
      loadDocuments();
    } catch (error) {
      setResult(null);
      setSubmitError(
        error instanceof Error ? error.message : "Unable to process document. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <header style={{ marginBottom: "2rem" }}>
          <p style={breadcrumbStyle}>Documents</p>
          <h1 style={titleStyle}>Documents</h1>
          <p style={subtitleStyle}>
            Upload and review your documents.
          </p>
        </header>

        <section style={panelStyle}>
          <h2 style={sectionTitleStyle}>Submit Document</h2>
          <form onSubmit={handleSubmit} style={formStyle}>
            <label style={fieldStyle}>
              <span style={fieldLabelStyle}>Local file</span>
              <input
                type="file"
                accept=".pdf,image/*"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  setSelectedFile(file);
                }}
                style={inputStyle}
              />
            </label>

            <label style={fieldStyle}>
              <span style={fieldLabelStyle}>Requested mode</span>
              <select
                value={mode}
                onChange={(event) => {
                  setMode(event.target.value as IngestionModePreference);
                }}
                style={selectStyle}
              >
                {MODE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label style={checkboxRowStyle}>
              <input
                type="checkbox"
                checked={ocrEnabled}
                onChange={(event) => {
                  setOcrEnabled(event.target.checked);
                }}
              />
              <span>
                Enable OCR capability for scanned PDFs and images.
              </span>
            </label>

            <div style={actionsStyle}>
              <button type="submit" disabled={submitting} style={buttonStyle}>
                {submitting ? "Uploading…" : "Upload Document"}
              </button>
              <span style={helperTextStyle}>
                OCR-enabled modes require the checkbox above. Auto mode only uses
                OCR when the file appears image-based and OCR is enabled.
              </span>
            </div>
          </form>

          {submitError ? <div style={errorPanelStyle}>{submitError}</div> : null}
        </section>

        <section style={{ ...panelStyle, marginTop: "1rem" }}>
          <button
            type="button"
            onClick={() => setShowCapabilities((prev) => !prev)}
            style={{ background: "none", border: "none", cursor: "pointer", padding: 0, width: "100%", textAlign: "left" }}
          >
            <h2 style={sectionTitleStyle}>{showCapabilities ? "Current Capabilities ▾" : "Current Capabilities ▸"}</h2>
          </button>
          {showCapabilities && (
            <>
              {capabilitiesLoading ? (
                <div style={mutedPanelStyle}>Loading capabilities...</div>
              ) : capabilitiesError ? (
                <div style={errorPanelStyle}>{capabilitiesError}</div>
              ) : capabilities ? (
                <>
              <div style={gridStyle}>
                {capabilities.modes.map((capability) => (
                  <article key={capability.mode} style={cardStyle}>
                    <div style={cardHeaderRowStyle}>
                      <h3 style={cardTitleStyle}>{capability.mode}</h3>
                      <span
                        style={{
                          ...statusPillStyle,
                          backgroundColor: capability.supported
                            ? "#e8f7ef"
                            : "#fff1f2",
                          color: capability.supported ? "#166534" : "#9f1239",
                        }}
                      >
                        {capability.supported ? "ready" : "not ready"}
                      </span>
                    </div>
                    <p style={cardMetaStyle}>
                      extractor: {capability.extractor_name ?? "none"}
                    </p>
                    <p style={cardMetaStyle}>
                      requires OCR: {capability.requires_ocr ? "yes" : "no"}
                    </p>
                    <ul style={listStyle}>
                      {capability.notes.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>

              <h3 style={{ ...sectionTitleStyle, marginTop: "1.5rem" }}>
                Current limitations
              </h3>
              <ul style={listStyle}>
                {capabilities.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          ) : null}
            </>
          )}
        </section>

        {result ? (
          <section style={{ ...panelStyle, marginTop: "1rem" }}>
            <h2 style={sectionTitleStyle}>Latest Result</h2>
            <div style={summaryGridStyle}>
              <SummaryItem label="Document ID" value={result.summary.document_id} />
              <SummaryItem label="Status" value={result.summary.status} />
              <SummaryItem label="Requested Mode" value={result.summary.requested_mode} />
              <SummaryItem label="Resolved Mode" value={result.summary.resolved_mode} />
              <SummaryItem label="Extractor" value={result.summary.extractor_name ?? "none"} />
              <SummaryItem
                label="Pages"
                value={String(result.summary.page_count)}
              />
              <SummaryItem
                label="Text Blocks"
                value={String(result.summary.text_block_count)}
              />
              <SummaryItem
                label="Geometry"
                value={result.summary.geometry_present ? "present" : "none"}
              />
              <SummaryItem
                label="Geometry Sources"
                value={
                  result.summary.geometry_sources.length > 0
                    ? result.summary.geometry_sources.join(", ")
                    : "none"
                }
              />
            </div>

            {result.errors.length > 0 ? (
              <div style={{ ...errorPanelStyle, marginTop: "1rem" }}>
                {result.errors.map((error) => (
                  <p key={`${error.code}-${error.message}`} style={errorLineStyle}>
                    {error.code}: {error.message}
                  </p>
                ))}
              </div>
            ) : null}

            {result.output ? (
              <>
                <div style={{ ...mutedPanelStyle, marginTop: "1rem" }}>
                  <strong>Source file:</strong> {result.output.source_file.filename}
                  {" · "}
                  {result.output.source_file.classification}
                  {" · "}
                  {result.output.source_file.content_type ?? "unknown mime"}
                </div>

                <h3 style={{ ...sectionTitleStyle, marginTop: "1.5rem" }}>
                  Page Metadata
                </h3>
                <div style={pageListStyle}>
                  {result.output.pages.map((page) => (
                    <PageCard key={page.page_number} page={page} />
                  ))}
                </div>
              </>
            ) : null}
          </section>
        ) : null}

        {/* Persisted documents list */}
        <section style={{ ...panelStyle, marginTop: "1rem" }}>
          <h2 style={sectionTitleStyle}>Persisted Documents</h2>
          {documentsLoading ? (
            <div style={mutedPanelStyle}>Loading documents...</div>
          ) : documents.length === 0 ? (
            <div style={mutedPanelStyle}>No documents ingested yet.</div>
          ) : (
            <div style={pageListStyle}>
              {documents.map((doc) => (
                <article key={doc.document_id} style={cardStyle}>
                  <div style={cardHeaderRowStyle}>
                    <h3 style={cardTitleStyle}>{doc.source_file.filename}</h3>
                    <span
                      style={{
                        ...statusPillStyle,
                        backgroundColor:
                          doc.status === "completed" ? "#e8f7ef" : "#fff1f2",
                        color:
                          doc.status === "completed" ? "#166534" : "#9f1239",
                      }}
                    >
                      {doc.status}
                    </span>
                  </div>
                  <p style={cardMetaStyle}>
                    mode: {doc.resolved_mode} · pages: {doc.page_count} ·
                    blocks: {doc.text_block_count}
                    {doc.geometry_present ? " · geometry" : ""}
                  </p>
                  <p style={{ ...cardMetaStyle, wordBreak: "break-all" }}>
                    {doc.document_id}
                  </p>
                  {doc.status === "completed" && (
                    <Link
                      href={`/documents/${doc.document_id}`}
                      style={reviewLinkStyle}
                    >
                      Open Review →
                    </Link>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div style={summaryItemStyle}>
      <span style={summaryLabelStyle}>{label}</span>
      <span style={summaryValueStyle}>{value}</span>
    </div>
  );
}

function PageCard({ page }: { page: PageArtifact }) {
  const textPreview = page.text.length > 280 ? `${page.text.slice(0, 280)}...` : page.text;

  return (
    <article style={cardStyle}>
      <div style={cardHeaderRowStyle}>
        <h3 style={cardTitleStyle}>Page {page.page_number}</h3>
        <span style={statusPillStyle}>{page.geometry_source ?? "no geometry source"}</span>
      </div>
      <p style={cardMetaStyle}>
        size: {page.width ?? "?"} × {page.height ?? "?"} {page.coordinate_space ?? ""}
      </p>
      <p style={cardMetaStyle}>text blocks: {page.text_blocks.length}</p>
      <p style={textPreviewStyle}>{textPreview || "No extracted text."}</p>
    </article>
  );
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2.5rem 1.25rem 3rem",
  backgroundColor: "#f5f7fa",
};

const containerStyle: CSSProperties = {
  maxWidth: "1120px",
  margin: "0 auto",
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

const panelStyle: CSSProperties = {
  padding: "1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "18px",
  backgroundColor: "#ffffff",
  boxShadow: "0 16px 32px rgba(15, 23, 42, 0.06)",
};

const mutedPanelStyle: CSSProperties = {
  padding: "1rem 1.1rem",
  border: "1px solid #d7dee8",
  borderRadius: "14px",
  backgroundColor: "#f8fafc",
  color: "#475569",
};

const errorPanelStyle: CSSProperties = {
  padding: "1rem 1.1rem",
  border: "1px solid #fecaca",
  borderRadius: "14px",
  backgroundColor: "#fff1f2",
  color: "#9f1239",
  marginTop: "1rem",
};

const formStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.4rem",
};

const fieldLabelStyle: CSSProperties = {
  fontSize: "0.9rem",
  fontWeight: 600,
  color: "#334155",
};

const inputStyle: CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "0.9rem",
  border: "1px solid #cbd5e1",
  borderRadius: "12px",
  backgroundColor: "#ffffff",
};

const selectStyle: CSSProperties = {
  ...inputStyle,
  appearance: "none",
};

const checkboxRowStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.65rem",
  color: "#334155",
};

const actionsStyle: CSSProperties = {
  display: "flex",
  gap: "0.75rem",
  alignItems: "center",
  flexWrap: "wrap",
};

const buttonStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0.85rem 1.1rem",
  borderRadius: "999px",
  border: "none",
  backgroundColor: "#102033",
  color: "#ffffff",
  fontWeight: 600,
  cursor: "pointer",
};

const helperTextStyle: CSSProperties = {
  color: "#64748b",
  fontSize: "0.9rem",
  lineHeight: 1.5,
};

const sectionTitleStyle: CSSProperties = {
  margin: "0 0 1rem",
  fontSize: "1.05rem",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "#475569",
};

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  gap: "1rem",
};

const cardStyle: CSSProperties = {
  padding: "1rem",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  backgroundColor: "#ffffff",
};

const cardHeaderRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "center",
};

const cardTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.05rem",
  color: "#102033",
};

const cardMetaStyle: CSSProperties = {
  margin: "0.4rem 0 0",
  color: "#64748b",
  fontFamily: "monospace",
  fontSize: "0.85rem",
};

const statusPillStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  borderRadius: "999px",
  padding: "0.25rem 0.6rem",
  backgroundColor: "#f8fafc",
  color: "#475569",
  fontSize: "0.8rem",
  fontFamily: "monospace",
};

const listStyle: CSSProperties = {
  margin: "0.75rem 0 0 1.2rem",
  padding: 0,
  color: "#475569",
  lineHeight: 1.7,
};

const summaryGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "0.75rem",
};

const summaryItemStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  border: "1px solid #d7dee8",
  borderRadius: "14px",
  backgroundColor: "#f8fafc",
  display: "grid",
  gap: "0.25rem",
};

const summaryLabelStyle: CSSProperties = {
  fontSize: "0.75rem",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "#64748b",
};

const summaryValueStyle: CSSProperties = {
  color: "#102033",
  fontWeight: 600,
  wordBreak: "break-word",
};

const errorLineStyle: CSSProperties = {
  margin: 0,
  lineHeight: 1.6,
};

const pageListStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
};

const textPreviewStyle: CSSProperties = {
  margin: "0.8rem 0 0",
  color: "#475569",
  lineHeight: 1.6,
  whiteSpace: "pre-wrap",
};

const reviewLinkStyle: CSSProperties = {
  display: "inline-flex",
  marginTop: "0.6rem",
  color: "#102033",
  fontWeight: 600,
  fontSize: "0.88rem",
  textDecoration: "none",
};
