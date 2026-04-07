# CaseGraph — Current HEAD Status

> **Machine-generated** from live codebase on 2026-04-07 14:08 UTC.
> Re-generate: `cd apps/api && python ../../scripts/generate_status.py --write`
> Validate: `pnpm validate`
>
> **Do not hand-edit** — changes will be overwritten. To change module
> maturity, update `app/status.py` and re-generate.

---

## Numbers at a Glance

| Metric | Value |
|---|---|
| API modules | 27 |
| API routes | 149 |
| Module maturity | 8 stable · 16 implemented · 3 scaffolded · 0 planned |
| SDK exports (Python) | 591 |
| SDK exports (TypeScript) | 595 |
| API test files | 31 |
| Frontend pages | 31 |
| Frontend API clients | 26 |
| Frontend tests | 0 |

---

## Stabilization Milestone

**Goal:** Freeze features, harden every `implemented` module to `stable`.

### Promotion criteria (implemented -> stable)

1. Dedicated regression-gate test file (`test_<module>_regression.py`)
2. Cross-layer contract coverage (SDK -> API -> DB round-trip)
3. Edge-case and error-path tests (not just happy-path)
4. Route count pinned in `test_structural_verification.py`
5. Entry updated in `app/status.py` with `has_regression_gate=True`

### Current progress

| Status | Modules |
|---|---|
| **Already stable** (8) | cases, domains, ingestion, packets, providers, readiness, submissions, workflow_packs |
| **Next to stabilize** | review, extraction, execution, operator_review |
| **Scaffolded (defer)** | automation, runtime, topology |

### Feature freeze rules

- No new modules until all `implemented` modules reach `stable`
- No new SDK types unless required by a stabilization task
- Scaffolded modules stay scaffolded until their external dependencies unblock
- All changes must pass `pnpm validate` before merge

---

## Module Registry

| Module | Maturity | Routes | DB | Tests | Gate | Notes |
|---|---|---|---|---|---|---|
| audit | implemented | 4 | ✓ | ✓ | — | Read-only timeline, decisions, lineage queries. |
| automation | scaffolded | 2 | — | ✓ | — | Thin proxy to agent-runtime /tools. No local logic. |
| cases | **stable** | 9 | ✓ | ✓ | ✓ | Central entity. Cross-layer contract + integration tested. |
| communications | implemented | 6 | ✓ | ✓ | — | Template registry, draft generation, provider fallback. |
| domains | **stable** | 5 | — | ✓ | ✓ | In-memory pack registry. All 8 packs regression-gated. |
| evals | implemented | 6 | ✓ | ✓ | — | Fixture/suite registry, regression runner. |
| execution | implemented | 13 | ✓ | ✓ | — | Gating, checkpoints, resume/block/skip. |
| extraction | implemented | 5 | ✓ | ✓ | — | Template registry, schema conversion, grounding, LLM extraction. |
| human_validation | implemented | 5 | ✓ | ✓ | — | Field validation, requirement review, state tracking. |
| ingestion | **stable** | 5 | ✓ | ✓ | ✓ | PDF/OCR routing, text extraction, page geometry. Persisted output + source file. |
| knowledge | implemented | 3 | — | ✓ | — | Chunking, embedding, vector indexing, search. |
| observability | implemented | 0 | — | ✓ | — | Request logging middleware, Langfuse client, trace_span. No routes. |
| operator_review | implemented | 9 | ✓ | ✓ | — | Stage machine, actions, queue, notes. |
| packets | **stable** | 6 | ✓ | ✓ | ✓ | Assembly, manifests, artifacts, export. Cross-layer tested. |
| providers | **stable** | 3 | — | ✓ | ✓ | Adapter registry, key validation, model discovery. Integration tested. |
| rag | implemented | 2 | — | ✓ | — | Task registry, evidence selection, citations. |
| readiness | **stable** | 5 | ✓ | ✓ | ✓ | Checklist generation, evaluation, overrides. Pack-aligned regression gates. |
| review | implemented | 12 | ✓ | ✓ | — | Page viewer, geometry, OCR results, annotations CRUD, word-level extraction. |
| reviewed_handoff | implemented | 6 | ✓ | ✓ | — | Snapshot, signoff, eligibility governance. |
| reviewed_release | implemented | 5 | ✓ | ✓ | — | Bundle creation, provenance, audit trail. |
| runtime | scaffolded | 4 | — | ✓ | — | Thin pass-through to agent-runtime. No local logic. |
| submissions | **stable** | 7 | ✓ | ✓ | ✓ | Targets, drafts, field mapping, approval gating. Cross-layer tested. |
| target_packs | implemented | 7 | — | ✓ | — | Registry, domain filtering, case selection. |
| tasks | implemented | 2 | — | ✓ | — | Registry lookup, prompt building, LLM execution. |
| topology | scaffolded | 1 | — | ✓ | — | Pure graph builder. Depends on agent-runtime for input. |
| work_management | implemented | 6 | ✓ | ✓ | — | Assignment, SLA, queue, summary. |
| workflow_packs | **stable** | 5 | ✓ | ✓ | ✓ | Built-in domain workflow orchestration. All 10 packs regression-gated. |

