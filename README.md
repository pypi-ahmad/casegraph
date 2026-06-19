# CaseGraph

Local-first case processing workspace for document-heavy regulated workflows with human oversight at every decision point.

CaseGraph provides operators in medical operations, insurance claims, pre-authorization coordination, and tax notice handling with a unified workspace for document ingestion, structured extraction, evidence retrieval, requirement tracking, reviewed handoff, and downstream artifact assembly — all grounded in persisted case state with a full audit trail. Model access is BYOK (bring your own key) for OpenAI, Anthropic, and Gemini. CaseGraph handles orchestration and structure; final decisions stay with human operators.

> [!IMPORTANT]
> CaseGraph does not make autonomous regulatory, clinical, financial, or legal decisions. It does not perform live filing, claim adjudication, or external portal submissions. It produces structured outputs for human review.

---

## What It Does

| Area | Capabilities |
| --- | --- |
| **Evidence pipeline** | PDF/image ingestion (PyMuPDF + RapidOCR), schema-driven extraction with source grounding, vector indexing and semantic search, document review with geometry overlays, human validation of extracted fields |
| **Case operations** | Persistent cases with domain context, requirement checklists with coverage evaluation, explicit stage transitions, operator review queue, work board with assignment/deadline tracking, audit trail with decision ledger and lineage |
| **Downstream preparation** | Export package assembly, communication drafts, submission drafts with field mapping, dry-run automation plans, approval-gated automation execution (read-only navigate steps via Playwright MCP) |
| **Reviewed release** | Immutable reviewed snapshots, operator sign-off, handoff eligibility governance, release bundle generation with provenance |
| **Registries** | 8 domain packs (medical, insurance, tax — US and India), 10 workflow packs, 6 target packs, submission targets, extraction templates, communication templates |

## Tech Stack

| Layer | Technologies |
| --- | --- |
| Frontend | Next.js 15, React 19, TypeScript 5.8, Auth.js v5 |
| Backend API | FastAPI, Pydantic, SQLModel, SQLite, Python 3.12+ |
| Agent runtime | LangGraph, LangChain Core, FastAPI |
| Retrieval | sentence-transformers (`all-MiniLM-L6-v2`), ChromaDB, Milvus Lite |
| Observability | Langfuse (optional), Promptfoo |
| Automation | Playwright MCP (read-only navigate) |
| Model access | OpenAI, Anthropic, Gemini (BYOK, per-request, not persisted) |

## Module Maturity

Source of truth: [`apps/api/app/status.py`](apps/api/app/status.py). Machine-generated snapshot: [`STATUS.md`](STATUS.md).

27 API modules — 149 routes — 589 Python SDK exports — 595 TypeScript SDK exports.

| Status | Modules |
| --- | --- |
| **stable** (8) | cases, domains, ingestion, packets, providers, readiness, submissions, workflow_packs |
| **implemented** (16) | audit, communications, evals, execution, extraction, human_validation, knowledge, observability, operator_review, rag, review, reviewed_handoff, reviewed_release, target_packs, tasks, work_management |
| **scaffolded** (3) | automation, runtime, topology |

## Repository Structure

```text
casegraph/
├── apps/
│   ├── web/                 # Next.js operator workspace (App Router)
│   ├── api/                 # FastAPI platform API (SQLite, 27 modules)
│   └── agent-runtime/       # LangGraph agent boundary (3 registered agents)
├── packages/
│   ├── agent-sdk/           # Shared Python + TypeScript contracts
│   └── workflows/           # Workflow definitions and registry metadata
├── services/
│   └── evals/               # Promptfoo suites, Langfuse assets
├── scripts/                 # Bootstrap, validate, smoke-test, status generation
├── infra/                   # Environment reference (.env.example)
└── docs/                    # Foundation and product documentation
```

| Surface | Purpose | Stack |
| --- | --- | --- |
| `apps/web` | Protected operator workspace and case-scoped review surfaces | Next.js, React 19, TypeScript |
| `apps/api` | Core API — registries, persistence, orchestration, artifact generation | FastAPI, SQLModel, SQLite |
| `apps/agent-runtime` | Agent runtime boundary (IntakeAgent, RouterAgent, ReviewAgent) | LangGraph, LangChain Core |
| `packages/agent-sdk` | Typed contracts shared across Python and TypeScript | Pydantic, TypeScript |
| `packages/workflows` | Workflow definitions and registry metadata | Python, TypeScript |

## Prerequisites

- **Node.js** `>= 20` (with corepack — no global pnpm install needed)
- **Python** `>= 3.12`

## Quick Start

```bash
# Bootstrap (one command)
pwsh scripts/bootstrap.ps1          # Windows
bash scripts/bootstrap.sh           # macOS / Linux
```

