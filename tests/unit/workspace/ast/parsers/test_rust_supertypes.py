# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Rust reports what a type implements and what a trait extends.

Proves: TECH-068 FR-4

Rust shipped `TYPE_DECLARATION_NODES = ()` and returned `{}`, so the contract test looped over an
empty dict and the gap read as a pass. Unlike Kotlin, Rust's grammar separates the two kinds
cleanly, so nothing here has to be collapsed into one bucket:

* `impl Trait for Type` — the TYPE implements the TRAIT. Unambiguous.
* `trait A: B` — `A` extends `B`, a supertrait bound.
* `impl Type { ... }` — an inherent block. No relationship at all.

Two shapes make Rust unlike every other language here. The subject of an `impl` is the identifier
AFTER `for`, so the shared `_declared_type_name` — which takes the first — would key every entry
under the trait instead of the type. And one type is spread over several nodes: `struct Impl;` and
`impl Runner for Impl` both name `Impl`, so the base method has to merge rather than overwrite.
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure


@pytest.fixture(scope="module")
def rust() -> RustCodeStructure:
    return RustCodeStructure()


class TestRustCodeStructureImplBlocks:
    def test_impl_trait_for_type_is_an_implementation(self, rust: RustCodeStructure) -> None:
        """Happy path, keyed on the TYPE — the thing that gained the behaviour."""
        code = "struct Impl;\ntrait Runner {}\nimpl Runner for Impl {}\n"

        assert rust.extract_supertypes(code)["Impl"]["implements"] == ["Runner"]

    def test_the_trait_is_not_the_subject(self, rust: RustCodeStructure) -> None:
        """Boundary: the shared name-finder takes the FIRST identifier, which is the trait.

        Keyed that way the graph would say `Runner implements Runner`, which is both wrong and
        self-consistent enough to survive a careless review.
        """
        supertypes = rust.extract_supertypes(
            "struct Impl;\ntrait Runner {}\nimpl Runner for Impl {}\n"
        )

        assert supertypes.get("Runner", {}).get("implements") == []

    def test_an_inherent_impl_claims_nothing(self, rust: RustCodeStructure) -> None:
        """Boundary: `impl Impl { .. }` adds methods and no relationship."""
        code = "struct Impl;\nimpl Impl { fn helper(&self) {} }\n"

        assert rust.extract_supertypes(code)["Impl"] == {"extends": [], "implements": []}

    def test_several_traits_are_all_reported(self, rust: RustCodeStructure) -> None:
        """Boundary: one type, several impl blocks — they must accumulate, not overwrite."""
        code = "struct Impl;\ntrait A {}\ntrait B {}\nimpl A for Impl {}\nimpl B for Impl {}\n"

        assert sorted(rust.extract_supertypes(code)["Impl"]["implements"]) == ["A", "B"]

    def test_a_struct_and_its_impl_are_one_entry(self, rust: RustCodeStructure) -> None:
        """Boundary: `struct Impl;` and `impl A for Impl` name the same type in two nodes.

        The base walker assigns per node, so whichever it reached last used to win — and the walk
        order is not something the source controls.
        """
        code = "struct Impl;\ntrait A {}\nimpl A for Impl {}\n"

        entry = rust.extract_supertypes(code)["Impl"]
        assert entry["implements"] == ["A"]

    def test_a_generic_subject_names_the_base_type(self, rust: RustCodeStructure) -> None:
        """Boundary: `impl<T> A for Vec<T>` is about `Vec`. `T` is a parameter, not a type."""
        code = "trait A {}\nimpl<T> A for Vec<T> {}\n"

        assert rust.extract_supertypes(code)["Vec"]["implements"] == ["A"]

    def test_a_reference_subject_names_the_type_it_refers_to(self, rust: RustCodeStructure) -> None:
        """Boundary: `impl A for &Foo` is about `Foo`."""
        code = "trait A {}\nimpl A for &Foo {}\n"

        assert rust.extract_supertypes(code)["Foo"]["implements"] == ["A"]

    def test_a_scoped_trait_names_its_last_segment(self, rust: RustCodeStructure) -> None:
        """Boundary: `crate::mod::Tr` is `Tr`, because resolution indexes bare declared names.

        A full path could never match an index key and would ghost even when the trait is right
        there in the parsed set.
        """
        code = "struct Bar;\nimpl crate::traits::Tr for Bar {}\n"

        assert rust.extract_supertypes(code)["Bar"]["implements"] == ["Tr"]


