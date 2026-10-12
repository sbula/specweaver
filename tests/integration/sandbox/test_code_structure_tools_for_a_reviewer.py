# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a reviewing model gets from the code-structure tools, through the dispatcher a review builds.

Proves: D-SENS-02 FR-1
Proves: D-SENS-02 FR-2
Proves: D-SENS-02 FR-3
Proves: D-SENS-02 FR-4
Proves: D-SENS-02 FR-6
Proves: D-SENS-02 FR-7
Proves: D-SENS-02 NFR-1
Proves: D-SENS-02 NFR-2

Real files, real tree-sitter, `ToolDispatcher.create_standard_set` with `ast` — the way
`sw review` offers them.

| Bucket | Case |
|---|---|
| Happy | a skeleton, one symbol, one body, a symbol list — Python and Java |
| Boundary | `visibility: [public]` drops `_private` and `private` symbols |
| Degradation | a file with a syntax error still gives a skeleton; an unknown type says to use read_file |
| Hostile | a path outside the grants is refused |
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_PY = '''import math


class Calc:
    """Adds numbers."""

    def add(self, a: int, b: int) -> int:
        """Sum."""
        return a + b

    def _secret(self) -> int:
        return 42


def area(r: float) -> float:
    return math.pi * r * r
'''
_JAVA = 'package demo;\n\npublic class Hello {\n    public String hi() { return "hi"; }\n    private int hidden() { return 1; }\n}\n'


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calc.py").write_text(_PY, encoding="utf-8")
    (tmp_path / "src" / "Hello.java").write_text(_JAVA, encoding="utf-8")
    (tmp_path / "src" / "broken.py").write_text(
        "def ok() -> int:\n    return 1\n\ndef bad(:\n    pass\n"
    )
    (tmp_path / "src" / "notes.xyz").write_text("x", encoding="utf-8")
    return tmp_path


def _call(project: Path, name: str, **args: Any) -> dict[str, Any]:
    dispatcher = ToolDispatcher.create_standard_set(
        WorkspaceBoundary([project]), role="reviewer", allowed_tools=["ast"]
    )
    return asyncio.run(dispatcher.execute(name, args))


def test_a_skeleton_keeps_signatures_and_docstrings_only(project: Path) -> None:
    structure = _call(project, "read_file_structure", path="src/calc.py")["structure"]

    assert "def add(self, a: int, b: int) -> int:" in structure and '"""Sum."""' in structure
    assert "return" not in structure


def test_one_symbol_and_one_body(project: Path) -> None:
    assert _call(project, "read_symbol", path="src/calc.py", symbol_name="area") == {
        "symbol": "def area(r: float) -> float:\n    return math.pi * r * r"
    }
    body = _call(project, "read_symbol_body", path="src/calc.py", symbol_name="Calc.add")["body"]
    assert body.endswith("return a + b") and "def add" not in body


@pytest.mark.parametrize(
    ("path", "public"),
    [("src/calc.py", ["Calc", "Calc.add", "area"]), ("src/Hello.java", ["Hello", "Hello.hi"])],
)
def test_a_listing_filters_by_visibility(project: Path, path: str, public: list[str]) -> None:
    assert _call(project, "list_symbols", path=path, visibility=["public"]) == {"symbols": public}


def test_a_broken_file_still_gives_a_skeleton(project: Path) -> None:
    structure = _call(project, "read_file_structure", path="src/broken.py")["structure"]

    assert "def ok() -> int:" in structure


def test_an_unknown_file_type_says_to_use_read_file(project: Path) -> None:
    assert "use read_file" in _call(project, "read_file_structure", path="src/notes.xyz")["error"]


def test_a_path_outside_the_grants_is_refused(project: Path) -> None:
    assert "error" in _call(project, "read_file_structure", path="../outside.py")


def test_a_skeleton_is_fast(project: Path) -> None:
    started = time.perf_counter()
    _call(project, "read_file_structure", path="src/calc.py")

    assert time.perf_counter() - started < 0.5  # NFR-1 is 50 ms per file; this includes setup
