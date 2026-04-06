"""Eval readiness gates — machine-verify eval infrastructure integrity.

These tests ensure the evaluation scaffolding (Promptfoo configs,
seed datasets, eval service registry) stays consistent without
actually running any evals or requiring provider API keys.

Gate philosophy: Promptfoo/Langfuse deepening is deferred until main
flows are frozen.  These tests prevent the scaffold from rotting
while we wait.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
EVALS_DIR = REPO / "services" / "evals"
PROMPTFOO_DIR = EVALS_DIR / "promptfoo"
DATASETS_DIR = EVALS_DIR / "datasets"

EXPECTED_PROMPTFOO_CONFIGS = [
    "provider-comparison.yaml",
    "retrieval-eval.yaml",
    "agent-workflow-eval.yaml",
    "workflow-pack-extraction-eval.yaml",
]


# ---------------------------------------------------------------------------
# Promptfoo config file integrity
# ---------------------------------------------------------------------------


class TestPromptfooConfigIntegrity:
    """Every Promptfoo YAML parses and references real files."""

    @pytest.fixture()
    def promptfoo_configs(self) -> list[Path]:
        return [PROMPTFOO_DIR / name for name in EXPECTED_PROMPTFOO_CONFIGS]

    def test_all_expected_configs_exist(self, promptfoo_configs: list[Path]) -> None:
        for path in promptfoo_configs:
            assert path.exists(), f"Missing Promptfoo config: {path.name}"

    @pytest.mark.parametrize("config_name", EXPECTED_PROMPTFOO_CONFIGS)
    def test_config_parses_as_valid_yaml(self, config_name: str) -> None:
        path = PROMPTFOO_DIR / config_name
        if not path.exists():
            pytest.skip(f"{config_name} not found")
        content = path.read_text(encoding="utf-8")
        doc = yaml.safe_load(content)
        assert isinstance(doc, dict), f"{config_name} did not parse as a YAML mapping"

    @pytest.mark.parametrize("config_name", EXPECTED_PROMPTFOO_CONFIGS)
    def test_config_has_required_keys(self, config_name: str) -> None:
        path = PROMPTFOO_DIR / config_name
        if not path.exists():
            pytest.skip(f"{config_name} not found")
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        for key in ("description", "providers", "tests"):
            assert key in doc, f"{config_name} missing required key '{key}'"

    @pytest.mark.parametrize("config_name", EXPECTED_PROMPTFOO_CONFIGS)
    def test_config_test_data_file_exists(self, config_name: str) -> None:
        path = PROMPTFOO_DIR / config_name
        if not path.exists():
            pytest.skip(f"{config_name} not found")
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        tests_ref = doc.get("tests", "")
        if isinstance(tests_ref, str) and tests_ref.startswith("file://"):
            rel = tests_ref.removeprefix("file://")
            # Promptfoo resolves relative to the evals dir (cwd when running)
            data_path = EVALS_DIR / rel
            assert data_path.exists(), (
                f"{config_name} references '{tests_ref}' but "
                f"{data_path} does not exist"
            )


# ---------------------------------------------------------------------------
# Seed dataset integrity
# ---------------------------------------------------------------------------


class TestSeedDatasets:
    """Seed data files are valid, non-empty JSON arrays."""

    def test_all_datasets_exist(self) -> None:
        assert DATASETS_DIR.exists(), "Datasets directory missing"
        json_files = list(DATASETS_DIR.glob("*.json"))
        assert len(json_files) >= 4, (
            f"Expected ≥ 4 seed datasets, found {len(json_files)}: "
            f"{[f.name for f in json_files]}"
        )

    @pytest.mark.parametrize("config_name", EXPECTED_PROMPTFOO_CONFIGS)
    def test_referenced_dataset_is_nonempty_json(self, config_name: str) -> None:
        path = PROMPTFOO_DIR / config_name
        if not path.exists():
            pytest.skip(f"{config_name} not found")
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        tests_ref = doc.get("tests", "")
        if not (isinstance(tests_ref, str) and tests_ref.startswith("file://")):
            pytest.skip(f"{config_name} tests is inline, not a file reference")
        rel = tests_ref.removeprefix("file://")
        data_path = EVALS_DIR / rel
        if not data_path.exists():
            pytest.skip(f"Dataset {data_path} missing (covered by config test)")
        data = json.loads(data_path.read_text(encoding="utf-8"))
        assert isinstance(data, list), f"Dataset {data_path.name} is not a JSON array"
        assert len(data) > 0, f"Dataset {data_path.name} is empty"


# ---------------------------------------------------------------------------
# Eval service registry consistency
# ---------------------------------------------------------------------------


class TestEvalServiceRegistryConsistency:
    """BenchmarkSuiteMeta entries match on-disk Promptfoo configs."""

    def test_every_benchmark_suite_has_config_on_disk(self) -> None:
        from app.evals.service import _BENCHMARK_SUITES

        for suite in _BENCHMARK_SUITES:
            config_path = REPO / suite.config_path
            assert config_path.exists(), (
                f"BenchmarkSuiteMeta '{suite.id}' references "
                f"'{suite.config_path}' but file does not exist"
            )

    def test_every_on_disk_config_has_registry_entry(self) -> None:
        from app.evals.service import _BENCHMARK_SUITES

        registered_paths = {s.config_path for s in _BENCHMARK_SUITES}
        for config_file in PROMPTFOO_DIR.glob("*.yaml"):
            rel = config_file.relative_to(REPO).as_posix()
            assert rel in registered_paths, (
                f"On-disk config '{rel}' has no BenchmarkSuiteMeta entry"
            )

    def test_benchmark_suite_ids_unique(self) -> None:
        from app.evals.service import _BENCHMARK_SUITES

        ids = [s.id for s in _BENCHMARK_SUITES]
        assert len(ids) == len(set(ids)), f"Duplicate suite IDs: {ids}"

    def test_workflow_regression_suites_exist(self) -> None:
        from app.evals.suites import get_eval_suite_registry

        registry = get_eval_suite_registry()
        suites = registry.list_response().suites
        assert len(suites) >= 3, (
            f"Expected ≥ 3 workflow regression suites, found {len(suites)}"
        )


# ---------------------------------------------------------------------------
# Observability wiring
# ---------------------------------------------------------------------------


class TestObservabilityWiring:
    """Verify observability is properly mounted in the app."""

    def test_middleware_mounted_on_app(self) -> None:
        from app.main import app
        from app.observability.middleware import RequestLoggingMiddleware

        middleware_types = [type(m) for m in getattr(app, "user_middleware", [])]
        # Starlette stores middleware as Middleware objects with .cls
        middleware_classes = [
            m.cls for m in getattr(app, "user_middleware", [])
            if hasattr(m, "cls")
        ]
        assert RequestLoggingMiddleware in middleware_classes, (
            "RequestLoggingMiddleware not found in app.user_middleware"
        )

    def test_langfuse_lifecycle_in_app_lifespan(self) -> None:
        """The app lifespan should reference Langfuse start/shutdown."""
        import inspect
        from app.main import lifespan

        source = inspect.getsource(lifespan)
        assert "get_langfuse" in source, "Lifespan doesn't initialise Langfuse"
        assert "shutdown_langfuse" in source, "Lifespan doesn't shut down Langfuse"
