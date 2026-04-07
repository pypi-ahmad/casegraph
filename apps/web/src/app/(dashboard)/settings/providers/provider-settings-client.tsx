"use client";

import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import type {
  ModelSummary,
  ProviderId,
  ProviderSummary,
  ProviderValidationResponse,
} from "@casegraph/agent-sdk";

import { fetchProviderModels, fetchProviders, validateProviderKey } from "@/lib/provider-api";

type ProviderCardState = {
  apiKey: string;
  validation: ProviderValidationResponse | null;
  validationLoading: boolean;
  models: ModelSummary[];
  modelsLoading: boolean;
  modelsError: string | null;
};

function createEmptyCardState(): ProviderCardState {
  return {
    apiKey: "",
    validation: null,
    validationLoading: false,
    models: [],
    modelsLoading: false,
    modelsError: null,
  };
}

export default function ProviderSettingsClient() {
  const [providers, setProviders] = useState<ProviderSummary[]>([]);
  const [providerStates, setProviderStates] = useState<Record<string, ProviderCardState>>({});
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadProviders() {
      setPageLoading(true);
      setPageError(null);

      try {
        const response = await fetchProviders();

        if (cancelled) {
          return;
        }

        setProviders(response.providers);
        setProviderStates((currentState) => {
          const nextState = { ...currentState };
          for (const provider of response.providers) {
            nextState[provider.id] = currentState[provider.id] ?? createEmptyCardState();
          }
          return nextState;
        });
      } catch (error) {
        if (!cancelled) {
          setPageError(error instanceof Error ? error.message : "Unable to load providers.");
        }
      } finally {
        if (!cancelled) {
          setPageLoading(false);
        }
      }
    }

    void loadProviders();

    return () => {
      cancelled = true;
    };
  }, []);

  function updateProviderState(
    providerId: ProviderId,
    updater: (currentState: ProviderCardState) => ProviderCardState,
  ) {
    setProviderStates((currentState) => ({
      ...currentState,
      [providerId]: updater(currentState[providerId] ?? createEmptyCardState()),
    }));
  }

  async function handleValidate(providerId: ProviderId) {
    const currentState = providerStates[providerId] ?? createEmptyCardState();
    const apiKey = currentState.apiKey.trim();

    if (!apiKey) {
      updateProviderState(providerId, (state) => ({
        ...state,
        validation: {
          provider: providerId,
          valid: false,
          message: "Enter an API key before validating.",
          error_code: "missing_api_key",
        },
      }));
      return;
    }

    updateProviderState(providerId, (state) => ({
      ...state,
      validationLoading: true,
      validation: null,
    }));

    try {
      const validation = await validateProviderKey({ provider: providerId, api_key: apiKey });
      updateProviderState(providerId, (state) => ({
        ...state,
        validationLoading: false,
        validation,
      }));
    } catch (error) {
      updateProviderState(providerId, (state) => ({
        ...state,
        validationLoading: false,
        validation: {
          provider: providerId,
          valid: false,
          message: error instanceof Error ? error.message : "Unable to validate the API key.",
          error_code: "validation_request_failed",
        },
      }));
    }
  }

  async function handleFetchModels(providerId: ProviderId) {
    const currentState = providerStates[providerId] ?? createEmptyCardState();
    const apiKey = currentState.apiKey.trim();

    if (!apiKey) {
      updateProviderState(providerId, (state) => ({
        ...state,
        modelsError: "Enter an API key before fetching models.",
      }));
      return;
    }

    updateProviderState(providerId, (state) => ({
      ...state,
      modelsLoading: true,
      modelsError: null,
    }));

    try {
      const response = await fetchProviderModels({ provider: providerId, api_key: apiKey });
      updateProviderState(providerId, (state) => ({
        ...state,
        modelsLoading: false,
        models: response.models,
        modelsError: null,
      }));
    } catch (error) {
      updateProviderState(providerId, (state) => ({
        ...state,
        modelsLoading: false,
        models: [],
        modelsError:
          error instanceof Error ? error.message : "Unable to fetch models from the provider.",
      }));
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        padding: "2.5rem 1.25rem 3rem",
        backgroundColor: "#f5f7fa",
      }}
    >
      <section
        style={{
          maxWidth: "1120px",
          margin: "0 auto",
        }}
      >
        <header style={{ marginBottom: "2rem" }}>
          <p
            style={{
              margin: 0,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              fontSize: "0.8rem",
              color: "#64748b",
            }}
          >
            Settings
          </p>
          <h1 style={{ margin: "0.5rem 0 0", fontSize: "2.2rem", color: "#102033" }}>
            AI Provider Settings
          </h1>
          <p style={{ maxWidth: "760px", color: "#55657a", lineHeight: 1.6 }}>
            Configure AI providers for your team. API keys are stored locally in your browser for this session only.
          </p>
        </header>

        {pageLoading ? (
          <div style={panelStyle}>Loading provider registry...</div>
        ) : pageError ? (
          <div style={{ ...panelStyle, borderColor: "#ef4444", color: "#991b1b" }}>
            {pageError}
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
              gap: "1rem",
            }}
          >
            {providers.map((provider) => {
              const state = providerStates[provider.id] ?? createEmptyCardState();

              return (
                <article key={provider.id} style={cardStyle}>
                  <header style={{ marginBottom: "1rem" }}>
                    <h2 style={{ margin: 0, fontSize: "1.25rem", color: "#102033" }}>
                      {provider.display_name}
                    </h2>
                    <p style={{ margin: "0.5rem 0 0", color: "#617287", lineHeight: 1.5 }}>
                      Provider discovery is active. Other provider features remain intentionally
                      unmodeled in this step.
                    </p>
                  </header>

                  <div style={{ marginBottom: "1rem" }}>
                    <label
                      htmlFor={`${provider.id}-api-key`}
                      style={{ display: "block", marginBottom: "0.5rem", fontWeight: 600 }}
                    >
                      API key
                    </label>
                    <input
                      id={`${provider.id}-api-key`}
                      type="password"
                      autoComplete="new-password"
                      autoCapitalize="none"
                      autoCorrect="off"
                      spellCheck={false}
                      disabled={state.validationLoading || state.modelsLoading}
                      value={state.apiKey}
                      onChange={(event) => {
                        const nextValue = event.target.value;
                        updateProviderState(provider.id, (currentState) => ({
                          ...currentState,
                          apiKey: nextValue,
                          validation: null,
                          models: [],
                          modelsError: null,
                        }));
                      }}
                      placeholder={`Enter a ${provider.display_name} API key`}
                      style={inputStyle}
                    />
                  </div>

                  <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      onClick={() => void handleValidate(provider.id)}
                      disabled={state.validationLoading || state.modelsLoading}
                      style={primaryButtonStyle}
                    >
                      {state.validationLoading ? "Validating..." : "Validate key"}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleFetchModels(provider.id)}
                      disabled={state.validationLoading || state.modelsLoading}
                      style={secondaryButtonStyle}
                    >
                      {state.modelsLoading ? "Fetching models..." : "Fetch models"}
                    </button>
                  </div>

                  <section style={sectionStyle}>
                    <h3 style={sectionHeadingStyle}>Status</h3>
                    {state.validation ? (
                      <div
                        style={{
                          ...statusStyle,
                          borderColor: state.validation.valid ? "#16a34a" : "#ef4444",
                          color: state.validation.valid ? "#166534" : "#991b1b",
                          backgroundColor: state.validation.valid ? "#f0fdf4" : "#fef2f2",
                        }}
                      >
                        {state.validation.message}
                      </div>
                    ) : (
                      <div style={mutedTextStyle}>No validation request has been sent yet.</div>
                    )}
                  </section>

                  <section style={sectionStyle}>
                    <h3 style={sectionHeadingStyle}>Capability placeholders</h3>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                      {provider.capabilities.map((capability) => (
                        <span key={capability.id} style={capabilityChipStyle}>
                          {capability.display_name}: {capability.status}
                        </span>
                      ))}
                    </div>
                  </section>

                  <section style={sectionStyle}>
                    <h3 style={sectionHeadingStyle}>Models</h3>
                    {state.modelsError ? (
                      <div
                        style={{
                          ...statusStyle,
                          borderColor: "#ef4444",
                          color: "#991b1b",
                          backgroundColor: "#fef2f2",
                        }}
                      >
                        {state.modelsError}
                      </div>
                    ) : state.models.length > 0 ? (
                      <div
                        style={{
                          display: "grid",
                          gap: "0.75rem",
                          maxHeight: "320px",
                          overflowY: "auto",
                        }}
                      >
                        {state.models.map((model) => (
                          <div key={`${provider.id}-${model.model_id}`} style={modelItemStyle}>
                            <div style={{ fontWeight: 600, color: "#102033" }}>
                              {model.display_name ?? model.model_id}
                            </div>
                            <div style={modelMetaStyle}>ID: {model.model_id}</div>
                            {model.description ? <div style={modelMetaStyle}>{model.description}</div> : null}
                            {model.input_token_limit || model.output_token_limit ? (
                              <div style={modelMetaStyle}>
                                Token limits: input {model.input_token_limit ?? "n/a"} / output{" "}
                                {model.output_token_limit ?? "n/a"}
                              </div>
                            ) : null}
                            {model.capabilities.length > 0 ? (
                              <div style={modelMetaStyle}>
                                Capabilities: {model.capabilities.join(", ")}
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={mutedTextStyle}>No models loaded yet.</div>
                    )}
                  </section>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}

const panelStyle: CSSProperties = {
  padding: "1rem 1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  backgroundColor: "#ffffff",
  color: "#334155",
};

const cardStyle: CSSProperties = {
  padding: "1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "18px",
  backgroundColor: "#ffffff",
  boxShadow: "0 16px 32px rgba(15, 23, 42, 0.06)",
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "0.8rem 0.9rem",
  borderRadius: "12px",
  border: "1px solid #cbd5e1",
  fontSize: "0.95rem",
  color: "#102033",
  boxSizing: "border-box",
};

const primaryButtonStyle: CSSProperties = {
  border: "none",
  borderRadius: "999px",
  backgroundColor: "#102033",
  color: "#ffffff",
  fontWeight: 600,
  padding: "0.75rem 1rem",
  cursor: "pointer",
};

const secondaryButtonStyle: CSSProperties = {
  border: "1px solid #c7d2e0",
  borderRadius: "999px",
  backgroundColor: "#ffffff",
  color: "#102033",
  fontWeight: 600,
  padding: "0.75rem 1rem",
  cursor: "pointer",
};

const sectionStyle: CSSProperties = {
  marginTop: "1.25rem",
};

const sectionHeadingStyle: CSSProperties = {
  margin: "0 0 0.75rem",
  fontSize: "0.95rem",
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: "#64748b",
};

const statusStyle: CSSProperties = {
  padding: "0.8rem 0.9rem",
  border: "1px solid transparent",
  borderRadius: "12px",
  lineHeight: 1.5,
};

const mutedTextStyle: CSSProperties = {
  color: "#64748b",
};

const capabilityChipStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  border: "1px solid #d5deea",
  borderRadius: "999px",
  padding: "0.35rem 0.65rem",
  backgroundColor: "#f8fafc",
  color: "#475569",
  fontSize: "0.85rem",
};

const modelItemStyle: CSSProperties = {
  padding: "0.85rem 0.9rem",
  border: "1px solid #e2e8f0",
  borderRadius: "14px",
  backgroundColor: "#fbfcfe",
};

const modelMetaStyle: CSSProperties = {
  marginTop: "0.3rem",
  color: "#617287",
  fontSize: "0.92rem",
  lineHeight: 1.5,
};