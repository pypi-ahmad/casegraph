#!/usr/bin/env bash
# Local smoke test: hit live API endpoints to verify the server is running.
#
# Requires: uvicorn running on http://localhost:8000
# Run:      bash scripts/smoke-api.sh
#
# Tests provider listing, document capabilities, case CRUD, and health.
# Does NOT require LLM keys — only exercises local API logic.

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

pass=0
fail=0

test_endpoint() {
  local method="$1" path="$2" expected="${3:-200}" body="${4:-}"
  printf "  %s %s ... " "$method" "$path"
  local status
  if [ -n "$body" ]; then
    status=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" \
      -H "Content-Type: application/json" -d "$body" "$BASE_URL$path") || true
  else
    status=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$BASE_URL$path") || true
  fi
  if [ "$status" = "$expected" ]; then
    echo "OK ($status)"
    pass=$((pass + 1))
  else
    echo "FAIL (got $status, expected $expected)"
    fail=$((fail + 1))
  fi
}

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  CaseGraph API Local Smoke Test          ║"
echo "╚══════════════════════════════════════════╝"

echo ""
echo "Health & info"
test_endpoint GET /health
test_endpoint GET /info
test_endpoint GET /status/modules

echo ""
echo "Providers"
test_endpoint GET /providers

echo ""
echo "Document ingestion"
test_endpoint GET /documents/capabilities
test_endpoint GET /documents

echo ""
echo "Cases"
test_endpoint GET /cases
test_endpoint POST /cases 200 \
  '{"title":"Smoke test case","category":"test","domain_pack_id":"medical_insurance_us","case_type_id":"medical_insurance_us:prior_auth_review"}'

echo ""
echo "Domain packs"
test_endpoint GET /domains/packs
test_endpoint GET /domains/case-types

echo ""
echo "Workflow packs"
test_endpoint GET /workflow-packs

echo ""
echo "Submissions"
test_endpoint GET /submission/targets

echo ""
echo "Knowledge"
test_endpoint GET /knowledge/capabilities

total=$((pass + fail))
echo ""
echo "════════════════════════════════════════"
if [ "$fail" -eq 0 ]; then
  echo "  ALL $total SMOKE CHECKS PASSED"
else
  echo "  $fail/$total SMOKE CHECKS FAILED"
fi
echo "════════════════════════════════════════"
echo ""

exit "$fail"