This enables corepack, installs JS/TS dependencies via the pinned pnpm (`10.33.0`), creates `.venv/` with all Python packages installed as editable, and copies `.env.example` → `.env` if needed.

### Start Services

Activate the venv, then run each service in a separate terminal:

```bash
# Frontend — http://localhost:3000
pnpm dev:web

# API — http://localhost:8000
cd apps/api && uvicorn app.main:app --reload --port 8000

# Agent runtime — http://localhost:8100 (optional, needed for automation features)
cd apps/agent-runtime && uvicorn app.main:app --reload --port 8100
```

Verify the API is running:

```bash
curl http://localhost:8000/health    # → {"status":"ok"}
```

### Manual Setup (Alternative)

```bash
corepack enable
pnpm install
python -m venv .venv
.venv/Scripts/activate              # Windows (or source .venv/bin/activate)
pip install -e packages/agent-sdk \
            -e packages/workflows \
            -e "apps/api[dev,observability]" \
            -e "apps/agent-runtime[dev]"
```

## Configuration

### Frontend Auth (`apps/web/.env.local`)

CaseGraph uses local credential-based authentication via Auth.js v5. Users are defined through environment variables — there is no registration flow.

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
AUTH_SECRET=<random-secret>
AUTH_TRUST_HOST=true
AUTH_USER_1_EMAIL=admin@local.dev
AUTH_USER_1_NAME=Admin
AUTH_USER_1_PASSWORD_HASH=<bcrypt-hash>
# AUTH_USER_1_ROLE=admin              # optional, defaults to admin
```

Generate values:

```bash
# AUTH_SECRET
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# Password hash
cd apps/web && node -e "import('bcryptjs').then(b=>b.hash('YOUR_PASSWORD',10).then(console.log))"
```

Up to 10 users can be defined by incrementing the index (`AUTH_USER_2_*`, etc.). Roles: `admin` (default) or `member`.

### API Environment

See [`infra/.env.example`](infra/.env.example) for the full reference.

| Variable | Default | Description |
| --- | --- | --- |
| `CASEGRAPH_DATABASE_URL` | `sqlite:///apps/api/.casegraph/casegraph.db` | Database URL (SQLite auto-created) |
| `CASEGRAPH_WEB_ORIGIN` | `http://localhost:3000` | Allowed CORS origin |
| `CASEGRAPH_AGENT_RUNTIME_URL` | `http://localhost:8100` | Agent runtime URL |
| `CASEGRAPH_PROVIDER_REQUEST_TIMEOUT_SECONDS` | `15` | LLM provider call timeout |
| `CASEGRAPH_AGENT_RUNTIME_TIMEOUT_SECONDS` | `10` | Agent runtime call timeout |
| `CASEGRAPH_DEBUG` | `false` | Debug mode |

LLM provider keys (OpenAI, Anthropic, Gemini) are entered in the web UI and sent per-request. They are not read from environment variables and are not persisted to disk.

Optional observability: `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST` for Langfuse trace integration.

## Available Scripts

| Command | Description |
| --- | --- |
| `pnpm dev:web` | Start the Next.js dev server |
| `pnpm build:web` | Production build of the frontend |
| `pnpm typecheck` | TypeScript type checking |
| `pnpm test:api` | Run Python API tests (pytest) |
| `pnpm validate` | Run all 9 validation gates |
| `pnpm smoke:api` | Smoke-test API endpoints |
| `pnpm generate:status` | Regenerate STATUS.md from live module registry |
| `pnpm bootstrap` | Full local setup (corepack, deps, venv, env) |

### Validation Gates

`pnpm validate` runs 9 sequential checks:

1. Python API tests (pytest)
2. TypeScript typecheck
3. Next.js production build
4. API import smoke test
5. Agent-runtime import smoke test
6. SDK barrel integrity check
7. Contract duplication guard
8. Eval config integrity
9. STATUS.md freshness

## Usage Guide

For the complete operator guide, see [**USAGE.md**](USAGE.md). It covers:

