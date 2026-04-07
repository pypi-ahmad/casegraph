# CaseGraph — Usage Guide

A local-first workspace for document-heavy regulated case processing with human oversight at every step.

---

## Table of Contents

- [Who This Is For](#who-this-is-for)
- [Before You Start](#before-you-start)
- [Starting the App Locally](#starting-the-app-locally)
- [Signing In](#signing-in)
- [Main Workflow](#main-workflow)
- [Feature Guide](#feature-guide)
  - [Cases](#cases)
  - [Documents](#documents)
  - [Extraction](#extraction)
  - [Checklist and Readiness](#checklist-and-readiness)
  - [Validation](#validation)
  - [Case Review](#case-review)
  - [Work Board](#work-board)
  - [Operator Queue](#operator-queue)
  - [Export Packages (Packets)](#export-packages-packets)
  - [Submission Drafts](#submission-drafts)
  - [Communication Drafts](#communication-drafts)
  - [Workflow Packs](#workflow-packs)
  - [Handoff and Sign-Off](#handoff-and-sign-off)
  - [Releases](#releases)
  - [Automation Runs](#automation-runs)
  - [Audit Trail](#audit-trail)
  - [Knowledge and RAG](#knowledge-and-rag)
  - [Provider Settings](#provider-settings)
  - [Domain Packs](#domain-packs)
  - [Target Packs](#target-packs)
- [Environment Variables](#environment-variables)
- [Validation and Testing](#validation-and-testing)
- [Error States and Troubleshooting](#error-states-and-troubleshooting)
- [Limitations and Important Notes](#limitations-and-important-notes)

---

## Who This Is For

CaseGraph is built for operators in regulated domains — medical operations, insurance claims, pre-authorization coordination, tax notice handling, and similar workflows where documents must be collected, facts extracted, evidence reviewed, and downstream submissions prepared with a full audit trail.

The app assumes an operator who:

- Processes cases involving multiple documents
- Needs structured data extraction from those documents
- Needs to track requirements and readiness before submission
- Wants human review and approval at every decision point
- Needs traceability from source documents through to final output

---

## Before You Start

### Prerequisites

| Requirement | Version |
| --- | --- |
| Node.js | `>= 20` (with corepack) |
| Python | `>= 3.12` |

No global pnpm install is needed — the repo uses corepack to activate the pinned version (`pnpm@10.33.0`).

### LLM Provider Keys (Optional)

Extraction, task execution, RAG, and communication draft generation require at least one LLM provider key (OpenAI, Anthropic, or Google/Gemini). You enter keys through the Provider Settings page in the web UI — they are sent per-request to the local API and are not stored on disk.

Document ingestion, case management, checklist evaluation, work management, and review workflows function without any LLM key.

---

## Starting the App Locally

### One-Command Bootstrap

```bash
# Windows (PowerShell)
pwsh scripts/bootstrap.ps1

# macOS / Linux
bash scripts/bootstrap.sh
```

This will:

1. Enable corepack and install JS/TS dependencies via the pinned pnpm.
2. Create a Python virtual environment at `.venv/` (repo root).
3. Install all Python packages (SDK, workflows, API, agent-runtime) as editable.
4. Copy `.env.example` → `.env` if no `.env` exists.

### Starting the Services

Open three terminals. Activate the Python venv in each, then start one service per terminal:

```bash
# Terminal 1 — Frontend (http://localhost:3000)
pnpm dev:web

# Terminal 2 — API (http://localhost:8000)
cd apps/api && uvicorn app.main:app --reload --port 8000

# Terminal 3 — Agent Runtime (http://localhost:8100)
cd apps/agent-runtime && uvicorn app.main:app --reload --port 8100
```

| Service | Default URL | Required |
| --- | --- | --- |
| Frontend | `http://localhost:3000` | Yes |
| API | `http://localhost:8000` | Yes |
| Agent Runtime | `http://localhost:8100` | Only for runtime/topology/automation features |

### Verifying the API Is Running

```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

Or run the full smoke test:

```bash
pnpm smoke:api        # Windows (PowerShell)
pnpm smoke:api:sh     # macOS / Linux
```

---

## Signing In

CaseGraph uses local credential-based authentication (Auth.js / next-auth v5). Users are defined via environment variables — there is no registration flow.

### Setting Up Your First User

Create `apps/web/.env.local` with the following:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
AUTH_SECRET=<random-secret>
AUTH_TRUST_HOST=true
AUTH_USER_1_EMAIL=admin@local.dev
AUTH_USER_1_NAME=Admin
AUTH_USER_1_PASSWORD_HASH=<bcrypt-hash>
```

Generate each value:

```bash
# AUTH_SECRET
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"

# Password hash
cd apps/web && node -e "import('bcryptjs').then(b=>b.hash('YOUR_PASSWORD',10).then(console.log))"
```

The example file at `infra/.env.example` contains a pre-generated hash for the password `changeme` — suitable for local development only.

You can define up to 10 users by incrementing the index: `AUTH_USER_2_EMAIL`, `AUTH_USER_2_PASSWORD_HASH`, etc. Each user can have role `admin` (default) or `member`.

### Signing In

Navigate to `http://localhost:3000`. You will see the landing page with a **Sign in** link. Enter the email and password you configured. After sign-in, you are redirected to the Cases page.

---

## Main Workflow

A typical end-to-end case lifecycle:

1. **Create a case** — give it a title, select a domain pack and case type.
2. **Upload documents** — ingest PDFs or images from the Documents page, then link them to the case.
3. **Run extraction** — extract structured fields from documents using templates defined by the domain pack.
4. **Validate** — review AI-extracted fields against source documents on the Validation page. Correct values where needed.
5. **Check readiness** — generate and evaluate the requirements checklist. Track which items are supported, missing, or need review.
6. **Review** — use the Case Review page to assess overall case state, generate action items, and manage stage transitions.
7. **Prepare downstream** — generate export packages, submission drafts, and communication drafts as needed.
8. **Process with workflow packs** — run the domain-specific processing workflow to execute extraction, checklist, packet assembly, and draft generation in sequence.
9. **Handoff** — create a reviewed snapshot, sign off, and select it for handoff.
10. **Release** — generate the final release bundle with all artifacts and provenance.

Not every case requires every step. The platform supports partial workflows — you can use only the stages you need.

---

## Feature Guide

### Cases

**Page:** `/cases` · **New case:** `/cases/new`

Cases are the central entity. Each case tracks a title, status, stage, domain context, linked documents, and all downstream artifacts.

- **Create a case:** Click "Create Case." Provide a title, select a domain pack and case type from the dropdowns. The case is created in `open` status at the `intake` stage.
- **Case detail:** Click any case to open it. The detail page shows case metadata, domain context, linked documents and workflows, and the platform flow map with links to all case-scoped pages.
- **Edit case:** Update the case title or status directly from the case detail page.
- **Link documents:** After uploading documents on the Documents page, link them to a case from the case detail page.

**Case statuses:** Open, Active, On Hold, Closed, Archived.
**Case stages:** Intake → Document Review → Readiness Review → Awaiting Documents → Ready → Closed.

Stage transitions are managed from the Case Review page.

### Documents

**Page:** `/documents`

- **Upload:** Select a file (PDF or image), choose an ingestion mode (Auto, Readable PDF, Scanned PDF, or Image), and upload. The API processes the document through its text extraction and optional OCR pipeline.
- **Review:** Click any uploaded document to open the Document Review page (`/documents/{documentId}`). View per-page text blocks, layout geometry, OCR results, and page images where available. Add annotations to specific pages.
- **Capabilities:** The page also displays the current ingestion capabilities — which modes are available and ready based on the installed extractors.

Documents are stored locally via the API. After upload, link documents to cases from the case detail page.

### Extraction

**Page:** `/extraction`

The Extraction Lab lets you run template-driven structured extraction against uploaded documents.

1. Select an extraction template (provided by domain packs).
2. Select a document to extract from.
3. Choose a strategy (auto, LLM, hybrid) and configure the LLM provider and model.
4. Run the extraction. Results show each extracted field with its value, confidence, and grounding references back to source text.

**Requires:** At least one LLM provider key configured in Provider Settings.

Extraction results are linked to the case and are visible on the Validation page.

### Checklist and Readiness

**Page:** `/cases/{caseId}/checklist`

The checklist tracks all document and evidence requirements for a case type.

- **Generate:** Click "Generate Checklist" to build the requirements list from the domain pack's case type definition.
- **Evaluate:** Click "Evaluate Checklist" to automatically assess which requirements are supported by linked documents and extractions.
- **Status per item:** Each item shows its current status (Supported, Partial, Missing, Needs Review, Optional, Waived) with linked documents and evidence references.
- **Readiness summary:** An overall readiness assessment (Ready, Incomplete, Needs Review, Not Started) with counts of supported vs. missing requirements.

### Validation

**Page:** `/cases/{caseId}/validation`

Review all AI-extracted field values against source documents.

- Each extraction group shows the template name and source document.
- For each field, view the extracted value, display name, and source references.
- Mark fields as correct or provide corrections with updated values.
- Requirement rows show the checklist item's review status with linked documents and auto-detected status.

An AI disclosure banner notes that outputs require human review.

### Case Review

**Page:** `/cases/{caseId}/review`

The central operator review surface for a case.

- **Action items:** Click "Find Next Steps" to generate recommended actions based on current case data (missing documents, extraction follow-ups, compliance gaps).
- **Stage transitions:** Move the case between lifecycle stages (e.g., Intake → Document Review → Readiness Review).
- **Review notes:** Add operator notes with category and priority for the case record.

### Work Board

**Page:** `/work`

The operator's main work dashboard. Shows all tracked cases organized by ownership and urgency.

- **Focus lanes:** My Work (cases assigned to you), Unassigned Queue, and At-Risk / Overdue.
- **Workload summary:** Cards showing total tracked cases, assigned, unassigned, due soon, overdue, attention needed, and escalation-ready counts.
- **Filtered queue:** Filter by search text, assignee, assignment status, deadline status, escalation, domain, and case type.
- **Case cards:** Each card shows the case title, owner, deadline, stage, readiness, open action count, and status badges.

### Operator Queue

**Page:** `/queue`

A lightweight operator queue showing cases that need attention, with summary statistics. Links to the full work board and case details.

### Export Packages (Packets)

**Page:** `/cases/{caseId}/packets`

Assemble and export a structured package of case artifacts.

- **Generate:** Click "Generate Export Package" to build a packet with extracted data, evidence, and case metadata.
- **Manifests and artifacts:** View the packet's manifest (what's included) and individual artifacts.
- **Download:** Download individual artifacts from generated packets.

### Submission Drafts

**Page:** `/cases/{caseId}/submission-drafts`

Plan submissions to downstream targets (payers, agencies, etc.).

- **Create draft:** Select a submission target and generate a draft with field mappings from case data to the target's required fields.
- **Mapping preview:** Review each mapped field, its source, value preview, and whether it's resolved.
- **Automation preview:** Generate a dry-run automation plan showing what steps would be executed, which need human input, and which are blocked.
- **Approval:** Set the draft's approval status and note before it can be used for automation.

### Communication Drafts

**Page:** `/cases/{caseId}/communication-drafts`

Generate structured communication from case data.

- **Create draft:** Select a communication template, optionally link to a workflow run and export package, then generate. The system assembles the communication from real case data and evidence.
- **Review:** Edit and review the generated sections. Each section shows its content, source references, and confidence.
- **Source data:** View the grounding — which case data, evidence references, and source entities were used.
- **Status tracking:** Mark drafts as needing review, revised, approved, or archived.

**Requires:** At least one LLM provider key.

### Workflow Packs

**Page:** `/cases/{caseId}/workflow-packs`

Run end-to-end domain-specific processing workflows.

- **Select a pack:** Choose from available workflow packs (matched to the case's domain and case type).
- **Execute:** Start the processing run. The pack runs through its stages in sequence (typically: extraction, checklist evaluation, packet assembly, communication drafts, submission drafts).
- **Review results:** Each stage shows its status, timing, and summary. Drill into individual stage outputs and notes.

Workflow packs do not make autonomous decisions — they orchestrate existing platform operations and produce outputs for human review.

### Handoff and Sign-Off

**Page:** `/cases/{caseId}/handoff`

Prepare a case for handoff by creating a reviewed checkpoint.

- **Eligibility:** The eligibility panel shows whether the case meets handoff requirements (release gate status, sign-off status, unresolved items, required reviews).
- **Create snapshot:** Save a reviewed checkpoint with an operator note. The snapshot captures the current case state including linked documents, extractions, validations, and reviews.
- **Sign off:** Approve the snapshot. Sign-off records the operator, timestamp, and note.
- **Select for handoff:** Mark the signed-off snapshot as the one to use for downstream release.

### Releases

**Page:** `/cases/{caseId}/releases`

Generate the final release bundle from a reviewed, signed-off snapshot.

- **Eligibility check:** View release readiness — requires a signed-off snapshot selected for handoff.
- **Create release:** Generate the release bundle. Each artifact is produced from the reviewed snapshot data.
- **Artifact detail:** View each artifact's status (generated, skipped, failed, blocked), type, source mode, and notes.

An AI disclosure banner notes that outputs require human review.

### Automation Runs

**Page:** `/cases/{caseId}/automation-runs`

Execute and monitor automation plans from approved submission drafts.

- **Execute:** Select an approved submission draft and its plan, then start execution.
- **Checkpoints:** The system pauses at approval checkpoints. Review each step's details, then approve, skip, or block.
- **Steps:** View all executed steps with their status, type, tool used, duration, and outcome.
- **Session:** See the automation session's backend connection status.

**Requires:** Agent runtime running on port 8100.

### Audit Trail

**Page:** `/cases/{caseId}/audit`

View the complete audit history for a case.

- **Timeline:** Chronological record of all events — case creation, document links, extractions, reviews, stage transitions, snapshots, releases.
- **Decision ledger:** All operator decisions with actor, timestamp, and rationale.
- **Lineage:** Trace the provenance of any artifact back through the processing chain.

### Knowledge and RAG

**Knowledge page:** `/knowledge` · **RAG page:** `/rag`

- **Knowledge:** Index documents into the vector store for semantic search. Search indexed content by query and view results with chunk text, similarity scores, and source references.
- **RAG:** Execute evidence-backed retrieval tasks. Select a task, provide a query, and receive a response grounded in retrieved evidence with citations.

**Requires:** At least one LLM provider key for RAG execution. Knowledge indexing and search use the local embedding model (sentence-transformers).

### Provider Settings

**Page:** `/settings/providers`

Configure LLM provider access.

- **View providers:** See available providers (OpenAI, Anthropic, Google) and their capability status.
- **Validate keys:** Enter an API key for a provider and validate it. Successful validation enables that provider for extraction, tasks, and RAG.
- **Discover models:** After validation, discover available models from the provider.

Keys are sent per-request to the local API. They are not persisted to disk.

### Domain Packs

**Page:** `/domain-packs`

Browse the built-in domain pack registry.

- View all registered domain packs with their jurisdiction, category, case types, and workflow bindings.
- Drill into a pack to see its case type definitions, extraction template bindings, workflow bindings, and requirement definitions.

Domain packs are defined in code (not user-editable). The registry includes packs for medical insurance (US/India), tax (US/India), and generic domains.

### Target Packs

**Page:** `/target-packs`

Browse submission target metadata.

- View target packs filtered by category and status.
- Drill into a pack to see organization details, compatibility (which domain packs, case types, and workflow packs it works with), field schema, and requirement overrides.
- Field schemas show each section's required and optional fields with their types and candidate source paths.

Target packs are read-only metadata. They define the structure of downstream submission targets but do not perform live filing.

---

## Environment Variables

### Frontend (`apps/web/.env.local`)

| Variable | Required | Description |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Yes | API server URL. Default: `http://localhost:8000` |
| `AUTH_SECRET` | Yes | Random secret for session signing |
| `AUTH_TRUST_HOST` | Yes | Set to `true` for local development |
| `AUTH_USER_{n}_EMAIL` | Yes (at least 1) | Login email for user *n* (1–10) |
| `AUTH_USER_{n}_PASSWORD_HASH` | Yes (at least 1) | bcrypt hash of the password |
| `AUTH_USER_{n}_NAME` | No | Display name. Defaults to `User {n}` |
| `AUTH_USER_{n}_ROLE` | No | `admin` (default) or `member` |

### API (`apps/api` — reads from process environment or repo-root `.env`)

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `CASEGRAPH_DATABASE_URL` | No | `sqlite:///apps/api/.casegraph/casegraph.db` | Database connection URL |
| `CASEGRAPH_WEB_ORIGIN` | No | `http://localhost:3000` | Allowed CORS origin |
| `CASEGRAPH_AGENT_RUNTIME_URL` | No | `http://localhost:8100` | Agent runtime URL |
| `CASEGRAPH_PROVIDER_REQUEST_TIMEOUT_SECONDS` | No | `15` | Timeout for LLM provider calls |
| `CASEGRAPH_AGENT_RUNTIME_TIMEOUT_SECONDS` | No | `10` | Timeout for agent runtime calls |
| `CASEGRAPH_DEBUG` | No | `false` | Enable debug mode |

### Observability (Optional)

| Variable | Description |
| --- | --- |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `LANGFUSE_HOST` | Langfuse host URL |

---

## Validation and Testing

### Full Validation

```bash
pnpm validate        # Windows (PowerShell)
pnpm validate:sh     # macOS / Linux
```

Runs 9 gates:

1. Python API tests (pytest)
2. TypeScript typecheck
3. Next.js production build
4. API import smoke test
5. Agent-runtime import smoke test
6. SDK barrel integrity check
7. Contract duplication guard
8. Eval configuration integrity
9. STATUS.md freshness check

### Individual Commands

```bash
# Python API tests only
pnpm test:api

# TypeScript typecheck only
pnpm typecheck

# Frontend build only
pnpm build:web

# API smoke test (requires API server running)
pnpm smoke:api
```

---

## Error States and Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Sign-in rejected | No `AUTH_USER_*` env vars configured, or password hash doesn't match | Verify `apps/web/.env.local` has correct email, hash, and `AUTH_SECRET` |
| "Unable to load…" on any page | API server not running or wrong `NEXT_PUBLIC_API_BASE_URL` | Start the API: `cd apps/api && uvicorn app.main:app --reload --port 8000` |
| Extraction fails with provider error | No LLM API key configured or key is invalid | Go to `/settings/providers`, enter and validate a key |
| "No workflow packs match this case type" | Case has no domain pack linked, or no packs match the case type | Verify the case's domain pack and case type on the case detail page |
| Knowledge search returns no results | No documents have been indexed | Go to `/knowledge`, select a document, and run indexing first |
| Automation features unavailable | Agent runtime not running | Start it: `cd apps/agent-runtime && uvicorn app.main:app --reload --port 8100` |
| Database locked errors | Multiple API processes writing to the same SQLite file | Stop duplicate API processes. Only one should run at a time |
| Bootstrap fails on Windows | Corepack not enabled or Python not in PATH | Run `corepack enable` manually, ensure `python --version` shows 3.12+ |

---

## Limitations and Important Notes

- **Local-first only.** All data is stored in a local SQLite database (`apps/api/.casegraph/casegraph.db`) and local file artifacts. There is no cloud deployment, multi-user server mode, or remote database support in the current implementation.

- **No autonomous decisions.** CaseGraph orchestrates and structures case processing but does not make autonomous regulatory, clinical, legal, or financial decisions. Final judgment stays with human operators.

- **No live filing or submission.** Submission drafts, automation plans, and release bundles produce structured output for review. They do not file claims, submit forms, or interact with external payer/agency/insurer systems.

- **No official compliance guarantees.** Domain packs, checklists, and requirement definitions are working references. They do not represent regulatory rulings, payer decisions, or tax advice.

- **BYOK model access.** LLM provider keys are entered by the operator and sent per-request. CaseGraph does not include, resell, or proxy model access.

- **Single-user local auth.** Authentication uses env-defined local credentials with JWT sessions. There is no user registration, password reset, SSO, or multi-tenant support.

- **SQLite concurrency.** Only one API server process should run at a time. SQLite does not support concurrent write access from multiple processes.

- **Agent runtime dependency.** The runtime, topology, and automation pages require the agent-runtime service running separately on port 8100. All other features work without it.
