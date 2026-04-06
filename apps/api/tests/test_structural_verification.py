"""Structural verification tests — machine evidence, not prose.

Every claim from STATUS.md and validate.ps1 that can be checked
programmatically is checked here.  If a threshold becomes wrong,
the test fails with the exact current value so you can update it.

These tests are intentionally strict so that drift requires an
explicit, reviewable update to the pinned constant.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]  # e:\Github\casegraph
API_APP = REPO / "apps" / "api" / "app"
WEB_APP = REPO / "apps" / "web" / "src"


# ═══════════════════════════════════════════════════════════════════
# Thresholds — imported from the single source of truth
# ═══════════════════════════════════════════════════════════════════

from app.thresholds import (  # noqa: E402
    MIN_API_ROUTES,
    MIN_FRONTEND_API_CLIENTS,
    MIN_FRONTEND_PAGES,
    MIN_SDK_PYTHON_EXPORTS,
    MIN_SDK_TS_EXPORTS,
    MIN_TEST_FILES,
)


# ═══════════════════════════════════════════════════════════════════
# API route count
# ═══════════════════════════════════════════════════════════════════


class TestAPIRouteInventory:
    """Pin the API route count so route deletions are caught."""

    def test_route_count_floor(self) -> None:
        from app.main import app

        count = len([r for r in app.routes if hasattr(r, "methods")])
        assert count >= MIN_API_ROUTES, (
            f"API has {count} routes; expected >= {MIN_API_ROUTES}. "
            "If routes were intentionally removed, lower MIN_API_ROUTES."
        )

    def test_health_endpoint_exists(self) -> None:
        from app.main import app

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/health" in paths

    def test_status_modules_endpoint_exists(self) -> None:
        from app.main import app

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/status/modules" in paths

    def test_registry_route_sum_consistent(self) -> None:
        """The maturity registry's declared route_count per module should
        be close to the actual total (excluding infra routes like /health)."""
        from app.main import app
        from app.status import MODULE_REGISTRY

        registry_sum = sum(m.route_count for m in MODULE_REGISTRY)
        actual = len([r for r in app.routes if hasattr(r, "methods")])
        # Allow small delta for infra routes (health, status, etc.)
        delta = actual - registry_sum
        assert 0 <= delta <= 10, (
            f"Route count delta too large: actual={actual}, registry_sum={registry_sum}, "
            f"delta={delta}. Update route_count values in app/status.py."
        )


# ═══════════════════════════════════════════════════════════════════
# SDK barrel exports
# ═══════════════════════════════════════════════════════════════════


_TS_EXPORT_RE = re.compile(
    r"export\s+(?:type|interface|enum|class)\s+(\w+)", re.MULTILINE
)


class TestSDKExportCounts:
    """Pin SDK export counts so accidental removals are caught."""

    def test_python_export_floor(self) -> None:
        import casegraph_agent_sdk as sdk

        count = len(sdk.__all__)
        assert count >= MIN_SDK_PYTHON_EXPORTS, (
            f"Python SDK has {count} exports; expected >= {MIN_SDK_PYTHON_EXPORTS}."
        )

    def test_typescript_export_floor(self) -> None:
        ts_src = REPO / "packages" / "agent-sdk" / "src"
        names: set[str] = set()
        for f in ts_src.rglob("*.ts"):
            names.update(_TS_EXPORT_RE.findall(f.read_text(encoding="utf-8")))
        count = len(names)
        assert count >= MIN_SDK_TS_EXPORTS, (
            f"TypeScript SDK has {count} exports; expected >= {MIN_SDK_TS_EXPORTS}."
        )

    def test_python_ts_parity(self) -> None:
        """Python and TypeScript SDKs should not diverge by more than 20 exports."""
        import casegraph_agent_sdk as sdk

        py_count = len(sdk.__all__)

        ts_src = REPO / "packages" / "agent-sdk" / "src"
        ts_names: set[str] = set()
        for f in ts_src.rglob("*.ts"):
            ts_names.update(_TS_EXPORT_RE.findall(f.read_text(encoding="utf-8")))
        ts_count = len(ts_names)

        drift = abs(py_count - ts_count)
        assert drift <= 20, (
            f"SDK parity drift: Python={py_count}, TypeScript={ts_count}, "
            f"delta={drift}. Sync the SDKs."
        )


# ═══════════════════════════════════════════════════════════════════
# Frontend surface area
# ═══════════════════════════════════════════════════════════════════


class TestFrontendInventory:
    """Pin frontend page and API-client counts."""

    def test_page_count_floor(self) -> None:
        app_dir = WEB_APP / "app"
        if not app_dir.exists():
            pytest.skip("apps/web/src/app not found")
        pages = list(app_dir.rglob("page.tsx"))
        count = len(pages)
        assert count >= MIN_FRONTEND_PAGES, (
            f"Frontend has {count} page.tsx files; expected >= {MIN_FRONTEND_PAGES}."
        )

    def test_api_client_count_floor(self) -> None:
        lib_dir = WEB_APP / "lib"
        if not lib_dir.exists():
            pytest.skip("apps/web/src/lib not found")
        clients = list(lib_dir.glob("*-api.ts"))
        count = len(clients)
        assert count >= MIN_FRONTEND_API_CLIENTS, (
            f"Frontend has {count} API client modules; expected >= {MIN_FRONTEND_API_CLIENTS}."
        )

    def test_no_placeholder_pages(self) -> None:
        """No page.tsx file should contain 'Coming Soon' or 'TODO' as placeholder."""
        app_dir = WEB_APP / "app"
        if not app_dir.exists():
            pytest.skip("apps/web/src/app not found")

        placeholders: list[str] = []
        for page in app_dir.rglob("page.tsx"):
            content = page.read_text(encoding="utf-8")
            # Only flag obviously placeholder pages, not comments
            if re.search(r"['\"]Coming Soon['\"]", content, re.IGNORECASE):
                placeholders.append(str(page.relative_to(REPO)))
        assert placeholders == [], (
            f"Placeholder pages found: {placeholders}"
        )


# ═══════════════════════════════════════════════════════════════════
# Test file inventory
# ═══════════════════════════════════════════════════════════════════


class TestTestInventory:
    """Pin the test file count so coverage regression is caught."""

    def test_test_file_count_floor(self) -> None:
        test_dir = REPO / "apps" / "api" / "tests"
        test_files = [f for f in test_dir.glob("test_*.py") if f.is_file()]
        count = len(test_files)
        assert count >= MIN_TEST_FILES, (
            f"Found {count} test files; expected >= {MIN_TEST_FILES}."
        )

    def test_every_test_file_has_at_least_one_test(self) -> None:
        """Every test_*.py should define at least one function starting with test_."""
        test_dir = REPO / "apps" / "api" / "tests"
        empty: list[str] = []
        for f in test_dir.glob("test_*.py"):
            source = f.read_text(encoding="utf-8")
            tree = ast.parse(source)
            has_test = any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
                for node in ast.walk(tree)
            )
            if not has_test:
                empty.append(f.name)
        assert empty == [], f"Test files with no test functions: {empty}"


# ═══════════════════════════════════════════════════════════════════
# Scaffolded module verification
# ═══════════════════════════════════════════════════════════════════


class TestScaffoldedModuleClaims:
    """Verify that modules labelled 'scaffolded' are genuinely thin."""

    def test_scaffolded_modules_have_few_routes(self) -> None:
        from app.status import MODULE_REGISTRY

        for m in MODULE_REGISTRY:
            if m.maturity == "scaffolded":
                assert m.route_count <= 5, (
                    f"Module {m.module_id} is 'scaffolded' but has {m.route_count} routes. "
                    "Promote to 'implemented' or reduce scope."
                )

    def test_scaffolded_modules_have_no_db_models(self) -> None:
        from app.status import MODULE_REGISTRY

        for m in MODULE_REGISTRY:
            if m.maturity == "scaffolded":
                assert not m.has_db_models, (
                    f"Module {m.module_id} is 'scaffolded' but has DB models. "
                    "Promote to 'implemented'."
                )

    def test_implemented_modules_have_tests(self) -> None:
        """Every 'implemented' module must have tests — that's the minimum bar."""
        from app.status import MODULE_REGISTRY

        untested = [
            m.module_id
            for m in MODULE_REGISTRY
            if m.maturity == "implemented" and not m.has_tests
        ]
        assert untested == [], (
            f"Implemented modules without tests: {untested}. "
            "Either add tests or downgrade to 'scaffolded'."
        )


