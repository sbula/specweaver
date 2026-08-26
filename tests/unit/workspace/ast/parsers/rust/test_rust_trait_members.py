# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A Rust trait's members are symbols, and they carry the trait's name.

Proves: B-SENS-03 FR-18

`pub trait Shape { fn area(&self) -> f64; fn name(&self) -> f64 {1.0} }` reported
`['Shape', 'name']`. Two independent defects, both measured 2026-08-26:

1. A **required** method is a `function_signature_item`, and the symbol query named only
   `function_item`. The part of a trait that IS the contract was invisible to everything
   downstream — no symbol, no chunk, no node in the graph.
2. `_get_symbol_scope` walked up for `impl_item` and nothing else, so a **defaulted** method
   arrived as `name` rather than `Shape.name` — a bare identifier colliding with every other `name`
   in the estate.

**Two causes need two assertions.** Fixing only the query gives `Shape.area` unscoped; fixing only
the scope leaves it missing. One test would let either half pass alone.
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure

TRAIT = "pub trait Shape {\n    fn area(&self) -> f64;\n    fn name(&self) -> f64 { 1.0 }\n}\n"


@pytest.fixture
def parser() -> RustCodeStructure:
    return RustCodeStructure()


class TestListSymbolsReportsRustTraitMembers:
    def test_a_required_method_is_a_symbol(self, parser: RustCodeStructure) -> None:
        """[Happy path] Cause 1. `fn area(&self) -> f64;` is a `function_signature_item` and was in
        no query, so it did not exist as far as the rest of the system was concerned."""
        assert "Shape.area" in parser.list_symbols(TRAIT)

    def test_a_defaulted_method_carries_the_traits_name(self, parser: RustCodeStructure) -> None:
        """[Happy path] Cause 2. It was reported, as the bare name `name`."""
        assert "Shape.name" in parser.list_symbols(TRAIT)

    def test_the_bare_name_is_gone(self, parser: RustCodeStructure) -> None:
        """[Happy path] Stated as an absence, because adding a scoped name while ALSO still
        reporting the unscoped one would satisfy the test above and index the method twice."""
        assert "name" not in parser.list_symbols(TRAIT)

    def test_the_exact_list(self, parser: RustCodeStructure) -> None:
        """[Happy path] All of it at once, so neither half can pass while the other is broken."""
        assert parser.list_symbols(TRAIT) == ["Shape", "Shape.area", "Shape.name"]


class TestExtractSymbolResolvesRustTraitMembers:
    """A reported name that nothing can look up is a name in a list, not a symbol."""

    def test_a_required_method_resolves(self, parser: RustCodeStructure) -> None:
        """[Boundary] `_process_symbol_match` was written when only `function_item` could carry a
        scope, so resolution had to move with the query rather than after it."""
        assert "area" in parser.extract_symbol(TRAIT, "Shape.area")

    def test_every_reported_name_resolves(self, parser: RustCodeStructure) -> None:
        """[Boundary] The rule rather than the case."""
        for name in parser.list_symbols(TRAIT):
            assert parser.extract_symbol(TRAIT, name) != ""

    def test_a_trait_member_is_public(self, parser: RustCodeStructure) -> None:
        """[Boundary] SF-01's rule, on nodes SF-01 never saw: a trait member carries no
        `visibility_modifier` of its own and takes the trait's."""
        assert parser.extract_symbol_visibility(TRAIT, "Shape.area") == "public"
        assert parser.extract_symbol_visibility(TRAIT, "Shape.name") == "public"

    def test_a_required_method_yields_its_description(self, parser: RustCodeStructure) -> None:
        """[Boundary] SF-02's rule, likewise. A signature item's parent is a `declaration_list` on a
        different row, so the climb stops and the previous sibling is the doc."""
        code = "pub trait Shape {\n    /// The area.\n    fn area(&self) -> f64;\n}\n"
        assert parser.extract_symbol_doc(code, "Shape.area") == "The area."


class TestGetSymbolScopeStillPrefersTheImplType:
    """The scope walk gained a branch. The one it had must keep working."""

    def test_an_impl_method_still_carries_the_type_name(self, parser: RustCodeStructure) -> None:
        """[Boundary] The regression this change could most easily cause."""
        code = "pub struct C;\nimpl C {\n    pub fn go(&self) -> i32 { 1 }\n}\n"
        assert parser.list_symbols(code) == ["C", "C.go"]

    def test_a_trait_impl_scopes_to_the_type_not_the_trait(self, parser: RustCodeStructure) -> None:
        """[Hostile] `impl Shape for C` has BOTH a trait and a type in scope. The method belongs to
        the type — a walk that stopped at the first `trait_item` OR `impl_item` it met without
        caring which would get this backwards."""
        code = "pub trait Shape { fn area(&self) -> f64; }\npub struct C;\nimpl Shape for C {\n    fn area(&self) -> f64 { 1.0 }\n}\n"
        symbols = parser.list_symbols(code)
        assert "C.area" in symbols
        assert "Shape.area" in symbols

    def test_a_free_function_has_no_scope(self, parser: RustCodeStructure) -> None:
        """[Boundary] Neither branch may fire for a function at module level."""
        assert parser.list_symbols("pub fn free() -> i32 { 1 }\n") == ["free"]


class TestListSymbolsOnRustTraitEdges:
    def test_an_empty_trait_reports_only_itself(self, parser: RustCodeStructure) -> None:
        """[Boundary]"""
        assert parser.list_symbols("pub trait Empty {}\n") == ["Empty"]

    def test_a_private_trait_still_reports_its_members(self, parser: RustCodeStructure) -> None:
        """[Boundary] Visibility is a separate question from existence. The members are reported;
        `FR-1` decides what level they carry."""
        code = "trait Hidden {\n    fn x(&self) -> i32;\n}\n"
        assert parser.list_symbols(code) == ["Hidden", "Hidden.x"]

    def test_unparseable_rust_does_not_raise(self, parser: RustCodeStructure) -> None:
        """[Graceful degradation]"""
        assert isinstance(parser.list_symbols("<<<< %%% >>>>"), list)
