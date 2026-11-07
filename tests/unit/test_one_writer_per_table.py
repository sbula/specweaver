# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`flow_artifact_events` has one writer, `graph.lineage`'s `LineageRepository`.

Proves: TECH-090 FR-14
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "specweaver"
_WRITER = _SRC / "graph" / "lineage" / "store" / "lineage_repository.py"
_MODEL = _SRC / "core" / "flow" / "store.py"


def _files_naming_the_table() -> set[Path]:
    return {
        p for p in _SRC.rglob("*.py") if "flow_artifact_events" in p.read_text(encoding="utf-8")
    }


def _classes_defining(method: str) -> list[str]:
    found = []
    for path in sorted(_SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method
                for item in node.body
            ):
                found.append(f"{path.relative_to(_SRC)}:{node.name}")
    return found


def test_only_the_writer_and_the_model_name_the_table() -> None:
    assert _files_naming_the_table() == {_WRITER, _MODEL}


def test_only_one_class_logs_an_artifact_event() -> None:
    assert _classes_defining("log_artifact_event") == [
        "graph/lineage/store/lineage_repository.py:LineageRepository"
    ]
