# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the C++ parser reads reaches the mapper, both kinds of dependency.

Proves: TECH-068 FR-3, FR-4

The parser's own tests prove it reads a base class and a call site. This proves the adapter carries
them, which is a different claim and the one a consumer actually depends on — `SF-01` exists because
a seam quietly dropped what the layer beneath it had already extracted.

C++ is worth its own file rather than the set-level sweep: it is the only language whose supertypes
were added after the seam was built, so it is the one where the two halves could most easily have
been wired to different expectations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.workspace.ast.adapters.graph_adapter import extract_ast_dict

if TYPE_CHECKING:
    from pathlib import Path


def _seam(tmp_path: Path, body: str) -> dict:
    path = tmp_path / "unit.cpp"
    path.write_text(body, encoding="utf-8")
    return extract_ast_dict(str(path))


def test_a_base_class_reaches_the_seam(tmp_path: Path) -> None:
    """Happy path: the supertype the parser read is the one the mapper receives."""
    ast = _seam(tmp_path, "class Impl : public Base { void go() { helper(); } };")
    impl = next(c for c in ast["children"] if c["name"] == "Impl")
    assert impl["supertypes"] == [{"name": "Base", "kind": "extends"}]


def test_a_call_reaches_the_seam_under_its_qualified_caller(tmp_path: Path) -> None:
    """Happy path: and the caller is the name the node carries, not the enclosing class."""
    ast = _seam(tmp_path, "class Impl : public Base { void go() { helper(); } };")
    go = next(c for c in ast["children"] if c["name"] == "Impl.go")
    assert go["calls"] == ["helper"]


def test_a_struct_base_reaches_the_seam(tmp_path: Path) -> None:
    """Boundary: the second top node, which the parser tests pin and the seam must not lose."""
    ast = _seam(tmp_path, "struct S : public Base { };")
    assert next(c for c in ast["children"] if c["name"] == "S")["supertypes"] == [
        {"name": "Base", "kind": "extends"}
    ]


def test_a_file_with_neither_carries_empty_fields(tmp_path: Path) -> None:
    """Graceful degradation: the shape holds when there is nothing to report."""
    ast = _seam(tmp_path, "class Plain { };")
    plain = next(c for c in ast["children"] if c["name"] == "Plain")
    assert plain["supertypes"] == []
    assert plain["calls"] == []
