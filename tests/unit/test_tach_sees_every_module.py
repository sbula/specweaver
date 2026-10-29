# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The layer check sees every module, fails on a loop, and allows no wrong edge.

Proves: TECH-081 FR-1, FR-2, FR-3, FR-5, FR-20

| Bucket | Case |
|---|---|
| Happy | `tach.toml` forbids code outside a module and checks type-only imports |
| Boundary | every `.py` file under `src/specweaver` falls in a registered module |
| Boundary | no edge is `deprecated`: none is owed, and none may come back (Q1 `[agreed 2026-10-29]`) |
| Degradation | a ledger path that no longer exists is named |
| Hostile | an import loop fails `tach check` |
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TACH = _ROOT / "tach.toml"
_LEDGER = _ROOT / "docs/architecture/06_lessons_and_future/known_boundary_violations.md"


def _config() -> dict:
    with _TACH.open("rb") as f:
        return tomllib.load(f)


def _deprecated_edges() -> set[tuple[str, str]]:
    edges = set()
    for module in _config()["modules"]:
        for dep in module.get("depends_on", []):
            if isinstance(dep, dict) and dep.get("deprecated"):
                edges.add((module["path"], dep["path"]))
    return edges


def test_code_outside_a_module_and_type_only_imports_are_checked() -> None:
    config = _config()

    assert config.get("root_module") == "forbid"
    assert config.get("ignore_type_checking_imports") is False


def test_every_source_file_belongs_to_a_registered_module() -> None:
    modules = [m["path"] for m in _config()["modules"]]
    stray = []
    for path in sorted((_ROOT / "src").rglob("*.py")):
        dotted = ".".join(path.with_suffix("").relative_to(_ROOT / "src").parts)
        dotted = dotted.removesuffix(".__init__")
        if not any(dotted == m or dotted.startswith(m + ".") for m in modules):
            stray.append(str(path.relative_to(_ROOT)))

    assert stray == [], f"files in no tach module: {stray}"


def test_import_loops_fail_the_check() -> None:
    assert _config().get("forbid_circular_dependencies") is True


def test_no_deprecated_edge_is_left() -> None:
    assert _deprecated_edges() == set()


def test_every_source_path_in_the_ledger_exists() -> None:
    cited = re.findall(r"`(src/specweaver/[\w/.]+?\.py)", _LEDGER.read_text(encoding="utf-8"))

    missing = sorted({p for p in cited if not (_ROOT / p).exists()})

    assert cited
    assert missing == []
