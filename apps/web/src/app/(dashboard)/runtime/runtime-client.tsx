"use client";

import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import type { AgentMetadata } from "@casegraph/agent-sdk";
import type { WorkflowDefinition } from "@casegraph/workflows";

import { fetchAgents, fetchWorkflows } from "@/lib/runtime-api";

export default function RuntimeClient() {
  const [agents, setAgents] = useState<AgentMetadata[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const [agentsRes, workflowsRes] = await Promise.all([
          fetchAgents(),
          fetchWorkflows(),
        ]);
        if (cancelled) return;
        setAgents(agentsRes.agents);
        setWorkflows(workflowsRes.workflows);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Unable to load runtime data.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <header style={{ marginBottom: "2rem" }}>
          <p style={breadcrumbStyle}>Runtime</p>
          <h1 style={titleStyle}>Agents &amp; Workflows</h1>
          <p style={subtitleStyle}>
            Registered agents and workflow definitions from the local agent
            runtime. No business logic or real inference is implemented yet.
          </p>
          <div style={{ padding: "0.6rem 1rem", borderRadius: "8px", backgroundColor: "#fef3c7", border: "1px solid #fde68a", color: "#92400e", fontSize: "0.85rem", marginTop: "0.75rem" }}>
            <strong>Scaffolded module</strong> — This is a pass-through proxy to the agent-runtime service. All data shown here is fetched from <code>http://localhost:8100</code>. No logic, inference, or orchestration runs locally.
          </div>
        </header>

        {loading ? (
          <div style={panelStyle}>Loading runtime metadata...</div>
        ) : error ? (
          <div style={errorPanelStyle}>{error}</div>
        ) : (
          <>
            {/* Agents */}
            <h2 style={sectionTitleStyle}>Registered Agents</h2>
            {agents.length === 0 ? (
              <div style={panelStyle}>No agents registered.</div>
            ) : (
              <div style={gridStyle}>
                {agents.map((agent) => (
                  <article key={agent.id} style={cardStyle}>
                    <h3 style={cardTitleStyle}>{agent.display_name}</h3>
                    <p style={cardIdStyle}>id: {agent.id}</p>
                    <p style={cardDescStyle}>{agent.description}</p>

                    <div style={chipSectionStyle}>
                      <span style={labelStyle}>Accepts:</span>
                      {agent.accepted_task_types.map((t) => (
                        <span key={t} style={chipStyle}>
                          {t}
                        </span>
                      ))}
                    </div>

                    {agent.handoff_targets.length > 0 && (
                      <div style={chipSectionStyle}>
                        <span style={labelStyle}>Handoff →</span>
                        {agent.handoff_targets.map((t) => (
                          <span key={t} style={chipStyle}>
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            )}

            {/* Workflows */}
            <h2 style={{ ...sectionTitleStyle, marginTop: "2.5rem" }}>
              Available Workflows
            </h2>
            {workflows.length === 0 ? (
              <div style={panelStyle}>No workflows defined.</div>
            ) : (
              <div style={gridStyle}>
                {workflows.map((wf) => (
                  <article key={wf.id} style={cardStyle}>
                    <h3 style={cardTitleStyle}>{wf.display_name}</h3>
                    <p style={cardIdStyle}>id: {wf.id}</p>
                    <p style={cardDescStyle}>{wf.description}</p>

                    <div style={{ marginTop: "0.75rem" }}>
                      <span style={labelStyle}>Steps:</span>
                      <ol style={stepListStyle}>
                        {wf.steps.map((step) => (
                          <li key={step.id} style={stepItemStyle}>
                            <strong>{step.display_name}</strong>{" "}
                            <span style={stepAgentStyle}>
                              (agent: {step.agent_id})
                            </span>
                            {step.depends_on.length > 0 && (
                              <span style={stepDepsStyle}>
                                {" "}
                                — after {step.depends_on.join(", ")}
                              </span>
                            )}
                          </li>
                        ))}
                      </ol>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

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
  maxWidth: "760px",
  color: "#55657a",
  lineHeight: 1.6,
};

const panelStyle: CSSProperties = {
  padding: "1rem 1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  backgroundColor: "#ffffff",
  color: "#334155",
};

const errorPanelStyle: CSSProperties = {
  ...panelStyle,
  borderColor: "#ef4444",
  color: "#991b1b",
};

const sectionTitleStyle: CSSProperties = {
  fontSize: "1.1rem",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "#475569",
  margin: "0 0 1rem",
};

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
  gap: "1rem",
};

const cardStyle: CSSProperties = {
  padding: "1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "18px",
  backgroundColor: "#ffffff",
  boxShadow: "0 16px 32px rgba(15, 23, 42, 0.06)",
};

const cardTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.25rem",
  color: "#102033",
};

const cardIdStyle: CSSProperties = {
  margin: "0.25rem 0 0",
  fontSize: "0.85rem",
  color: "#94a3b8",
  fontFamily: "monospace",
};

const cardDescStyle: CSSProperties = {
  margin: "0.5rem 0 0",
  color: "#617287",
  lineHeight: 1.5,
};

const chipSectionStyle: CSSProperties = {
  marginTop: "0.75rem",
  display: "flex",
  flexWrap: "wrap",
  alignItems: "center",
  gap: "0.4rem",
};

const labelStyle: CSSProperties = {
  fontSize: "0.85rem",
  fontWeight: 600,
  color: "#475569",
  marginRight: "0.25rem",
};

const chipStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid #d5deea",
  borderRadius: "999px",
  padding: "0.25rem 0.6rem",
  backgroundColor: "#f8fafc",
  color: "#475569",
  fontSize: "0.85rem",
  fontFamily: "monospace",
};

const stepListStyle: CSSProperties = {
  margin: "0.5rem 0 0 1.25rem",
  padding: 0,
  lineHeight: 1.7,
};

const stepItemStyle: CSSProperties = {
  color: "#334155",
  fontSize: "0.95rem",
};

const stepAgentStyle: CSSProperties = {
  color: "#64748b",
  fontSize: "0.85rem",
  fontFamily: "monospace",
};

const stepDepsStyle: CSSProperties = {
  color: "#94a3b8",
  fontSize: "0.85rem",
};
