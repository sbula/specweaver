# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The run builder raises; only a door exits or answers HTTP.

Proves: TECH-077 NFR-3

| Bucket | Case |
|---|---|
| Happy | the builder module imports no CLI framework and raises no exit |
| Boundary | not applicable — one module is scanned |
| Degradation | not applicable — the source is read, nothing runs |
| Hostile | a planted `typer` import or `SystemExit` is found by the scan |
"""

from __future__ import annotations

import ast
from pathlib import Path

_BUILDER = (
    Path(__file__).resolve().parents[4]
    / "src"
    / "specweaver"
    / "interfaces"
    / "run_setup"
    / "builder.py"
)


def _exits(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
            found += [n for n in names if n.split(".")[0] in {"typer", "click", "fastapi"}]
        if isinstance(node, ast.Name) and node.id in {"SystemExit", "exit"}:
            found.append(node.id)
    return found


def test_the_builder_never_exits() -> None:
    assert _exits(_BUILDER.read_text(encoding="utf-8")) == []


def test_a_planted_exit_is_found() -> None:
    assert _exits("import typer\nraise SystemExit(1)\n") == ["typer", "SystemExit"]
