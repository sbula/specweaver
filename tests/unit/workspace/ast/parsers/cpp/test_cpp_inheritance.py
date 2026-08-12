# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C++ reports the base classes it inherits from (`TECH-034`).

`CppCodeStructure` extracted **no inheritance at all** — zero references to `_extract_bases` or
`base_class_clause` — while Java, Kotlin, Python and TypeScript all did. C++ obviously has
inheritance, so this was a capability gap, not a design decision, and `class D : public B` reported
no bases.

It stayed invisible because the single shared base class never asked for it. Introducing
`ClassBasedParser` made it impossible to miss: the parser stopped being instantiable at all until
the methods existed, which is the argument for the tier split stated as a test.
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.cpp.codestructure import CppCodeStructure


@pytest.fixture
def parser() -> CppCodeStructure:
    return CppCodeStructure()


def _markers(parser: CppCodeStructure, code: str) -> dict[str, dict[str, list[str]]]:
    return parser.extract_framework_markers(code)


def test_a_single_public_base_is_reported(parser: CppCodeStructure) -> None:
    markers = _markers(parser, "class Derived : public Base { public: int f(); };")

    assert markers.get("Derived", {}).get("extends") == ["Base"]


def test_every_base_in_a_multiple_inheritance_list_is_reported(parser: CppCodeStructure) -> None:
    """C++ allows several bases, which is exactly what a single-value field would have lost."""
    markers = _markers(parser, "class D : public A, private B, protected C { };")

    assert markers.get("D", {}).get("extends") == ["A", "B", "C"]


def test_access_specifiers_are_not_mistaken_for_base_names(parser: CppCodeStructure) -> None:
    """`public` / `private` / `protected` sit inside the clause as siblings of the type names.

    A naive walk over the clause's children collects them as bases, which is the obvious way to
    get this wrong.
    """
    markers = _markers(parser, "class D : public A { };")
    extends = markers.get("D", {}).get("extends", [])

    assert "public" not in extends
    assert extends == ["A"]


def test_a_struct_reports_its_bases_too(parser: CppCodeStructure) -> None:
    """`struct` is a class with different default access, and inherits the same way."""
    markers = _markers(parser, "struct S : public Base { };")

    assert markers.get("S", {}).get("extends") == ["Base"]


def test_a_class_without_bases_reports_an_empty_list(parser: CppCodeStructure) -> None:
    """The control: absent inheritance must read as "none", not as "not supported".

    Without this, a fix that always returned `[]` would pass every test above that asserts a
    non-empty result and still be wrong in the same way as before.
    """
    markers = _markers(parser, "class Standalone { public: int f(); };")

    assert markers.get("Standalone", {}).get("extends") == []
