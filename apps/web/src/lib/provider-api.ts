import type {
  ModelDiscoveryRequest,
  ModelDiscoveryResponse,
  ProvidersResponse,
  ProviderValidationRequest,
  ProviderValidationResponse,
} from "@casegraph/agent-sdk";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

interface ApiErrorDetail {
  message?: string;
}

async function getErrorMessage(
  response: Response,
  fallbackMessage: string,
): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: ApiErrorDetail | string };
    if (typeof payload.detail === "string" && payload.detail) {
      return payload.detail;
    }

    if (
      payload.detail &&
      typeof payload.detail === "object" &&
      typeof payload.detail.message === "string" &&
      payload.detail.message
    ) {
      return payload.detail.message;
    }
  } catch {
    return fallbackMessage;
  }

  return fallbackMessage;
}

export async function fetchProviders(): Promise<ProvidersResponse> {
  const response = await fetch(`${API_BASE_URL}/providers`, {
    method: "GET",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load providers."));
  }

  return (await response.json()) as ProvidersResponse;
}

export async function validateProviderKey(
  payload: ProviderValidationRequest,
): Promise<ProviderValidationResponse> {
  const response = await fetch(`${API_BASE_URL}/providers/validate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to validate the API key."));
  }

  return (await response.json()) as ProviderValidationResponse;
}

export async function fetchProviderModels(
  payload: ModelDiscoveryRequest,
): Promise<ModelDiscoveryResponse> {
  const response = await fetch(`${API_BASE_URL}/providers/models`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, "Unable to load models from the provider."));
  }

  return (await response.json()) as ModelDiscoveryResponse;
}