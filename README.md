# CaseGraph

<div align="center">
  <h3>🗂️ Local-first operating platform for document-heavy regulated workflows</h3>
  <p>
    CaseGraph gives operators a single case-centric workspace for ingestion, extraction, retrieval,
    review, downstream packet assembly, submission planning, and supervised automation — all grounded
    in explicit persisted case state.
  </p>
  <p>
    <img src="https://img.shields.io/badge/Status-Foundation%20platform-0F172A?style=for-the-badge" alt="Foundation platform" />
    <img src="https://img.shields.io/badge/Mode-Local--first-1D4ED8?style=for-the-badge" alt="Local first" />
    <img src="https://img.shields.io/badge/Model%20Access-BYOK-0F766E?style=for-the-badge" alt="BYOK" />
    <img src="https://img.shields.io/badge/Control-Human--reviewed-92400E?style=for-the-badge" alt="Human reviewed" />
  </p>
  <p>
    <img src="https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=nextdotjs&logoColor=white" alt="Next.js 15" />
    <img src="https://img.shields.io/badge/React-19-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React 19" />
    <img src="https://img.shields.io/badge/TypeScript-5.8-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript 5.8" />
    <img src="https://img.shields.io/badge/FastAPI-Python%203.12+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI and Python" />
    <img src="https://img.shields.io/badge/SQLite-Local%20persistence-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite" />
    <img src="https://img.shields.io/badge/Auth.js-Credentials-111827?style=flat-square" alt="Auth.js" />
    <img src="https://img.shields.io/badge/Playwright-MCP-2EAD33?style=flat-square&logo=playwright&logoColor=white" alt="Playwright MCP" />
  </p>
</div>

> [!IMPORTANT]
> CaseGraph already ships a broad set of real platform foundations: working registries, protected operator surfaces, persistence, audit and lineage, reviewed handoff and release flows, downstream provenance, and guarded execution paths. It does not claim autonomous decisioning, live filing, official payer, insurer, or agency integrations, or compliance guarantees.

## ✨ Why CaseGraph

Teams in medical operations, insurance claims, pre-authorization coordination, tax notice handling, and similar regulated domains lose time on assembly work: collecting documents, extracting the same facts into multiple systems, navigating portals, coordinating handoffs, and tracking case state across fragmented tools.

CaseGraph reduces that assembly burden with a unified case workspace. Documents can be ingested and structurally extracted, evidence can be indexed and retrieved, workflows can be reviewed end-to-end, and downstream artifacts can stay traceable back to real source material. Model access is BYOK (OpenAI, Anthropic, Gemini) — CaseGraph handles orchestration and structure, not model resale.

CaseGraph is not a chatbot, not a diagnosis engine, not a claim adjudicator, and not an autonomous filing system. Final decisions stay with human operators.

For the full problem statement, solution thesis, guardrails, and architecture-to-value mapping, see [docs/product-thesis.md](docs/product-thesis.md).

## 🧭 At a Glance

| Pillar | What exists today |
| --- | --- |
| 🧠 Model access | BYOK provider discovery, model validation, structured task execution, and evidence-backed RAG execution |
| 📄 Evidence pipeline | Document ingestion, OCR, extraction, retrieval, document review, and human validation |
| 🗂️ Case operations | Persistent cases, readiness, operator review, work management, audit trail, handoff, and reviewed release |
| 🧩 Metadata registries | Domain packs, target packs, workflow packs, submission targets, and typed shared contracts in Python and TypeScript |
| 🚦 Downstream preparation | Packets, communication drafts, submission drafts, dry-run automation plans, and approval-gated automation execution |

## 📊 Module Maturity

> Source of truth: [`apps/api/app/status.py`](apps/api/app/status.py). Machine-generated detail: [`STATUS.md`](STATUS.md).

| Module | Status | Description |
| --- | --- | --- |
| cases | **stable** | Central entity. Cross-layer contract + integration tested. |
| domains | **stable** | In-memory pack registry. All 8 packs regression-gated. |
| ingestion | **stable** | PDF/OCR routing, text extraction, page geometry. |
| packets | **stable** | Assembly, manifests, artifacts, export. Cross-layer tested. |
| providers | **stable** | Adapter registry, key validation, model discovery. |
| readiness | **stable** | Checklist generation, evaluation, overrides. |
| submissions | **stable** | Targets, drafts, field mapping, approval gating. |
| workflow_packs | **stable** | Built-in domain workflow orchestration. All 10 packs regression-gated. |
| audit | implemented | Read-only timeline, decisions, lineage queries. |
| communications | implemented | Template registry, draft generation, provider fallback. |
| evals | implemented | Fixture/suite registry, regression runner. |
| execution | implemented | Gating, checkpoints, resume/block/skip. |
| extraction | implemented | Template registry, schema conversion, grounding, LLM extraction. |
| human_validation | implemented | Field validation, requirement review, state tracking. |
| knowledge | implemented | Chunking, embedding, vector indexing, search. |
| observability | implemented | Request logging middleware, Langfuse client, trace_span. |
| operator_review | implemented | Stage machine, actions, queue, notes. |
| review | implemented | Page viewer, geometry, OCR results, annotations CRUD. |
| reviewed_handoff | implemented | Snapshot, signoff, eligibility governance. |
| reviewed_release | implemented | Bundle creation, provenance, audit trail. |
| target_packs | implemented | Registry, domain filtering, case selection. |
| tasks | implemented | Registry lookup, prompt building, LLM execution. |
| work_management | implemented | Assignment, SLA, queue, summary. |
| rag | implemented | Task registry, evidence selection, citations. |
| automation | scaffolded | Thin proxy to agent-runtime. No local logic. |
| runtime | scaffolded | Thin pass-through to agent-runtime. |
| topology | scaffolded | Pure graph builder. Depends on agent-runtime for input. |

## 🏗️ Repository Overview

| Surface | Purpose | Primary stack |
| --- | --- | --- |
| `apps/web` | Protected operator workspace, explorers, and case-scoped review surfaces | Next.js App Router, React 19, TypeScript |
| `apps/api` | Core API, registries, persistence, orchestration, and downstream artifact generation | FastAPI, SQLModel, SQLite |
| `apps/agent-runtime` | Agent and workflow runtime boundary | LangGraph, LangChain Core, FastAPI |
| `packages/agent-sdk` | Shared Python and TypeScript contracts | Pydantic, TypeScript |
| `packages/workflows` | Shared workflow definitions and registry metadata | Python, TypeScript |
| `services/evals` | Eval and observability assets | Promptfoo, Langfuse, Python |
| `infra` | Local-first environment references | env examples and setup docs |
| `docs` | Product and foundation documentation | Markdown |

### Monorepo Layout

```text
casegraph/
├── apps/
│   ├── web/              # 🌐 Next.js operator workspace
│   ├── api/              # ⚙️ FastAPI core platform service
│   └── agent-runtime/    # 🤖 LangGraph-based runtime boundary
├── packages/
│   ├── agent-sdk/        # 📦 Shared TS + Python contracts
│   └── workflows/        # 🧭 Workflow definitions and registry metadata
├── services/
│   └── evals/            # 📊 Eval and observability assets
├── infra/                # 🛠️ Local-first environment references
└── docs/                 # 📚 Foundation and product documentation
```

## 🧰 Tech Stack

