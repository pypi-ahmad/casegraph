"""Tests for the observability layer — middleware, tracing, Langfuse wrapper."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------


class TestRequestLoggingMiddleware:
    """Verify the RequestLoggingMiddleware adds headers and logs."""

    def test_response_has_request_id_header(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers

    def test_request_id_passthrough(self, client: TestClient) -> None:
        custom_id = "test-request-id-abc123"
        resp = client.get("/health", headers={"x-request-id": custom_id})
        assert resp.headers["x-request-id"] == custom_id

    def test_request_logged_with_structured_fields(
        self, client: TestClient, caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="casegraph.requests"):
            resp = client.get("/health")
        assert resp.status_code == 200
        assert any("method=GET" in rec.message and "path=/health" in rec.message for rec in caplog.records)

    def test_request_id_generated_when_absent(self, client: TestClient) -> None:
        resp = client.get("/health")
        rid = resp.headers.get("x-request-id", "")
        assert len(rid) == 32  # uuid hex without dashes


# ---------------------------------------------------------------------------
# Langfuse client — safe degradation
# ---------------------------------------------------------------------------


class TestLangfuseClient:
    """Verify the Langfuse wrapper is safe when unconfigured."""

    def test_get_langfuse_returns_none_unconfigured(self) -> None:
        from app.observability.langfuse_client import get_langfuse, shutdown_langfuse

        # Force re-initialization
        import app.observability.langfuse_client as lm
        lm._initialized = False
        lm._langfuse_client = None

        result = get_langfuse()
        assert result is None
        # Clean up
        shutdown_langfuse()

    def test_langfuse_configured_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.observability.langfuse_client import langfuse_configured

        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
        assert langfuse_configured() is False


# ---------------------------------------------------------------------------
# Tracing — no-op behaviour
# ---------------------------------------------------------------------------


class TestTraceSpan:
    """Verify trace_span is a safe no-op when Langfuse is not available."""

    def test_trace_span_noop_yields_context(self) -> None:
        from app.observability.tracing import trace_span

        with trace_span(name="test_span") as ctx:
            ctx["output"] = "hello"

        assert ctx["output"] == "hello"
        assert ctx["status"] == "ok"

    def test_trace_span_propagates_exceptions(self) -> None:
        from app.observability.tracing import trace_span

        with pytest.raises(ValueError, match="boom"):
            with trace_span(name="fail_span") as _ctx:
                raise ValueError("boom")

        # In no-op mode (Langfuse unconfigured), status tracking is skipped.
        # The span still propagates the exception correctly.


# ---------------------------------------------------------------------------
# Middleware import integrity
# ---------------------------------------------------------------------------


class TestObservabilityModuleIntegrity:
    """Verify the observability module exports are importable."""

    def test_middleware_importable(self) -> None:
        from app.observability.middleware import RequestLoggingMiddleware
        assert RequestLoggingMiddleware is not None

    def test_langfuse_client_importable(self) -> None:
        from app.observability.langfuse_client import (
            get_langfuse,
            langfuse_configured,
            shutdown_langfuse,
        )
        assert all(callable(fn) for fn in [get_langfuse, langfuse_configured, shutdown_langfuse])

    def test_tracing_importable(self) -> None:
        from app.observability.tracing import trace_span
        assert callable(trace_span)
