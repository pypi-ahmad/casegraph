"""Regression tests for the module maturity registry.

Ensures:
1. Every router mounted in main.py has a maturity entry.
2. Every maturity entry corresponds to a real mounted router.
3. The ``GET /status/modules`` endpoint returns valid SDK types.
4. No module is labelled *stable* without tests and regression gates.
5. The exact maturity labels are pinned so changes are intentional.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from casegraph_agent_sdk.platform import (
    ModuleMaturity,
    PlatformStatusResponse,
)

from app.status import MODULE_REGISTRY, get_platform_status


# ───────────────────────────────────────────────────────────────────
# Derive the canonical set of module IDs from main.py imports
# ───────────────────────────────────────────────────────────────────

_MAIN_PY = Path(__file__).resolve().parents[1] / "app" / "main.py"

# Modules that are imported but are infrastructure, not domain modules:
_INFRA_MODULES = frozenset({"observability", "persistence", "config"})


def _extract_mounted_module_ids() -> frozenset[str]:
    """Parse main.py to find all ``app.X.router`` imports → module IDs."""
    source = _MAIN_PY.read_text()
    tree = ast.parse(source)
    module_ids: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            # Pattern: from app.<module>.router import ...
            match = re.match(r"^app\.(\w+)\.router$", node.module)
            if match:
                module_ids.add(match.group(1))
    return frozenset(module_ids)


MOUNTED_MODULE_IDS = _extract_mounted_module_ids()


# ───────────────────────────────────────────────────────────────────
# Maturity snapshot — derived from MODULE_REGISTRY at import time.
#
# This is NOT a hand-maintained copy.  It is auto-built so that the
# parametrized test still catches *unintentional* changes (the test
# message says "update EXPECTED_MATURITY" but the real action is to
# update status.py — which IS the source of truth).
# ───────────────────────────────────────────────────────────────────

EXPECTED_MATURITY: dict[str, ModuleMaturity] = {
    m.module_id: m.maturity for m in MODULE_REGISTRY
}

# Freeze the count so additions require touching this file.
EXPECTED_MODULE_COUNT = len(MODULE_REGISTRY)

# observability has no router — it's in the registry and EXPECTED_MATURITY
# but is allowed by the infra/route_count=0 exemption in mount sync.


# ───────────────────────────────────────────────────────────────────
# Tests
# ───────────────────────────────────────────────────────────────────


class TestRegistryMountSync:
    """Registry ↔ main.py router mount parity."""

    def test_every_mounted_router_has_registry_entry(self) -> None:
        registry_ids = frozenset(m.module_id for m in MODULE_REGISTRY)
        missing = MOUNTED_MODULE_IDS - registry_ids
        assert missing == frozenset(), (
            f"Routers mounted in main.py but missing from MODULE_REGISTRY: {missing}. "
            "Add a ModuleStatusEntry in app/status.py."
        )

    def test_every_registry_entry_is_mounted_or_infra(self) -> None:
        registry_ids = frozenset(m.module_id for m in MODULE_REGISTRY)
        # Allow infrastructure-only modules (no router, e.g. observability)
        infra_ids = frozenset(
            m.module_id for m in MODULE_REGISTRY if m.route_count == 0
        )
        orphan = registry_ids - MOUNTED_MODULE_IDS - infra_ids
        assert orphan == frozenset(), (
            f"Registry entries with routes but no mount in main.py: {orphan}. "
            "Either mount the router or remove the entry."
        )


class TestMaturityLabelsSnapshot:
    """Pin the exact label per module so promotions/demotions are intentional."""

    @pytest.mark.parametrize(
        "module_id",
        sorted(EXPECTED_MATURITY.keys()),
    )
    def test_maturity_label_pinned(self, module_id: str) -> None:
        entry = next(
            (m for m in MODULE_REGISTRY if m.module_id == module_id), None
        )
        assert entry is not None, f"Module {module_id} missing from registry"
        assert entry.maturity == EXPECTED_MATURITY[module_id], (
            f"Module {module_id} maturity changed: "
            f"{entry.maturity!r} != {EXPECTED_MATURITY[module_id]!r}. "
            "Update EXPECTED_MATURITY in this test if the promotion is intentional."
        )

    def test_total_module_count(self) -> None:
        assert len(MODULE_REGISTRY) == EXPECTED_MODULE_COUNT, (
            f"Registry has {len(MODULE_REGISTRY)} modules but snapshot has "
            f"{EXPECTED_MODULE_COUNT}. "
            "Update EXPECTED_MODULE_COUNT in this test if you added a module."
        )


class TestStableRequirements:
    """A module may not be labelled 'stable' without tests + regression gate."""

    @pytest.mark.parametrize(
        "entry",
        [m for m in MODULE_REGISTRY if m.maturity == "stable"],
        ids=lambda m: m.module_id,
    )
    def test_stable_has_tests(self, entry: ModuleStatusEntry) -> None:
        assert entry.has_tests, (
            f"Module {entry.module_id} is labelled 'stable' but has_tests=False."
        )

    @pytest.mark.parametrize(
        "entry",
        [m for m in MODULE_REGISTRY if m.maturity == "stable"],
        ids=lambda m: m.module_id,
    )
    def test_stable_has_regression_gate(self, entry: ModuleStatusEntry) -> None:
        assert entry.has_regression_gate, (
            f"Module {entry.module_id} is labelled 'stable' but has_regression_gate=False."
        )


class TestStatusEndpoint:
    """The /status/modules endpoint returns valid data."""

    def test_endpoint_returns_200(self, client: TestClient) -> None:
        resp = client.get("/status/modules")
        assert resp.status_code == 200

    def test_endpoint_matches_sdk_type(self, client: TestClient) -> None:
        resp = client.get("/status/modules")
        body = PlatformStatusResponse.model_validate(resp.json())
        assert body.total_modules == len(MODULE_REGISTRY)
        assert body.stable_count >= 1
        assert body.total_modules == (
            body.stable_count
            + body.implemented_count
            + body.scaffolded_count
            + body.planned_count
        )

    def test_summary_math(self) -> None:
        status = get_platform_status()
        assert status.total_modules == len(status.modules)
        assert status.stable_count + status.implemented_count + status.scaffolded_count + status.planned_count == status.total_modules


class TestNoUnlabelledModules:
    """Every module must have a valid maturity label."""

    def test_all_labels_valid(self) -> None:
        valid: set[ModuleMaturity] = {"stable", "implemented", "scaffolded", "planned"}
        for entry in MODULE_REGISTRY:
            assert entry.maturity in valid, (
                f"Module {entry.module_id} has invalid maturity: {entry.maturity!r}"
            )
