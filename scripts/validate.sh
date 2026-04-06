#!/usr/bin/env bash
# Canonical whole-repo validation.  One command, one pass/fail verdict.
#
# Mirrors scripts/validate.ps1 exactly — same 9 gates, same thresholds
# (imported from app.thresholds at runtime, not hardcoded).
#
# Gates:
#   1. Python API tests
#   2. TypeScript typecheck
#   3. Next.js production build
#   4. API import smoke          (routes >= MIN_API_ROUTES)
#   5. Agent-runtime import smoke
#   6. SDK barrel integrity      (exports >= MIN_SDK_PYTHON_EXPORTS)
#   7. Contract duplication guard
#   8. Eval config integrity
#   9. STATUS.md freshness
#
# Usage:  bash scripts/validate.sh
#         pnpm validate:sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Resolve python — canonical location is .venv at repo root
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PYTHON="$REPO_ROOT/.venv/bin/python"
elif [ -x "$REPO_ROOT/.venv/Scripts/python.exe" ]; then
  PYTHON="$REPO_ROOT/.venv/Scripts/python.exe"
else
  echo "ERROR: .venv not found at $REPO_ROOT — run 'pnpm bootstrap' first."
  exit 1
fi

failures=()
pass_count=0
total=0
start_time=$SECONDS

run_gate() {
  local name="$1"; shift
  total=$((total + 1))
  echo ""
  echo "────────────────────────────────────────"
  echo "  [$total] $name"
  echo "────────────────────────────────────────"
  local gate_start=$SECONDS
  if "$@" 2>&1 | sed 's/^/    /'; then
    local elapsed=$(( SECONDS - gate_start ))
    echo "  PASS  (${elapsed}s)"
    pass_count=$((pass_count + 1))
  else
    local elapsed=$(( SECONDS - gate_start ))
    echo "  FAIL"
    failures+=("$name")
  fi
}

# Gates

run_gate 'Python API tests' \
  bash -c "cd '$REPO_ROOT/apps/api' && '$PYTHON' -m pytest tests -q --tb=short"

run_gate 'TypeScript typecheck' \
  bash -c "cd '$REPO_ROOT' && pnpm typecheck"

run_gate 'Next.js production build' \
  bash -c "cd '$REPO_ROOT' && pnpm build:web"

run_gate 'API import smoke' \
  bash -c "cd '$REPO_ROOT/apps/api' && '$PYTHON' -c \"
from app.thresholds import MIN_API_ROUTES
from app.main import app
r=len(app.routes)
assert r>=MIN_API_ROUTES, f'Only {r} routes (need {MIN_API_ROUTES})'
print(f'app.main loaded — {r} routes')
\""

run_gate 'Agent-runtime import smoke' \
  bash -c "cd '$REPO_ROOT/apps/agent-runtime' && PYTHONPATH='$REPO_ROOT/apps/api' '$PYTHON' -c \"
from app.thresholds import MIN_AGENT_RUNTIME_ROUTES as T
import sys; sys.path.insert(0,'.')
from app.main import app
r=len(app.routes)
assert r>=T, f'Only {r} routes (need {T})'
print(f'app.main loaded — {r} routes')
\""

run_gate 'SDK barrel integrity' \
  bash -c "PYTHONPATH='$REPO_ROOT/apps/api' '$PYTHON' -c \"
from app.thresholds import MIN_SDK_PYTHON_EXPORTS as T
from casegraph_agent_sdk import __all__ as a
n=len(a)
assert n>=T, f'Only {n} exports (need {T})'
print(f'SDK barrel OK — {n} Python exports')
\""

run_gate 'Contract duplication guard' \
  bash -c "'$PYTHON' '$REPO_ROOT/scripts/check_contract_duplication.py'"

run_gate 'Eval config integrity' \
  bash -c "cd '$REPO_ROOT/apps/api' && '$PYTHON' -m pytest tests/test_eval_readiness.py -q --tb=short"

run_gate 'STATUS.md freshness' \
  bash -c "
cd '$REPO_ROOT/apps/api'
tmpfile=\$(mktemp)
'$PYTHON' '$REPO_ROOT/scripts/generate_status.py' --write-to \"\$tmpfile\"
expected=\$(sed 's/on [0-9]\\{4\\}-[0-9]\\{2\\}-[0-9]\\{2\\} [0-9]\\{2\\}:[0-9]\\{2\\} UTC/on DATE/' \"\$tmpfile\")
actual=\$(sed 's/on [0-9]\\{4\\}-[0-9]\\{2\\}-[0-9]\\{2\\} [0-9]\\{2\\}:[0-9]\\{2\\} UTC/on DATE/' '$REPO_ROOT/STATUS.md')
rm -f \"\$tmpfile\"
if [ \"\$expected\" != \"\$actual\" ]; then
  echo 'STATUS.md is stale. Run: pnpm generate:status'
  exit 1
fi
echo 'STATUS.md is fresh'
"

# Summary

elapsed=$(( SECONDS - start_time ))
echo ""
echo "════════════════════════════════════════"
if [ ${#failures[@]} -eq 0 ]; then
  echo "  ALL $total GATES PASSED  (${elapsed}s)"
else
  echo "  ${#failures[@]}/$total GATES FAILED  (${elapsed}s)"
  for f in "${failures[@]}"; do
    echo "    ✗ $f"
  done
fi
echo "════════════════════════════════════════"
echo ""

exit ${#failures[@]}