**Summary:** 8 stable · 16 implemented · 3 scaffolded · 0 planned

---

## Shared Contracts

One rule enforced across all layers:

- **Source of truth**: `packages/agent-sdk` (Python + TypeScript)
- **Enforcement**: `scripts/check_contract_duplication.py` (Gate #7 in validate)
- **Rule**: No class/type in `packages/agent-sdk` or `packages/workflows` may be redefined in `apps/api`, `apps/agent-runtime`, or `apps/web` without an explicit `# OVERRIDE:` comment
- **Coverage**: 591 Python + 595 TypeScript shared names scanned

---

## Canonical Validation

One command: `pnpm validate`

| # | Gate | What | Threshold |
|---|---|---|---|
| 1 | Python API tests | pytest | All pass |
| 2 | TypeScript typecheck | tsc --noEmit | 0 errors |
| 3 | Next.js production build | next build | Compiles |
| 4 | API import smoke | import app.main | ≥ 140 routes |
| 5 | Agent-runtime import smoke | import app.main | ≥ 5 routes |
| 6 | SDK barrel integrity | Python __all__ | ≥ 575 exports |
| 7 | Contract duplication guard | check_contract_duplication.py | 0 collisions |
| 8 | Eval config integrity | test_eval_readiness.py | All pass |

---

## Bootstrap

### JavaScript / TypeScript

```bash
corepack enable
pnpm install
pnpm dev:web          # http://localhost:3000
```

### Python

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate | Unix: source .venv/bin/activate
pip install -e packages/agent-sdk -e packages/workflows \
            -e "apps/api[dev,observability]" -e "apps/agent-runtime[dev]"
cd apps/api && uvicorn app.main:app --reload --port 8000
```

### One-command

```bash
pnpm bootstrap        # or: pwsh scripts/bootstrap.ps1
```

---

## Blockers

| Blocker | Affected | Unblock |
|---|---|---|
| No LLM provider key | extraction, tasks, rag, communications, evals | Add `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` to `.env` |
| Agent runtime not running | topology, automation, runtime proxy | `cd apps/agent-runtime && uvicorn app.main:app --port 8100` |
| No MCP server for Playwright | Agent runtime browser tools | Wire Playwright MCP or direct integration |
| No containerization | Deployment | Create Dockerfiles + docker-compose |
| No CI/CD | Automated gates | Add `.github/workflows/` |
| No frontend tests | apps/web | Add vitest + React Testing Library |

---

## Architecture Rules

1. **One shared-contract source**: `packages/agent-sdk` defines all API types. Python and TypeScript must stay in sync. Gate #7 enforces no redefinition.
2. **One validation runner**: `pnpm validate` is the only pass/fail gate. 8 sub-gates, exit 0 = green.
3. **One status document**: This file, machine-generated from `app/status.py`. No prose claims — only what the code proves.
4. **One bootstrap per language**: `pnpm install` for JS, `pip install -e ...` for Python. `pnpm bootstrap` does both.
5. **Module maturity is code**: Labels live in `app/status.py`, enforced by `test_module_maturity.py`. STATUS.md is derived.
6. **Feature freeze until stable**: No new modules until implemented -> stable promotion is complete.
