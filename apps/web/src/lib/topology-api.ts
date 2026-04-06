import type { TopologyResponse } from "@casegraph/agent-sdk";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export async function fetchTopology(): Promise<TopologyResponse> {
  const response = await fetch(`${API_BASE_URL}/topology`, {
    method: "GET",
    cache: "no-store",
  });
  if (!response.ok) {
    let message = "Unable to load topology.";
    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string" && payload.detail) {
        message = payload.detail;
      }
    } catch {
      // ignore parse errors
    }
    throw new Error(message);
  }
  return (await response.json()) as TopologyResponse;
}