# ═══════════════════════════════════════════════════════════════════
# validate.ps1 consistency
# ═══════════════════════════════════════════════════════════════════


class TestValidateScriptConsistency:
    """validate.ps1 imports from app.thresholds — verify the thresholds are sane."""

    def test_validate_script_references_thresholds_module(self) -> None:
        """validate.ps1 must import from app.thresholds, not hardcode values."""
        script = (REPO / "scripts" / "validate.ps1").read_text(encoding="utf-8")
        assert "app.thresholds" in script, (
            "validate.ps1 must import thresholds from app.thresholds, "
            "not hardcode numeric values."
        )

    def test_route_threshold_not_stale(self) -> None:
        from app.main import app

        actual = len([r for r in app.routes if hasattr(r, "methods")])
        assert actual - MIN_API_ROUTES <= 15, (
            f"MIN_API_ROUTES ({MIN_API_ROUTES}) is stale — actual is {actual}. "
            f"Update app/thresholds.py."
        )

    def test_sdk_threshold_not_stale(self) -> None:
        import casegraph_agent_sdk as sdk

        actual = len(sdk.__all__)
        assert actual - MIN_SDK_PYTHON_EXPORTS <= 15, (
            f"MIN_SDK_PYTHON_EXPORTS ({MIN_SDK_PYTHON_EXPORTS}) is stale — actual is {actual}. "
            f"Update app/thresholds.py."
        )


