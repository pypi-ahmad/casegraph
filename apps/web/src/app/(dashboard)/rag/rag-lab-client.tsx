"use client";

import { useEffect, useState } from "react";
import AiDisclosureBanner from "@/components/ai-disclosure-banner";
import type { CSSProperties, FormEvent } from "react";

import type {
  RagTaskDefinitionMeta,
  RagTaskExecutionResult,
  EvidenceChunkReference,
  CitationReference,
  ModelSummary,
  ProviderId,
  ProviderSummary,
  TaskExecutionEvent,
} from "@casegraph/agent-sdk";

import { fetchRagTasks, executeRagTask } from "@/lib/rag-api";
import { fetchProviders, fetchProviderModels } from "@/lib/provider-api";

export default function RagLabClient() {
  // --- registry data ---
  const [tasks, setTasks] = useState<RagTaskDefinitionMeta[]>([]);
  const [providers, setProviders] = useState<ProviderSummary[]>([]);
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // --- form state ---
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedModelId, setSelectedModelId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [query, setQuery] = useState("");
  const [useStructured, setUseStructured] = useState(false);
  const [temperature, setTemperature] = useState("");
  const [maxTokens, setMaxTokens] = useState("");
  const [topK, setTopK] = useState("5");
  const [scopeKind, setScopeKind] = useState<"global" | "case" | "document">("global");
  const [scopeCaseId, setScopeCaseId] = useState("");
  const [scopeDocumentIds, setScopeDocumentIds] = useState("");

  // --- execution state ---
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<RagTaskExecutionResult | null>(null);
  const [events, setEvents] = useState<TaskExecutionEvent[]>([]);
  const [execError, setExecError] = useState<string | null>(null);

  // --- model loading ---
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setLoadError(null);
      try {
        const [taskRes, provRes] = await Promise.all([
          fetchRagTasks(),
          fetchProviders(),
        ]);
        if (!cancelled) {
          setTasks(taskRes.tasks);
          setProviders(provRes.providers);
          if (taskRes.tasks.length > 0) setSelectedTaskId(taskRes.tasks[0].task_id);
          if (provRes.providers.length > 0) setSelectedProvider(provRes.providers[0].id);
        }
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : "Load failed.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  async function handleFetchModels() {
    if (!selectedProvider || !apiKey.trim()) return;
    setModelsLoading(true);
    setModelsError(null);
    setModels([]);
    try {
      const res = await fetchProviderModels({ provider: selectedProvider as ProviderId, api_key: apiKey });
      setModels(res.models);
      if (res.models.length > 0) setSelectedModelId(res.models[0].model_id);
    } catch (err) {
      setModelsError(err instanceof Error ? err.message : "Unable to fetch models. Verify your API key and try again.");
    } finally {
      setModelsLoading(false);
    }
  }

  async function handleExecute(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTaskId || !selectedProvider || !selectedModelId || !apiKey.trim() || !query.trim()) return;

    setExecuting(true);
    setResult(null);
    setEvents([]);
    setExecError(null);

    try {
      const res = await executeRagTask({
        task_id: selectedTaskId,
        query: query.trim(),
        parameters: {},
        provider: selectedProvider,
        model_id: selectedModelId,
        api_key: apiKey,
        retrieval_scope: {
          kind: scopeKind,
          case_id: scopeKind === "case" && scopeCaseId.trim() ? scopeCaseId.trim() : null,
          document_ids: scopeKind === "document" && scopeDocumentIds.trim()
            ? scopeDocumentIds.split(",").map((s) => s.trim()).filter(Boolean)
            : [],
        },
        top_k: parseInt(topK, 10) || 5,
        max_tokens: maxTokens ? parseInt(maxTokens, 10) : null,
        temperature: temperature ? parseFloat(temperature) : null,
        use_structured_output: useStructured,
      });
      setResult(res.result);
      setEvents(res.events);
    } catch (err) {
      setExecError(err instanceof Error ? err.message : "RAG query failed. Check your API key and model selection, then try again.");
    } finally {
      setExecuting(false);
    }
  }

  if (loading) return <main style={pageStyle}><section style={containerStyle}><div style={panelStyle}>Loading RAG lab...</div></section></main>;
  if (loadError) return <main style={pageStyle}><section style={containerStyle}><div style={errorPanelStyle}>{loadError}</div></section></main>;

  const selectedTask = tasks.find((t) => t.task_id === selectedTaskId);
  const scopeError = scopeKind === "case"
    ? (!scopeCaseId.trim() ? "Case ID is required for case-scoped retrieval." : null)
    : scopeKind === "document"
      ? (!scopeDocumentIds.split(",").map((s) => s.trim()).filter(Boolean).length
        ? "At least one document ID is required for document-scoped retrieval."
        : null)
      : null;

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <header style={{ marginBottom: "1.5rem" }}>
          <p style={breadcrumbStyle}>RAG</p>
          <h1 style={titleStyle}>Evidence-Backed Task Lab</h1>
          <p style={subtitleStyle}>Execute tasks with retrieved evidence from indexed knowledge. Results include citations referencing evidence sources.</p>
        </header>

        <AiDisclosureBanner />

        <div style={layoutStyle}>
          {/* --- Configuration --- */}
          <form onSubmit={handleExecute} style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Configuration</h2>

            <label style={fieldStyle}>
              <span style={labelStyle}>Task</span>
              <select value={selectedTaskId} onChange={(e) => setSelectedTaskId(e.target.value)} style={inputStyle}>
                {tasks.map((t) => <option key={t.task_id} value={t.task_id}>{t.display_name}</option>)}
              </select>
            </label>

            {selectedTask && (
              <div style={hintStyle}>
                {selectedTask.description}
                <br />Evidence: {selectedTask.requires_evidence ? "required" : "optional"} | Citations: {selectedTask.returns_citations ? "yes" : "no"}
              </div>
            )}

            <label style={fieldStyle}>
              <span style={labelStyle}>Provider</span>
              <select value={selectedProvider} onChange={(e) => { setSelectedProvider(e.target.value); setModels([]); setSelectedModelId(""); }} style={inputStyle}>
                {providers.map((p) => <option key={p.id} value={p.id}>{p.display_name}</option>)}
              </select>
            </label>

            <label style={fieldStyle}>
              <span style={labelStyle}>API Key</span>
              <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} style={inputStyle} autoComplete="off" spellCheck={false} placeholder="Enter provider API key" />
            </label>

            <div style={inlineFormStyle}>
              <button type="button" onClick={handleFetchModels} style={secondaryButtonStyle} disabled={modelsLoading || !apiKey.trim()}>
                {modelsLoading ? "Loading..." : "Fetch Models"}
              </button>
              {modelsError && <span style={errorTextStyle}>{modelsError}</span>}
            </div>

            <label style={fieldStyle}>
              <span style={labelStyle}>Model</span>
              {models.length > 0 ? (
                <select value={selectedModelId} onChange={(e) => setSelectedModelId(e.target.value)} style={inputStyle}>
                  {models.map((m) => <option key={m.model_id} value={m.model_id}>{m.display_name ?? m.model_id}</option>)}
                </select>
              ) : (
                <input value={selectedModelId} onChange={(e) => setSelectedModelId(e.target.value)} style={inputStyle} placeholder="Enter model ID or fetch models above" />
              )}
            </label>

            <h3 style={subSectionTitleStyle}>Retrieval</h3>

            <label style={fieldStyle}>
              <span style={labelStyle}>Scope</span>
              <select value={scopeKind} onChange={(e) => setScopeKind(e.target.value as "global" | "case" | "document")} style={inputStyle}>
                <option value="global">Global (all indexed knowledge)</option>
                <option value="case">Case-scoped (linked documents)</option>
                <option value="document">Document-scoped (specific IDs)</option>
              </select>
            </label>

            {scopeKind === "case" && (
              <label style={fieldStyle}>
                <span style={labelStyle}>Case ID</span>
                <input value={scopeCaseId} onChange={(e) => setScopeCaseId(e.target.value)} style={inputStyle} placeholder="Enter case ID" />
              </label>
            )}

            {scopeKind === "document" && (
              <label style={fieldStyle}>
                <span style={labelStyle}>Document IDs (comma-separated)</span>
                <input value={scopeDocumentIds} onChange={(e) => setScopeDocumentIds(e.target.value)} style={inputStyle} placeholder="doc-001, doc-002" />
              </label>
            )}

            <label style={fieldStyle}>
              <span style={labelStyle}>Top K (evidence chunks)</span>
              <input value={topK} onChange={(e) => setTopK(e.target.value)} style={inputStyle} type="number" min="1" max="50" />
            </label>

            {scopeError && <div style={errorPanelStyle}>{scopeError}</div>}

            <label style={fieldStyle}>
              <span style={labelStyle}>Query / Instruction</span>
              <textarea value={query} onChange={(e) => setQuery(e.target.value)} style={textareaStyle} rows={4} placeholder="Enter your query or instruction..." required />
            </label>

            <div style={rowStyle}>
              <label style={{ ...fieldStyle, flex: 1 }}>
                <span style={labelStyle}>Temperature</span>
                <input value={temperature} onChange={(e) => setTemperature(e.target.value)} style={inputStyle} type="number" step="0.1" min="0" max="2" placeholder="default" />
              </label>
              <label style={{ ...fieldStyle, flex: 1 }}>
                <span style={labelStyle}>Max Tokens</span>
                <input value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)} style={inputStyle} type="number" min="1" placeholder="default" />
              </label>
            </div>

            <label style={checkboxFieldStyle}>
              <input type="checkbox" checked={useStructured} onChange={(e) => setUseStructured(e.target.checked)} />
              <span>Request structured output (JSON schema)</span>
            </label>

            <div style={actionRowStyle}>
              <button type="submit" style={primaryButtonStyle} disabled={executing || !query.trim() || !selectedModelId || !apiKey.trim() || scopeError !== null}>
                {executing ? "Executing..." : "Execute with Evidence"}
              </button>
            </div>

            {execError && <div style={errorPanelStyle}>{execError}</div>}
          </form>

          {/* --- Results --- */}
          <div style={resultColumnStyle}>
            <div style={sectionCardStyle}>
              <h2 style={sectionTitleStyle}>Result</h2>

              {!result && !execError && <div style={panelStyle}>Execute a task to see results here.</div>}

              {result && (
                <div style={stackStyle}>
                  <div style={resultHeaderStyle}>
                    <span style={badgeStyle(result.finish_reason === "completed" ? "#16a34a" : "#dc2626")}>{result.finish_reason}</span>
                    <span style={metaTextStyle}>{result.provider} / {result.model_id}</span>
                    {result.duration_ms != null && <span style={metaTextStyle}>{result.duration_ms}ms</span>}
                  </div>

                  {result.usage && (
                    <div style={usageRowStyle}>
                      {result.usage.input_tokens != null && <span>Input: {result.usage.input_tokens} tokens</span>}
                      {result.usage.output_tokens != null && <span>Output: {result.usage.output_tokens} tokens</span>}
                    </div>
                  )}

                  {result.error && (
                    <div style={errorPanelStyle}><strong>{result.error.error_code}</strong>: {result.error.message}</div>
                  )}

                  {result.grounding && (
                    <div style={hintStyle}>
                      Evidence provided: {result.grounding.evidence_provided ? "yes" : "no"} |
                      Chunks: {result.grounding.evidence_chunk_count} |
                      Citations: {result.grounding.citation_count} |
                      Method: {result.grounding.grounding_method}
                    </div>
                  )}

                  {result.structured_output && (
                    <div>
                      <h3 style={subTitleStyle}>Structured Output</h3>
                      <div style={hintStyle}>Schema valid: {result.structured_output.schema_valid ? "✓" : "✗"}</div>
                      <pre style={preStyle}>{JSON.stringify(result.structured_output.parsed, null, 2)}</pre>
                    </div>
                  )}

                  {result.output_text && !result.structured_output && (
                    <div>
                      <h3 style={subTitleStyle}>Output</h3>
                      <pre style={preStyle}>{result.output_text}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* --- Citations --- */}
            {result && result.citations.length > 0 && (
              <div style={sectionCardStyle}>
                <h2 style={sectionTitleStyle}>Citations ({result.citations.length})</h2>
                <div style={stackStyle}>
                  {result.citations.map((c: CitationReference) => (
                    <div key={c.citation_index} style={citationRowStyle}>
                      <span style={citationIndexStyle}>[{c.citation_index}]</span>
                      <div>
                        {c.source_filename && <span style={metaTextStyle}>{c.source_filename}</span>}
                        {c.page_number != null && <span style={metaTextStyle}> · page {c.page_number}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* --- Evidence --- */}
            {result && result.evidence.length > 0 && (
              <div style={sectionCardStyle}>
                <h2 style={sectionTitleStyle}>Evidence Chunks ({result.evidence.length})</h2>
                {result.evidence_summary && (
                  <div style={hintStyle}>
                    Retrieved: {result.evidence_summary.total_retrieved} |
                    Selected: {result.evidence_summary.total_selected} |
                    Model: {result.evidence_summary.embedding_model ?? "—"} |
                    Store: {result.evidence_summary.vector_store ?? "—"}
                  </div>
                )}
                <div style={stackStyle}>
                  {result.evidence.map((e: EvidenceChunkReference, i: number) => (
                    <div key={e.chunk_id} style={evidenceRowStyle}>
                      <div style={evidenceHeaderStyle}>
                        <span style={citationIndexStyle}>[{i + 1}]</span>
                        <span style={metaTextStyle}>score: {e.score.raw_score.toFixed(3)}</span>
                        {e.source_filename && <span style={metaTextStyle}>{e.source_filename}</span>}
                        {e.page_number != null && <span style={metaTextStyle}>page {e.page_number}</span>}
                      </div>
                      <pre style={evidenceTextStyle}>{e.text}</pre>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* --- Events --- */}
            {events.length > 0 && (
              <div style={sectionCardStyle}>
                <h2 style={sectionTitleStyle}>Events ({events.length})</h2>
                <div style={stackStyle}>
                  {events.map((evt, i) => (
                    <div key={i} style={eventRowStyle}>
                      <span style={eventKindStyle}>{evt.kind}</span>
                      <span style={metaTextStyle}>{evt.timestamp}</span>
                      {Object.keys(evt.metadata).length > 0 && <pre style={eventMetaStyle}>{JSON.stringify(evt.metadata, null, 2)}</pre>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const pageStyle: CSSProperties = { minHeight: "100vh", padding: "2.5rem 1.25rem 3rem", backgroundColor: "#f5f7fa" };
const containerStyle: CSSProperties = { maxWidth: "1280px", margin: "0 auto" };
const breadcrumbStyle: CSSProperties = { margin: 0, textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "0.8rem", color: "#64748b" };
const titleStyle: CSSProperties = { margin: "0.5rem 0 0", fontSize: "2.2rem", color: "#102033" };
const subtitleStyle: CSSProperties = { maxWidth: "750px", color: "#55657a", lineHeight: 1.6, marginTop: "0.5rem" };
const layoutStyle: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", alignItems: "start" };
const sectionCardStyle: CSSProperties = { padding: "1.5rem", border: "1px solid #d7dee8", borderRadius: "12px", backgroundColor: "#fff" };
const sectionTitleStyle: CSSProperties = { margin: "0 0 1rem", fontSize: "1.2rem", color: "#102033" };
const subSectionTitleStyle: CSSProperties = { margin: "1rem 0 0.5rem", fontSize: "1rem", fontWeight: 600, color: "#334155" };
const subTitleStyle: CSSProperties = { margin: "1rem 0 0.5rem", fontSize: "1rem", fontWeight: 600, color: "#102033" };
const fieldStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: "0.25rem", marginBottom: "0.75rem" };
const labelStyle: CSSProperties = { fontSize: "0.85rem", fontWeight: 600, color: "#334155" };
const inputStyle: CSSProperties = { padding: "0.5rem 0.75rem", border: "1px solid #d1d5db", borderRadius: "6px", fontSize: "0.9rem", fontFamily: "inherit" };
const textareaStyle: CSSProperties = { ...inputStyle, resize: "vertical", fontFamily: "monospace" };
const panelStyle: CSSProperties = { padding: "1rem 1.25rem", border: "1px solid #d7dee8", borderRadius: "8px", backgroundColor: "#f8f9fa", color: "#55657a" };
const errorPanelStyle: CSSProperties = { ...panelStyle, borderColor: "#fca5a5", backgroundColor: "#fef2f2", color: "#991b1b" };
const hintStyle: CSSProperties = { fontSize: "0.82rem", color: "#64748b", marginBottom: "0.75rem", lineHeight: 1.5 };
const rowStyle: CSSProperties = { display: "flex", gap: "1rem" };
const inlineFormStyle: CSSProperties = { display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" };
const actionRowStyle: CSSProperties = { marginTop: "0.5rem" };
const checkboxFieldStyle: CSSProperties = { display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem", fontSize: "0.9rem", color: "#334155" };
const primaryButtonStyle: CSSProperties = { padding: "0.55rem 1.5rem", backgroundColor: "#102033", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: 600, fontSize: "0.9rem" };
const secondaryButtonStyle: CSSProperties = { ...primaryButtonStyle, backgroundColor: "#475569" };
const errorTextStyle: CSSProperties = { color: "#dc2626", fontSize: "0.85rem" };
const stackStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: "0.75rem" };
const resultColumnStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: "1.5rem" };
const resultHeaderStyle: CSSProperties = { display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" };
const metaTextStyle: CSSProperties = { fontSize: "0.82rem", color: "#64748b" };
const usageRowStyle: CSSProperties = { display: "flex", gap: "1.5rem", fontSize: "0.85rem", color: "#475569" };
const preStyle: CSSProperties = { margin: 0, padding: "0.75rem", backgroundColor: "#f1f5f9", borderRadius: "6px", fontSize: "0.82rem", overflow: "auto", maxHeight: "400px", whiteSpace: "pre-wrap", wordBreak: "break-word" };
const citationRowStyle: CSSProperties = { display: "flex", gap: "0.5rem", padding: "0.5rem 0.75rem", border: "1px solid #e2e8f0", borderRadius: "6px", backgroundColor: "#fafbfc" };
const citationIndexStyle: CSSProperties = { fontWeight: 700, fontSize: "0.9rem", color: "#2563eb", minWidth: "2rem" };
const evidenceRowStyle: CSSProperties = { border: "1px solid #e2e8f0", borderRadius: "6px", overflow: "hidden" };
const evidenceHeaderStyle: CSSProperties = { display: "flex", gap: "0.75rem", alignItems: "center", padding: "0.5rem 0.75rem", backgroundColor: "#f8fafc", borderBottom: "1px solid #e2e8f0" };
const evidenceTextStyle: CSSProperties = { ...preStyle, borderRadius: 0, maxHeight: "200px" };
const eventRowStyle: CSSProperties = { padding: "0.5rem 0.75rem", border: "1px solid #e2e8f0", borderRadius: "6px", backgroundColor: "#fafbfc" };
const eventKindStyle: CSSProperties = { fontWeight: 600, fontSize: "0.85rem", color: "#102033", marginRight: "0.5rem" };
const eventMetaStyle: CSSProperties = { ...preStyle, marginTop: "0.25rem", fontSize: "0.78rem", maxHeight: "150px" };

function badgeStyle(color: string): CSSProperties {
  return { display: "inline-block", padding: "0.2rem 0.6rem", borderRadius: "999px", fontSize: "0.78rem", fontWeight: 600, color: "#fff", backgroundColor: color };
}
