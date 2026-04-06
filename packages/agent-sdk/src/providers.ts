export type ProviderId = "openai" | "anthropic" | "gemini";

export type ProviderCapabilityId =
  | "model_discovery"
  | "text_generation"
  | "embeddings"
  | "vision"
  | "tool_calling";

export type CapabilityPlaceholderStatus = "implemented" | "not_modeled";

export interface ProviderCapabilityPlaceholder {
  id: ProviderCapabilityId;
  display_name: string;
  status: CapabilityPlaceholderStatus;
}

export interface ProviderSummary {
  id: ProviderId;
  display_name: string;
  capabilities: ProviderCapabilityPlaceholder[];
}

export interface ProvidersResponse {
  providers: ProviderSummary[];
}

export interface ModelSummary {
  provider: ProviderId;
  model_id: string;
  display_name: string | null;
  description: string | null;
  created_at: string | null;
  owned_by: string | null;
  input_token_limit: number | null;
  output_token_limit: number | null;
  capabilities: string[];
}

export interface ProviderValidationRequest {
  provider: ProviderId;
  api_key: string;
}

export interface ProviderValidationResponse {
  provider: ProviderId;
  valid: boolean;
  message: string;
  error_code: string | null;
}

export interface ModelDiscoveryRequest {
  provider: ProviderId;
  api_key: string;
}

export interface ModelDiscoveryResponse {
  provider: ProviderId;
  models: ModelSummary[];
}