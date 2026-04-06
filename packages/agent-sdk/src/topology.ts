/**
 * Visual topology contracts for the CaseGraph platform.
 *
 * These types describe the normalized graph structure used to render
 * agent/workflow topology in the frontend. The backend derives this
 * from the existing agent and workflow registries.
 */

// ---------------------------------------------------------------------------
// Node categories
// ---------------------------------------------------------------------------

export type TopologyNodeCategory = "agent" | "workflow" | "service";

// ---------------------------------------------------------------------------
// Nodes
// ---------------------------------------------------------------------------

export interface TopologyNode {
  id: string;
  label: string;
  category: TopologyNodeCategory;
  /** Optional short description shown in tooltips or subtitles. */
  description?: string;
  /** Category-specific metadata bag. */
  meta?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Edge types
// ---------------------------------------------------------------------------

export type TopologyEdgeType = "handoff" | "step" | "membership";

export interface TopologyEdge {
  id: string;
  source: string;
  target: string;
  type: TopologyEdgeType;
  label?: string;
}

// ---------------------------------------------------------------------------
// Response
// ---------------------------------------------------------------------------

export interface TopologyResponse {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}
