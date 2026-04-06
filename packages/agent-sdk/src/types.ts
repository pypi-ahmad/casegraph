import type { ProviderId } from "./providers";
import type { AgentCapability, AgentCapabilityStatus, AgentMetadata } from "./agents";

export type ModelProvider = ProviderId;

export type { AgentCapability, AgentCapabilityStatus, AgentMetadata };

/** @deprecated Use AgentMetadata instead. */
export type AgentDefinition = AgentMetadata;
