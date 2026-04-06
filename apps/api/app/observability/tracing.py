"""Lightweight tracing helpers that wrap Langfuse spans.

Every function here is a no-op when Langfuse is not configured.
Import and call freely — no try/except needed at call sites.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Generator

from app.observability.langfuse_client import get_langfuse


@contextmanager
def trace_span(
    *,
    name: str,
    trace_name: str | None = None,
    metadata: dict[str, Any] | None = None,
    input_data: Any | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager that creates a Langfuse trace + span.

    Yields a mutable dict where callers can set ``output``, ``status``,
    or additional ``metadata`` before the span closes.

    If Langfuse is not configured the body still executes — the dict
    is just never sent anywhere.
    """
    ctx: dict[str, Any] = {"output": None, "status": "ok", "metadata": metadata or {}}
    lf = get_langfuse()

    if lf is None:
        yield ctx
        return

    start = time.perf_counter()
    trace = lf.trace(name=trace_name or name, metadata=metadata, input=input_data)
    span = trace.span(name=name, input=input_data)

    try:
        yield ctx
    except Exception as exc:
        ctx["status"] = "error"
        ctx["metadata"]["error"] = str(exc)
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        ctx["metadata"]["duration_ms"] = round(duration_ms, 2)
        span.end(
            output=ctx.get("output"),
            metadata=ctx["metadata"],
            level="ERROR" if ctx["status"] == "error" else "DEFAULT",
        )