- [Who This Is For](USAGE.md#who-this-is-for)
- [Before You Start](USAGE.md#before-you-start) — prerequisites and LLM provider keys
- [Starting the App Locally](USAGE.md#starting-the-app-locally) — bootstrap, services, health check
- [Signing In](USAGE.md#signing-in) — user setup and authentication
- [Main Workflow](USAGE.md#main-workflow) — end-to-end case lifecycle
- [Feature Guide](USAGE.md#feature-guide) — Cases, Documents, Extraction, Checklist, Validation, Review, Work Board, Queue, Packets, Submission Drafts, Communication Drafts, Workflow Packs, Handoff, Releases, Automation Runs, Audit, Knowledge, RAG, Providers, Domain Packs, Target Packs
- [Environment Variables](USAGE.md#environment-variables) — frontend, API, and observability config
- [Validation and Testing](USAGE.md#validation-and-testing) — gates and individual commands
- [Error States and Troubleshooting](USAGE.md#error-states-and-troubleshooting)
- [Limitations and Important Notes](USAGE.md#limitations-and-important-notes)

## API Overview

The API server (`apps/api`) exposes 149 routes across 27 modules. Key surface areas:

| Area | Example Routes |
| --- | --- |
| Health | `GET /health`, `GET /info`, `GET /status/modules` |
| Cases | `GET/POST /cases`, `GET/PATCH /cases/{id}`, `GET/POST /cases/{id}/documents` |
| Documents | `POST /documents/ingest`, `GET /documents/{id}`, `GET /documents/{id}/pages/{n}/image` |
| Extraction | `POST /extraction/execute`, `GET /extraction/templates` |
| Knowledge | `POST /knowledge/index`, `POST /knowledge/search` |
| RAG | `POST /rag/execute`, `GET /rag/tasks` |
| Providers | `POST /providers/validate`, `POST /providers/models` |
| Checklist / Readiness | `POST /cases/{id}/checklist/generate`, `POST /cases/{id}/checklist/evaluate` |
| Review / Queue | `GET /queue`, `GET/PATCH /cases/{id}/stage`, `POST /cases/{id}/actions/generate` |
| Work management | `GET /work/queue`, `PATCH /cases/{id}/assignment` |
| Packets | `POST /cases/{id}/packets/generate`, `GET /packets/{id}/download/{artifact_id}` |
| Submissions | `POST /cases/{id}/submission-drafts`, `POST /submission-drafts/{id}/plan` |
| Communications | `POST /cases/{id}/communication-drafts`, `GET /communication/templates` |
| Automation | `POST /submission-drafts/{id}/execute`, `POST /automation-runs/{id}/checkpoints/{cid}/approve` |
| Handoff / Release | `POST /cases/{id}/reviewed-snapshots`, `POST /reviewed-snapshots/{id}/signoff` |
| Audit | `GET /cases/{id}/audit`, `GET /cases/{id}/decisions`, `GET /cases/{id}/lineage` |
| Domain packs | `GET /domain-packs`, `GET /case-types/{id}/requirements` |
| Workflow packs | `POST /cases/{id}/workflow-packs/{wpid}/execute` |

The agent runtime (`apps/agent-runtime`) exposes `GET /health`, `GET /agents`, and `GET /workflows`.

## Testing

```bash
pnpm test:api       # ~600 pytest tests (API modules, contracts, integration)
pnpm validate       # Full 9-gate validation suite
pnpm smoke:api      # Endpoint smoke test (requires running API)
```

## Documentation

| Document | Description |
| --- | --- |
| [USAGE.md](USAGE.md) | Operator usage guide — setup, workflow, features, troubleshooting |
| [docs/product-thesis.md](docs/product-thesis.md) | Problem statement, solution thesis, guardrails |
| [docs/target-pack-foundation.md](docs/target-pack-foundation.md) | Target-pack metadata, compatibility, field schemas |
| [docs/auditability-foundation.md](docs/auditability-foundation.md) | Audit trail, decision ledger, lineage scope |
| [docs/reviewed-release-foundation.md](docs/reviewed-release-foundation.md) | Release bundle scope and limitations |
| [docs/human-validation-foundation.md](docs/human-validation-foundation.md) | Human validation layer scope |
| [docs/reviewed-handoff-foundation.md](docs/reviewed-handoff-foundation.md) | Reviewed handoff governance |

## Limitations

- **Local-only.** SQLite persistence, single-process API, no multi-tenant or remote database support.
- **No backend auth enforcement.** Frontend routes are session-protected; the API does not verify sessions. Local-first design only.
- **No autonomous decisions.** No claim adjudication, filing automation, regulatory rulings, or outcome prediction.
- **No live submission.** Submission drafts and automation plans produce structured output — no portal writes, form fills, or external delivery.
- **Agents are placeholders.** The three registered agents (IntakeAgent, RouterAgent, ReviewAgent) return placeholder results. No LLM calls or real reasoning.
- **Read-only automation.** Automation execution supports `browser_navigate` only. Field population, attachment uploads, and form submission are blocked.
- **Single-turn LLM.** Task and RAG execution are single-turn completions. No chat, streaming, function calling, or multi-hop retrieval.
- **No Docker or CI.** No Dockerfile, docker-compose, or CI/CD pipeline.
- **No deployment config.** Local development only — no production deployment tooling.
