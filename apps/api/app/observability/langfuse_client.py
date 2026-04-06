"""Langfuse integration — safe-degrading observability wrapper.

If LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set in the environment,
``get_langfuse()`` returns a configured Langfuse client.  Otherwise it
returns ``None`` and all calling code must handle that gracefully.

The ``langfuse`` package is an optional dependency.  If it is not installed,
this module logs a debug message and ``get_langfuse()`` returns ``None``.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langfuse import Langfuse

logger = logging.getLogger(__name__)

_langfuse_client: "Langfuse | None" = None
_initialized = False


def langfuse_configured() -> bool:
    """Return True if the required Langfuse env vars are present."""
    return bool(
        os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
    )


def get_langfuse() -> "Langfuse | None":
    """Return a Langfuse client singleton, or None if not configured."""
    global _langfuse_client, _initialized

    if _initialized:
        return _langfuse_client

    _initialized = True

    if not langfuse_configured():
        logger.debug("Langfuse not configured — tracing disabled.")
        return None

    try:
        from langfuse import Langfuse  # noqa: WPS433
    except ImportError:
        logger.debug("langfuse package not installed — tracing disabled.")
        return None

    _langfuse_client = Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    logger.info("Langfuse tracing enabled (host=%s).", _langfuse_client.base_url)
    return _langfuse_client


def shutdown_langfuse() -> None:
    """Flush and shut down the Langfuse client if initialized."""
    global _langfuse_client, _initialized
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
            _langfuse_client.shutdown()
        except Exception:
            logger.debug("Langfuse shutdown error (non-fatal).", exc_info=True)
    _langfuse_client = None
    _initialized = False
