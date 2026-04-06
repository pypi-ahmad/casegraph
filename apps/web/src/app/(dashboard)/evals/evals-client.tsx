"use client";

import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";
import type {
  EvalCapabilitiesResponse,
  EvalSuiteListResponse,
  EvalSuiteDefinition,
  EvalRunResponse,
  EvalRunRecord,
  EvalCaseResult,
  EvalAssertionResult,
  IntegrationInfo,
  BenchmarkSuiteMeta,
} from "@casegraph/agent-sdk";
import {
  fetchEvalCapabilities,
  fetchEvalSuites,
  runEvalSuite,
} from "@/lib/evals-api";

type Tab = "suites" | "capabilities";

export default function EvalsClient() {
  const [tab, setTab] = useState<Tab>("suites");
  const [capabilities, setCapabilities] = useState<EvalCapabilitiesResponse | null>(null);
  const [suites, setSuites] = useState<EvalSuiteListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Run state
  const [runningId, setRunningId] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<EvalRunResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [caps, sts] = await Promise.all([
        fetchEvalCapabilities(),
        fetchEvalSuites(),
      ]);
      setCapabilities(caps);
      setSuites(sts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load eval data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleRun = async (suiteId: string) => {
    setRunningId(suiteId);
    setLastRun(null);
    try {
      const result = await runEvalSuite(suiteId);
      setLastRun(result);
    } catch (err) {
      setLastRun({
        success: false,
        message: err instanceof Error ? err.message : "Run failed.",
        run: { run_id: "", suite_id: suiteId, status: "failed", case_results: [], total_cases: 0, passed_cases: 0, failed_cases: 0, error_cases: 0, skipped_cases: 0, started_at: "", completed_at: "", duration_ms: 0, notes: [] } as EvalRunRecord,
      });
    } finally {
      setRunningId(null);
    }
  };

  return (
    <main style={pageStyle}>
      <section style={headerSection}>
        <p style={breadcrumbStyle}>Evals</p>
        <h1 style={titleStyle}>Evaluation Workspace</h1>
        <p style={subtitleStyle}>
          Workflow regression suites, provider comparison metadata, and
          observability integrations. Seed coverage — not full production benchmarks.
        </p>
      </section>

      <div style={tabBarStyle}>
        <button type="button" onClick={() => setTab("suites")} style={tab === "suites" ? activeTabStyle : tabBtnStyle}>
          Eval Suites
        </button>
        <button type="button" onClick={() => setTab("capabilities")} style={tab === "capabilities" ? activeTabStyle : tabBtnStyle}>
          Capabilities & Integrations
        </button>
      </div>

      {loading ? (
        <div style={panelStyle}>Loading evaluation data…</div>
      ) : error ? (
        <div style={errorPanelStyle}>
          <p>{error}</p>
          <button type="button" onClick={load} style={retryBtnStyle}>Retry</button>
        </div>
      ) : tab === "suites" ? (
        <SuitesTab
          suites={suites?.suites ?? []}
          runningId={runningId}
          lastRun={lastRun}
          onRun={handleRun}
        />
      ) : (
        <CapabilitiesTab data={capabilities} />
      )}
    </main>
  );
}

/* ------------------------------------------------------------------ */
/* Suites Tab                                                          */
/* ------------------------------------------------------------------ */

function SuitesTab({
  suites,
  runningId,
  lastRun,
  onRun,
}: {
  suites: EvalSuiteDefinition[];
  runningId: string | null;
  lastRun: EvalRunResponse | null;
  onRun: (suiteId: string) => void;
}) {
  return (
    <div style={contentStyle}>
      {suites.length === 0 && <div style={panelStyle}>No eval suites registered.</div>}

      {suites.map((suite) => (
        <SuiteCard
          key={suite.suite_id}
          suite={suite}
          isRunning={runningId === suite.suite_id}
          runResult={lastRun?.run.suite_id === suite.suite_id ? lastRun : null}
          onRun={() => onRun(suite.suite_id)}
        />
      ))}
    </div>
  );
}

function SuiteCard({
  suite,
  isRunning,
  runResult,
  onRun,
}: {
  suite: EvalSuiteDefinition;
  isRunning: boolean;
  runResult: EvalRunResponse | null;
  onRun: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div style={suiteCardStyle}>
      <div style={suiteHeaderStyle}>
        <div>
          <span style={suiteTitleStyle}>{suite.display_name}</span>
          <span style={categoryBadgeStyle}>{suite.category.replace(/_/g, " ")}</span>
          <span style={countBadgeStyle}>{suite.cases.length} cases</span>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button type="button" onClick={() => setExpanded(!expanded)} style={smallBtnStyle}>
            {expanded ? "Collapse" : "Details"}
          </button>
          <button type="button" onClick={onRun} disabled={isRunning} style={runBtnStyle}>
            {isRunning ? "Running…" : "Run Suite"}
          </button>
        </div>
      </div>

      <p style={suiteDescStyle}>{suite.description}</p>

      {suite.target_ids.length > 0 && (
        <div style={targetListStyle}>
          <span style={labelStyle}>Targets:</span>
          {suite.target_ids.map((id) => (
            <code key={id} style={targetCodeStyle}>{id}</code>
          ))}
        </div>
      )}

      {suite.limitations.length > 0 && (
        <div style={limitationsStyle}>
          {suite.limitations.map((l) => (
            <span key={l} style={limitationTagStyle}>{l}</span>
          ))}
        </div>
      )}

      {expanded && (
        <div style={casesListStyle}>
          <h4 style={casesHeaderStyle}>Eval Cases</h4>
          {suite.cases.map((c) => (
            <div key={c.case_id} style={caseItemStyle}>
              <strong>{c.display_name}</strong>
              <p style={caseDescStyle}>{c.description}</p>
              <div style={fixtureTagStyle}>
                Fixture: {c.fixture.display_name} · {c.fixture.document_filenames.length} doc(s) · {c.assertions.length} assertion(s)
              </div>
            </div>
          ))}
        </div>
      )}

      {runResult && (
        <RunResultPanel run={runResult.run} message={runResult.message} />
      )}
    </div>
  );
}

function RunResultPanel({ run, message }: { run: EvalRunRecord; message: string }) {
  const [showDetails, setShowDetails] = useState(false);
  const statusColor = run.status === "completed" ? "#16a34a" : run.status === "completed_partial" ? "#ca8a04" : "#dc2626";

  return (
    <div style={runPanelStyle}>
      <div style={runHeaderStyle}>
        <span style={{ ...statusBadge, backgroundColor: statusColor }}>{run.status}</span>
        <span style={runStatsStyle}>
          {run.passed_cases} passed · {run.failed_cases} failed · {run.error_cases} errors · {run.duration_ms.toFixed(0)}ms
        </span>
        {run.case_results.length > 0 && (
          <button type="button" onClick={() => setShowDetails(!showDetails)} style={smallBtnStyle}>
            {showDetails ? "Hide Assertions" : "Show Assertions"}
          </button>
        )}
      </div>
      <p style={runMsgStyle}>{message}</p>

      {showDetails && run.case_results.map((cr) => (
        <CaseResultDetail key={cr.case_id} result={cr} />
      ))}
    </div>
  );
}

function CaseResultDetail({ result }: { result: EvalCaseResult }) {
  const statusColor = result.status === "pass" ? "#16a34a" : result.status === "fail" ? "#dc2626" : "#94a3b8";
  return (
    <div style={caseResultStyle}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <span style={{ ...assertionDot, backgroundColor: statusColor }} />
        <strong>{result.display_name}</strong>
        <span style={caseTimingStyle}>{result.duration_ms.toFixed(0)}ms</span>
      </div>
      {result.error_message && <p style={errorTextStyle}>{result.error_message}</p>}
      {result.assertion_results.map((ar, i) => (
        <AssertionLine key={`${ar.assertion_id}-${i}`} result={ar} />
      ))}
    </div>
  );
}

function AssertionLine({ result }: { result: EvalAssertionResult }) {
  const icon = result.status === "pass" ? "✓" : result.status === "fail" ? "✗" : "–";
  const color = result.status === "pass" ? "#16a34a" : result.status === "fail" ? "#dc2626" : "#94a3b8";
  return (
    <div style={assertionLineStyle}>
      <span style={{ color, fontWeight: 600, marginRight: "0.4rem" }}>{icon}</span>
      <span style={assertionTypeStyle}>{result.assertion_type}</span>
      <span style={assertionMsgStyle}>{result.message}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Capabilities Tab                                                    */
/* ------------------------------------------------------------------ */

function CapabilitiesTab({ data }: { data: EvalCapabilitiesResponse | null }) {
  if (!data) return <div style={panelStyle}>No capability data available.</div>;

  return (
    <div style={contentStyle}>
      <section style={sectionStyle}>
        <h2 style={sectionTitleStyle}>Integrations</h2>
        <div style={gridStyle}>
          {data.integrations.map((i) => <IntegrationCard key={i.id} info={i} />)}
        </div>
      </section>

      <section style={sectionStyle}>
        <h2 style={sectionTitleStyle}>Promptfoo Benchmark Suites</h2>
        <div style={gridStyle}>
          {data.benchmark_suites.map((s) => <BenchmarkCard key={s.id} suite={s} />)}
        </div>
      </section>

      <section style={sectionStyle}>
        <h2 style={sectionTitleStyle}>Current Limitations</h2>
        <ul style={listStyle}>
          {data.limitations.map((t) => <li key={t} style={listItemStyle}>{t}</li>)}
        </ul>
      </section>
    </div>
  );
}

function IntegrationCard({ info }: { info: IntegrationInfo }) {
  const statusColor = info.status === "configured" ? "#16a34a" : info.status === "available" ? "#ca8a04" : "#94a3b8";
  const statusLabel = info.status === "configured" ? "Configured" : info.status === "available" ? "Available" : "Not configured";
  return (
    <div style={cardStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={cardTitleStyle}>{info.display_name}</span>
        <span style={{ ...badgeStyle, backgroundColor: statusColor }}>{statusLabel}</span>
      </div>
      <ul style={noteListStyle}>
        {info.notes.map((n) => <li key={n} style={noteStyle}>{n}</li>)}
      </ul>
    </div>
  );
}

function BenchmarkCard({ suite }: { suite: BenchmarkSuiteMeta }) {
  return (
    <div style={cardStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={cardTitleStyle}>{suite.display_name}</span>
        <span style={categoryBadgeStyle}>{suite.category.replace(/_/g, " ")}</span>
      </div>
      <p style={cardDescStyle}>{suite.description}</p>
      <code style={codeStyle}>{suite.config_path}</code>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Styles                                                              */
/* ------------------------------------------------------------------ */

const pageStyle: CSSProperties = { minHeight: "100vh", padding: "2.5rem 1.25rem 2rem", backgroundColor: "#f5f7fa" };
const headerSection: CSSProperties = { maxWidth: "1120px", margin: "0 auto 1rem" };
const breadcrumbStyle: CSSProperties = { margin: 0, textTransform: "uppercase", letterSpacing: "0.08em", fontSize: "0.8rem", color: "#64748b" };
const titleStyle: CSSProperties = { margin: "0.5rem 0 0", fontSize: "2.2rem", color: "#102033" };
const subtitleStyle: CSSProperties = { maxWidth: "760px", color: "#55657a", lineHeight: 1.6 };
const contentStyle: CSSProperties = { maxWidth: "1120px", margin: "0 auto" };
const panelStyle: CSSProperties = { maxWidth: "1120px", margin: "0 auto", padding: "1rem 1.25rem", border: "1px solid #d7dee8", borderRadius: "16px", backgroundColor: "#fff", color: "#334155" };
const errorPanelStyle: CSSProperties = { ...panelStyle, borderColor: "#fca5a5", backgroundColor: "#fef2f2" };
const retryBtnStyle: CSSProperties = { marginTop: "0.5rem", padding: "0.4rem 1rem", border: "1px solid #d7dee8", borderRadius: "8px", cursor: "pointer", backgroundColor: "#fff" };

// Tabs
const tabBarStyle: CSSProperties = { maxWidth: "1120px", margin: "0 auto 1.5rem", display: "flex", gap: "0.5rem" };
const tabBtnStyle: CSSProperties = { padding: "0.5rem 1.2rem", border: "1px solid #d7dee8", borderRadius: "8px", cursor: "pointer", backgroundColor: "#fff", color: "#334155", fontSize: "0.9rem" };
const activeTabStyle: CSSProperties = { ...tabBtnStyle, backgroundColor: "#102033", color: "#fff", borderColor: "#102033" };

// Suite cards
const suiteCardStyle: CSSProperties = { marginBottom: "1rem", padding: "1.25rem", border: "1px solid #d7dee8", borderRadius: "16px", backgroundColor: "#fff" };
const suiteHeaderStyle: CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" };
const suiteTitleStyle: CSSProperties = { fontWeight: 700, fontSize: "1.1rem", color: "#102033" };
const suiteDescStyle: CSSProperties = { color: "#55657a", margin: "0.5rem 0", lineHeight: 1.5 };
const categoryBadgeStyle: CSSProperties = { display: "inline-block", marginLeft: "0.5rem", padding: "0.15rem 0.6rem", borderRadius: "999px", backgroundColor: "#e0e7ff", color: "#3730a3", fontSize: "0.75rem", textTransform: "capitalize" };
const countBadgeStyle: CSSProperties = { display: "inline-block", marginLeft: "0.4rem", padding: "0.15rem 0.6rem", borderRadius: "999px", backgroundColor: "#f1f5f9", color: "#475569", fontSize: "0.75rem" };
const targetListStyle: CSSProperties = { display: "flex", flexWrap: "wrap", gap: "0.4rem", alignItems: "center", margin: "0.5rem 0" };
const labelStyle: CSSProperties = { fontSize: "0.8rem", color: "#64748b" };
const targetCodeStyle: CSSProperties = { padding: "0.15rem 0.5rem", borderRadius: "6px", backgroundColor: "#f1f5f9", color: "#334155", fontSize: "0.8rem", fontFamily: "monospace" };
const limitationsStyle: CSSProperties = { display: "flex", flexWrap: "wrap", gap: "0.4rem", margin: "0.5rem 0" };
const limitationTagStyle: CSSProperties = { padding: "0.2rem 0.5rem", borderRadius: "6px", backgroundColor: "#fef3c7", color: "#92400e", fontSize: "0.75rem" };

// Buttons
const smallBtnStyle: CSSProperties = { padding: "0.35rem 0.8rem", border: "1px solid #d7dee8", borderRadius: "8px", cursor: "pointer", backgroundColor: "#fff", fontSize: "0.8rem", color: "#334155" };
const runBtnStyle: CSSProperties = { padding: "0.4rem 1rem", border: "none", borderRadius: "8px", cursor: "pointer", backgroundColor: "#102033", color: "#fff", fontSize: "0.85rem", fontWeight: 600 };

// Cases list
const casesListStyle: CSSProperties = { marginTop: "1rem", padding: "0.75rem", borderTop: "1px solid #e2e8f0" };
const casesHeaderStyle: CSSProperties = { margin: "0 0 0.75rem", fontSize: "0.95rem", color: "#334155" };
const caseItemStyle: CSSProperties = { padding: "0.5rem 0", borderBottom: "1px solid #f1f5f9" };
const caseDescStyle: CSSProperties = { margin: "0.25rem 0", color: "#64748b", fontSize: "0.85rem" };
const fixtureTagStyle: CSSProperties = { fontSize: "0.8rem", color: "#64748b", fontStyle: "italic" };

// Run result panel
const runPanelStyle: CSSProperties = { marginTop: "1rem", padding: "1rem", border: "1px solid #e2e8f0", borderRadius: "12px", backgroundColor: "#f8fafc" };
const runHeaderStyle: CSSProperties = { display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" };
const statusBadge: CSSProperties = { display: "inline-block", padding: "0.2rem 0.6rem", borderRadius: "999px", color: "#fff", fontSize: "0.75rem", fontWeight: 600 };
const runStatsStyle: CSSProperties = { fontSize: "0.85rem", color: "#475569" };
const runMsgStyle: CSSProperties = { margin: "0.5rem 0 0", color: "#55657a", fontSize: "0.85rem" };

// Case result detail
const caseResultStyle: CSSProperties = { padding: "0.5rem 0", borderBottom: "1px solid #f1f5f9" };
const assertionDot: CSSProperties = { display: "inline-block", width: "8px", height: "8px", borderRadius: "50%" };
const caseTimingStyle: CSSProperties = { fontSize: "0.75rem", color: "#94a3b8" };
const errorTextStyle: CSSProperties = { color: "#dc2626", fontSize: "0.8rem", margin: "0.25rem 0" };
const assertionLineStyle: CSSProperties = { display: "flex", alignItems: "baseline", gap: "0.3rem", padding: "0.15rem 0 0.15rem 1rem", fontSize: "0.82rem" };
const assertionTypeStyle: CSSProperties = { color: "#475569", fontFamily: "monospace", fontSize: "0.78rem" };
const assertionMsgStyle: CSSProperties = { color: "#64748b" };

// Capabilities tab
const sectionStyle: CSSProperties = { marginBottom: "1.5rem" };
const sectionTitleStyle: CSSProperties = { margin: "0 0 0.75rem", fontSize: "1.15rem", color: "#102033" };
const gridStyle: CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "1rem" };
const cardStyle: CSSProperties = { padding: "1rem 1.25rem", border: "1px solid #d7dee8", borderRadius: "16px", backgroundColor: "#fff" };
const cardTitleStyle: CSSProperties = { fontWeight: 600, color: "#102033" };
const badgeStyle: CSSProperties = { display: "inline-block", padding: "0.15rem 0.6rem", borderRadius: "999px", color: "#fff", fontSize: "0.75rem", fontWeight: 600 };
const cardDescStyle: CSSProperties = { color: "#55657a", lineHeight: 1.5, fontSize: "0.9rem", margin: "0.5rem 0" };
const codeStyle: CSSProperties = { display: "block", padding: "0.4rem 0.6rem", borderRadius: "6px", backgroundColor: "#f1f5f9", color: "#334155", fontSize: "0.8rem", fontFamily: "monospace" };
const noteListStyle: CSSProperties = { margin: "0.5rem 0 0", paddingLeft: "1rem", listStyle: "disc" };
const noteStyle: CSSProperties = { color: "#64748b", fontSize: "0.85rem", lineHeight: 1.5 };
const listStyle: CSSProperties = { margin: 0, paddingLeft: "1.25rem" };
const listItemStyle: CSSProperties = { color: "#55657a", lineHeight: 1.6 };
