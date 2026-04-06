/**
 * Transforms a TopologyResponse into React Flow nodes and edges.
 *
 * Layout is computed with a simple deterministic algorithm:
 * - workflows on the left column
 * - agents in the center, stacked vertically
 * - future categories can be placed in additional columns
 */

import type { Node, Edge } from "@xyflow/react";
import type {
  TopologyResponse,
  TopologyNode,
  TopologyEdge,
} from "@casegraph/agent-sdk";

// --- Node data contract visible to custom components ----------------------

export interface AgentNodeData {
  label: string;
  description?: string;
  acceptedTaskTypes?: string[];
  capabilityCount?: number;
  [key: string]: unknown;
}

export interface WorkflowNodeData {
  label: string;
  description?: string;
  stepCount?: number;
  [key: string]: unknown;
}

// --- Layout constants -----------------------------------------------------

const COL_WORKFLOW_X = 0;
const COL_AGENT_X = 360;
const ROW_GAP = 140;
const INITIAL_Y = 40;

// --- Edge styling by type -------------------------------------------------

const EDGE_STYLES: Record<string, Partial<Edge>> = {
  handoff: {
    animated: true,
    style: { stroke: "#6366f1", strokeWidth: 2 },
  },
  step: {
    animated: false,
    style: { stroke: "#0ea5e9", strokeWidth: 2, strokeDasharray: "6 3" },
  },
  membership: {
    animated: false,
    style: { stroke: "#94a3b8", strokeWidth: 1.5 },
  },
};

// --- Transform function ---------------------------------------------------

export function toReactFlowGraph(topology: TopologyResponse): {
  nodes: Node[];
  edges: Edge[];
} {
  const agentNodes = topology.nodes.filter((n) => n.category === "agent");
  const workflowNodes = topology.nodes.filter(
    (n) => n.category === "workflow",
  );

  const nodes: Node[] = [];

  // Layout agents
  agentNodes.forEach((n, i) => {
    nodes.push(toFlowNode(n, COL_AGENT_X, INITIAL_Y + i * ROW_GAP));
  });

  // Layout workflows
  workflowNodes.forEach((n, i) => {
    nodes.push(toFlowNode(n, COL_WORKFLOW_X, INITIAL_Y + i * ROW_GAP));
  });

  // Convert edges
  const edges: Edge[] = topology.edges.map(toFlowEdge);

  return { nodes, edges };
}

// --- Helpers --------------------------------------------------------------

function toFlowNode(node: TopologyNode, x: number, y: number): Node {
  const base = {
    id: node.id,
    position: { x, y },
  };

  switch (node.category) {
    case "agent":
      return {
        ...base,
        type: "agentNode",
        data: {
          label: node.label,
          description: node.description,
          acceptedTaskTypes: (node.meta?.accepted_task_types ?? []) as string[],
          capabilityCount: (node.meta?.capability_count ?? 0) as number,
        },
      };
    case "workflow":
      return {
        ...base,
        type: "workflowNode",
        data: {
          label: node.label,
          description: node.description,
          stepCount: (node.meta?.step_count ?? 0) as number,
        },
      };
    default:
      return {
        ...base,
        type: "default",
        data: {
          label: node.label,
          description: node.description,
          ...node.meta,
        },
      };
  }
}

function toFlowEdge(edge: TopologyEdge): Edge {
  const styling = EDGE_STYLES[edge.type] ?? {};
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.label,
    ...styling,
  };
}
