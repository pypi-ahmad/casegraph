"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import type { Node, Edge, NodeTypes } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { CSSProperties } from "react";

import { fetchTopology } from "@/lib/topology-api";
import { toReactFlowGraph } from "@/lib/topology-transform";
import AgentNode from "@/components/topology/agent-node";
import WorkflowNode from "@/components/topology/workflow-node";

const NODE_TYPES: NodeTypes = {
  agentNode: AgentNode,
  workflowNode: WorkflowNode,
};

export default function TopologyClient() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const topology = await fetchTopology();
      const graph = toReactFlowGraph(topology);
      setNodes(graph.nodes);
      setEdges(graph.edges);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load topology. Check that the API server is running.",
      );
    } finally {
      setLoading(false);
    }
  }, [setNodes, setEdges]);

  useEffect(() => {
    void load();
  }, [load]);

  const legend = useMemo(
    () => (
      <div style={legendStyle}>
        <span style={legendItemStyle}>
          <span style={{ ...legendDot, backgroundColor: "#6366f1" }} /> Agent
        </span>
        <span style={legendItemStyle}>
          <span style={{ ...legendDot, backgroundColor: "#0ea5e9" }} /> Workflow
        </span>
        <span style={legendItemStyle}>
          <span style={{ ...legendLine, borderColor: "#6366f1" }} /> Handoff
        </span>
        <span style={legendItemStyle}>
          <span style={{ ...legendLine, borderColor: "#0ea5e9", borderStyle: "dashed" }} /> Step dep
        </span>
        <span style={legendItemStyle}>
          <span style={{ ...legendLine, borderColor: "#94a3b8" }} /> Member
        </span>
      </div>
    ),
    [],
  );

  return (
    <main style={pageStyle}>
      <section style={headerSection}>
        <p style={breadcrumbStyle}>Topology</p>
        <h1 style={titleStyle}>Visual Flow Inspector</h1>
        <p style={subtitleStyle}>
          Graph of registered agents, workflows, and their relationships.
          Built from live runtime metadata.
        </p>
        <div style={{ padding: "0.6rem 1rem", borderRadius: "8px", backgroundColor: "#fef3c7", border: "1px solid #fde68a", color: "#92400e", fontSize: "0.85rem", marginTop: "0.75rem" }}>
          <strong>Live connection</strong> — This graph shows agents and workflows registered in your runtime. It reflects definitions, not live execution.
        </div>
      </section>

      {loading ? (
        <div style={panelStyle}>Loading topology…</div>
      ) : error ? (
        <div style={errorPanelStyle}>
          <p>{error}</p>
          <button type="button" onClick={load} style={retryBtnStyle}>
            Retry
          </button>
        </div>
      ) : nodes.length === 0 ? (
        <div style={panelStyle}>
          No agents or workflows registered. Start the agent runtime to see
          topology here.
        </div>
      ) : (
        <div style={canvasWrapperStyle}>
          {legend}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={NODE_TYPES}
            fitView
            fitViewOptions={{ padding: 0.3 }}
            proOptions={{ hideAttribution: true }}
            minZoom={0.3}
            maxZoom={2}
          >
            <Background gap={20} size={1} color="#e2e8f0" />
            <Controls showInteractive={false} />
            <MiniMap
              pannable
              zoomable
              nodeColor={(n) =>
                n.type === "agentNode" ? "#eef2ff" : "#f0f9ff"
              }
              style={{ borderRadius: 8 }}
            />
          </ReactFlow>
        </div>
      )}
    </main>
  );
}

/* ------------------------------------------------------------------ */
/* Styles                                                              */
/* ------------------------------------------------------------------ */

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2.5rem 1.25rem 0",
  backgroundColor: "#f5f7fa",
};

const headerSection: CSSProperties = {
  maxWidth: "1120px",
  margin: "0 auto 1.5rem",
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
  maxWidth: "1120px",
  margin: "0 auto",
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

const retryBtnStyle: CSSProperties = {
  marginTop: "0.75rem",
  padding: "0.5rem 1.25rem",
  borderRadius: "8px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  cursor: "pointer",
  fontWeight: 500,
  fontSize: "0.85rem",
};

const canvasWrapperStyle: CSSProperties = {
  position: "relative",
  width: "100%",
  height: "calc(100vh - 220px)",
  minHeight: 400,
  borderRadius: "16px",
  border: "1px solid #d7dee8",
  backgroundColor: "#ffffff",
  overflow: "hidden",
};

const legendStyle: CSSProperties = {
  position: "absolute",
  top: 12,
  left: 12,
  zIndex: 10,
  display: "flex",
  gap: 14,
  padding: "6px 14px",
  borderRadius: "8px",
  backgroundColor: "rgba(255,255,255,0.92)",
  border: "1px solid #e2e8f0",
  fontSize: "0.75rem",
  color: "#475569",
};

const legendItemStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 5,
};

const legendDot: CSSProperties = {
  width: 10,
  height: 10,
  borderRadius: "50%",
  display: "inline-block",
};

const legendLine: CSSProperties = {
  width: 16,
  height: 0,
  borderTop: "2px solid",
  display: "inline-block",
};
