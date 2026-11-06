# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""File endings live in one table: `commons/languages.py`; no other module writes its own.

Proves: TECH-079 FR-12

| Bucket | Case |
|---|---|
| Happy | each language's main ending is its first; `.cts` and `.mts` are TypeScript |
| Boundary | the main ending of a language with no generator is still its first |
| Degradation | a language the table does not know has no main ending: refused, naming it |
| Hostile | a module outside `commons` that writes `.tsx` (or any table-only ending) as a string fails the guard; prose that mentions it does not |
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from specweaver.commons.languages import LANGUAGE_SUFFIXES, language_of, main_suffix

_SRC = Path(__file__).resolve().parents[3] / "src" / "specweaver"
#: Endings only a language table needs; a module writing one is keeping its own table.
_TABLE_ONLY = {".pyi", ".kts", ".tsx", ".jsx", ".mjs", ".cjs", ".hpp", ".cc", ".cxx"}


@pytest.mark.parametrize(
    ("language", "suffix"),
    [
        ("python", ".py"),
        ("java", ".java"),
        ("kotlin", ".kt"),
        ("typescript", ".ts"),
        ("rust", ".rs"),
        ("cpp", ".cpp"),
    ],
)
def test_the_main_ending_is_the_first(language: str, suffix: str) -> None:
    assert main_suffix(language) == suffix


def test_an_unknown_language_has_no_main_ending() -> None:
    with pytest.raises(ValueError, match="cobol"):
        main_suffix("cobol")


@pytest.mark.parametrize("name", ["a.cts", "B.MTS"])
def test_cts_and_mts_are_typescript(name: str) -> None:
    assert language_of(name) == "typescript"
    assert {".cts", ".mts"} <= set(LANGUAGE_SUFFIXES["typescript"])


def _table_literals(source: str) -> list[str]:
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and node.value in _TABLE_ONLY
        and id(node) not in docstrings
    ]


def test_the_guard_reads_strings_not_prose() -> None:
    assert _table_literals('"""Reads .tsx too."""\nX = (".tsx",)\n# .jsx\n') == [".tsx"]


def test_no_module_outside_commons_keeps_its_own_ending_table() -> None:
    found = {
        str(path.relative_to(_SRC)): literals
        for path in sorted(_SRC.rglob("*.py"))
        if "commons" not in path.relative_to(_SRC).parts
        and (literals := _table_literals(path.read_text(encoding="utf-8")))
    }

    assert found == {}
