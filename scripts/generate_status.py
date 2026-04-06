"""Generate STATUS.md from live codebase inspection.

Usage:
    cd apps/api
    python ../../scripts/generate_status.py          # prints to stdout
    python ../../scripts/generate_status.py --write   # overwrites STATUS.md
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure apps/api is importable
REPO = Path(__file__).resolve().parents[1]
api_dir = REPO / "apps" / "api"
sys.path.insert(0, str(api_dir))

from app.main import app  # noqa: E402
from app.status import MODULE_REGISTRY  # noqa: E402
from casegraph_agent_sdk import __all__ as sdk_all  # noqa: E402


def _count_ts_exports() -> int:
    total = 0
    for ts_file in (REPO / "packages" / "agent-sdk" / "src").glob("*.ts"):
        import re
        total += len(re.findall(
            r"export\s+(?:type|interface|enum|class)\s+\w+",
            ts_file.read_text(encoding="utf-8"),
        ))
    return total


def _count_files(base: Path, pattern: str) -> int:
    return len(list(base.rglob(pattern)))


def _route_count() -> int:
    return len([r for r in app.routes if hasattr(r, "methods")])


def _maturity_table() -> str:
    lines = [
        "| Module | Maturity | Routes | DB | Tests | Gate | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in sorted(MODULE_REGISTRY, key=lambda x: x.module_id):
        mat = f"**{m.maturity}**" if m.maturity == "stable" else m.maturity
        db = "✓" if m.has_db_models else "—"
        tests = "✓" if m.has_tests else "—"
        gate = "✓" if m.has_regression_gate else "—"
        lines.append(f"| {m.module_id} | {mat} | {m.route_count} | {db} | {tests} | {gate} | {m.notes} |")
    return "\n".join(lines)


def _blockers() -> str:
    return """| Blocker | Affected | Unblock |
|---|---|---|
| No LLM provider key | extraction, tasks, rag, communications, evals | Add `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` to `.env` |
| Agent runtime not running | topology, automation, runtime proxy | `cd apps/agent-runtime && uvicorn app.main:app --port 8100` |
| No MCP server for Playwright | Agent runtime browser tools | Wire Playwright MCP or direct integration |
| No containerization | Deployment | Create Dockerfiles + docker-compose |
| No CI/CD | Automated gates | Add `.github/workflows/` |
| No frontend tests | apps/web | Add vitest + React Testing Library |"""


def generate() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    routes = _route_count()
    sdk_py = len(sdk_all)
    sdk_ts = _count_ts_exports()
    modules = len(MODULE_REGISTRY)
    stable = sum(1 for m in MODULE_REGISTRY if m.maturity == "stable")
    implemented = sum(1 for m in MODULE_REGISTRY if m.maturity == "implemented")
    scaffolded = sum(1 for m in MODULE_REGISTRY if m.maturity == "scaffolded")
    planned = sum(1 for m in MODULE_REGISTRY if m.maturity == "planned")
    pages = _count_files(REPO / "apps" / "web" / "src" / "app", "page.tsx")
    api_clients = _count_files(REPO / "apps" / "web" / "src" / "lib", "*-api.ts")
    test_files = _count_files(REPO / "apps" / "api" / "tests", "test_*.py")

    return f"""# CaseGraph — Current HEAD Status

> **Machine-generated** from live codebase on {now}.
> Re-generate: `cd apps/api && python ../../scripts/generate_status.py --write`
> Validate: `pnpm validate`
>
> **Do not hand-edit** — changes will be overwritten. To change module
> maturity, update `app/status.py` and re-generate.

---

## Numbers at a Glance

| Metric | Value |
|---|---|
| API modules | {modules} |
| API routes | {routes} |
| Module maturity | {stable} stable · {implemented} implemented · {scaffolded} scaffolded · {planned} planned |
| SDK exports (Python) | {sdk_py} |
| SDK exports (TypeScript) | {sdk_ts} |
| API test files | {test_files} |
| Frontend pages | {pages} |
| Frontend API clients | {api_clients} |
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
| **Already stable** ({stable}) | {', '.join(m.module_id for m in sorted(MODULE_REGISTRY, key=lambda x: x.module_id) if m.maturity == 'stable')} |
| **Next to stabilize** | review, extraction, execution, operator_review |
| **Scaffolded (defer)** | {', '.join(m.module_id for m in sorted(MODULE_REGISTRY, key=lambda x: x.module_id) if m.maturity == 'scaffolded')} |

### Feature freeze rules

- No new modules until all `implemented` modules reach `stable`
- No new SDK types unless required by a stabilization task
- Scaffolded modules stay scaffolded until their external dependencies unblock
- All changes must pass `pnpm validate` before merge

---

## Module Registry

{_maturity_table()}

**Summary:** {stable} stable · {implemented} implemented · {scaffolded} scaffolded · {planned} planned

---

## Shared Contracts

One rule enforced across all layers:

- **Source of truth**: `packages/agent-sdk` (Python + TypeScript)
- **Enforcement**: `scripts/check_contract_duplication.py` (Gate #7 in validate)
- **Rule**: No class/type in `packages/agent-sdk` or `packages/workflows` may be redefined in `apps/api`, `apps/agent-runtime`, or `apps/web` without an explicit `# OVERRIDE:` comment
- **Coverage**: {sdk_py} Python + {sdk_ts} TypeScript shared names scanned

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
# Windows: .venv\\Scripts\\activate | Unix: source .venv/bin/activate
pip install -e packages/agent-sdk -e packages/workflows \\
            -e "apps/api[dev,observability]" -e "apps/agent-runtime[dev]"
cd apps/api && uvicorn app.main:app --reload --port 8000
```

### One-command

```bash
pnpm bootstrap        # or: pwsh scripts/bootstrap.ps1
```

---

## Blockers

{_blockers()}

---

## Architecture Rules

1. **One shared-contract source**: `packages/agent-sdk` defines all API types. Python and TypeScript must stay in sync. Gate #7 enforces no redefinition.
2. **One validation runner**: `pnpm validate` is the only pass/fail gate. 8 sub-gates, exit 0 = green.
3. **One status document**: This file, machine-generated from `app/status.py`. No prose claims — only what the code proves.
4. **One bootstrap per language**: `pnpm install` for JS, `pip install -e ...` for Python. `pnpm bootstrap` does both.
5. **Module maturity is code**: Labels live in `app/status.py`, enforced by `test_module_maturity.py`. STATUS.md is derived.
6. **Feature freeze until stable**: No new modules until implemented -> stable promotion is complete.
"""


if __name__ == "__main__":
    content = generate()
    if "--write" in sys.argv:
        (REPO / "STATUS.md").write_text(content, encoding="utf-8")
        print(f"STATUS.md written ({len(content)} bytes)")
    elif "--write-to" in sys.argv:
        idx = sys.argv.index("--write-to")
        target = Path(sys.argv[idx + 1])
        target.write_text(content, encoding="utf-8")
        print(f"Written to {target} ({len(content)} bytes)")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(content)
