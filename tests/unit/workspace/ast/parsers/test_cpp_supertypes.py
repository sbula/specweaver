# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C++ declares base classes, so the graph reports them.

Proves: TECH-068 FR-4

`SF-03` gave `extract_supertypes` to python, java, kotlin and typescript and left C++ returning `{}`,
so `TECH-068` would have closed with a language whose inheritance it said it covered and did not.
`SF-05` opens this file for the call query anyway, which is why the gap closes on contact rather
than becoming a ticket.

Two shapes, not one: `class Impl : ...` is a `class_specifier` and `struct S : ...` is a
`struct_specifier`, and both carry `base_class_clause`. Declaring only the first would silently
cover half the language.

C++ has no interfaces, so every base is extension — the same answer as Python and Kotlin, for a
different reason.
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.factory import get_default_parsers


def _cpp() -> object:
    return next(p for exts, p in get_default_parsers().items() if ".cpp" in exts)


def test_a_class_reports_its_base() -> None:
    """Happy path."""
    assert _cpp().extract_supertypes("class Impl : public Base {};")["Impl"] == {
        "extends": ["Base"],
        "implements": [],
    }


def test_a_struct_reports_its_base() -> None:
    """Boundary: the second of two top nodes, which a one-node implementation would miss."""
    assert _cpp().extract_supertypes("struct S : public Base {};")["S"] == {
        "extends": ["Base"],
        "implements": [],
    }


def test_multiple_inheritance_reports_every_base() -> None:
    """Boundary: one clause, several bases."""
    result = _cpp().extract_supertypes("struct S : private A, public B {};")
    assert result["S"]["extends"] == ["A", "B"]


def test_an_access_specifier_is_never_a_base() -> None:
    """Hostile: `public` is a keyword, and a supertype called `public` would be nonsense.

    Verified rather than assumed — `access_specifier` is its own node type, so a walk that captured
    every identifier would report it and nothing downstream could tell.
    """
    result = _cpp().extract_supertypes("class Impl : private Base {};")
    assert "private" not in result["Impl"]["extends"]
    assert "public" not in result["Impl"]["extends"]


def test_a_class_with_no_base_reports_empty_lists() -> None:
    """Graceful degradation: absent and empty stay different."""
    assert _cpp().extract_supertypes("class Plain {};")["Plain"] == {
        "extends": [],
        "implements": [],
    }


def test_empty_source_reports_nothing() -> None:
    assert _cpp().extract_supertypes("") == {}