| Layer | Stack |
| --- | --- |
| Frontend | <img src="https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=nextdotjs&logoColor=white" alt="Next.js" /> <img src="https://img.shields.io/badge/React-19-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React" /> <img src="https://img.shields.io/badge/TypeScript-5.8-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript" /> |
| Backend API | <img src="https://img.shields.io/badge/FastAPI-API-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" /> <img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" /> <img src="https://img.shields.io/badge/SQLite-Local-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite" /> |
| Runtime | <img src="https://img.shields.io/badge/LangGraph-Runtime-121212?style=flat-square" alt="LangGraph" /> <img src="https://img.shields.io/badge/LangChain-Core-1C3C3C?style=flat-square" alt="LangChain Core" /> |
| Retrieval | <img src="https://img.shields.io/badge/sentence--transformers-all--MiniLM--L6--v2-4B5563?style=flat-square" alt="sentence-transformers" /> <img src="https://img.shields.io/badge/ChromaDB-Local%20vector%20store-5B21B6?style=flat-square" alt="ChromaDB" /> <img src="https://img.shields.io/badge/Milvus%20Lite-Linux%20option-2563EB?style=flat-square" alt="Milvus Lite" /> |
| Auth and observability | <img src="https://img.shields.io/badge/Auth.js-v5-111827?style=flat-square" alt="Auth.js" /> <img src="https://img.shields.io/badge/Promptfoo-Evals-F97316?style=flat-square" alt="Promptfoo" /> <img src="https://img.shields.io/badge/Langfuse-Observability-16A34A?style=flat-square" alt="Langfuse" /> |
| Automation and execution | <img src="https://img.shields.io/badge/Playwright-MCP-2EAD33?style=flat-square&logo=playwright&logoColor=white" alt="Playwright" /> <img src="https://img.shields.io/badge/httpx-Client-7C3AED?style=flat-square" alt="httpx" /> |
| Model gateway | <img src="https://img.shields.io/badge/OpenAI-BYOK-412991?style=flat-square&logo=openai&logoColor=white" alt="OpenAI" /> <img src="https://img.shields.io/badge/Anthropic-BYOK-D97706?style=flat-square" alt="Anthropic" /> <img src="https://img.shields.io/badge/Gemini-BYOK-1A73E8?style=flat-square&logo=googlegemini&logoColor=white" alt="Gemini" /> |

## 📚 Documentation

- [docs/README.md](docs/README.md) — Documentation index
- [docs/product-thesis.md](docs/product-thesis.md) — Product problem statement, solution thesis, and guardrails
- [docs/target-pack-foundation.md](docs/target-pack-foundation.md) — Versioned target-pack metadata, compatibility, field schemas, and downstream provenance
- [docs/auditability-foundation.md](docs/auditability-foundation.md) — Audit trail, decision ledger, and lineage scope
- [docs/reviewed-release-foundation.md](docs/reviewed-release-foundation.md) — Reviewed release bundle scope and limitations

## ✅ Prerequisites

- Node.js `>= 20` (ships with corepack)
- Python `>= 3.12`

> **No global pnpm install is needed.** The repo's `packageManager` field lets
> corepack activate the exact pinned pnpm version automatically.

## 🚀 Quick Start (one command)

```bash
# Windows (PowerShell)
pwsh scripts/bootstrap.ps1

# macOS / Linux
bash scripts/bootstrap.sh
```

The bootstrap script will:
1. Enable corepack and install JS/TS deps via the pinned pnpm (`packageManager: pnpm@10.33.0`).
2. Create a single `.venv/` Python venv at the repo root.
3. Install all Python editable deps (SDK, workflows, API, agent-runtime) into `.venv/`.
4. Copy `.env.example` → `.env` if it doesn't exist.

After bootstrap, activate the venv and start services:

```bash
# Activate Python venv (do this once per terminal)
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# Frontend
pnpm dev:web                                                           # http://localhost:3000

# API
cd apps/api && uvicorn app.main:app --reload --port 8000               # http://localhost:8000

# Agent runtime (separate terminal)
cd apps/agent-runtime && uvicorn app.main:app --reload --port 8100     # http://localhost:8100

# Validate everything
pnpm validate
```

## 🛠️ Manual Setup (alternative)

If you prefer manual steps over the bootstrap script:

### 🌐 Frontend (Next.js)

```bash
corepack enable          # activates the pinned pnpm
pnpm install             # installs all workspace packages
pnpm dev:web             # http://localhost:3000
```

### ⚙️ Python (API + agent-runtime)

One venv at the repo root covers both Python apps:

```bash
python -m venv .venv
.venv/Scripts/activate                    # Windows
# source .venv/bin/activate              # macOS/Linux
pip install -e packages/agent-sdk \
            -e packages/workflows \
            -e "apps/api[dev,observability]" \
            -e "apps/agent-runtime[dev]"
```

Then in separate terminals (with the venv activated):

```bash
cd apps/api && uvicorn app.main:app --reload --port 8000
cd apps/agent-runtime && uvicorn app.main:app --reload --port 8100
```

