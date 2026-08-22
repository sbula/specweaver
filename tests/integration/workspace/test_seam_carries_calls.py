# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The seam carries what each symbol calls, and what the file itself calls.

Proves: TECH-068 FR-7

`SF-02` declared `calls` on every child and left it empty, so this fills a field rather than
reshaping the payload — the last of the three `AD-1` set aside.

It also ADDS a file-level `calls`, which `AD-1` did not anticipate. Module-level code — a decorator
argument, a constant built by calling something — has no enclosing declaration and therefore no
child to hang on, yet it is a real dependency. A new key is additive: nothing that reads the payload
today breaks, unlike changing a declared field's type. `imports` is already file-scoped for the same
reason, so the shape stays symmetrical.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.workspace.ast.adapters.graph_adapter import extract_ast_dict

if TYPE_CHECKING:
    from pathlib import Path


def _seam(tmp_path: Path, name: str, body: str) -> dict:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return extract_ast_dict(str(path))


def _calls_of(ast: dict, symbol: str) -> list[str]:
    return next(c["calls"] for c in ast["children"] if c["name"] == symbol)


def test_a_functions_calls_reach_the_seam(tmp_path: Path) -> None:
    """Happy path."""
    ast = _seam(tmp_path, "m.py", "def a():\n    helper()\n")
    assert _calls_of(ast, "a") == ["helper"]


def test_a_methods_calls_arrive_under_its_qualified_name(tmp_path: Path) -> None:
    """The caller key must be the one the child carries, or the calls attach to nothing."""
    ast = _seam(tmp_path, "m.py", "class Impl:\n    def go(self):\n        helper()\n")
    assert _calls_of(ast, "Impl.go") == ["helper"]


def test_a_symbol_that_calls_nothing_carries_an_empty_list(tmp_path: Path) -> None:
    """Boundary: the field stays declared, so absent and empty stay different."""
    ast = _seam(tmp_path, "m.py", "def a():\n    pass\n")
    assert _calls_of(ast, "a") == []


def test_module_level_calls_are_carried_by_the_file(tmp_path: Path) -> None:
    """Boundary: no child owns them, and dropping them would lose a real dependency."""
    ast = _seam(tmp_path, "m.py", "VALUE = build()\n\ndef a():\n    pass\n")
    assert ast["calls"] == ["build"]


def test_a_language_with_no_call_concept_carries_empty_lists(tmp_path: Path) -> None:
    """Graceful degradation: the shape must not depend on the language.

    This named Kotlin until `SF-05` gave it a locally-held query. `sql` has no calls to find, so it
    keeps the property and the assertion stays about the shape rather than about one language.
    """
    ast = _seam(tmp_path, "m.sql", "SELECT 1;")
    assert ast["calls"] == []
    assert all(child["calls"] == [] for child in ast["children"])


def test_a_file_that_cannot_be_read_still_has_the_shape(tmp_path: Path) -> None:
    """Hostile: every early return keeps the payload well-formed."""
    trap = tmp_path / "trap.py"
    trap.mkdir()
    ast = extract_ast_dict(str(trap))
    assert ast["calls"] == []
    assert ast["children"] == []
