# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`core/config` is `pure-logic`, as its manifest says: it opens no database and owns no queue.

Proves: TECH-090 FR-11

`core/config/bootstrap` and `core/config/interfaces` are their own `adapter` packages and are not
judged here.

| Bucket | Case |
|---|---|
| Happy | no module directly in `core/config` imports `sqlite3`, `sqlalchemy`, `logging.handlers` or `asyncio` |
| Boundary | the manifest still says `pure-logic` |
| Hostile | a private `_now_iso` copy anywhere outside `commons` is caught |
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[4] / "src" / "specweaver"
_CONFIG = _SRC / "core" / "config"
_IO = ("sqlite3", "sqlalchemy", "logging.handlers", "asyncio")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_config_module_does_io() -> None:
    offenders = {
        path.name: sorted(n for n in _imports(path) if n.startswith(_IO))
        for path in _CONFIG.glob("*.py")
        if any(n.startswith(_IO) for n in _imports(path))
    }

    assert offenders == {}


def test_the_manifest_says_pure_logic() -> None:
    assert "archetype: pure-logic" in (_CONFIG / "context.yaml").read_text(encoding="utf-8")


def test_no_private_now_iso_outside_commons() -> None:
    copies = [
        str(path.relative_to(_SRC))
        for path in _SRC.rglob("*.py")
        if "commons" not in path.parts
        and any(
            isinstance(node, ast.FunctionDef) and node.name == "_now_iso"
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        )
    ]

    assert copies == []
