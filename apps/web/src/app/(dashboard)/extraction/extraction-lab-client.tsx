"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  ExtractionResult,
  ExtractionStrategy,
  ExtractionTemplateMetadata,
  ExtractedFieldResult,
  GroundingReference,
} from "@casegraph/agent-sdk";

import {
  executeExtraction,
  fetchExtractionTemplates,
} from "@/lib/extraction-api";
import { fetchDocumentsList } from "@/lib/review-api";

export default function ExtractionLabClient() {
  const [templates, setTemplates] = useState<ExtractionTemplateMetadata[]>([]);
  const [documents, setDocuments] = useState<Awaited<ReturnType<typeof fetchDocumentsList>>["documents"]>([]);
  const [availableStrategies, setAvailableStrategies] = useState<ExtractionStrategy[]>([]);
  const [backendLimitations, setBackendLimitations] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [selectedDocument, setSelectedDocument] = useState("");
  const [strategy, setStrategy] = useState<ExtractionStrategy>("auto");
  const [provider, setProvider] = useState("openai");
  const [modelId, setModelId] = useState("gpt-4o-mini");
  const [apiKey, setApiKey] = useState("");

  // Result state
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [executing, setExecuting] = useState(false);
  const [executeError, setExecuteError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      fetchExtractionTemplates(),
      fetchDocumentsList({ limit: 100 }),
    ])
      .then(([templatesResp, docsResp]) => {
        if (!cancelled) {
          setTemplates(templatesResp.templates);
          setAvailableStrategies(templatesResp.available_strategies);
          setBackendLimitations(templatesResp.limitations);
          setDocuments(docsResp.documents ?? []);
          if (templatesResp.templates.length > 0) {
            setSelectedTemplate(templatesResp.templates[0].template_id);
          }
          if (templatesResp.available_strategies.length > 0) {
            setStrategy(templatesResp.available_strategies[0]);
          }
        }
      })
      .catch((err) => {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Unable to load data.",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleExecute(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTemplate || !selectedDocument) return;

    setExecuting(true);
    setExecuteError(null);
    setResult(null);

    try {
      const resp = await executeExtraction({
        template_id: selectedTemplate,
        document_id: selectedDocument,
        strategy,
        provider:
          strategy === "langextract_grounded" ? null : provider || null,
        model_id:
          strategy === "langextract_grounded" ? null : modelId || null,
        api_key:
          strategy === "langextract_grounded" ? null : apiKey || null,
      });
      setResult(resp.result);
    } catch (err) {
      setExecuteError(
        err instanceof Error ? err.message : "Extraction failed.",
      );
    } finally {
      setExecuting(false);
    }
  }

  const completedDocuments = documents.filter(
    (d) => d.status === "completed",
  );

  if (loading) {
    return (
      <main style={pageStyle}>
        <section style={containerStyle}>
          <div style={panelStyle}>Loading extraction lab...</div>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main style={pageStyle}>
        <section style={containerStyle}>
          <div style={errorPanelStyle}>{error}</div>
        </section>
      </main>
    );
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <header style={{ marginBottom: "1.5rem" }}>
          <p style={breadcrumbStyle}>Extraction</p>
          <h1 style={titleStyle}>Extraction Lab</h1>
          <p style={subtitleStyle}>
            Define and test schema-driven extraction templates against ingested
            documents. Results include source grounding and geometry references
            when available.
          </p>
        </header>

        {/* Configuration form */}
        <section style={cardStyle}>
          <h2 style={sectionTitleStyle}>Configure Extraction</h2>
          {backendLimitations.length > 0 && (
            <div style={{ ...panelStyle, marginBottom: "1rem" }}>
              {backendLimitations.map((item) => (
                <p key={item} style={{ margin: 0 }}>
                  {item}
                </p>
              ))}
            </div>
          )}
          <form onSubmit={handleExecute} style={formGridStyle}>
            <label style={fieldStyle}>
              <span style={labelStyle}>Template</span>
              <select
                value={selectedTemplate}
                onChange={(e) => setSelectedTemplate(e.target.value)}
                style={inputStyle}
              >
                <option value="">Select a template</option>
                {templates.map((t) => (
                  <option key={t.template_id} value={t.template_id}>
                    {t.display_name} ({t.template_id})
                  </option>
                ))}
              </select>
            </label>

            <label style={fieldStyle}>
              <span style={labelStyle}>Document</span>
              <select
                value={selectedDocument}
                onChange={(e) => setSelectedDocument(e.target.value)}
                style={inputStyle}
              >
                <option value="">Select a document</option>
                {completedDocuments.map((d) => (
                  <option key={d.document_id} value={d.document_id}>
                    {d.source_file.filename} ({d.document_id.slice(0, 8)}...)
                  </option>
                ))}
              </select>
            </label>

            <label style={fieldStyle}>
              <span style={labelStyle}>Strategy</span>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value as ExtractionStrategy)}
                style={inputStyle}
              >
                {availableStrategies.map((availableStrategy) => (
                  <option key={availableStrategy} value={availableStrategy}>
                    {availableStrategy === "auto"
                      ? "Auto"
                      : availableStrategy === "provider_structured"
                        ? "Provider Structured"
                        : "LangExtract Grounded"}
                  </option>
                ))}
              </select>
            </label>

            {strategy !== "langextract_grounded" && (
              <>
                <label style={fieldStyle}>
                  <span style={labelStyle}>Provider</span>
                  <select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    style={inputStyle}
                  >
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="gemini">Gemini</option>
                  </select>
                </label>

                <label style={fieldStyle}>
                  <span style={labelStyle}>Model</span>
                  <input
                    value={modelId}
                    onChange={(e) => setModelId(e.target.value)}
                    placeholder="gpt-4o-mini"
                    style={inputStyle}
                  />
                </label>

                <label style={fieldStyle}>
                  <span style={labelStyle}>API Key</span>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-..."
                    style={inputStyle}
                  />
                </label>
              </>
            )}

            <div style={actionRowStyle}>
              <button
                type="submit"
                style={primaryButtonStyle}
                disabled={
                  executing || !selectedTemplate || !selectedDocument
                }
              >
                {executing ? "Extracting..." : "Run Extraction"}
              </button>
            </div>
          </form>
        </section>

        {/* Error display */}
        {executeError && (
          <div style={{ ...errorPanelStyle, marginTop: "1rem" }}>
            {executeError}
          </div>
        )}

        {/* Results */}
        {result && <ExtractionResultView result={result} />}
      </section>
    </main>
  );
}

