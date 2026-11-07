# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No module imports a store only for its side effect: tables are named where they are created.

Proves: TECH-090 FR-13
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[4] / "src" / "specweaver"


def _side_effect_store_imports() -> list[str]:
    found = []
    for path in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found += [
                    f"{path.relative_to(_SRC)}:{node.lineno} {alias.name}"
                    for alias in node.names
                    if alias.name.endswith(".store") and alias.asname is None
                ]
    return found


def test_the_source_tree_exists() -> None:
    assert (_SRC / "workspace" / "memory" / "store.py").is_file()


def test_no_store_is_imported_for_its_side_effect() -> None:
    assert _side_effect_store_imports() == []
