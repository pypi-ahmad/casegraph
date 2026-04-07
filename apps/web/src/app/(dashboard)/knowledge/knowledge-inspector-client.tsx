"use client";

import { useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  IndexResult,
  IngestionResult,
  KnowledgeCapabilitiesResponse,
  SearchRequest,
  SearchResult,
  SearchResultItem,
} from "@casegraph/agent-sdk";

import {
  fetchKnowledgeCapabilities,
  indexDocument,
  searchKnowledge,
} from "@/lib/knowledge-api";
import { ingestDocument } from "@/lib/documents-api";

export default function KnowledgeInspectorClient() {
  /* ---------------------------------------------------------------- */
  /* Capabilities                                                      */
  /* ---------------------------------------------------------------- */
  const [capabilities, setCapabilities] =
    useState<KnowledgeCapabilitiesResponse | null>(null);
  const [capsLoading, setCapsLoading] = useState(true);
  const [capsError, setCapsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setCapsLoading(true);
      setCapsError(null);
      try {
        const data = await fetchKnowledgeCapabilities();
        if (!cancelled) setCapabilities(data);
      } catch (err) {
        if (!cancelled)
          setCapsError(err instanceof Error ? err.message : "Unable to load knowledge capabilities. Try refreshing the page.");
      } finally {
        if (!cancelled) setCapsLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  /* ---------------------------------------------------------------- */
  /* Index flow: upload file → ingest → index                          */
  /* ---------------------------------------------------------------- */
  const [indexFile, setIndexFile] = useState<File | null>(null);
  const [indexing, setIndexing] = useState(false);
  const [indexError, setIndexError] = useState<string | null>(null);
  const [indexResult, setIndexResult] = useState<IndexResult | null>(null);

  async function handleIndex(event: FormEvent) {
    event.preventDefault();
    if (!indexFile) {
      setIndexError("Select a file to index.");
      return;
    }
    setIndexing(true);
    setIndexError(null);
    setIndexResult(null);

    try {
      // Step 1: ingest the file
      const ingestionResult: IngestionResult = await ingestDocument(indexFile, {
        mode: "auto",
        ocrEnabled: false,
      });

      if (!ingestionResult.output) {
        setIndexError(
          `Ingestion failed: ${ingestionResult.errors.map((e) => e.message).join("; ") || "unknown error"}`,
        );
        return;
      }

      // Step 2: index the extraction output into the knowledge base
      const result = await indexDocument(ingestionResult.output);
      setIndexResult(result);
    } catch (err) {
      setIndexError(err instanceof Error ? err.message : "Indexing failed. Check the file format and try again.");
    } finally {
      setIndexing(false);
    }
  }

  /* ---------------------------------------------------------------- */
  /* Search flow                                                       */
  /* ---------------------------------------------------------------- */
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    if (!searchQuery.trim()) {
      setSearchError("Enter a search query.");
      return;
    }
    setSearching(true);
    setSearchError(null);
    setSearchResult(null);

    try {
      const result = await searchKnowledge({
        query: searchQuery.trim(),
        top_k: 10,
        filters: [],
      });
      setSearchResult(result);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Search failed. Try a different query or check that documents have been indexed.");
    } finally {
      setSearching(false);
    }
  }

  /* ---------------------------------------------------------------- */
  /* Render                                                            */
  /* ---------------------------------------------------------------- */
  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <header style={{ marginBottom: "2rem" }}>
          <p style={breadcrumbStyle}>Knowledge</p>
          <h1 style={titleStyle}>Retrieval Inspector</h1>
          <p style={subtitleStyle}>
            Index ingested documents into the vector store and search across
            your knowledge base.
          </p>
        </header>

        {/* Capabilities */}
        <section style={panelStyle}>
          <h2 style={sectionTitleStyle}>Current Capabilities</h2>
          {capsLoading ? (
            <p style={mutedStyle}>Loading...</p>
          ) : capsError ? (
            <div style={errorPanelStyle}>{capsError}</div>
          ) : capabilities ? (
            <>
              <div style={gridStyle}>
                <CapabilityCard
                  label="Embedding"
                  available={capabilities.embedding.available}
                  name={capabilities.embedding.name}
                  notes={capabilities.embedding.notes}
                />
                <CapabilityCard
                  label="Vector Store"
                  available={capabilities.vector_store.available}
                  name={capabilities.vector_store.name}
                  notes={capabilities.vector_store.notes}
                />
                <div style={metricCardStyle}>
                  <span style={metricLabelStyle}>Indexed Chunks</span>
                  <span style={metricValueStyle}>{capabilities.indexed_chunks}</span>
                </div>
                {capabilities.embedding_model ? (
                  <div style={metricCardStyle}>
                    <span style={metricLabelStyle}>Model</span>
                    <span style={metricValueStyle}>
                      {capabilities.embedding_model.model_name}
                    </span>
                    <span style={metricSubStyle}>
                      {capabilities.embedding_model.dimension}d · {capabilities.embedding_model.provider}
                    </span>
                  </div>
                ) : null}
              </div>

              <h3 style={{ ...sectionTitleStyle, marginTop: "1.5rem" }}>
                Current Limitations
              </h3>
              <ul style={listStyle}>
                {capabilities.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          ) : null}
        </section>

        {/* Index */}
        <section style={{ ...panelStyle, marginTop: "1rem" }}>
          <h2 style={sectionTitleStyle}>Index Document</h2>
          <p style={subtitleStyle}>
            Upload a PDF or image. It will be ingested and then indexed into the
            vector store in a single flow.
          </p>
          <form onSubmit={handleIndex} style={formStyle}>
            <label style={fieldStyle}>
              <span style={fieldLabelStyle}>File</span>
              <input
                type="file"
                accept=".pdf,image/*"
                onChange={(e) => setIndexFile(e.target.files?.[0] ?? null)}
                style={inputStyle}
              />
            </label>
            <div style={actionsStyle}>
              <button type="submit" disabled={indexing} style={buttonStyle}>
                {indexing ? "Indexing..." : "Ingest & Index"}
              </button>
            </div>
          </form>
          {indexError ? <div style={errorPanelStyle}>{indexError}</div> : null}
          {indexResult ? (
            <div style={{ ...mutedPanelStyle, marginTop: "1rem" }}>
              <strong>Indexed:</strong> {indexResult.summary.chunks_indexed} chunks
              {" · "}embedding: {indexResult.summary.embedding_model ?? "n/a"}
              {" · "}store: {indexResult.summary.vector_store ?? "n/a"}
              {indexResult.errors.length > 0 ? (
                <div style={{ ...errorPanelStyle, marginTop: "0.5rem" }}>
                  {indexResult.errors.map((e) => (
                    <p key={e.code} style={{ margin: 0 }}>{e.code}: {e.message}</p>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </section>

        {/* Search */}
        <section style={{ ...panelStyle, marginTop: "1rem" }}>
          <h2 style={sectionTitleStyle}>Search Knowledge</h2>
          <form onSubmit={handleSearch} style={formStyle}>
            <label style={fieldStyle}>
              <span style={fieldLabelStyle}>Query</span>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Enter a semantic search query..."
                style={inputStyle}
              />
            </label>
            <div style={actionsStyle}>
              <button type="submit" disabled={searching} style={buttonStyle}>
                {searching ? "Searching..." : "Search"}
              </button>
            </div>
          </form>
          {searchError ? <div style={errorPanelStyle}>{searchError}</div> : null}
          {searchResult ? (
            <div style={{ marginTop: "1rem" }}>
              <p style={mutedStyle}>
                {searchResult.total_results} result{searchResult.total_results !== 1 ? "s" : ""}
                {" · "}model: {searchResult.embedding_model ?? "n/a"}
                {" · "}store: {searchResult.vector_store ?? "n/a"}
              </p>
              {searchResult.items.length === 0 ? (
                <p style={mutedStyle}>No results found.</p>
              ) : (
                <div style={{ display: "grid", gap: "0.75rem" }}>
                  {searchResult.items.map((item) => (
                    <SearchHitCard key={item.chunk_id} item={item} />
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </section>
      </section>
    </main>
  );
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                      */
/* ------------------------------------------------------------------ */

function CapabilityCard({
  label,
  available,
  name,
  notes,
}: {
  label: string;
  available: boolean;
  name: string | null;
  notes: string[];
}) {
  return (
    <article style={cardStyle}>
      <div style={cardHeaderRow}>
        <h3 style={cardTitleStyle}>{label}</h3>
        <span
          style={{
            ...pillStyle,
            backgroundColor: available ? "#e8f7ef" : "#fff1f2",
            color: available ? "#166534" : "#9f1239",
          }}
        >
          {available ? "ready" : "not ready"}
        </span>
      </div>
      <p style={cardMetaStyle}>{name ?? "unavailable"}</p>
      <ul style={listStyle}>
        {notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </article>
  );
}

function SearchHitCard({ item }: { item: SearchResultItem }) {
  const snippet =
    item.text.length > 200 ? `${item.text.slice(0, 200)}...` : item.text;

  return (
    <article style={cardStyle}>
      <div style={cardHeaderRow}>
        <span style={pillStyle}>score: {item.score.raw_score.toFixed(4)}</span>
        <span style={cardMetaStyle}>
          page: {item.metadata.page_number ?? "?"}
        </span>
      </div>
      <p style={{ margin: "0.5rem 0 0", fontFamily: "monospace", fontSize: "0.8rem", color: "#64748b" }}>
        chunk: {item.chunk_id}
      </p>
      <p style={{ margin: "0.5rem 0 0", fontFamily: "monospace", fontSize: "0.8rem", color: "#64748b" }}>
        doc: {item.source_reference.document_id}
      </p>
      <p style={snippetStyle}>{snippet}</p>
    </article>
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
const containerStyle: CSSProperties = { maxWidth: "1120px", margin: "0 auto" };
const breadcrumbStyle: CSSProperties = {
  margin: 0, textTransform: "uppercase", letterSpacing: "0.08em",
  fontSize: "0.8rem", color: "#64748b",
};
const titleStyle: CSSProperties = { margin: "0.5rem 0 0", fontSize: "2.2rem", color: "#102033" };
const subtitleStyle: CSSProperties = { maxWidth: "780px", color: "#55657a", lineHeight: 1.6 };
const panelStyle: CSSProperties = {
  padding: "1.25rem", border: "1px solid #d7dee8", borderRadius: "18px",
  backgroundColor: "#ffffff", boxShadow: "0 16px 32px rgba(15, 23, 42, 0.06)",
};
const mutedPanelStyle: CSSProperties = {
  padding: "1rem 1.1rem", border: "1px solid #d7dee8", borderRadius: "14px",
  backgroundColor: "#f8fafc", color: "#475569",
};
const errorPanelStyle: CSSProperties = {
  padding: "1rem 1.1rem", border: "1px solid #fecaca", borderRadius: "14px",
  backgroundColor: "#fff1f2", color: "#9f1239", marginTop: "1rem",
};
const formStyle: CSSProperties = { display: "grid", gap: "1rem" };
const fieldStyle: CSSProperties = { display: "grid", gap: "0.4rem" };
const fieldLabelStyle: CSSProperties = { fontSize: "0.9rem", fontWeight: 600, color: "#334155" };
const inputStyle: CSSProperties = {
  width: "100%", boxSizing: "border-box", padding: "0.9rem",
  border: "1px solid #cbd5e1", borderRadius: "12px", backgroundColor: "#ffffff",
};
const actionsStyle: CSSProperties = { display: "flex", gap: "0.75rem", alignItems: "center" };
const buttonStyle: CSSProperties = {
  display: "inline-flex", alignItems: "center", justifyContent: "center",
  padding: "0.85rem 1.1rem", borderRadius: "999px", border: "none",
  backgroundColor: "#102033", color: "#ffffff", fontWeight: 600, cursor: "pointer",
};
const sectionTitleStyle: CSSProperties = {
  margin: "0 0 1rem", fontSize: "1.05rem", textTransform: "uppercase",
  letterSpacing: "0.06em", color: "#475569",
};
const gridStyle: CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem",
};
const cardStyle: CSSProperties = {
  padding: "1rem", border: "1px solid #d7dee8", borderRadius: "16px", backgroundColor: "#ffffff",
};
const cardHeaderRow: CSSProperties = {
  display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "center",
};
const cardTitleStyle: CSSProperties = { margin: 0, fontSize: "1.05rem", color: "#102033" };
const cardMetaStyle: CSSProperties = {
  margin: "0.4rem 0 0", color: "#64748b", fontFamily: "monospace", fontSize: "0.85rem",
};
const pillStyle: CSSProperties = {
  display: "inline-flex", alignItems: "center", borderRadius: "999px",
  padding: "0.25rem 0.6rem", backgroundColor: "#f8fafc", color: "#475569",
  fontSize: "0.8rem", fontFamily: "monospace",
};
const listStyle: CSSProperties = {
  margin: "0.75rem 0 0 1.2rem", padding: 0, color: "#475569", lineHeight: 1.7,
};
const mutedStyle: CSSProperties = { color: "#64748b", fontSize: "0.9rem" };
const metricCardStyle: CSSProperties = {
  ...cardStyle, display: "grid", gap: "0.25rem",
};
const metricLabelStyle: CSSProperties = {
  fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "#64748b",
};
const metricValueStyle: CSSProperties = { color: "#102033", fontWeight: 600, fontSize: "1.3rem" };
const metricSubStyle: CSSProperties = { color: "#64748b", fontFamily: "monospace", fontSize: "0.8rem" };
const snippetStyle: CSSProperties = {
  margin: "0.8rem 0 0", color: "#475569", lineHeight: 1.6, whiteSpace: "pre-wrap",
};
