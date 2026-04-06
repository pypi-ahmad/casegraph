#!/usr/bin/env bash
#
# Bootstrap the entire CaseGraph monorepo from a fresh clone.
#
#   1. Enables corepack so the pinned pnpm version (from packageManager) is
#      activated automatically — no global pnpm install required.
#   2. Runs pnpm install for all JS/TS workspace packages.
#   3. Creates a single Python virtual-environment (.venv) at repo root and
#      installs all Python editable deps (SDK, workflows, API, agent-runtime).
#
# Prerequisites: Node.js >= 20, Python >= 3.12
# Idempotent — safe to re-run after pulling new changes.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# -------------------------------------------------------------------
# 1. Node / pnpm (via corepack — version pinned in packageManager)
# -------------------------------------------------------------------
echo ""
echo "==> Enabling corepack ..."
corepack enable

echo "==> Installing JS/TS dependencies (pnpm) ..."
pnpm install --frozen-lockfile

# -------------------------------------------------------------------
# 2. Python — single venv for all Python apps
# -------------------------------------------------------------------
VENV="$REPO_ROOT/.venv"
if [ ! -f "$VENV/bin/python" ]; then
    echo ""
    echo "==> Creating Python venv at $VENV ..."
    python3 -m venv "$VENV"
fi

echo "==> Upgrading pip ..."
"$VENV/bin/python" -m pip install --quiet --upgrade pip

echo "==> Installing Python packages (SDK + workflows + API + runtime) ..."
"$VENV/bin/python" -m pip install --quiet \
    -e "packages/agent-sdk" \
    -e "packages/workflows" \
    -e "apps/api[dev,observability]" \
    -e "apps/agent-runtime[dev]"

# -------------------------------------------------------------------
# 3. Seed .env from example if missing
# -------------------------------------------------------------------
if [ ! -f "$REPO_ROOT/.env" ] && [ -f "$REPO_ROOT/.env.example" ]; then
    echo "==> Copying .env.example → .env (edit to add API keys)"
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
fi

# -------------------------------------------------------------------
# 4. Summary
# -------------------------------------------------------------------
echo ""
echo "✅  Bootstrap complete."
echo ""
echo "  Activate Python :  source .venv/bin/activate"
echo ""
echo "  Frontend        :  pnpm dev:web                                          →  http://localhost:3000"
echo "  API             :  cd apps/api && uvicorn app.main:app --reload --port 8000"
echo "  Agent runtime   :  cd apps/agent-runtime && uvicorn app.main:app --reload --port 8100"
echo "  Validate all    :  pnpm validate"
echo ""