/* ------------------------------------------------------------------ */
/* Result display components                                           */
/* ------------------------------------------------------------------ */

function ExtractionResultView({ result }: { result: ExtractionResult }) {
  const [expandedField, setExpandedField] = useState<string | null>(null);

  return (
    <section style={{ marginTop: "1.5rem" }}>
      {/* Run metadata */}
      <div style={cardStyle}>
        <h2 style={sectionTitleStyle}>Extraction Result</h2>
        <div style={metaGridStyle}>
          <MetaItem label="Extraction ID" value={result.run.extraction_id} />
          <MetaItem
            label="Status"
            value={result.run.status}
          />
          <MetaItem label="Strategy" value={result.run.strategy_used} />
          <MetaItem
            label="Provider"
            value={result.run.provider ?? "none"}
          />
          <MetaItem
            label="Model"
            value={result.run.model_id ?? "none"}
          />
          <MetaItem
            label="Duration"
            value={
              result.run.duration_ms != null
                ? `${result.run.duration_ms}ms`
                : "—"
            }
          />
          <MetaItem
            label="Fields"
            value={`${result.run.fields_extracted} / ${result.run.field_count}`}
          />
          <MetaItem
            label="Grounding"
            value={result.run.grounding_available ? "available" : "none"}
          />
        </div>

        {result.errors.length > 0 && (
          <div style={errorPanelStyle}>
            <strong>Errors:</strong>
            {result.errors.map((e, i) => (
              <p key={i} style={{ margin: "0.3rem 0" }}>
                [{e.code}] {e.message}
              </p>
            ))}
          </div>
        )}

        {/* Document link */}
        <div style={{ marginTop: "0.75rem" }}>
          <Link
            href={`/documents/${result.run.document_id}`}
            style={linkStyle}
          >
            Open Document Review →
          </Link>
        </div>
      </div>

      {/* Extracted fields */}
      {result.fields.length > 0 && (
        <div style={{ ...cardStyle, marginTop: "1rem" }}>
          <h3 style={sectionTitleStyle}>
            Extracted Fields ({result.fields.length})
          </h3>
          <div style={fieldListStyle}>
            {result.fields.map((field) => (
              <FieldResultItem
                key={field.field_id}
                field={field}
                expanded={expandedField === field.field_id}
                onToggle={() =>
                  setExpandedField(
                    expandedField === field.field_id
                      ? null
                      : field.field_id,
                  )
                }
              />
            ))}
          </div>
        </div>
      )}

      {/* Events timeline */}
      {result.events.length > 0 && (
        <div style={{ ...cardStyle, marginTop: "1rem" }}>
          <h3 style={sectionTitleStyle}>
            Events ({result.events.length})
          </h3>
          <div style={eventListStyle}>
            {result.events.map((event, i) => (
              <div key={i} style={eventItemStyle}>
                <span style={eventKindStyle}>{event.kind}</span>
                <span style={eventTimestampStyle}>
                  {event.timestamp}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function FieldResultItem({
  field,
  expanded,
  onToggle,
}: {
  field: ExtractedFieldResult;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <article style={fieldItemStyle}>
      <button
        type="button"
        onClick={onToggle}
        style={fieldHeaderButtonStyle}
      >
        <span style={fieldIdStyle}>{field.field_id}</span>
        <span style={fieldBadgeStyle}>
          {field.is_present ? field.field_type : "empty"}
          {field.grounding.length > 0 &&
            ` · ${field.grounding.length} ref${field.grounding.length > 1 ? "s" : ""}`}
        </span>
      </button>
      <div style={fieldValueStyle}>
        {field.is_present
          ? typeof field.value === "object"
            ? JSON.stringify(field.value, null, 2)
            : String(field.value ?? "")
          : "(not found)"}
      </div>
      {expanded && field.grounding.length > 0 && (
        <div style={groundingPanelStyle}>
          <strong>Source Grounding:</strong>
          {field.grounding.map((ref, i) => (
            <GroundingRefItem key={i} reference={ref} />
          ))}
        </div>
      )}
    </article>
  );
}

function GroundingRefItem({
  reference,
}: {
  reference: GroundingReference;
}) {
  return (
    <div style={groundingItemStyle}>
      {reference.page_number != null && (
        <span style={groundingTagStyle}>Page {reference.page_number}</span>
      )}
      {reference.block_id && (
        <span style={groundingTagStyle}>{reference.block_id}</span>
      )}
      {reference.geometry_source && (
        <span style={groundingTagStyle}>{reference.geometry_source}</span>
      )}
      {reference.bbox && (
        <span style={groundingTagStyle}>
          bbox: ({reference.bbox.x0.toFixed(0)},{reference.bbox.y0.toFixed(0)})→(
          {reference.bbox.x1.toFixed(0)},{reference.bbox.y1.toFixed(0)})
        </span>
      )}
      {reference.polygon && (
        <span style={groundingTagStyle}>
          polygon: {reference.polygon.points.length} pts
        </span>
      )}
      {reference.text_span && (
        <span style={groundingSpanStyle}>
          &quot;{reference.text_span.slice(0, 80)}
          {reference.text_span.length > 80 ? "…" : ""}&quot;
        </span>
      )}
      {reference.grounding_method && (
        <span style={groundingMethodStyle}>
          [{reference.grounding_method}]
        </span>
      )}
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div style={metaItemStyle}>
      <span style={metaLabelStyle}>{label}</span>
      <span style={metaValueStyle}>{value}</span>
    </div>
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
  maxWidth: "1100px",
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
  padding: "0.9rem 1rem",
  border: "1px solid #ef4444",
  borderRadius: "12px",
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

const formGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
  gap: "0.75rem",
};

const fieldStyle: CSSProperties = { display: "grid", gap: "0.3rem" };

const labelStyle: CSSProperties = {
  fontSize: "0.72rem",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "#64748b",
};

const inputStyle: CSSProperties = {
  padding: "0.5rem 0.65rem",
  border: "1px solid #d7dee8",
  borderRadius: "8px",
  fontSize: "0.88rem",
  color: "#102033",
  backgroundColor: "#ffffff",
};

const actionRowStyle: CSSProperties = {
  gridColumn: "1 / -1",
  display: "flex",
  gap: "0.5rem",
  marginTop: "0.5rem",
};

const primaryButtonStyle: CSSProperties = {
  padding: "0.55rem 1.25rem",
  border: "1px solid #102033",
  borderRadius: "8px",
  backgroundColor: "#102033",
  color: "#ffffff",
  fontWeight: 600,
  cursor: "pointer",
};

const linkStyle: CSSProperties = {
  color: "#6366f1",
  textDecoration: "none",
  fontWeight: 600,
  fontSize: "0.88rem",
};

const metaGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: "0.6rem",
};

const metaItemStyle: CSSProperties = {
  padding: "0.55rem 0.7rem",
  border: "1px solid #d7dee8",
  borderRadius: "10px",
  backgroundColor: "#f8fafc",
  display: "grid",
  gap: "0.15rem",
};

const metaLabelStyle: CSSProperties = {
  fontSize: "0.68rem",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "#64748b",
};

const metaValueStyle: CSSProperties = {
  color: "#102033",
  fontWeight: 600,
  wordBreak: "break-word",
  fontSize: "0.85rem",
};

const fieldListStyle: CSSProperties = {
  display: "grid",
  gap: "0.5rem",
};

const fieldItemStyle: CSSProperties = {
  border: "1px solid #d7dee8",
  borderRadius: "10px",
  overflow: "hidden",
};

const fieldHeaderButtonStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  width: "100%",
  padding: "0.6rem 0.8rem",
  border: "none",
  backgroundColor: "#f8fafc",
  cursor: "pointer",
  fontFamily: "inherit",
  textAlign: "left",
};

const fieldIdStyle: CSSProperties = {
  fontWeight: 600,
  fontSize: "0.88rem",
  color: "#102033",
};

const fieldBadgeStyle: CSSProperties = {
  fontSize: "0.72rem",
  color: "#64748b",
};

const fieldValueStyle: CSSProperties = {
  padding: "0.5rem 0.8rem",
  fontSize: "0.85rem",
  color: "#334155",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
};

const groundingPanelStyle: CSSProperties = {
  padding: "0.6rem 0.8rem",
  backgroundColor: "#f0fdf4",
  borderTop: "1px solid #d7dee8",
  fontSize: "0.82rem",
};

const groundingItemStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "0.4rem",
  alignItems: "center",
  marginTop: "0.4rem",
};

const groundingTagStyle: CSSProperties = {
  padding: "0.15rem 0.45rem",
  borderRadius: "6px",
  backgroundColor: "#dbeafe",
  color: "#1e40af",
  fontSize: "0.72rem",
  fontWeight: 600,
};

const groundingSpanStyle: CSSProperties = {
  color: "#475569",
  fontStyle: "italic",
  fontSize: "0.78rem",
};

const groundingMethodStyle: CSSProperties = {
  color: "#64748b",
  fontSize: "0.72rem",
};

const eventListStyle: CSSProperties = {
  display: "grid",
  gap: "0.3rem",
};

const eventItemStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  padding: "0.4rem 0.6rem",
  border: "1px solid #e2e8f0",
  borderRadius: "8px",
  fontSize: "0.82rem",
};

const eventKindStyle: CSSProperties = {
  fontWeight: 600,
  color: "#334155",
};

const eventTimestampStyle: CSSProperties = {
  color: "#94a3b8",
  fontSize: "0.72rem",
};
