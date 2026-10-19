# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Only `core.config.bootstrap` opens the settings files; every other module takes what it parsed.

Proves: C-FLOW-13 NFR-4

Every source file outside `core/config/bootstrap` is parsed, and any path built from, or file
opened by, one of the three file names is a second reader.

| Bucket | Case |
|---|---|
| Happy | no module outside bootstrap builds a path to `settings.toml`, `specweaver.toml` or `keys.env` |
| Boundary | a file name in a message or a label is not a read |
| Degradation | not applicable — the source is read, nothing runs |
| Hostile | a planted `root / "settings.toml"` and `open("keys.env")` are caught |
"""

from __future__ import annotations

import ast
from pathlib import Path

_NAMES = frozenset({"settings.toml", "specweaver.toml", "keys.env"})
_SRC = Path(__file__).resolve().parents[4] / "src" / "specweaver"
_BOOTSTRAP = _SRC / "core" / "config" / "bootstrap"


def _reads(source: str) -> list[int]:
    """The lines that build a path to, or open, one of the settings files."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            parts = (node.left, node.right)
        elif isinstance(node, ast.Call):
            parts = tuple(node.args)
        else:
            continue
        if any(isinstance(p, ast.Constant) and p.value in _NAMES for p in parts):
            found.append(node.lineno)
    return found


def test_only_bootstrap_reads_the_settings_files() -> None:
    readers = {
        str(path.relative_to(_SRC)): lines
        for path in sorted(_SRC.rglob("*.py"))
        if _BOOTSTRAP not in path.parents and (lines := _reads(path.read_text(encoding="utf-8")))
    }

    assert readers == {}


def test_a_name_in_a_message_is_not_a_read() -> None:
    assert _reads('print("Raise the limit in settings.toml")\nlabel = "keys.env"\n') == []


def test_a_planted_reader_is_caught() -> None:
    planted = 'text = (root / "settings.toml").read_text()\nkeys = open("keys.env").read()\n'

    assert _reads(planted) == [1, 2]
