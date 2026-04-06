# Langfuse Integration

The Langfuse integration lives in the Python API backend at `apps/api/app/observability/`.

See the [main evals README](../README.md) for setup instructions.

## Architecture

The integration provides a thin wrapper (`get_langfuse()`) that:
1. Returns a configured Langfuse client if env vars are set
2. Returns `None` if not configured — all calling code handles this gracefully
3. Does not import langfuse at module level, so the API starts without it installed

## Instrumentation Points

Current instrumentation hooks (foundation only):
- Provider validation / model discovery boundaries
- Knowledge search boundary

These are wired as lightweight `trace()` / `span()` calls, not full auto-instrumentation.

## Required Environment Variables

```
LANGFUSE_HOST=http://localhost:3002   # or https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```
