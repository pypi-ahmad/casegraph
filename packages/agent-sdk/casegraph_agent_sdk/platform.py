"""Platform status types — module maturity tracking."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ModuleMaturity = Literal[
    "implemented",
    "stable",
    "scaffolded",
    "planned",
]
"""
Maturity labels (ordered from most to least mature):

- **stable**: Fully implemented, regression-gated, exercised in cross-layer flows.
- **implemented**: Working logic, endpoints, and tests — but not yet hardened
  with dedicated regression gates or cross-layer contract tests.
- **scaffolded**: Router + service exist, but logic is thin/proxy/stub.
  Endpoints return real HTTP responses but don't do substantive work.
- **planned**: Module directory may exist; no working endpoints or logic.
"""


class ModuleStatusEntry(BaseModel):
    """Status of a single API module."""

    module_id: str
    display_name: str
    maturity: ModuleMaturity
    route_count: int = 0
    has_db_models: bool = False
    has_tests: bool = False
    has_regression_gate: bool = False
    notes: str = ""


class PlatformStatusResponse(BaseModel):
    """Aggregate platform maturity summary."""

    modules: list[ModuleStatusEntry] = Field(default_factory=list)
    total_modules: int = 0
    stable_count: int = 0
    implemented_count: int = 0
    scaffolded_count: int = 0
    planned_count: int = 0
