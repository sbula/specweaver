# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Kotlin's call query is positional, so the shapes it must match are pinned here.

Proves: TECH-068 FR-3

`tree-sitter-kotlin` 1.1.0 ships no `.scm` of any kind, and its `call_expression` exposes **no field
names** — `field_name_for_child` returns `None` for both children. Every other language in this
ticket addresses the callee by field, so its pattern states what it means and a grammar change that
moved the callee would fail loudly. Kotlin's cannot: it matches by position, so the same change
would quietly yield a thinner graph.

This file is the mitigation. Each shape below is written out so that breakage surfaces as a red
rather than as silence. It is not redundant with the other languages' tests — it is the reason this
sub-feature has its own boundary.

The naive pattern is wrong, and measurably so: `(navigation_expression (identifier) @name)` captures
BOTH `obj` and `deep` from `obj.deep()`, because the receiver is an identifier too. Constraining it
to an identifier that follows something is what separates the call from the thing it was called on.
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.factory import get_default_parsers


def _kotlin() -> object:
    return next(p for exts, p in get_default_parsers().items() if ".kt" in exts)


class TestKotlinCallSites:
    def test_a_plain_call_inside_a_method(self) -> None:
        """Happy path, with the caller qualified."""
        code = "class K { fun go() { helper() } }"
        assert _kotlin().extract_call_sites(code) == {"K.go": ["helper"]}

    def test_a_top_level_call(self) -> None:
        """Boundary: no enclosing class."""
        assert _kotlin().extract_call_sites("fun top() { x() }") == {"top": ["x"]}

    def test_a_call_on_this(self) -> None:
        """Boundary: the receiver is a `this_expression`, not an identifier."""
        code = "class K { fun go() { this.other() } }"
        assert _kotlin().extract_call_sites(code) == {"K.go": ["other"]}

    def test_a_call_on_an_object_reports_the_method_not_the_receiver(self) -> None:
        """Hostile: the naive positional pattern reports `obj` here. That is the whole risk."""
        code = "class K { fun go() { obj.deep() } }"
        assert _kotlin().extract_call_sites(code) == {"K.go": ["deep"]}

    def test_a_chained_call_reports_only_the_called_name(self) -> None:
        """Hostile: `a.b.c()` is a call to `c`; `a` and `b` are not calls."""
        code = "class K { fun go() { a.b.c() } }"
        assert _kotlin().extract_call_sites(code) == {"K.go": ["c"]}

    def test_arguments_are_not_calls(self) -> None:
        """Hostile: `build(x, y)` calls `build`. Arguments live under `value_arguments`."""
        code = "class K { fun go() { build(x, y) } }"
        assert _kotlin().extract_call_sites(code) == {"K.go": ["build"]}

    def test_a_file_with_no_calls_reports_nothing(self) -> None:
        """Graceful degradation."""
        assert _kotlin().extract_call_sites("class K { fun go() { } }") == {}

    def test_empty_source_reports_nothing(self) -> None:
        assert _kotlin().extract_call_sites("") == {}
