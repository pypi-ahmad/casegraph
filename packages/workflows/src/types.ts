export interface WorkflowStepDefinition {
  id: string;
  display_name: string;
  agent_id: string;
  description: string | null;
  depends_on: string[];
}

export interface WorkflowDefinition {
  id: string;
  display_name: string;
  description: string;
  steps: WorkflowStepDefinition[];
}

export interface WorkflowsResponse {
  workflows: WorkflowDefinition[];
}

/** @deprecated Use WorkflowStepDefinition instead. */
export type WorkflowStep = WorkflowStepDefinition;
