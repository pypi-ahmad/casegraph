"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";

import type { CaseTypeTemplateMetadata } from "@casegraph/agent-sdk";

import { createCase } from "@/lib/cases-api";
import { fetchCaseTypeDetail } from "@/lib/domains-api";
import { fetchWorkflows } from "@/lib/runtime-api";

import type { WorkflowDefinition } from "@casegraph/workflows";

export default function NewCaseClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const domainPackId = searchParams.get("domain_pack_id");
  const caseTypeId = searchParams.get("case_type_id");

  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [caseType, setCaseType] = useState<CaseTypeTemplateMetadata | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [summary, setSummary] = useState("");
  const [workflowId, setWorkflowId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [workflowsResp, caseTypeResp] = await Promise.all([
          fetchWorkflows(),
          caseTypeId
            ? fetchCaseTypeDetail(caseTypeId).catch(() => null)
            : Promise.resolve(null),
        ]);
        if (!cancelled) {
          setWorkflows(workflowsResp.workflows);
          if (caseTypeResp) {
            setCaseType(caseTypeResp.case_type);
            if (!title) setTitle(caseTypeResp.case_type.display_name);
            if (!category) setCategory(caseTypeResp.pack_metadata.domain_category);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to load data.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseTypeId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setError("Case title is required.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const created = await createCase({
        title: trimmedTitle,
        category: category.trim() || null,
        summary: summary.trim() || null,
        metadata: {},
        workflow_id: workflowId || null,
        domain_pack_id: domainPackId || null,
        case_type_id: caseTypeId || null,
      });
      router.push(`/cases/${created.case_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create case.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main style={pageStyle}>
      <section style={containerStyle}>
        <Link href="/cases" style={backLinkStyle}>
          Back to cases
        </Link>
        <header style={{ marginBottom: "1.5rem" }}>
          <p style={breadcrumbStyle}>Cases</p>
          <h1 style={titleStyle}>Create Case</h1>
          <p style={subtitleStyle}>
            Open a new case and optionally select a processing workflow.
          </p>
        </header>

        {loading ? (
          <div style={panelStyle}>Loading options...</div>
        ) : (
          <form onSubmit={handleSubmit} style={formStyle}>
            {caseType && (
              <div style={domainContextPanelStyle}>
                <strong>Domain Context:</strong> {caseType.display_name}
                <br />
                <span style={{ fontSize: "0.82rem", color: "#55657a" }}>
                  Pack: {domainPackId} · Case Type: {caseType.case_type_id}
                  {caseType.document_requirements.length > 0 && (
                    <> · {caseType.document_requirements.length} document requirement{caseType.document_requirements.length > 1 ? "s" : ""}</>
                  )}
                </span>
              </div>
            )}

            <label style={fieldStyle}>
              <span style={labelStyle}>Title</span>
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                style={inputStyle}
                maxLength={160}
                required
              />
            </label>

            <label style={fieldStyle}>
              <span style={labelStyle}>Category</span>
              <input
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                style={inputStyle}
                maxLength={80}
                placeholder="Generic case category"
              />
            </label>

            <label style={fieldStyle}>
              <span style={labelStyle}>Summary</span>
              <textarea
                value={summary}
                onChange={(event) => setSummary(event.target.value)}
                style={textareaStyle}
                rows={5}
                maxLength={2000}
              />
            </label>

            <label style={fieldStyle}>
              <span style={labelStyle}>Workflow</span>
              <select
                value={workflowId}
                onChange={(event) => setWorkflowId(event.target.value)}
                style={inputStyle}
              >
                <option value="">No workflow selected</option>
                {workflows.map((workflow) => (
                  <option key={workflow.id} value={workflow.id}>
                    {workflow.display_name}
                  </option>
                ))}
              </select>
            </label>

            {error && <div style={errorPanelStyle}>{error}</div>}

            <div style={actionRowStyle}>
              <button type="submit" style={primaryButtonStyle} disabled={saving}>
                {saving ? "Creating..." : "Create Case"}
              </button>
            </div>
          </form>
        )}
      </section>
    </main>
  );
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  padding: "2.5rem 1.25rem 3rem",
  backgroundColor: "#f5f7fa",
};

const containerStyle: CSSProperties = {
  maxWidth: "920px",
  margin: "0 auto",
};

const breadcrumbStyle: CSSProperties = {
  margin: 0,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  fontSize: "0.8rem",
  color: "#64748b",
};

const titleStyle: CSSProperties = {
  margin: "0.5rem 0 0",
  fontSize: "2.2rem",
  color: "#102033",
};

const subtitleStyle: CSSProperties = {
  maxWidth: "700px",
  color: "#55657a",
  lineHeight: 1.6,
};

const backLinkStyle: CSSProperties = {
  display: "inline-flex",
  marginBottom: "1rem",
  color: "#102033",
  textDecoration: "none",
  fontWeight: 600,
};

const panelStyle: CSSProperties = {
  padding: "1rem 1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  backgroundColor: "#ffffff",
  color: "#334155",
};

const domainContextPanelStyle: CSSProperties = {
  padding: "0.9rem 1rem",
  border: "1px solid #bfdbfe",
  borderRadius: "12px",
  backgroundColor: "#eff6ff",
  color: "#1e40af",
  fontSize: "0.88rem",
};

const formStyle: CSSProperties = {
  display: "grid",
  gap: "1rem",
  padding: "1.25rem",
  border: "1px solid #d7dee8",
  borderRadius: "16px",
  backgroundColor: "#ffffff",
};

const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "0.5rem",
};

const labelStyle: CSSProperties = {
  fontSize: "0.9rem",
  fontWeight: 600,
  color: "#334155",
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "0.7rem 0.85rem",
  borderRadius: "10px",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#102033",
};

const textareaStyle: CSSProperties = {
  ...inputStyle,
  resize: "vertical",
};

const actionRowStyle: CSSProperties = {
  display: "flex",
  justifyContent: "flex-end",
};

const primaryButtonStyle: CSSProperties = {
  padding: "0.7rem 1rem",
  borderRadius: "10px",
  border: "none",
  backgroundColor: "#102033",
  color: "#ffffff",
  fontWeight: 600,
  cursor: "pointer",
};

const errorPanelStyle: CSSProperties = {
  padding: "0.75rem 1rem",
  borderRadius: "10px",
  border: "1px solid #fecaca",
  backgroundColor: "#fff1f2",
  color: "#9f1239",
};