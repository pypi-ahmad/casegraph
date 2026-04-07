"""Base tool abstraction for CaseGraph automation tools.

Every tool in the registry must subclass ``BaseTool`` and implement
``metadata()`` and ``execute()``.  The base class enforces typed
contracts and safety checks.

This is the foundation layer only — it deliberately does not cover
session management, persistence, or approval workflows.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from casegraph_agent_sdk.automation import (
    ToolExecutionError,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolMetadata,
)


class BaseTool(ABC):
    """Abstract base for all CaseGraph automation tools."""

    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Return static metadata for this tool."""

    @abstractmethod
    async def _execute(
        self, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """Perform the tool action and return a result dict.

        Subclasses raise ``ToolExecutionException`` on failure.
        """

    # ------------------------------------------------------------------
    # Public entry point with safety and timing wrapper
    # ------------------------------------------------------------------

    async def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        meta = self.metadata()

        # Dry-run short-circuit
        if request.dry_run:
            return ToolExecutionResult(
                tool_id=meta.id,
                status="success",
                output={"dry_run": True, "tool_metadata": meta.model_dump()},
                correlation_id=request.correlation_id,
            )

        # Not-implemented guard (planned or adapter_only)
        if meta.implementation_status in ("planned", "adapter_only"):
            return ToolExecutionResult(
                tool_id=meta.id,
                status="not_implemented",
                error=ToolExecutionError(
                    error_code=meta.implementation_status,
                    message=(
                        f"Tool '{meta.id}' is not executable yet "
                        f"(status: {meta.implementation_status})."
                    ),
                    recoverable=False,
                ),
                correlation_id=request.correlation_id,
            )

        # Approval guard
        if meta.capability_flags.requires_approval:
            return ToolExecutionResult(
                tool_id=meta.id,
                status="approval_required",
                error=ToolExecutionError(
                    error_code="approval_required",
                    message=f"Tool '{meta.id}' requires explicit approval before execution.",
                    recoverable=True,
                ),
                correlation_id=request.correlation_id,
            )

        start = time.perf_counter()
        try:
            output = await self._execute(request.parameters)
            duration_ms = (time.perf_counter() - start) * 1000
            return ToolExecutionResult(
                tool_id=meta.id,
                status="success",
                output=output,
                duration_ms=round(duration_ms, 2),
                correlation_id=request.correlation_id,
            )
        except ToolExecutionException as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            return ToolExecutionResult(
                tool_id=meta.id,
                status="error",
                error=ToolExecutionError(
                    error_code=exc.error_code,
                    message=str(exc),
                    recoverable=exc.recoverable,
                ),
                duration_ms=round(duration_ms, 2),
                correlation_id=request.correlation_id,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            return ToolExecutionResult(
                tool_id=meta.id,
                status="error",
                error=ToolExecutionError(
                    error_code="unexpected_error",
                    message=str(exc),
                    recoverable=False,
                ),
                duration_ms=round(duration_ms, 2),
                correlation_id=request.correlation_id,
            )


class ToolExecutionException(Exception):
    """Raised by tool implementations on expected failures."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "tool_error",
        recoverable: bool = False,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.recoverable = recoverable
