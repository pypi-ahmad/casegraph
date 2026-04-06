#!/usr/bin/env bash
# Run a Promptfoo eval suite from the services/evals directory.
# Usage: ./scripts/run-promptfoo.sh <config-name>
# Example: ./scripts/run-promptfoo.sh provider-comparison
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVALS_DIR="$(dirname "$SCRIPT_DIR")"

CONFIG_NAME="${1:-}"
if [ -z "$CONFIG_NAME" ]; then
  echo "Usage: $0 <config-name>"
  echo "Available configs:"
  ls "$EVALS_DIR/promptfoo/"*.yaml 2>/dev/null | xargs -I{} basename {} .yaml
  exit 1
fi

CONFIG_FILE="$EVALS_DIR/promptfoo/${CONFIG_NAME}.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Error: Config file not found: $CONFIG_FILE"
  exit 1
fi

# Load env if available
if [ -f "$EVALS_DIR/config/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$EVALS_DIR/config/.env"
  set +a
fi

: "${CASEGRAPH_API_URL:=http://localhost:8000}"
export CASEGRAPH_API_URL

mkdir -p "$EVALS_DIR/results"

echo "Running Promptfoo eval: $CONFIG_NAME"
cd "$EVALS_DIR"
npx promptfoo@latest eval -c "$CONFIG_FILE"
echo "Done. View results: npx promptfoo@latest view"
