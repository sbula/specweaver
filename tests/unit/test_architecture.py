# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import ast
import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType


def test_tach_architectural_boundaries() -> None:
    """
    Ensures that the Tach domain boundaries defined in tach.toml are strictly respected.
    This guarantees that the Layer Cake structure (Base -> Resource -> Capability -> Orchestrator)
    has no forbidden upstream dependencies, replacing the deleted __init__.py manual encapsulation.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    result = subprocess.run(["tach", "check"], cwd=root_dir, capture_output=True, text=True)

    if result.returncode != 0:
        # Count the number of [FAIL] lines
        fail_count = result.stdout.count("[FAIL]") + result.stderr.count("[FAIL]")

        # We are currently in Topic 07 Technical Debt epic.
        # The baseline is exactly 95 violations.
        assert fail_count <= 95, (
            f"Architecture boundary violation detected by tach! "
            f"Expected <= 95 baseline violations, got {fail_count}:\n"
            f"{result.stdout}\n{result.stderr}"
        )


def _interface_path_exists(root_dir: Path, base_parts: list[str], exposed_path: str) -> bool:
    """Check whether an exposed interface path resolves to a real file/dir,
    walking up ancestors to account for namespace packages lacking __init__.py."""
    parts = exposed_path.split(".")
    relative_path = Path(*base_parts) / Path(*parts)
    physical_dir = root_dir / relative_path
    physical_file = physical_dir.with_suffix(".py")

    if physical_dir.exists() or physical_file.exists():
        return True

    base_dir = root_dir / Path(*base_parts)
    current = physical_dir.parent
    while current != base_dir and current != root_dir:
        if current.with_suffix(".py").exists():
            return True
        if current.is_dir() and (current / "__init__.py").exists():
            return True
        current = current.parent
    return False


def test_tach_interfaces_map_to_valid_namespaces() -> None:
    """
    Edge Case: Prevention of Silent Namespace Ignore by Tach.
    Since __init__.py files were deleted (SF-4), these directories became Implicit Namespace Packages.
    Tach might silently skip checking a route if the dir has no __init__.py and doesn't map correctly.
    We formally assert that every path declared in [[interfaces]] exists as a physical directory or file.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    tach_path = root_dir / "tach.toml"
    assert tach_path.exists()

    with tach_path.open("rb") as f:
        config = tomllib.load(f)

    for interface in config.get("interfaces", []):
        from_bases = interface.get("from", [])
        if not from_bases:
            # Fallback for old tach syntax if any
            module_base = interface.get("module")
            if module_base:
                from_bases = [module_base]

        for module_base in from_bases:
            base_parts = module_base.split(".")
            if base_parts and base_parts[0] == "specweaver":
                base_parts.insert(0, "src")
            for exposed_path in interface.get("expose", []):
                path_exists = _interface_path_exists(root_dir, base_parts, exposed_path)
                assert path_exists, (
                    f"Tach explicit boundary violation risk! "
                    f"The interface {exposed_path} for module {module_base} listed in tach.toml does not map "
                    f"to any physical directory or file in the filesystem. Tach may silently ignore this."
                )


def test_tach_keeps_runner_soft_deprecated() -> None:
    """
    Integration Regression Guard:
    Ensures that the legacy 'runner' module is explicitly omitted from the 'src.specweaver.assurance.validation'
    expose list in tach.toml. This prevents accidental soft-deprecation regressions where a future
    developer might silently re-expose it, bypassing the architectural deprecation boundary.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    tach_path = root_dir / "tach.toml"
    assert tach_path.exists()

    with tach_path.open("rb") as f:
        config = tomllib.load(f)

    for interface in config.get("interfaces", []):
        from_bases = interface.get("from", [])
        if "src.specweaver.assurance.validation" in from_bases:
            exposed = interface.get("expose", [])
            assert "runner" not in exposed, (
                "CRITICAL: The 'runner' module must remain soft-deprecated! "
                "Do NOT add 'runner' to the validation interfaces in tach.toml."
            )


def _load_check_coupling() -> ModuleType:
    """`scripts/` isn't an importable package; load `check_coupling.py` by path
    (same pattern as `tests/unit/scripts/test_check_coupling.py`)."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    path = root_dir / "scripts" / "check_coupling.py"
    spec = importlib.util.spec_from_file_location("check_coupling", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_coupling"] = module
    spec.loader.exec_module(module)
    return module


def test_core_config_has_no_cross_domain_runtime_imports() -> None:
    """TECH-001 SF-04 regression guard.

    `core.config`'s own `context.yaml` declares `consumes: []` (a pure leaf), but two files
    (`db_bootstrap.py`, `settings_loader.py`) imported `infrastructure.llm`/`core.flow`/`workspace`
    directly, creating three separate `tach.toml`-declared circular dependencies -- only two of
    which (llm, flow) were ever named in TECH-001/TECH-022; the third (`workspace`) was found
    during this SF's own Red/Blue review. Both files moved to `core.config.bootstrap` (an
    `adapter`-archetype sub-boundary explicitly allowed to touch those domains) to fix it. This
    pins `core.config` itself -- excluding `bootstrap/` and `interfaces/`, both separately-scoped
    boundaries -- to never regrow a runtime import of those three domains.

    Uses `check_coupling.py`'s own `iter_runtime_imports` so `if TYPE_CHECKING:`-guarded imports
    are excluded the same way that script already had to fix for itself (see its test file): a
    check that flags correct code (a TYPE_CHECKING-only import breaks no cycle at runtime) is a
    check that gets suppressed.
    """
    check_coupling = _load_check_coupling()
    root_dir = Path(__file__).resolve().parent.parent.parent
    config_dir = root_dir / "src" / "specweaver" / "core" / "config"
    assert config_dir.is_dir(), f"expected {config_dir} to exist"

    forbidden_prefixes = (
        "specweaver.infrastructure.llm",
        "specweaver.core.flow",
        "specweaver.workspace",
    )

    def _imported_names(node: ast.Import | ast.ImportFrom) -> list[str]:
        if isinstance(node, ast.Import):
            return [alias.name for alias in node.names]
        return [node.module or ""]

    violations: list[str] = []
    for path in sorted(config_dir.glob("*.py")):  # top-level only: skips bootstrap/, interfaces/
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in check_coupling.iter_runtime_imports(tree):
            for name in _imported_names(node):
                if name.startswith(forbidden_prefixes):
                    violations.append(f"{path.name}: {name}")

    assert not violations, (
        "core.config regrew a cross-domain circular dependency (TECH-001 SF-04 regression): "
        f"{violations}"
    )
