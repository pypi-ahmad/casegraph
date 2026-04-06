import type {
  PacketArtifactListResponse,
  PacketDetailResponse,
  PacketGenerateRequest,
  PacketGenerateResponse,
  PacketListResponse,
  PacketManifestResponse,
} from "@casegraph/agent-sdk";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

async function getErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string" && payload.detail) {
      return payload.detail;
    }
  } catch {
    /* ignore */
  }
  return fallback;
}

export async function generatePacket(
  caseId: string,
  payload?: PacketGenerateRequest,
): Promise<PacketGenerateResponse> {
  const response = await fetch(
    `${API_BASE_URL}/cases/${caseId}/packets/generate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to generate packet."),
    );
  }
  return (await response.json()) as PacketGenerateResponse;
}

export async function fetchPackets(
  caseId: string,
): Promise<PacketListResponse> {
  const response = await fetch(
    `${API_BASE_URL}/cases/${caseId}/packets`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load packets."),
    );
  }
  return (await response.json()) as PacketListResponse;
}

export async function fetchPacketDetail(
  packetId: string,
): Promise<PacketDetailResponse> {
  const response = await fetch(
    `${API_BASE_URL}/packets/${packetId}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load packet detail."),
    );
  }
  return (await response.json()) as PacketDetailResponse;
}

export async function fetchPacketManifest(
  packetId: string,
): Promise<PacketManifestResponse> {
  const response = await fetch(
    `${API_BASE_URL}/packets/${packetId}/manifest`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load packet manifest."),
    );
  }
  return (await response.json()) as PacketManifestResponse;
}

export async function fetchPacketArtifacts(
  packetId: string,
): Promise<PacketArtifactListResponse> {
  const response = await fetch(
    `${API_BASE_URL}/packets/${packetId}/artifacts`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      await getErrorMessage(response, "Unable to load packet artifacts."),
    );
  }
  return (await response.json()) as PacketArtifactListResponse;
}

export function artifactDownloadUrl(
  packetId: string,
  artifactId: string,
): string {
  return `${API_BASE_URL}/packets/${packetId}/download/${artifactId}`;
}
