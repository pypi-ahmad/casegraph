"use client";

import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import type { CSSProperties } from "react";
import type { WorkflowNodeData } from "@/lib/topology-transform";

export default function WorkflowNode({ data }: NodeProps) {
  const d = data as WorkflowNodeData;
  return (
    <div style={containerStyle}>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <div style={badgeStyle}>Workflow</div>
      <div style={labelStyle}>{d.label}</div>
      {d.description && <div style={descStyle}>{d.description}</div>}
      {typeof d.stepCount === "number" && d.stepCount > 0 && (
        <div style={metaStyle}>{d.stepCount} steps</div>
      )}
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </div>
  );
}

const containerStyle: CSSProperties = {
  padding: "12px 16px",
  borderRadius: "12px",
  border: "1.5px solid #0ea5e9",
  backgroundColor: "#ffffff",
  minWidth: 180,
  maxWidth: 260,
  fontFamily: "system-ui, sans-serif",
};

const badgeStyle: CSSProperties = {
  display: "inline-block",
  padding: "2px 8px",
  borderRadius: "6px",
  backgroundColor: "#f0f9ff",
  color: "#0369a1",
  fontSize: "0.7rem",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  marginBottom: 6,
};

const labelStyle: CSSProperties = {
  fontWeight: 600,
  fontSize: "0.92rem",
  color: "#1e293b",
  marginBottom: 2,
};

const descStyle: CSSProperties = {
  fontSize: "0.78rem",
  color: "#64748b",
  lineHeight: 1.35,
  marginBottom: 4,
};

const metaStyle: CSSProperties = {
  fontSize: "0.72rem",
  color: "#94a3b8",
  marginTop: 4,
};

const handleStyle: CSSProperties = {
  width: 8,
  height: 8,
  backgroundColor: "#0ea5e9",
};