- Health: `GET http://localhost:8000/health`
- Info: `GET http://localhost:8000/info`
- Providers: `GET http://localhost:8000/providers`
- Agents metadata: `GET http://localhost:8000/agents`
- Workflows metadata: `GET http://localhost:8000/workflows`
- Document ingestion capabilities: `GET http://localhost:8000/documents/capabilities`
- Document ingestion: `POST http://localhost:8000/documents/ingest`
- Knowledge capabilities: `GET http://localhost:8000/knowledge/capabilities`
- Knowledge indexing: `POST http://localhost:8000/knowledge/index`
- Knowledge search: `POST http://localhost:8000/knowledge/search`
- Persisted documents: `GET http://localhost:8000/documents`
- Cases: `GET/POST http://localhost:8000/cases`
- Case detail/update: `GET/PATCH http://localhost:8000/cases/{case_id}`
- Case document links: `GET/POST http://localhost:8000/cases/{case_id}/documents`
- Case runs: `GET/POST http://localhost:8000/cases/{case_id}/runs`
- Run detail: `GET http://localhost:8000/runs/{run_id}`
- `POST /cases/{case_id}/runs` can execute the built-in generic workflow `provider-task-execution` when a `task_execution` payload is supplied
- Topology graph: `GET http://localhost:8000/topology`
- Eval capabilities: `GET http://localhost:8000/evals/capabilities`
- Automation capabilities: `GET http://localhost:8000/automation/capabilities`
- Automation tools: `GET http://localhost:8000/automation/tools`
- Task definitions: `GET http://localhost:8000/tasks`
- Task execution: `POST http://localhost:8000/tasks/execute`
- RAG task definitions: `GET http://localhost:8000/rag/tasks`
- RAG task execution: `POST http://localhost:8000/rag/execute`
- `POST /cases/{case_id}/runs` can execute `rag-task-execution` when a `rag_task_execution` payload is supplied
- Validate key: `POST http://localhost:8000/providers/validate`
- Discover models: `POST http://localhost:8000/providers/models`
- Domain packs: `GET http://localhost:8000/domain-packs`
- Domain pack detail: `GET http://localhost:8000/domain-packs/{pack_id}`
- Pack case types: `GET http://localhost:8000/domain-packs/{pack_id}/case-types`
- Case type detail: `GET http://localhost:8000/case-types/{case_type_id}`
- Case type requirements: `GET http://localhost:8000/case-types/{case_type_id}/requirements`
- Target packs: `GET http://localhost:8000/target-packs`
- Target pack detail: `GET http://localhost:8000/target-packs/{pack_id}`
- Target pack compatibility: `GET http://localhost:8000/target-packs/{pack_id}/compatibility`
- Target pack field schema: `GET http://localhost:8000/target-packs/{pack_id}/field-schema`
- Target pack requirements: `GET http://localhost:8000/target-packs/{pack_id}/requirements`
- Case target-pack selection: `GET/PATCH http://localhost:8000/cases/{case_id}/target-pack`
- Case checklist: `GET http://localhost:8000/cases/{case_id}/checklist`
- Generate checklist: `POST http://localhost:8000/cases/{case_id}/checklist/generate`
- Evaluate coverage: `POST http://localhost:8000/cases/{case_id}/checklist/evaluate`
- Case readiness: `GET http://localhost:8000/cases/{case_id}/readiness`
- Operator queue: `GET http://localhost:8000/queue`
- Operator queue summary: `GET http://localhost:8000/queue/summary`
- Work queue: `GET http://localhost:8000/work/queue`
- Work summary: `GET http://localhost:8000/work/summary`
- Case assignment update: `PATCH http://localhost:8000/cases/{case_id}/assignment`
- Case assignment history: `GET http://localhost:8000/cases/{case_id}/assignment-history`
- Case SLA update: `PATCH http://localhost:8000/cases/{case_id}/sla`
- Case work status: `GET http://localhost:8000/cases/{case_id}/work-status`
- Case stage: `GET/PATCH http://localhost:8000/cases/{case_id}/stage`
- Stage history: `GET http://localhost:8000/cases/{case_id}/stage-history`
- Case action items: `GET http://localhost:8000/cases/{case_id}/actions`
- Generate action items: `POST http://localhost:8000/cases/{case_id}/actions/generate`
- Review notes: `GET/POST http://localhost:8000/cases/{case_id}/review-notes`
- Generate packet: `POST http://localhost:8000/cases/{case_id}/packets/generate`
- List packets: `GET http://localhost:8000/cases/{case_id}/packets`
- Packet detail: `GET http://localhost:8000/packets/{packet_id}`
- Packet manifest: `GET http://localhost:8000/packets/{packet_id}/manifest`
- Packet artifacts: `GET http://localhost:8000/packets/{packet_id}/artifacts`
- Download artifact: `GET http://localhost:8000/packets/{packet_id}/download/{artifact_id}`
- List reviewed snapshots: `GET http://localhost:8000/cases/{case_id}/reviewed-snapshots`
- Create reviewed snapshot: `POST http://localhost:8000/cases/{case_id}/reviewed-snapshots`
- Reviewed snapshot detail: `GET http://localhost:8000/reviewed-snapshots/{snapshot_id}`
- Sign off reviewed snapshot: `POST http://localhost:8000/reviewed-snapshots/{snapshot_id}/signoff`
- Handoff eligibility: `GET http://localhost:8000/cases/{case_id}/handoff-eligibility`
- Select reviewed snapshot for handoff: `PATCH http://localhost:8000/cases/{case_id}/reviewed-snapshots/{snapshot_id}/select-for-handoff`
- Communication templates: `GET http://localhost:8000/communication/templates`
- Create communication draft: `POST http://localhost:8000/cases/{case_id}/communication-drafts`
- List communication drafts: `GET http://localhost:8000/cases/{case_id}/communication-drafts`
- Communication draft detail: `GET http://localhost:8000/communication-drafts/{draft_id}`
- Communication draft sources: `GET http://localhost:8000/communication-drafts/{draft_id}/sources`
- Update communication draft review metadata: `PATCH http://localhost:8000/communication-drafts/{draft_id}/review`
- Case audit timeline: `GET http://localhost:8000/cases/{case_id}/audit`
- Case decision ledger: `GET http://localhost:8000/cases/{case_id}/decisions`
- Case artifact lineage: `GET http://localhost:8000/cases/{case_id}/lineage`
- Artifact lineage lookup: `GET http://localhost:8000/artifacts/{artifact_type}/{artifact_id}/lineage`
- Submission targets: `GET http://localhost:8000/submission/targets`
- Create submission draft: `POST http://localhost:8000/cases/{case_id}/submission-drafts`
- List submission drafts: `GET http://localhost:8000/cases/{case_id}/submission-drafts`
- Submission draft detail: `GET http://localhost:8000/submission-drafts/{draft_id}`
- Generate dry-run automation plan: `POST http://localhost:8000/submission-drafts/{draft_id}/plan`
- Get latest dry-run automation plan: `GET http://localhost:8000/submission-drafts/{draft_id}/plan`
- Update approval metadata: `PATCH http://localhost:8000/submission-drafts/{draft_id}/approval`
- Execute automation plan: `POST http://localhost:8000/submission-drafts/{draft_id}/execute`
- List case automation runs: `GET http://localhost:8000/cases/{case_id}/automation-runs`
- Automation run summary: `GET http://localhost:8000/automation-runs/{run_id}`
- Automation run detail: `GET http://localhost:8000/automation-runs/{run_id}/detail`
- Automation run steps: `GET http://localhost:8000/automation-runs/{run_id}/steps`
- Automation run artifacts: `GET http://localhost:8000/automation-runs/{run_id}/artifacts`
- Automation run events: `GET http://localhost:8000/automation-runs/{run_id}/events`
- Automation run checkpoints: `GET http://localhost:8000/automation-runs/{run_id}/checkpoints`
- Approve checkpoint: `POST http://localhost:8000/automation-runs/{run_id}/checkpoints/{checkpoint_id}/approve`
- Skip checkpoint: `POST http://localhost:8000/automation-runs/{run_id}/checkpoints/{checkpoint_id}/skip`
- Block checkpoint: `POST http://localhost:8000/automation-runs/{run_id}/checkpoints/{checkpoint_id}/block`
- Resume paused automation run: `POST http://localhost:8000/automation-runs/{run_id}/resume`
- Workflow packs: `GET http://localhost:8000/workflow-packs`
- Workflow pack detail: `GET http://localhost:8000/workflow-packs/{workflow_pack_id}`
- Execute workflow pack: `POST http://localhost:8000/cases/{case_id}/workflow-packs/{workflow_pack_id}/execute`
- Workflow pack run detail: `GET http://localhost:8000/workflow-pack-runs/{run_id}`
- Case workflow pack runs: `GET http://localhost:8000/cases/{case_id}/workflow-pack-runs`

### 🤖 Agent Runtime

```bash
cd apps/agent-runtime
python -m venv .venv
.venv/Scripts/activate   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -e "../../packages/agent-sdk" -e "../../packages/workflows" -e ".[dev]"
uvicorn app.main:app --reload --port 8100
```

- Health: `GET http://localhost:8100/health`
- Agents: `GET http://localhost:8100/agents`
- Workflows: `GET http://localhost:8100/workflows`

## ⚙️ Environment Variables

Use `infra/.env.example` as the reference for local configuration.

- For frontend/Auth.js local development, create `apps/web/.env.local`.
- For shared local service overrides, use a repo-root `.env` only where the service actually reads from it.

Provider keys are not read from environment variables in this step; they are entered in the web UI and sent to the local API per request.

```
CASEGRAPH_DEBUG=false
CASEGRAPH_WEB_ORIGIN=http://localhost:3000
CASEGRAPH_PROVIDER_REQUEST_TIMEOUT_SECONDS=15
CASEGRAPH_AGENT_RUNTIME_URL=http://localhost:8100
CASEGRAPH_AGENT_RUNTIME_TIMEOUT_SECONDS=10
CASEGRAPH_DATABASE_URL=<optional sqlite or postgres URL>
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# Auth (Auth.js / next-auth)
AUTH_SECRET=<random-secret>
AUTH_TRUST_HOST=true
AUTH_USER_1_EMAIL=admin@local.dev
AUTH_USER_1_NAME=Admin
AUTH_USER_1_PASSWORD_HASH=<bcrypt-hash>
AUTH_USER_1_ROLE=admin   # optional; defaults to admin
```

If `CASEGRAPH_DATABASE_URL` is unset, the API defaults to a local SQLite file at `apps/api/.casegraph/casegraph.db`.

Generate `AUTH_SECRET`: `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`

Generate a password hash: `cd apps/web && node -e "import('bcryptjs').then(b=>b.hash('YOUR_PASSWORD',10).then(console.log))"`

