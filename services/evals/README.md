# Eval & Observability Foundation

Local-first evaluation and observability scaffolding for CaseGraph.

## Integrations

| Tool                 | Purpose                            | Status                  |
| -------------------- | ---------------------------------- | ----------------------- |
| Promptfoo            | Offline evals, regression testing  | 4 benchmark configs     |
| Langfuse             | LLM traces, prompt/version metadata| Instrumentation hooks   |
| Workflow Regression   | Code-based workflow pack eval      | 3 suites, 8 eval cases  |

## Structure

```
services/evals/
├── promptfoo/              # Promptfoo YAML configs per benchmark class
│   ├── provider-comparison.yaml
│   ├── retrieval-eval.yaml
│   ├── agent-workflow-eval.yaml
│   └── workflow-pack-extraction-eval.yaml
├── datasets/               # Small seed fixtures (scaffold only)
│   ├── provider-comparison-seed.json
│   ├── retrieval-eval-seed.json
│   ├── agent-workflow-eval-seed.json
│   └── workflow-pack-extraction-seed.json
├── langfuse/               # Langfuse setup notes
│   └── README.md
├── config/                 # Shared eval configuration
│   └── env.example
├── scripts/                # Local run helpers
│   ├── run-promptfoo.sh
│   └── run-promptfoo.ps1
└── README.md               # This file
```

## Workflow Regression Suites

The API provides code-based workflow regression suites that execute real
workflow packs against materialized seed fixtures and check deterministic assertions.

| Suite ID                                | Domain            | Cases | Workflow Packs Tested                                      |
| --------------------------------------- | ----------------- | ----- | ---------------------------------------------------------- |
| `medical_insurance_workflow_regression` | Medical Insurance | 3     | `prior_auth_packet_review`, `pre_claim_packet_review`      |
| `insurance_workflow_regression`         | General Insurance | 2     | `insurance_claim_intake_review`, `coverage_correspondence_review` |
| `tax_workflow_regression`               | Tax               | 3     | `tax_intake_packet_review`, `tax_notice_review`            |

### Running workflow regression via API

```bash
# List available suites
curl http://localhost:8000/evals/suites

# Execute a suite
curl -X POST http://localhost:8000/evals/suites/medical_insurance_workflow_regression/run

# View run details
curl http://localhost:8000/evals/runs/<run_id>
```

### Fixtures (8 seed)

Seed fixtures define minimal case setups — 1–3 documents each. They are
materialized into real `CaseRecordModel` + `DocumentRecord` objects before
each eval case executes. No fabricated outputs or hallucinated results.

## Running Promptfoo Locally

### Prerequisites

```bash
npm install -g promptfoo
# or: npx promptfoo@latest
```

### Run a benchmark suite

```bash
# From repo root
cd services/evals

# Provider comparison
./scripts/run-promptfoo.sh provider-comparison

# Retrieval evaluation
./scripts/run-promptfoo.sh retrieval-eval

# Agent/workflow evaluation
./scripts/run-promptfoo.sh agent-workflow-eval

# View results
promptfoo view
```

On Windows PowerShell, use:

```powershell
.\scripts\run-promptfoo.ps1 provider-comparison
```

### Environment variables

Copy `config/env.example` to `config/.env` and fill in the values:

```bash
cp config/env.example config/.env
```

Provider keys must be set for provider-comparison evals.
HTTP-based suites read `CASEGRAPH_API_URL` and default to `http://localhost:8000` in the helper scripts.
Langfuse keys are optional and only needed for trace capture.

## Langfuse Integration

Langfuse instrumentation hooks are wired into the API backend at key boundaries:
- Provider calls (validation, model discovery)
- Agent execution (future — when real LLM calls are added)
- Knowledge retrieval (search)

The integration is **safe-degrading**: if `LANGFUSE_PUBLIC_KEY` and
`LANGFUSE_SECRET_KEY` are not set, all tracing calls are no-ops.

### Local Langfuse (self-hosted)

To run Langfuse locally:

```bash
# Docker Compose (official)
# See: https://langfuse.com/docs/deployment/self-host
git clone https://github.com/langfuse/langfuse.git
cd langfuse
docker compose up -d
```

Default local URL: `http://localhost:3002`

Then set in `config/.env`:
```
LANGFUSE_HOST=http://localhost:3002
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

## Current Limitations

- Seed fixtures only — 8 fixtures, 8 eval cases across 3 domains (not full benchmark coverage)
- No real benchmark datasets — Promptfoo configs use scaffold seed fixtures
- No CI integration yet — configs are designed for local `promptfoo eval` only
- Provider comparison evals require live API keys (OpenAI, Anthropic, Gemini)
- Langfuse traces require a running Langfuse instance (local or cloud)
- No production red-team suites or domain-specific evals
- Extraction pass always reports completed_partial in seed fixtures (no extraction runs exist)
- Provider comparison results are metadata-driven, not quality-ranked
- OpenTelemetry is structurally anticipated but not instrumented in this step
