# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A real key reaches only tests marked `live`.

Proves: TECH-094 FR-10

`SPECWEAVER_LIVE_KEYS` is the one way a test gets a real key: `scripts/live.py` sets it for the
nightly run, and CI never does. A test file that reads it and is not marked `live` would run in a
plain `pytest`, and on a machine with keys it would call a real model.

| Bucket | Case |
|---|---|
| Happy | every test file naming `SPECWEAVER_LIVE_KEYS` carries the `live` marker |
| Boundary | a file whose module-level `pytestmark` is `live` counts as marked |
| Degradation | a file that names the variable only in prose (a docstring or comment) is ignored |
| Hostile | a planted unmarked file that reads the variable is caught |
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_TESTS = Path(__file__).resolve().parents[1]
_VARIABLE = "SPECWEAVER_LIVE_KEYS"


def _reads_live_keys(tree: ast.AST) -> bool:
    """Whether the code (not its prose) names the variable as a string."""
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
    }
    return any(
        isinstance(node, ast.Constant) and node.value == _VARIABLE and id(node) not in docstrings
        for node in ast.walk(tree)
    )


def _marked_live(tree: ast.AST) -> bool:
    """Whether `pytest.mark.live` appears as a marker anywhere in the file."""
    return any(
        isinstance(node, ast.Attribute)
        and node.attr == "live"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        for node in ast.walk(tree)
    )


def _unmarked_readers(source: str) -> bool:
    tree = ast.parse(source)
    return _reads_live_keys(tree) and not _marked_live(tree)


def test_every_reader_of_the_live_keys_is_a_live_test() -> None:
    offenders = [
        str(path.relative_to(_TESTS))
        for path in sorted(_TESTS.rglob("*.py"))
        if path.name != Path(__file__).name and _unmarked_readers(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def test_the_live_tests_that_read_it_exist() -> None:
    readers = [
        path
        for path in _TESTS.rglob("*.py")
        if path.name != Path(__file__).name
        and _reads_live_keys(ast.parse(path.read_text(encoding="utf-8")))
    ]

    assert len(readers) >= 4


@pytest.mark.parametrize(
    ("source", "caught"),
    [
        ('import os\nKEYS = os.environ["SPECWEAVER_LIVE_KEYS"]\n', True),
        (
            'import os, pytest\npytestmark = pytest.mark.live\nK = os.environ["SPECWEAVER_LIVE_KEYS"]\n',
            False,
        ),
        ('"""Reads SPECWEAVER_LIVE_KEYS? No."""\n# SPECWEAVER_LIVE_KEYS\nX = 1\n', False),
        (
            'import pytest\n@pytest.mark.live\ndef test_x():\n    return "SPECWEAVER_LIVE_KEYS"\n',
            False,
        ),
    ],
)
def test_the_rule_reads_code_not_prose(source: str, caught: bool) -> None:
    assert _unmarked_readers(source) is caught