For the current local-first auth flow, the minimum working frontend env file is:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
AUTH_SECRET=<random-secret>
AUTH_TRUST_HOST=true
AUTH_USER_1_EMAIL=admin@local.dev
AUTH_USER_1_NAME=Admin
AUTH_USER_1_PASSWORD_HASH=<bcrypt-hash>
# AUTH_USER_1_ROLE=admin
```

## 📦 What's Included

### Target Pack Foundation

- Versioned target-pack registry with six built-in generic packs for prior-auth, pre-claim, claim, correspondence, tax notice, and tax intake flows.
- Typed target-pack metadata covering organization category, lifecycle status, compatibility, notes, and explicit limitations.
- Explicit compatibility metadata linking target packs to real domain packs, case types, workflow packs, and submission targets.
- Target field schema sections used to extend submission mapping previews with destination-specific metadata-only fields.
- Requirement override and additive requirement metadata for target-specific review context without mutating the base case-type registry.
- Extraction-template and communication-template bindings for reusing existing registries instead of inventing separate target-specific execution systems.
- Case-scoped target-pack selection persisted as typed case metadata and exposed through dedicated API routes.
- Submission drafts and reviewed releases persist selected target-pack references; automation plan responses reconstruct compatible target-pack context from the persisted draft metadata when the stored pack id and version still match the registry.
- Protected target-pack explorer at `/target-packs` and case-level selection controls inside the case workspace.
- Limitations: no official payer/insurer/agency support, no live filing integrations, no target-specific rules engine, no selectors/forms automation, and no claim of authoritative form completeness.

See [docs/target-pack-foundation.md](docs/target-pack-foundation.md) for the detailed scope and honest limitations.

### Work Management Foundation

- Explicit case ownership with local-user assignment, reassignment, and clearing.
- Append-only assignment history recording every ownership transition with actor, reason, and note.
- Due-date / SLA metadata with deterministic state computation (no_deadline, on_track, due_soon, overdue).
- Descriptive escalation-readiness assessment computed from real case blocking signals (overdue SLA, unresolved review items, release blocked, submission planning blocked, lingering open actions, missing assignment). No automatic escalation or notifications.
- Workload segmentation derived from assignment status, SLA state, and escalation readiness.
- Work queue and summary endpoints with multi-field filtering (assignee, status, SLA, escalation, domain, case type).
- Protected operator work board at `/work` with focus lanes (my work, unassigned, at-risk), filtered queue, and workload summary cards.
- Case-level work management section with assignment and deadline controls, assignment history, and work status snapshot.
- Compact work-context panels integrated into handoff and release workspaces.
- Audit events (`case_assignment_updated`, `case_sla_updated`) with field-level change tracking and linked decision-ledger entries.
- Local-user assignee registry derived from existing `AUTH_USER_<n>_*` environment variables.
- Limitations: no org management, no invitations, no notifications, no automatic escalation actions, no productivity analytics, no enterprise RBAC beyond local admin/member, no SLA policy engine.

### Reviewed Handoff Foundation

- Immutable reviewed snapshots built from the current human validation projection.
- Explicit operator sign-off records stored separately from snapshot content.
- Descriptive handoff eligibility rules for missing sign-off, unresolved review items, and incomplete required requirement reviews.
- Reviewed-source packet generation that records source mode, reviewed snapshot lineage, and sign-off metadata.
- Submission drafts, automation plans, and automation runs that preserve reviewed snapshot provenance through source-mode fields.
- Protected dashboard workspace for snapshot creation, sign-off, eligibility inspection, and eligible handoff selection.

### Reviewed Release Foundation

- Release bundle generation from signed-off reviewed snapshots with frozen downstream artifacts.
- Reviewed-source packets, submission drafts, communication drafts, and automation plan metadata per bundle.
- Source provenance metadata capturing snapshot id, sign-off operator, timestamp, and content summary.
- Release eligibility checks reusing handoff eligibility with multi-reason blocking reports.
- Audit events (`release_bundle_created`) and lineage records linking bundle to snapshot and downstream artifacts.
- Protected release workspace at `/cases/{caseId}/releases` for eligibility, creation, and artifact inspection.

See [docs/reviewed-release-foundation.md](docs/reviewed-release-foundation.md) for the detailed scope and honest limitations.

### Auditability Foundation

CaseGraph now persists an append-oriented audit trail for a focused set of real mutations across case, checklist, review, extraction, packet, submission, automation, communication, and workflow-pack flows. It also stores a linked decision ledger and artifact lineage records so the case audit UI can explain how downstream artifacts were derived from persisted case state.

This is operational traceability for local development and internal review. It does not claim WORM storage, cryptographic tamper-proofing, external notarization, formal compliance archiving, or retroactive reconstruction of history that was never recorded. See [docs/auditability-foundation.md](docs/auditability-foundation.md) for the exact scope.

### Human Validation Foundation

CaseGraph now includes a human-in-the-loop validation layer between machine-generated outputs (extraction fields, requirement assessments) and operational use. Operators can accept, correct, reject, or flag extracted fields and confirm, dispute, or request more information on checklist requirements — without ever deleting or silently overwriting the original machine outputs.

- **Field validation**: Each extracted field can be marked as accepted, corrected (with a human-supplied value), rejected, or needs_followup. The original machine value and grounding references are preserved alongside the human overlay.
- **Requirement review**: Each checklist item can be confirmed as supported, confirmed as missing, flagged as requiring more information, or manually overridden. Machine-assessed status is never removed.
- **Reviewed case state projection**: A single endpoint computes the full reviewed state of a case by merging extraction outputs with field validations and checklist items with requirement reviews, producing summary counts and an unresolved items list.
- **Persistence**: Two dedicated tables (`field_validations`, `requirement_reviews`) with upsert semantics and full audit integration.
- **Audit integration**: New `human_validation` audit category with `field_validation_recorded` and `requirement_review_recorded` event types. Each validation/review action creates a linked audit event and decision ledger entry.
- **Packet and workflow integration**: Assembled packets include a `human_review_state` section. Workflow pack orchestration includes a `human_review_check` stage.
- **Protected UI**: Validation workspace at `/cases/{caseId}/validation` with field-level accept/correct/reject controls, requirement-level review controls, and status summary. Navigation links from case detail, audit, packets, review, and automation-runs pages.
- **Shared contracts**: Full Python + TypeScript type parity in the agent-sdk for 20+ validation types, request/response schemas, and new audit/decision/packet/workflow literals.

See [docs/human-validation-foundation.md](docs/human-validation-foundation.md) for the detailed scope and honest limitations.

## 🚧 What's Not Included Yet

- Chat or conversational inference (task execution supports single-turn completions only)
- Real LLM-powered agent intelligence (current agents return placeholder results only)
- Autonomous multi-agent reasoning
- Visual flow builder (current topology page is read-only inspection)
- General workflow execution engine (runtime-defined workflows remain metadata only; the built-in `provider-task-execution` and `rag-task-execution` case-run paths execute today)
- Document annotation authoring (the review workspace displays read-only overlays; no drawing, editing, or collaborative annotation)
- Table reconstruction, semantic extraction, or domain-specific parsing
- Full RAG pipeline with multi-hop retrieval, conversation memory, and domain-specific prompts (single-turn evidence-backed generation exists)
- Reranking, late interaction, or hybrid retrieval
- Production-ready migration tooling and non-local database deployment setup
- Docker Compose
- CI/CD pipeline
- Deployment configuration
- Browser automation execution (a minimal approval-gated foundation exists for read-only navigate steps via Playwright MCP; write actions remain blocked)
- Computer-use provider execution (capability metadata exists, execution does not)
- Real workflow execution, queue workers, or persistent run state transitions for case runs
- Comments, collaboration, and notifications for cases/runs (audit trails exist; operator approval exists for automation execution)

## Current Topology Limitations

- The visual flow page is read-only inspection only. No drag-to-create, no-code editing, or node manipulation.
- Layout is deterministic column-based (workflows left, agents right). No auto-layout algorithm.
- Graph data is derived from registered agent/workflow metadata only. Live execution state is not reflected.
- No real-time updates. Page fetches topology on mount; manual refresh required after runtime changes.

## Current Eval & Observability Limitations

- Workflow regression suites use seed fixtures (8 fixtures, 8 eval cases across 3 domains) — not full production benchmarks.
- Promptfoo configs (4 YAML suites) use scaffold seed datasets, not real domain benchmarks.
- Provider comparison evals require live API keys for OpenAI, Anthropic, and/or Gemini.
- Retrieval evals require the CaseGraph API running with indexed documents.
- Langfuse traces require a running Langfuse instance (local Docker Compose or cloud).
- Langfuse is an optional dependency — the API starts and operates normally without it.
- No CI pipeline for automated eval runs yet.
- No production red-team, adversarial, or domain-specific eval suites.
- Extraction pass always reports completed_partial in seed fixtures since no extraction runs exist.
- Provider comparison results are metadata-driven, not quality-ranked.
- OpenTelemetry is structurally anticipated but not instrumented in this step.
- The eval workspace page displays suite metadata, triggers runs, and shows assertion results — not a full trace explorer.

## Current Automation Limitations

- An approval-gated execution layer exists for read-only navigate steps. All write actions (field population, attachment uploads, final submission) remain explicitly blocked.
- Navigate steps execute real Playwright MCP `browser_navigate` calls when the MCP server is reachable; they fail honestly with connection-error details when it is not.
- Navigate section steps pause for operator review and resume only through metadata-only computer-use fallback routing; no computer-use provider execution is implemented.
- Operator approval exists at both the draft level and the step-checkpoint level, but there is no broader workflow engine, delegation model, or multi-party approval chain.
- No browser preview, screenshot stream, or session replay.
- No domain-specific automation tools (medical, insurance, tax).
- No screenshot capture yet — only page metadata and text log artifacts are captured.
- The automation run inspector page is a minimal operator workspace for supervised execution and checkpoint decisions, not a full orchestration dashboard.
- Execution runs are synchronous. No queue processing, progress streaming, or background execution.

## Current Case Workspace Limitations

- Case persistence is local-first and defaults to SQLite. PostgreSQL migration is structurally straightforward but not wired in this step.
- Case-to-document linking stores persisted document summary metadata only. Raw uploaded files and full extracted artifacts are not stored in the case layer.
- Workflow bindings and run records still validate against real workflow metadata. Two built-in case-run paths execute immediately: `provider-task-execution` through the task service and `rag-task-execution` through the RAG service; other workflows do not execute yet.
- Run execution remains synchronous and minimal. There is no queue processing, live progress streaming, replay, or general workflow engine.
- The protected case workspace UI is intentionally minimal. There are no comments, assignments, collaboration features, kanban views, or approval flows.
- API authorization is still not implemented. The frontend pages are protected, but the backend remains local-first without session verification.

## Current Auth Limitations

- Authentication uses a local credentials provider only. No OAuth, SSO, or social login.
- Users are bootstrapped from environment variables. No signup flow or persistent user database.
- Local users can be assigned `admin` or `member` via `AUTH_USER_n_ROLE`; RBAC is not enforced yet.
- Sessions are JWT-based and stored client-side. No server-side session store.
- The backend API does not verify frontend sessions. API authorization is not implemented yet.
- No organization, team, or multi-tenant isolation.

## Current Task Execution Limitations

- Task execution is single-turn completion only. No multi-turn conversation, streaming, or function calling.
- The task registry ships three generic infrastructure tasks. No domain-specific tasks are included.
- Structured output uses basic required-field validation, not a full JSON Schema validator.
- Task execution records are persisted locally (SQLite). No export, search, or analytics.
- Two built-in case-run workflow paths invoke real execution: `provider-task-execution` for direct tasks and `rag-task-execution` for evidence-backed tasks. Other workflow run records remain tracking objects only.
- The task-execution and RAG workflow paths are API-driven today. They are not yet surfaced in runtime workflow metadata, topology, or the case workspace UI.
- No retry, rate limiting, or circuit-breaker logic for provider calls.
- No cost tracking or budget enforcement.
- The task lab and RAG lab UIs are developer tools, not polished end-user interfaces.

## Current RAG Limitations

- RAG execution is single-turn evidence-backed generation only. No multi-turn conversation, follow-up, or streaming.
- Citation extraction is honest chunk-level: the system finds [N] references in model output and maps them to evidence chunks. It does not claim fine-grained sentence-to-source grounding.
- Evidence selection uses a simple top-K retrieval with character-budget truncation. No reranking, late interaction, or hybrid retrieval.
- Case-scoped retrieval with no linked documents returns no evidence; it does not fall back to global search.
- Case-scoped retrieval can optionally narrow to explicitly requested linked document IDs. The current vector store filter still supports only a single `document_id`, so when multiple eligible documents remain only the first matching ID is searched.
- The RAG task registry ships three generic evidence-backed tasks. No domain-specific RAG tasks or prompts are included.
- Structured output in RAG tasks uses the same basic required-field validation as generic tasks — not a full JSON Schema validator.
- No confidence scores on citations beyond what the retrieval similarity score provides.
- There is no dedicated persistence/query surface for RAG-specific metadata yet. Direct `POST /rag/execute` persists the shared execution record fields, while full evidence/citation payloads are returned in the response and stored in case-run output when executed through `rag-task-execution`.
- The evidence-backed task lab is a developer/testing tool, not a polished end-user interface.

## Current BYOK Limitations

- Provider keys remain in browser component state only for the current page session.
- The local API uses keys request-by-request and does not persist them to disk or a database.
- Key validation and model discovery rely on real upstream provider model-list APIs.
- Model discovery only normalizes metadata returned by provider model-list endpoints.
- Single-turn task execution is implemented via `POST /tasks/execute` and the built-in `provider-task-execution` case-run path. Evidence-backed single-turn execution is available via `POST /rag/execute` and the built-in `rag-task-execution` case-run path. Chat, embeddings, agent execution, and general workflow execution remain out of scope.

## Current Agent Runtime Limitations

- Agents return placeholder results only — no LLM calls, tool use, or real reasoning.
- The supervisor graph compiles and routes by task type but does not execute real multi-step inference.
- Handoff structure is defined and wired but does not carry real context between agents yet.
- Workflow definitions describe step ordering; there is no workflow execution engine.
- Agent metadata endpoints require the agent-runtime to be running (the API proxies to the runtime service).
- No persistence, no state resumption, no human-in-the-loop.

## Current Ingestion Limitations

- Readable PDF ingestion uses PyMuPDF text extraction only; it does not reconstruct tables, forms, or higher-order layout semantics.
- OCR is explicit and opt-in. Auto mode only routes to OCR for image-based inputs when OCR is enabled on the request.
- The current OCR path is real but minimal: RapidOCR supplies text, polygons, scores, and derived bounding boxes. The document review workspace renders those persisted overlays, but docTR-specific extraction is not implemented.
- Scanned PDF OCR rasterizes pages locally before OCR and returns geometry in pixel coordinates. Readable PDF extraction returns geometry in PDF point coordinates.
- Uploaded binaries are handled in request-scoped local temp storage only. The API persists document summary metadata and page-level review artifacts, but raw uploaded files and raw extractor blobs are not stored. Indexing into the knowledge base is still a separate explicit step via `POST /knowledge/index`.

## Current Retrieval Limitations

- Embedding uses sentence-transformers locally with `all-MiniLM-L6-v2` (384 dimensions). No provider-based embedding is implemented yet.
- The vector store prefers Milvus Lite when available and otherwise falls back to ChromaDB. In the current local setup, ChromaDB is the default on Windows/macOS and Milvus Lite is typically used on Linux. Both store data in local files.
- Chunking uses simple fixed-size character windows with overlap (512 chars, 64 overlap). No semantic splitting.
- Search returns cosine similarity scores only. No reranking, late interaction, or hybrid retrieval.
- Metadata filtering is limited to document_id, source_filename, page_number, and embedding_model.
- There is no background indexing queue. Indexing happens synchronously in the API request.
- No multi-tenant isolation. All documents share a single vector collection.
- Generation with retrieved evidence is handled by the RAG execution layer (`/rag/execute`). The retrieval foundation itself provides search only; the RAG layer orchestrates retrieve → format → generate → cite on top of it.

## Document Review Workspace

A protected document review workspace for inspecting ingested documents, page artifacts, and OCR/extraction geometry.

### What is available now

- **Readable PDF review**: ingests a born-digital PDF, rasterizes each page to a PNG image, preserves PyMuPDF bounding-box geometry in `pdf_points` coordinate space, and persists page-level and block-level artifacts. The review UI shows page images with SVG-based bounding-box overlays.
- **Scanned PDF / image OCR review**: ingests via the RapidOCR path, persists the rasterized page images and OCR polygon/bounding-box geometry in `pixels` coordinate space with per-block confidence scores. The review UI shows page images with polygon overlays and confidence indicators.
- **Page artifact persistence**: `document_pages` table stores per-page dimensions, coordinate space, geometry source, full text, text blocks (with bbox/polygon/confidence as JSON), and page image path references.
- **Document review API**: `GET /documents/{id}` returns a `DocumentReviewResponse` with document metadata, page summaries, and honest capability reporting. `GET /documents/{id}/review` remains as an explicit alias. `GET /documents/{id}/pages` returns page summaries. `GET /documents/{id}/pages/{n}` returns full page detail with text blocks. `GET /documents/{id}/pages/{n}/image` serves the real persisted page image when one exists.
- **Review UI**: Protected page at `/documents/{id}` with page navigation sidebar, page image viewer with toggleable SVG overlays, text block inspector with expandable geometry details, and document metadata panel.
- **Case integration**: Linked documents in the case detail page show an "Open Review" link navigating directly to the review workspace.
- **Honest capability reporting**: Each document review response reports exactly what is available (page images, geometry, overlay types) and lists current limitations.

### Current Document Review Limitations

- Page images are rasterized during ingestion. If a document was ingested before this feature, no page images exist for it. Re-ingestion would be required.
- Bounding-box overlays are only shown when genuine geometry was produced by the extractor. No fabricated boxes are displayed.
- Overlays use SVG `preserveAspectRatio="none"` aligned to the page coordinate space. Alignment accuracy depends on the extraction coordinate space matching the rasterized image dimensions.
- No annotation authoring, collaborative review, comments, approval workflows, or redaction tools.
- No drag-to-draw overlays or manual geometry editing.
- No side-by-side document diffing.
- No semantic extraction review workflows.
- No page thumbnail generation separate from full-page rasterization.
- Uploaded raw files are still cleaned up after ingestion. Only the rasterized page images are persisted.
- The review workspace is read-only inspection only.

## Schema-Driven Extraction Foundation

A schema-driven extraction layer for running structured extraction over ingested documents, with source grounding and geometry-aware references.

### What is available now

- **Extraction template registry**: In-memory registry of extraction templates with typed field schemas. Three built-in generic templates: `contact_info`, `document_header`, `key_value_packet`. Templates define field schemas (string, integer, number, boolean, date, list, object), system prompts, and preferred extraction strategy.
- **Provider-backed structured extraction**: Reuses the existing BYOK task execution foundation (`TaskExecutionService.execute_prepared_prompt`). Converts extraction template schemas to JSON Schema for provider structured output. Works with OpenAI, Anthropic, and Gemini adapters.
- **LangExtract strategy boundary**: The extraction contracts and backend metadata include a `langextract_grounded` strategy so the architecture is ready for a real LangExtract adapter. In this build the runtime adapter is intentionally scaffolded, the backend reports it unavailable, and the protected UI only exposes strategies the backend says are executable.
- **Source grounding**: After extraction, the grounding service searches document page records for text overlap between extracted field values and ingestion text blocks. When a match is found, it attaches the block reference, page number, and genuine geometry (bounding box or polygon) when available from the extractor.
- **Extraction persistence**: `extraction_runs` table stores extraction results with fields (as JSON), errors, and lifecycle events. Results are tied to document ID, optional case ID, template ID, and strategy used.
- **Extraction API**: `GET /extraction/templates`, `GET /extraction/templates/{id}`, `POST /extraction/execute`, `GET /documents/{id}/extractions`, `GET /extractions/{id}`. All routes use real extraction logic — no fake or demo outputs.
- **Extraction lab UI**: Protected page at `/extraction` with template selection, document selection, strategy selection sourced from backend metadata, provider/model/API key entry for provider-backed runs, and result display with extracted fields, source grounding metadata (page, block, geometry), and lifecycle events. Links out to document review page.
- **Observability**: Extraction runs are traced through the existing Langfuse integration via `trace_span`. Each provider-backed extraction produces traces with extraction_id, template_id, and strategy metadata.

### Current Extraction Limitations

- Source grounding uses text-overlap matching at the text-block level. It does not provide character-perfect or fine-grained span-level grounding within blocks.
- Geometry references (bounding boxes, polygons) are attached only when they genuinely exist from the original ingestion extractor. No fabricated geometry.
- LangExtract is scaffolded in this build. The strategy contract exists, but the runtime adapter is not enabled yet, so only provider-backed extraction is executable.
- No domain-specific extraction templates (medical, insurance, tax) are included yet. Only generic templates exist.
- No human review, approval, or correction workflows.
- No confidence scoring unless the extraction strategy or provider genuinely produces it.
- Extraction operates on the full document text collected from page records. No selective page/section extraction yet.
- No extraction template authoring UI — templates are defined in code.
- No extraction result diffing or comparison across runs.
- No batch extraction across multiple documents.
- Structured output validation is basic (JSON parse + required field presence). No deep semantic validation.

## Domain Pack Foundation

A jurisdiction-aware domain pack layer for organizing cases by regulated domain — medical, medical insurance, general insurance, and taxation — across US and India jurisdictions.

### What is available now

- **Domain pack registry**: In-memory registry of domain packs with typed metadata. Eight built-in packs registered: `medical_us`, `medical_india`, `medical_insurance_us`, `medical_insurance_india`, `insurance_us`, `insurance_india`, `tax_us`, `tax_india`.
- **Case type templates**: Each pack defines case type templates with operational metadata: typical stages, workflow bindings, extraction bindings, and document requirements. Examples include medical record review, referral packet review, prior auth packet review, claim intake review, policy review, coverage packet review, tax intake packet review, and tax notice review.
- **Workflow and extraction bindings**: Case types reference existing built-in generic workflows (`provider-task-execution`, `rag-task-execution`) and extraction templates (`contact_info`, `document_header`, `key_value_packet`). Bindings are metadata associations only.
- **Document requirement definitions**: Each case type defines required, recommended, and optional document categories. Categories include identity, referral/order, clinical notes, diagnostic reports, claim forms, invoices, policy documents, tax notices, income documents, and supporting attachments. This is a structured checklist layer, not a filing rules engine.
- **Case integration**: Cases can optionally carry domain context (domain pack, jurisdiction, case type, domain category). The `POST /cases` endpoint accepts `domain_pack_id` and `case_type_id` parameters. Domain context is persisted in the cases table and included in all case API responses.
- **Domain pack API**: `GET /domain-packs`, `GET /domain-packs/{id}`, `GET /domain-packs/{id}/case-types`, `GET /case-types/{id}`, `GET /case-types/{id}/requirements`. All routes serve real registry data.
- **Domain pack explorer UI**: Protected page at `/domain-packs` for browsing packs, case types, workflow/extraction bindings, and document requirements. Case creation links pre-populate the form with domain context.
- **Case creation integration**: The create-case page accepts `domain_pack_id` and `case_type_id` query parameters and shows domain context when creating a domain-scoped case. The case detail page displays persisted domain context and, when the linked case type is still registered, resolves the current workflow bindings, extraction bindings, and document requirement checklist for that template.

### Current Domain Pack Limitations

- Domain packs provide operational metadata only. No regulatory logic, compliance engines, payer rules, or automated decisions are implemented.
- Cases persist domain context only. They do not snapshot case-type definitions, so the case detail page resolves the current registered template metadata at read time.
- No medical, legal, tax, or insurance advice is provided or claimed.
- No prior authorization approval prediction, claim adjudication, coverage determination, or tax filing automation.
- Workflow bindings reference existing generic workflows only. No domain-specific workflows are implemented.
- Extraction bindings reference existing generic extraction templates only. No domain-specific extraction templates are implemented.
- Document requirements are a structured checklist layer. They do not enforce filing rules, payer policies, or regulatory requirements.
- No payer/insurer-specific rules, provider directories, CPT/ICD engines, IRS/GST engines, or form packs.
- No confidence scoring, decision engines, or outcome prediction.
- Approval workflows, role-gated review chains, and chain-of-custody tracking are not implemented yet. The operator review foundation provides explicit stage transitions and manual follow-up actions — see below.
- No policy/regulation version tracking or change history.
- No domain-specific UI beyond the metadata explorer.
- The design is intentionally extensible for future domain-specific logic without requiring major rework.

## Case Readiness Foundation

A requirement checklist and readiness evaluation layer that connects domain pack document requirements to real case artifacts — linked documents and extraction results.

### What is available now

- **Checklist generation**: For domain-scoped cases, generates a structured checklist from the case type's document requirement definitions. Each requirement becomes a checklist item with category, priority (required/recommended/optional), and initial status. Supports force-regeneration.
- **Coverage evaluation**: Re-derives document and extraction linkage for each checklist item from the case's actual linked documents and completed extraction runs. Uses coarse filename-keyword matching to associate documents with requirement categories.
- **Status derivation**: Each item's status is derived from explicit linkage counts — not scores or predictions. Status values: `missing`, `partially_supported` (document linked but no extraction), `supported` (both document and extraction linked), `needs_human_review` (extraction exists without a linked case document), `optional_unfilled`, `waived`.
- **Readiness summary**: Aggregates item statuses into an overall readiness status (`not_evaluated`, `incomplete`, `needs_review`, `ready`) with honest counts of supported, missing, partially supported, needs-review, optional-unfilled, and waived items. Cases remain `not_evaluated` until coverage evaluation runs, and any partially-supported or review-needed items keep the case out of `ready`.
- **Operator overrides**: Operators can add notes and apply limited non-support overrides such as `waived` or `needs_human_review`. Support states remain evaluation-derived.
- **Persistence**: Four new tables (`checklists`, `checklist_items`, `checklist_item_document_links`, `checklist_item_extraction_links`) persist checklist state, item linkage, and evaluation results.
- **API endpoints**: `GET /cases/{id}/checklist`, `POST /cases/{id}/checklist/generate`, `POST /cases/{id}/checklist/evaluate`, `GET /cases/{id}/readiness`, `PATCH /cases/{id}/checklist/items/{item_id}`.
- **Protected checklist UI**: Operator-facing page at `/cases/{id}/checklist` shows the readiness summary, requirement items with status badges, linked documents and extractions, and evaluation controls. Includes an honest disclaimer about matching precision.
- **Shared SDK contracts**: Python and TypeScript contracts for `CaseChecklist`, `ChecklistItem`, `ReadinessSummary`, and all request/response types.

### Current Readiness Limitations

- Document-to-category matching uses coarse filename keyword heuristics. It does not perform semantic classification, content analysis, or deep document understanding.
- Readiness evaluation does not claim regulatory compliance, filing completeness, or adjudication readiness. It reports what is linked and what is missing.
- No automated approval, denial, or filing decisions are implemented or planned at this layer.
- No confidence scores, risk assessments, or outcome predictions.
- No payer-specific, insurer-specific, or jurisdiction-specific rules. Coverage evaluation is domain-agnostic.
- Extraction linkage requires completed extraction runs. In-progress or failed extractions are excluded.
- Items with only extraction links (no linked case documents) are flagged as `needs_human_review` rather than assumed correct.
- Evidence references are typed in the shared contracts for future retrieval-grounded linkage, but they are not populated yet in this foundation step.
- The checklist is derived from the current registered domain pack template, not from a snapshot. If the pack template changes, regeneration will reflect the new requirements.
- No version history or audit trail for checklist state changes beyond timestamps.

## Operator Review Foundation

A deterministic operator workspace layer that adds explicit case stages, a protected review queue, follow-up action generation, and manual review notes on top of the existing case and readiness foundations.

### What is available now

- **Explicit case stages**: Cases now carry a simple current stage with typed values: `intake`, `document_review`, `readiness_review`, `awaiting_documents`, `ready_for_next_step`, and `closed_placeholder`.
- **Manual stage transitions**: Operators can transition cases through a small deterministic transition map. Each explicit transition records the previous stage, next stage, reason, optional note, and timestamp.
- **Deterministic follow-up action generation**: Action items are generated only from real existing state such as no linked documents, missing or partially-supported checklist items, checklist evaluation still needed, failed or not-started workflow runs, and completed extraction runs without grounding.
- **Traceable action items**: Persisted action items store their category, source, source reason, and any relevant checklist item, document, extraction, or run reference so operators can see why the action exists.
- **Review notes and simple decisions**: Operators can record freeform notes with lightweight decision labels such as `follow_up_required`, `hold`, or `ready_for_next_step`. These notes do not trigger automated decisions.
- **Protected operator queue UI**: The `/queue` page shows cases currently needing operator attention, with simple filters for stage, missing items, generated open actions, domain pack, and case type.
- **Protected case review UI**: The `/cases/{id}/review` page shows the current stage, generated action items, stage history, and review notes, and allows manual stage transitions and note entry.
- **Queue and lifecycle API**: `GET /queue`, `GET /queue/summary`, `GET/PATCH /cases/{id}/stage`, `GET /cases/{id}/stage-history`, `GET /cases/{id}/actions`, `POST /cases/{id}/actions/generate`, `GET/POST /cases/{id}/review-notes`.
- **Shared SDK contracts**: Python and TypeScript contracts exist for stages, stage history, action items, queue items, queue summary, review notes, and mutation responses.

### Current Operator Review Limitations

- No automated approval, denial, adjudication, filing, medical, insurance, tax, legal, or regulatory decisions.
- No fake urgency scores, SLA scoring, or AI-prioritized queue ordering.
- No multi-user assignment, collaboration, notifications, comments, or approval chains yet.
- Action items are deterministic and local-state-based only. They do not include semantic recommendations or generated operational plans.
- Generated action items can be refreshed and resolved when the underlying condition clears, but there is no manual action-assignment or dismissal workflow yet.
- Review decisions recorded in notes are operator annotations only. They do not automatically transition stages or trigger outbound actions.
- Stage transitions are intentionally simple and manual. This step does not introduce a workflow engine or role-gated approvals.
- Evidence-gap actions are limited to explicit missing grounding metadata on extraction runs. No retrieval-grounded evidence linkage is added in this step.
- Queue filters are intentionally minimal and case-centric. No SLA, escalation, batching, or team-level workload management is implemented.

## Packet Assembly / Export Foundation

A deterministic packet assembly layer that packages explicit case state into reviewable, downloadable export artifacts for operator review and external handoff preparation.

### What is available now

- **Packet generation from case state**: Assembles a structured packet manifest from the case's current linked documents, extraction results, readiness/checklist summary, open action items, review notes, and workflow run history. All data comes from existing persisted state — nothing is fabricated.
- **Eight packet sections**: `case_summary`, `domain_metadata`, `linked_documents`, `extraction_results`, `readiness_summary`, `open_actions`, `review_notes`, `run_history`. Empty sections are marked honestly.
- **JSON manifest export**: Full structured JSON export of the packet manifest, including all section data and metadata.
- **Markdown summary export**: Human-readable markdown summary with overview table, per-section rendering, and an explicit disclaimer that the packet does not constitute a regulatory filing or guaranteed-complete submission.
- **Artifact download**: Each export artifact is persisted with content and metadata, downloadable via a clean API endpoint with proper Content-Disposition headers.
- **Packet history**: Multiple packets can be generated per case, each capturing a point-in-time snapshot. Packets are listed in reverse chronological order.
- **Protected packet UI**: The `/cases/{id}/packets` page allows generating packets, viewing packet history, inspecting manifest sections, and downloading export artifacts. Cross-linked from the case detail and operator review pages.
- **Packet API**: `POST /cases/{id}/packets/generate`, `GET /cases/{id}/packets`, `GET /packets/{id}`, `GET /packets/{id}/manifest`, `GET /packets/{id}/artifacts`, `GET /packets/{id}/download/{artifact_id}`.
- **Shared SDK contracts**: Python and TypeScript contracts for packet manifests, sections, entries, artifacts, and all request/response types.

### Current Packet Assembly Limitations

- No external filing, portal submission, form filling, email sending, or automated delivery.
- No PDF rendering, cover sheets, formatted bundles, or binary packaging yet.
- No payer-specific, insurer-specific, or form-specific field mapping.
- No operator sign-off, digital signatures, or chain-of-custody tracking.
- No narrative summaries generated from AI or LLM analysis. Section data is direct from persisted state.
- Packets are point-in-time snapshots. They do not auto-update if the case changes after generation.
- No ZIP bundle packaging for multi-file export yet.
- No submission-readiness validation or completeness scoring.
- The design supports future formatted PDF packets, cover sheets, submission automation, and operator sign-off without major rework.

## Submission Draft / Automation Planning Foundation

An approval-gated, reviewable bridge between packet assembly and any future real submission automation. This layer creates deterministic submission draft records, mapping previews, and dry-run automation plans from existing case, packet, extraction, and automation capability metadata.

### What is available now

- **Submission target registry**: Static target profiles for generic portal submission, insurer portal placeholder, tax portal placeholder, form/packet export, and internal handoff packet. These profiles expose metadata only.
- **Submission draft records**: A draft can be created for a case and packet against a selected target profile. Drafts store source metadata, mapping previews, approval metadata, and plan references.
- **Field mapping foundation**: Each target exposes explicit target fields. Draft generation builds deterministic mapping previews from current case state, packet manifest data, and persisted extraction fields only. Missing values are left unresolved or flagged for human input.
- **Dry-run automation plan generation**: A plan can be generated from the selected target, current mappings, packet-linked documents, and automation capability metadata. Plan steps distinguish informational review, future automation placeholders, human-input-required fields, and blocked submit actions.
- **Approval metadata**: Drafts record whether future execution has been operator-reviewed, approved for future execution, or rejected. This is metadata only; no execution occurs.
- **Protected submission UI**: The `/cases/{id}/submission-drafts` page lets operators select packets and targets, create drafts, inspect mapping previews, generate dry-run plans, and record approval metadata.
- **Automation integration at metadata level**: Dry-run plans reference the existing Playwright MCP / automation capability foundation only as metadata. No tool execution is triggered.

### Current Submission Draft Limitations

- No real portal navigation, browser writes, attachment uploads, or external submission execution.
- No portal-specific selectors, payer-specific templates, insurer-specific rules, tax filing logic, or regulatory form packs.
- No manual mapping edit endpoint yet. This step provides mapping previews and missing-value visibility only.
- No PDF form renderer, final submission package renderer, or live delivery channel.
- No role engine, multi-party approval workflow, or full audit trail beyond stored approval metadata.
- Dry-run plans remain placeholders for future automation. They do not claim that a case is ready for live submission.
- Approval metadata alone does not authorize unrestricted execution. It only unlocks the supervised execution workspace, where explicit checkpoint decisions and guardrails still control run progression.

## Communication Draft Foundation

A case-scoped, reviewable draft-generation layer that turns explicit case state into missing-document requests, internal handoff notes, and packet-cover-note style drafts without sending anything externally.

### What is available now

- **Template registry**: Three built-in templates are exposed through typed metadata: `missing_document_request`, `internal_handoff_note`, and `packet_cover_note`.
- **Deterministic draft generation**: Draft content is assembled from persisted case data only: case metadata, readiness/checklist state, open action items, packet manifests, workflow runs, workflow-pack runs, and optional linked-document retrieval evidence.
- **Optional provider-assisted phrasing**: Operators can request a BYOK provider rewrite that only rewrites the deterministic base draft. If the provider path fails or returns invalid structured output, the deterministic draft is preserved and the fallback is recorded honestly.
- **Grounding metadata**: Each draft stores source metadata, source-entity references, and evidence references so the operator can inspect exactly what state the draft relied on.
- **Review metadata**: Drafts are persisted case-scoped records with explicit review status, reviewer identity, review notes, and human-review-required metadata.
- **Workflow-pack handoff**: Workflow-pack review now deep-links into communication draft creation with real workflow-pack run references so missing-document, handoff, and packet-cover-note drafts can be opened from the current run context.
- **Protected communication UI**: The `/cases/{id}/communication-drafts` page lets operators create drafts, inspect sections, inspect grounding, update review metadata, and copy/export plain text or markdown artifacts.
- **Communication draft API**: `GET /communication/templates`, `POST /cases/{id}/communication-drafts`, `GET /cases/{id}/communication-drafts`, `GET /communication-drafts/{id}`, `GET /communication-drafts/{id}/sources`, `PATCH /communication-drafts/{id}/review`.

### Current Communication Draft Limitations

- No outbound sending, recipient lookup, contact resolution, channel selection, or delivery tracking.
- No fabricated medical, legal, tax, payer, insurer, or regulatory statements. Draft content only reflects explicit stored state.
- No fake recipients, deadlines, escalation policies, or unsupported case facts.
- Provider-assisted wording is optional and constrained to rewriting a deterministic base draft. It does not override the human-review requirement.
- Retrieval evidence is optional and limited by the current local vector-store path. When evidence is unavailable, the draft still persists with honest notes.
- Packet cover notes require a real generated packet. The feature does not generate packets implicitly.
- Multiple drafts can coexist for the same case and template. This foundation does not supersede, archive, or auto-select older drafts.

## Automation Execution Foundation

An approval-gated automation execution layer that takes an approved submission draft and its automation plan, enforces guardrail gating, pauses at explicit operator checkpoints, and only executes the safe deterministic subset through the Playwright MCP boundary. Write actions remain blocked. Fallback-only steps are represented honestly as metadata and routing hints rather than fake execution.

### What is available now

- **Approval gating enforcement**: Before any execution, the system validates that the draft is not superseded or blocked, that approval status is `approved_for_future_execution`, and that the plan is not blocked. Unapproved or invalid drafts receive a typed blocked response.
- **Step-level checkpoint enforcement**: Any plan step marked `checkpoint_required`, any `review_before_submit` step, and any step routed as `computer_use_fallback` or `manual_only` becomes a persisted approval checkpoint. Runs pause with `awaiting_operator_review` until an operator explicitly approves, skips, or blocks that checkpoint.
- **Resumable paused runs**: Paused runs persist `paused_run` metadata, checkpoint state, and operator override history. Resume continues from persisted run state only. It does not claim browser-session replay or hidden session continuity.
- **Deterministic step dispatch**: Each plan step is classified and dispatched by type:
  - `open_target` with Playwright MCP → real `browser_navigate` call to the MCP server, with page metadata and text log artifact capture on success and honest error capture on failure
  - `navigate_section` → paused behind an approval checkpoint and, after approval, resolved as a metadata-only fallback step with no computer-use execution
  - `review_before_submit` → paused behind an approval checkpoint and, after approval, resolved as a manual-only step with no automated browser action
  - `populate_field_placeholder`, `attach_document_placeholder`, `submit_blocked_placeholder` → always blocked with guardrail reason
- **Step execution journal**: Every executed step is persisted with status, outcome, timing, error details, and notes.
- **Artifact capture**: Navigate steps that succeed capture page metadata (title, URL) and a text log artifact. No screenshots or fabricated data.
- **Event timeline**: All lifecycle events (run started, session initialized, checkpoint created/approved/skipped/blocked, run paused/resumed, step started/completed/blocked/failed/skipped, artifact captured, run completed) are persisted with timestamps.
- **Run summary**: Each run computes honest step counts, checkpoint counts, pending review counts, and summary notes.
- **Session boundary**: When the Playwright MCP backend is available, a session boundary is established and closed. When it is not, the session status reflects that honestly.
- **Protected automation run inspector UI**: The `/cases/{caseId}/automation-runs` page allows launching execution from an approved draft/plan, inspecting persisted case runs, reviewing checkpoint metadata and fallback hints, recording operator decisions, resuming paused runs, and inspecting steps, blocked actions, artifacts, and the event journal.
- **Shared SDK contracts**: Python and TypeScript contracts for `AutomationRunRecord`, `ExecutedStepRecord`, `RunArtifactRecord`, `RunEventRecord`, `AutomationCheckpointRecord`, `AutomationOperatorOverrideRecord`, `PausedAutomationRunMetadata`, `AutomationSessionMetadata`, `AutomationRunSummary`, `BlockedActionRecord`, and all request/response types.
- **Execution API**: `POST /submission-drafts/{draft_id}/execute`, `GET /cases/{case_id}/automation-runs`, `GET /automation-runs/{run_id}`, `GET /automation-runs/{run_id}/detail`, `GET /automation-runs/{run_id}/steps`, `GET /automation-runs/{run_id}/artifacts`, `GET /automation-runs/{run_id}/events`, `GET /automation-runs/{run_id}/checkpoints`, `POST /automation-runs/{run_id}/checkpoints/{checkpoint_id}/approve`, `POST /automation-runs/{run_id}/checkpoints/{checkpoint_id}/skip`, `POST /automation-runs/{run_id}/checkpoints/{checkpoint_id}/block`, and `POST /automation-runs/{run_id}/resume`.

### Current Execution Limitations

- Only read-only navigate steps execute real browser actions. All write actions (field population, attachment uploads, final submission) are explicitly blocked.
- Navigate steps call the Playwright MCP server via HTTP. If the MCP server is not running, steps fail with honest connection-error details — no fake portal data is shown.
- Navigate section steps are checkpointed and routed as metadata-only computer-use fallbacks because page selectors and true computer-use execution are not implemented in this build.
- No screenshot capture. Only page metadata and text log artifacts are captured.
- Execution is synchronous. No background execution, queue processing, or progress streaming.
- No retry, timeout tuning, or circuit-breaker logic for MCP calls beyond a 15-second httpx timeout.
- No browser-session replay or multi-step session continuity. Resume works from persisted run/checkpoint state only.
- No domain-specific automation tools, portal-specific selectors, or payer-specific rules.
- No execution history search, analytics, or comparison across runs.
- The automation run inspector is a minimal operator tool, not a full orchestration dashboard.
