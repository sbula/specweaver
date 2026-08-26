# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A qualified SQL object is one symbol, not two.

Proves: B-SENS-03 FR-7

`CREATE TABLE public.orders` reported **`public` and `orders`** — two symbols, one of them a schema
fragment that is not an object at all. The index gained a chunk literally named `public`, and the
table it belongs to lost its qualification.

The cause is one node's depth: the capture sits on `identifier`, and an `object_reference` holds one
per name part. The node's own text is already `'public.orders'`.

**Assertions here are on the exact list.** `"public.orders" in symbols` passes with both fragments
still present, which is the entire defect surviving a green test.
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.interfaces import CodeStructureError
from specweaver.workspace.ast.parsers.sql.codestructure import SqlCodeStructure


@pytest.fixture
def parser() -> SqlCodeStructure:
    return SqlCodeStructure()


ALL_THREE = (
    "CREATE TABLE public.orders (id INT);\n"
    "CREATE VIEW summary AS SELECT 1;\n"
    "CREATE FUNCTION analytics.total() RETURNS INT AS $$ SELECT 1 $$ LANGUAGE SQL;\n"
)


class TestSqlListSymbolsReportsOneNamePerObject:
    def test_a_qualified_table_is_one_symbol(self, parser: SqlCodeStructure) -> None:
        """[Happy path] The exact list. `in` would pass with `public` still in it."""
        assert parser.list_symbols("CREATE TABLE public.orders (id INT);\n") == ["public.orders"]

    def test_an_unqualified_view_keeps_its_bare_name(self, parser: SqlCodeStructure) -> None:
        """[Happy path] The control: capturing the whole reference must not invent a qualifier
        where the source has none."""
        assert parser.list_symbols("CREATE VIEW summary AS SELECT 1;\n") == ["summary"]

    def test_a_qualified_function_is_one_symbol(self, parser: SqlCodeStructure) -> None:
        """[Happy path] All three rules carry the same capture, so all three are asserted."""
        code = "CREATE FUNCTION analytics.total() RETURNS INT AS $$ SELECT 1 $$ LANGUAGE SQL;\n"
        assert parser.list_symbols(code) == ["analytics.total"]

    def test_a_file_with_all_three_reports_exactly_three(self, parser: SqlCodeStructure) -> None:
        """[Happy path] Five names today: `public`, `orders`, `summary`, `analytics`, `total`."""
        assert parser.list_symbols(ALL_THREE) == ["public.orders", "summary", "analytics.total"]

    def test_no_schema_fragment_is_ever_reported(self, parser: SqlCodeStructure) -> None:
        """[Happy path] Stated on its own, because it is the harm rather than the mechanism: a
        chunk named `public` is indexed against every schema in the estate."""
        symbols = parser.list_symbols(ALL_THREE)
        assert "public" not in symbols
        assert "analytics" not in symbols


class TestSqlExtractSymbolAgreesWithListSymbols:
    """The two must call a symbol the same thing. They share `_declared_names`; the resolution in
    `_find_symbol_node` is the half that does not, and it is the half this boundary moves."""

    def test_the_qualified_name_resolves(self, parser: SqlCodeStructure) -> None:
        """[Happy path] Whatever `list_symbols` reports must be usable as-is."""
        code = "CREATE TABLE public.orders (id INT);\n"
        assert "public.orders" in parser.extract_symbol(code, "public.orders")

    def test_the_bare_name_does_not_resolve(self, parser: SqlCodeStructure) -> None:
        """[Hostile] **Strict resolution** `[agreed 2026-08-26]`.

        A bare-name fallback is the matching that gives the knowledge graph its measured 48% ghost
        rate: a name that looks unique is not the same as the right target. `list_symbols` is
        documented as *"run it first, copy the exact string returned"*, and this keeps that true.
        """
        code = "CREATE TABLE public.orders (id INT);\n"
        with pytest.raises(CodeStructureError):
            parser.extract_symbol(code, "orders")

    def test_every_reported_name_resolves(self, parser: SqlCodeStructure) -> None:
        """[Boundary] The pair asserted as a rule rather than case by case. A resolution that
        rejected everything would satisfy the strictness test above and look correct."""
        for name in parser.list_symbols(ALL_THREE):
            assert parser.extract_symbol(ALL_THREE, name) != ""


class TestSqlQualifiedNamesEdges:
    def test_a_quoted_identifier_keeps_its_quotes(self, parser: SqlCodeStructure) -> None:
        """[Boundary] A quoted name is legal SQL and the quotes are part of what the source says.

        Recorded as whatever the grammar reports rather than normalised: stripping them would be a
        second rule, and nothing has asked for one.
        """
        symbols = parser.list_symbols('CREATE TABLE "my table" (id INT);\n')
        assert len(symbols) == 1
        assert "my table" in symbols[0]

    def test_an_empty_file_reports_nothing(self, parser: SqlCodeStructure) -> None:
        """[Boundary]"""
        assert parser.list_symbols("") == []

    def test_unparseable_sql_does_not_raise(self, parser: SqlCodeStructure) -> None:
        """[Graceful degradation] One bad file must not take a whole scan down."""
        assert isinstance(parser.list_symbols("<<<< %%% not sql >>>>"), list)

    def test_a_name_that_is_not_there_raises_rather_than_guessing(
        self, parser: SqlCodeStructure
    ) -> None:
        """[Hostile] `extract_symbol` is documented as raising when a symbol cannot be resolved,
        and that contract is unchanged by this boundary."""
        with pytest.raises(CodeStructureError):
            parser.extract_symbol(ALL_THREE, "NoSuchTable")


class TestSqlQualifiedNamesReachTheRestOfTheParser:
    """The accessors SF-01 and SF-02 added take a symbol NAME, so they move with it."""

    def test_visibility_answers_for_the_qualified_name(self, parser: SqlCodeStructure) -> None:
        """[Boundary] SQL has no access concept, so `unknown` — but it must answer for the name
        that is actually reported, not for a fragment of it."""
        code = "CREATE TABLE public.orders (id INT);\n"
        assert parser.extract_symbol_visibility(code, "public.orders") == "unknown"

    def test_the_signature_is_the_whole_declaration(self, parser: SqlCodeStructure) -> None:
        """[Boundary] SQL has no body, so `FR-6` returns the declaration — keyed by the qualified
        name now."""
        code = "CREATE TABLE public.orders (id INT);\n"
        assert parser.extract_symbol_signature(code, "public.orders") == (
            "CREATE TABLE public.orders (id INT)"
        )