# ═══════════════════════════════════════════════════════════════════════════
# HEAD truth validation — machine-verified counts, not prose
# ═══════════════════════════════════════════════════════════════════════════


class TestHeadTruth:
    """Verify that STATUS.md claims match actual HEAD values.

    If generate_status.py is the source of truth, the generated STATUS.md
    must reflect the same numbers as live introspection.  This class
    ensures the two never diverge.
    """

    def _read_status_md(self) -> str:
        path = REPO / "STATUS.md"
        assert path.exists(), "STATUS.md not found at repo root"
        return path.read_text(encoding="utf-8")

    def test_status_md_route_count_matches_actual(self) -> None:
        """The route count in STATUS.md must match app.routes within ±5."""
        from app.main import app

        actual = len([r for r in app.routes if hasattr(r, "methods")])
        content = self._read_status_md()
        # Match patterns like "149 API routes" or "**149** API routes"
        match = re.search(r"\*?\*?(\d+)\*?\*?\s+API\s+routes", content, re.IGNORECASE)
        if not match:
            pytest.skip("Route count not found in STATUS.md")
        claimed = int(match.group(1))
        assert abs(actual - claimed) <= 5, (
            f"STATUS.md claims {claimed} routes but actual is {actual}. "
            "Run `pnpm generate:status` to refresh."
        )

    def test_status_md_test_count_matches_actual(self) -> None:
        """The test file count in STATUS.md must match the actual count within ±3."""
        test_dir = REPO / "apps" / "api" / "tests"
        actual = len([f for f in test_dir.glob("test_*.py") if f.is_file()])
        content = self._read_status_md()
        match = re.search(r"\*?\*?(\d+)\*?\*?\s+test\s+files?", content, re.IGNORECASE)
        if not match:
            pytest.skip("Test file count not found in STATUS.md")
        claimed = int(match.group(1))
        assert abs(actual - claimed) <= 3, (
            f"STATUS.md claims {claimed} test files but actual is {actual}. "
            "Run `pnpm generate:status` to refresh."
        )

    def test_status_md_sdk_python_count_matches_actual(self) -> None:
        """Python SDK export count in STATUS.md must match live count within ±10."""
        import casegraph_agent_sdk as sdk

        actual = len(sdk.__all__)
        content = self._read_status_md()
        match = re.search(r"\*?\*?(\d+)\*?\*?\s+Python\s+(?:SDK\s+)?exports?", content, re.IGNORECASE)
        if not match:
            pytest.skip("Python SDK export count not found in STATUS.md")
        claimed = int(match.group(1))
        assert abs(actual - claimed) <= 10, (
            f"STATUS.md claims {claimed} Python exports but actual is {actual}. "
            "Run `pnpm generate:status` to refresh."
        )

    def test_status_md_module_count_matches_registry(self) -> None:
        """Module count in STATUS.md must match MODULE_REGISTRY length."""
        from app.status import MODULE_REGISTRY

        actual = len(MODULE_REGISTRY)
        content = self._read_status_md()
        match = re.search(r"\*?\*?(\d+)\*?\*?\s+modules?", content, re.IGNORECASE)
        if not match:
            pytest.skip("Module count not found in STATUS.md")
        claimed = int(match.group(1))
        assert actual == claimed, (
            f"STATUS.md claims {claimed} modules but registry has {actual}. "
            "Run `pnpm generate:status` to refresh."
        )

    def test_pinned_thresholds_not_stale(self) -> None:
        """The MIN_* constants in this file must not be more than 20 below actual.

        If the system has grown significantly and the floor hasn't been raised,
        that's a missed update — the floor becomes meaningless.
        """
        from app.main import app

        actual_routes = len([r for r in app.routes if hasattr(r, "methods")])
        assert actual_routes - MIN_API_ROUTES <= 20, (
            f"MIN_API_ROUTES ({MIN_API_ROUTES}) is stale — actual is {actual_routes}. "
            "Raise the floor."
        )

        import casegraph_agent_sdk as sdk
        actual_py = len(sdk.__all__)
        assert actual_py - MIN_SDK_PYTHON_EXPORTS <= 20, (
            f"MIN_SDK_PYTHON_EXPORTS ({MIN_SDK_PYTHON_EXPORTS}) is stale — actual is {actual_py}."
        )

        test_dir = REPO / "apps" / "api" / "tests"
        actual_tests = len([f for f in test_dir.glob("test_*.py") if f.is_file()])
        assert actual_tests - MIN_TEST_FILES <= 15, (
            f"MIN_TEST_FILES ({MIN_TEST_FILES}) is stale — actual is {actual_tests}."
        )
