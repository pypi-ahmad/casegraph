"""Centralized validation thresholds — single source of truth.

Every floor/threshold used by ``pnpm validate``, ``test_structural_verification.py``,
and ``generate_status.py`` must be defined here.  If you need to raise a floor,
change it here and all consumers pick it up automatically.

validate.ps1 reads these values at runtime via:
    python -c "from app.thresholds import *; print(MIN_API_ROUTES)"
"""

from __future__ import annotations

# ── API route floor ──────────────────────────────────────────────────
MIN_API_ROUTES: int = 140

# ── SDK export floors ────────────────────────────────────────────────
MIN_SDK_PYTHON_EXPORTS: int = 575
MIN_SDK_TS_EXPORTS: int = 575

# ── Frontend floors ──────────────────────────────────────────────────
MIN_FRONTEND_PAGES: int = 29
MIN_FRONTEND_API_CLIENTS: int = 25

# ── Test floors ──────────────────────────────────────────────────────
MIN_TEST_FILES: int = 25

# ── Agent-runtime floor (used by validate.ps1 only) ─────────────────
MIN_AGENT_RUNTIME_ROUTES: int = 5
