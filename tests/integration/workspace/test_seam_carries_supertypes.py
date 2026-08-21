# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The seam carries each type's supertypes, and says which kind each one is.

Proves: TECH-068 FR-6

`SF-02` declared `supertypes` on every child and left it empty, so this fills a field rather than
reshaping the payload — which is what `AD-1` bought and what lets `SF-04` land beside this without
either sub-feature moving the other's ground.

It stays a LIST for the same reason. A mapping of `{"extends": [...], "implements": [...]}` would
have changed the declared empty value's type, which is a reshape however small it looks. A list of
`{"name", "kind"}` records fills what was declared, and carries a third kind later without moving
anything again.

The tier is integration: the adapter's claim is about what the parsers give it.
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


def _supertypes_of(ast: dict, symbol: str) -> list[dict]:
    return next(c["supertypes"] for c in ast["children"] if c["name"] == symbol)


def test_java_carries_both_kinds_across_the_seam(tmp_path: Path) -> None:
    """Happy path: what the grammar separated must still be separate at the mapper."""
    ast = _seam(tmp_path, "Impl.java", "class Impl extends Base implements Runner {}")
    assert _supertypes_of(ast, "Impl") == [
        {"name": "Base", "kind": "extends"},
        {"name": "Runner", "kind": "implements"},
    ]


def test_kotlin_carries_extension_only(tmp_path: Path) -> None:
    """Graceful degradation: the decision not to guess has to survive the seam too."""
    ast = _seam(tmp_path, "Impl.kt", "class Impl : Base(), Runner {}")
    assert _supertypes_of(ast, "Impl") == [
        {"name": "Base", "kind": "extends"},
        {"name": "Runner", "kind": "extends"},
    ]


def test_a_class_with_no_supertypes_carries_an_empty_list(tmp_path: Path) -> None:
    """Boundary: the field stays declared, so absent and empty do not become the same thing."""
    ast = _seam(tmp_path, "Plain.java", "class Plain {}")
    assert _supertypes_of(ast, "Plain") == []


def test_a_function_carries_an_empty_list_not_a_missing_key(tmp_path: Path) -> None:
    """Boundary: only types have supertypes, and every child still declares the field."""
    ast = _seam(tmp_path, "m.py", "def f():\n    pass\n")
    assert _supertypes_of(ast, "f") == []


def test_a_file_that_cannot_be_read_has_no_children_and_does_not_raise(tmp_path: Path) -> None:
    """Hostile: the payload stays well-formed on the paths that return early."""
    trap = tmp_path / "trap.py"
    trap.mkdir()
    ast = extract_ast_dict(str(trap))
    assert ast["children"] == []
    assert ast["unparsed"] == "read"
