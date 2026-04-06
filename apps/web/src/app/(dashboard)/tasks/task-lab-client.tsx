"use client";

import { useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type {
  TaskDefinitionMeta,
  ModelSummary,
  ProviderId,
  ProviderSummary,
  TaskExecutionResult,
  TaskExecutionEvent,
} from "@casegraph/agent-sdk";

import { fetchTasks, executeTask } from "@/lib/tasks-api";
import { fetchProviders, fetchProviderModels } from "@/lib/provider-api";

export default function TaskLabClient() {
  // --- registry data ---
  const [tasks, setTasks] = useState<TaskDefinitionMeta[]>([]);
  const [providers, setProviders] = useState<ProviderSummary[]>([]);
  const [models, setModels] = useState<ModelSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // --- form state ---
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedModelId, setSelectedModelId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [inputText, setInputText] = useState("");
  const [useStructured, setUseStructured] = useState(true);
  const [temperature, setTemperature] = useState("");
  const [maxTokens, setMaxTokens] = useState("");

  // --- execution state ---
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<TaskExecutionResult | null>(null);
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
          fetchTasks(),
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
      const res = await fetchProviderModels({
        provider: selectedProvider as ProviderId,
        api_key: apiKey,
      });
      setModels(res.models);
      if (res.models.length > 0) setSelectedModelId(res.models[0].model_id);
    } catch (err) {
      setModelsError(err instanceof Error ? err.message : "Failed to load models.");
    } finally {
      setModelsLoading(false);
    }
  }

  async function handleExecute(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTaskId || !selectedProvider || !selectedModelId || !apiKey.trim() || !inputText.trim()) return;

    setExecuting(true);
    setResult(null);
    setEvents([]);
    setExecError(null);

    try {
      const res = await executeTask({
        task_id: selectedTaskId,
        input: { text: inputText.trim(), parameters: {} },
        provider: selectedProvider,
        model_id: selectedModelId,
        api_key: apiKey,
        max_tokens: maxTokens ? parseInt(maxTokens, 10) : null,
        temperature: temperature ? parseFloat(temperature) : null,
        use_structured_output: useStructured,
      });
      setResult(res.result);
      setEvents(res.events);
    } catch (err) {
      setExecError(err instanceof Error ? err.message : "Execution failed.");
    } finally {
      setExecuting(false);
    }
  }

  if (loading) {
    return <main style={pageStyle}><section style={containerStyle}><div style={panelStyle}>Loading task lab...</div></section></main>;
  }
  if (loadError) {
    return <main style={pageStyle}><section style={containerStyle}><div style={errorPanelStyle}>{loadError}</div></section></main>;
  }

  const selectedTask = tasks.find((t) => t.task_id === selectedTaskId);

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <header style={{ marginBottom: "1.5rem" }}>
          <p style={breadcrumbStyle}>Tasks</p>
          <h1 style={titleStyle}>Task Execution Lab</h1>
          <p style={subtitleStyle}>
            Execute generic infrastructure tasks against BYOK providers. Results include structured output and execution events.
          </p>
        </header>

        <div style={layoutStyle}>
          {/* --- Configuration --- */}
          <form onSubmit={handleExecute} style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Configuration</h2>

            <label style={fieldStyle}>
              <span style={labelStyle}>Task</span>
              <select value={selectedTaskId} onChange={(e) => setSelectedTaskId(e.target.value)} style={inputStyle}>
                {tasks.map((t) => (
                  <option key={t.task_id} value={t.task_id}>{t.display_name} ({t.task_id})</option>
                ))}
              </select>
            </label>

            {selectedTask && (
              <div style={hintStyle}>
                {selectedTask.description}
                <br />Category: {selectedTask.category} | Structured output: {selectedTask.supports_structured_output ? "yes" : "no"}
              </div>
            )}

            <label style={fieldStyle}>
              <span style={labelStyle}>Provider</span>
              <select value={selectedProvider} onChange={(e) => { setSelectedProvider(e.target.value); setModels([]); setSelectedModelId(""); }} style={inputStyle}>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>{p.display_name} ({p.id})</option>
                ))}
              </select>
            </label>

            <label style={fieldStyle}>
              <span style={labelStyle}>API Key</span>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                style={inputStyle}
                autoComplete="off"
                spellCheck={false}
                placeholder="Enter provider API key"
              />
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
                  {models.map((m) => (
                    <option key={m.model_id} value={m.model_id}>{m.display_name ?? m.model_id}</option>
                  ))}
                </select>
              ) : (
                <input value={selectedModelId} onChange={(e) => setSelectedModelId(e.target.value)} style={inputStyle} placeholder="Enter model ID or fetch models above" />
              )}
            </label>

            <label style={fieldStyle}>
              <span style={labelStyle}>Input Text</span>
              <textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                style={textareaStyle}
                rows={6}
                placeholder="Enter text for the task..."
                required
              />
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
              <button type="submit" style={primaryButtonStyle} disabled={executing || !inputText.trim() || !selectedModelId || !apiKey.trim()}>
                {executing ? "Executing..." : "Execute Task"}
              </button>
            </div>

            {execError && <div style={errorPanelStyle}>{execError}</div>}
          </form>

          {/* --- Results --- */}
          <div style={sectionCardStyle}>
            <h2 style={sectionTitleStyle}>Result</h2>

            {!result && !execError && (
              <div style={panelStyle}>Execute a task to see results here.</div>
            )}

            {result && (
              <div style={stackStyle}>
                <div style={resultHeaderStyle}>
                  <span style={badgeStyle(result.finish_reason === "completed" ? "#16a34a" : "#dc2626")}>
                    {result.finish_reason}
                  </span>
                  <span style={metaTextStyle}>{result.provider} / {result.model_id}</span>
                  {result.duration_ms != null && <span style={metaTextStyle}>{result.duration_ms}ms</span>}
                </div>

                {result.usage && (
                  <div style={usageRowStyle}>
                    {result.usage.input_tokens != null && <span>Input: {result.usage.input_tokens} tokens</span>}
                    {result.usage.output_tokens != null && <span>Output: {result.usage.output_tokens} tokens</span>}
                    {result.usage.total_tokens != null && <span>Total: {result.usage.total_tokens} tokens</span>}
                  </div>
                )}

                {result.error && (
                  <div style={errorPanelStyle}>
                    <strong>{result.error.error_code}</strong>: {result.error.message}
                  </div>
                )}

                {result.structured_output && (
                  <div>
                    <h3 style={subTitleStyle}>Structured Output</h3>
                    <div style={hintStyle}>
                      Schema valid: {result.structured_output.schema_valid ? "✓" : "✗"}
                      {result.structured_output.validation_errors.length > 0 && (
                        <> | Errors: {result.structured_output.validation_errors.join(", ")}</>
                      )}
                    </div>
                    <pre style={preStyle}>{JSON.stringify(result.structured_output.parsed, null, 2)}</pre>
                  </div>
                )}

                {result.output_text && !result.structured_output && (
                  <div>
                    <h3 style={subTitleStyle}>Output Text</h3>
                    <pre style={preStyle}>{result.output_text}</pre>
                  </div>
                )}
              </div>
            )}

            {events.length > 0 && (
              <div style={{ marginTop: "1.5rem" }}>
                <h3 style={subTitleStyle}>Execution Events</h3>
                <div style={stackStyle}>
                  {events.map((evt, i) => (
                    <div key={i} style={eventRowStyle}>
                      <span style={eventKindStyle}>{evt.kind}</span>
                      <span style={metaTextStyle}>{evt.timestamp}</span>
                      {Object.keys(evt.metadata).length > 0 && (
                        <pre style={eventMetaStyle}>{JSON.stringify(evt.metadata, null, 2)}</pre>
                      )}
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
const containerStyle: CSSProperties = { maxWidth: "1200px", margin: "0 auto" };
const breadcrumbStyle: CSSProperties = { margin: 0, textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "0.8rem", color: "#64748b" };
const titleStyle: CSSProperties = { margin: "0.5rem 0 0", fontSize: "2.2rem", color: "#102033" };
const subtitleStyle: CSSProperties = { maxWidth: "700px", color: "#55657a", lineHeight: 1.6, marginTop: "0.5rem" };
const layoutStyle: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", alignItems: "start" };
const sectionCardStyle: CSSProperties = { padding: "1.5rem", border: "1px solid #d7dee8", borderRadius: "12px", backgroundColor: "#fff" };
const sectionTitleStyle: CSSProperties = { margin: "0 0 1rem", fontSize: "1.2rem", color: "#102033" };
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
const resultHeaderStyle: CSSProperties = { display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" };
const metaTextStyle: CSSProperties = { fontSize: "0.82rem", color: "#64748b" };
const usageRowStyle: CSSProperties = { display: "flex", gap: "1.5rem", fontSize: "0.85rem", color: "#475569" };
const preStyle: CSSProperties = { margin: 0, padding: "0.75rem", backgroundColor: "#f1f5f9", borderRadius: "6px", fontSize: "0.82rem", overflow: "auto", maxHeight: "400px", whiteSpace: "pre-wrap", wordBreak: "break-word" };
const eventRowStyle: CSSProperties = { padding: "0.5rem 0.75rem", border: "1px solid #e2e8f0", borderRadius: "6px", backgroundColor: "#fafbfc" };
const eventKindStyle: CSSProperties = { fontWeight: 600, fontSize: "0.85rem", color: "#102033", marginRight: "0.5rem" };
const eventMetaStyle: CSSProperties = { ...preStyle, marginTop: "0.25rem", fontSize: "0.78rem", maxHeight: "150px" };

function badgeStyle(color: string): CSSProperties {
  return {
    display: "inline-block",
    padding: "0.2rem 0.6rem",
    borderRadius: "999px",
    fontSize: "0.78rem",
    fontWeight: 600,
    color: "#fff",
    backgroundColor: color,
  };
}
