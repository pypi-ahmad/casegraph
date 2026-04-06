"""Guard against duplicated SDK/workflow contract names in consuming layers.

Run:  python scripts/check_contract_duplication.py
Exit: 0 = clean, 1 = collisions found

Any class defined in packages/agent-sdk or packages/workflows must NOT be
re-defined under apps/api, apps/agent-runtime, or apps/web (TS) unless it
carries an explicit ``# contract-override: <reason>`` comment on the class.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Python shared exports ────────────────────────────────────────────────

def _sdk_python_names() -> set[str]:
    from casegraph_agent_sdk import __all__ as sdk_all  # type: ignore[import-untyped]
    return set(sdk_all)


def _workflows_python_names() -> set[str]:
    wf = importlib.import_module("casegraph_workflows")
    return {
        n
        for n in dir(wf)
        if inspect.isclass(getattr(wf, n)) and not n.startswith("_")
    }


# ── TypeScript shared exports ────────────────────────────────────────────

_TS_EXPORT_RE = re.compile(
    r"export\s+(?:type|interface|enum|class)\s+(\w+)", re.MULTILINE
)

def _sdk_ts_names() -> set[str]:
    names: set[str] = set()
    sdk_ts = REPO_ROOT / "packages" / "agent-sdk" / "src"
    for f in sdk_ts.rglob("*.ts"):
        names.update(_TS_EXPORT_RE.findall(f.read_text(encoding="utf-8")))
    wf_ts = REPO_ROOT / "packages" / "workflows" / "src"
    for f in wf_ts.rglob("*.ts"):
        names.update(_TS_EXPORT_RE.findall(f.read_text(encoding="utf-8")))
    return names


# ── Python collision scanner ─────────────────────────────────────────────

_OVERRIDE_RE = re.compile(r"#\s*contract-override:")

def _scan_python(shared: set[str]) -> list[str]:
    violations: list[str] = []
    scan_dirs = [
        REPO_ROOT / "apps" / "api" / "app",
        REPO_ROOT / "apps" / "agent-runtime" / "app",
    ]
    for root in scan_dirs:
        if not root.exists():
            continue
        for py in root.rglob("*.py"):
            try:
                source = py.read_text(encoding="utf-8")
                tree = ast.parse(source)
            except Exception:
                continue
            lines = source.splitlines()
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                if node.name not in shared:
                    continue
                # Check for override comment on the line above or same line
                has_override = False
                for offset in (node.lineno - 2, node.lineno - 1):
                    if 0 <= offset < len(lines) and _OVERRIDE_RE.search(lines[offset]):
                        has_override = True
                        break
                if has_override:
                    continue
                rel = py.relative_to(REPO_ROOT)
                violations.append(
                    f"  {rel}:{node.lineno}  class {node.name} "
                    f"collides with shared SDK/workflows export"
                )
    return violations


# ── TypeScript collision scanner ─────────────────────────────────────────

_TS_LOCAL_DEF_RE = re.compile(
    r"^(?:export\s+)?(?:type|interface|enum|class)\s+(\w+)", re.MULTILINE
)

def _scan_typescript(shared: set[str]) -> list[str]:
    violations: list[str] = []
    scan_dirs = [
        REPO_ROOT / "apps" / "web" / "src",
        REPO_ROOT / "apps" / "agent-runtime",
    ]
    for root in scan_dirs:
        if not root.exists():
            continue
        for ts in root.rglob("*.ts"):
            _check_ts_file(ts, shared, violations)
        for tsx in root.rglob("*.tsx"):
            _check_ts_file(tsx, shared, violations)
    return violations


def _check_ts_file(
    path: Path, shared: set[str], violations: list[str]
) -> None:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return
    for match in _TS_LOCAL_DEF_RE.finditer(content):
        name = match.group(1)
        if name not in shared:
            continue
        lineno = content[: match.start()].count("\n") + 1
        # Check for override comment
        line_start = content.rfind("\n", 0, match.start()) + 1
        prev_line_start = content.rfind("\n", 0, max(0, line_start - 1)) + 1
        context = content[prev_line_start : match.end()]
        if _OVERRIDE_RE.search(context):
            continue
        rel = path.relative_to(REPO_ROOT)
        violations.append(
            f"  {rel}:{lineno}  {name} collides with shared SDK/workflows export"
        )


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> int:
    py_shared = _sdk_python_names() | _workflows_python_names()
    ts_shared = _sdk_ts_names()

    py_violations = _scan_python(py_shared)
    ts_violations = _scan_typescript(ts_shared)
    all_violations = py_violations + ts_violations

    if all_violations:
        print(
            f"CONTRACT DUPLICATION: {len(all_violations)} collision(s) found.\n"
            "Shared types from packages/agent-sdk and packages/workflows must\n"
            "not be re-defined in apps/.  Import them instead.\n"
            "If intentional, add '# contract-override: <reason>' above the class.\n"
        )
        for v in sorted(all_violations):
            print(v)
        return 1

    print(
        f"No contract duplications. "
        f"(checked {len(py_shared)} Python + {len(ts_shared)} TS shared names)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