class TestRustCodeStructureTraitBounds:
    def test_a_supertrait_is_an_extension(self, rust: RustCodeStructure) -> None:
        """Happy path: trait-to-trait really is extension, and Rust says so in syntax."""
        code = "trait Runner {}\ntrait Super: Runner {}\n"

        assert rust.extract_supertypes(code)["Super"]["extends"] == ["Runner"]

    def test_several_bounds_are_all_reported(self, rust: RustCodeStructure) -> None:
        code = "trait A {}\ntrait B {}\ntrait C: A + B {}\n"

        assert sorted(rust.extract_supertypes(code)["C"]["extends"]) == ["A", "B"]

    def test_a_plain_trait_extends_nothing(self, rust: RustCodeStructure) -> None:
        """Boundary: the control."""
        assert rust.extract_supertypes("trait Alone {}\n")["Alone"]["extends"] == []


class TestRustCodeStructureDegradation:
    def test_every_declared_type_appears(self, rust: RustCodeStructure) -> None:
        """Boundary: the adapter reads these keys to tell a type from a procedure."""
        code = "struct S;\nenum E { A }\ntrait T {}\n"

        assert {"S", "E", "T"} <= set(rust.extract_supertypes(code))

    def test_source_that_does_not_parse_reports_nothing(self, rust: RustCodeStructure) -> None:
        """Graceful degradation: one bad file must not take a build down."""
        assert rust.extract_supertypes("fn ((( not rust") == {}

    def test_empty_source_reports_nothing(self, rust: RustCodeStructure) -> None:
        assert rust.extract_supertypes("") == {}

    def test_hostile_input_does_not_raise(self, rust: RustCodeStructure) -> None:
        """Hostile: text that is not Rust and never claimed to be."""
        assert isinstance(rust.extract_supertypes("\x00\x01 ../../etc/passwd {{{"), dict)


class TestRustCodeStructureReportsTraitsAsSymbols:
    """A trait is a declared type, so it is a symbol like any other.

    Proves: TECH-068 FR-9, FR-10

    `SCM_SYMBOL_QUERY` matched `struct_item`, `impl_item` and `function_item` and no trait, so a
    trait was invisible to everything downstream: no symbol, no child at the seam, no node in the
    graph. Rust has no struct inheritance, so **every** Rust hierarchy edge targets a trait — which
    made `FR-9` deliver literally nothing for the language. `trait Derived: Base` emitted no edge at
    all, not even a ghost, because `Derived` was not a symbol for `_map_supertypes` to run on.
    """

    def test_a_trait_is_a_symbol(self, rust: RustCodeStructure) -> None:
        """Happy path: without this there is no node for anything to point at."""
        assert "Runner" in rust.list_symbols("pub trait Runner {\n    fn go(&self);\n}\n")

    def test_a_supertrait_and_its_base_are_both_symbols(self, rust: RustCodeStructure) -> None:
        """Happy path: both ends of a trait hierarchy, or the edge still cannot resolve."""
        symbols = rust.list_symbols("trait Base {}\ntrait Derived: Base {}\n")

        assert {"Base", "Derived"} <= set(symbols), symbols

    def test_structs_and_functions_are_still_symbols(self, rust: RustCodeStructure) -> None:
        """The control. Adding a pattern must not cost the ones that were already matching.

        `list_symbols` feeds skeleton extraction and symbol editing as well as the graph, so a
        regression here reaches well past this ticket.
        """
        code = "struct Impl;\nfn helper() {}\nimpl Impl { fn method(&self) {} }\n"

        symbols = rust.list_symbols(code)

        assert "Impl" in symbols
        assert "helper" in symbols
        assert any(s.endswith("method") for s in symbols), symbols

    def test_a_trait_reports_its_own_supertypes_under_its_own_name(
        self, rust: RustCodeStructure
    ) -> None:
        """Boundary: the symbol and the supertype entry must agree on the name, or they never meet.

        `extract_supertypes` keys on the declared name and `list_symbols` produces the child the
        seam carries. A mismatch leaves both halves passing their own tests while the edge is built
        against a name no node has.
        """
        code = "trait Base {}\ntrait Derived: Base {}\n"

        assert "Derived" in rust.list_symbols(code)
        assert rust.extract_supertypes(code)["Derived"]["extends"] == ["Base"]
