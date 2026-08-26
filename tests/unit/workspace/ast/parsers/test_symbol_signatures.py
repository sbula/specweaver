# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One symbol's contract: what it promises, and what it says about itself.

Proves: B-SENS-03 FR-6

`extract_skeleton` already produces this shape for a whole **file**. `FR-6` is the per-symbol form,
because a whole-file skeleton is a poor retrieval unit: for a 27,000-character file it is large and
vague, so it matches everything and discriminates nothing.

**These tests compose `FR-5` for real.** The description is not hand-built here. `FR-6` is `FR-5`
plus an elision, so a test that assembles the doc itself would prove the elision and mock the half
that was harder to get right — the dev skill's *"is this only ever used in sequence with something
else?"* question, answered yes.
"""

from __future__ import annotations

import typing

import pytest

from specweaver.workspace.ast.parsers.factory import get_default_parsers

from .test_visibility_vocabulary import _BY_CLASS


@pytest.fixture(scope="module")
def parsers() -> dict[str, typing.Any]:
    return {_BY_CLASS[type(p).__name__]: p for p in get_default_parsers().values()}


#: (source, symbol, expected). Description first, then the signature, and no body.
DOCUMENTED: dict[str, tuple[str, str, str]] = {
    "java": (
        "public class B {\n  /** Places an order. */\n  public int place(int a){ return a; }\n}\n",
        "B.place",
        "Places an order.\npublic int place(int a)",
    ),
    "kotlin": (
        "class B {\n  /** Places an order. */\n  fun place(a: Int): Int { return a }\n}\n",
        "B.place",
        "Places an order.\nfun place(a: Int): Int",
    ),
    "typescript": (
        "export class B {\n  /** Places an order. */\n  place(a: number): number { return a }\n}\n",
        "B.place",
        "Places an order.\nplace(a: number): number",
    ),
    "rust": (
        "pub struct B;\nimpl B {\n  /// Places an order.\n  pub fn place(&self, a: i32) -> i32 { a }\n}\n",
        "B.place",
        "Places an order.\npub fn place(&self, a: i32) -> i32",
    ),
    "go": (
        "package m\n// Places an order.\nfunc Place(a int) int { return a }\n",
        "Place",
        "Places an order.\nfunc Place(a int) int",
    ),
    "python": (
        'class B:\n    def place(self, a: int) -> int:\n        """Places an order."""\n        return a\n',
        "B.place",
        "Places an order.\ndef place(self, a: int) -> int:",
    ),
}


class TestExtractSymbolSignatureHappyPath:
    @pytest.mark.parametrize("lang", sorted(DOCUMENTED), ids=str)
    def test_a_documented_symbol_yields_its_description_and_signature(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Happy path] The whole claim, in one assertion, in six languages."""
        code, symbol, expected = DOCUMENTED[lang]
        assert parsers[lang].extract_symbol_signature(code, symbol) == expected

    @pytest.mark.parametrize("lang", sorted(DOCUMENTED), ids=str)
    def test_the_body_is_gone(self, parsers: dict[str, typing.Any], lang: str) -> None:
        """[Happy path] Stated separately and asserted as an ABSENCE, because that is the half a
        passing equality can hide: if the accessor returned `""` the equality above would be the
        only thing to catch it, and if it elided nothing this assertion would be."""
        code, symbol, _ = DOCUMENTED[lang]
        result = parsers[lang].extract_symbol_signature(code, symbol)
        assert "return a" not in result and result != ""

    @pytest.mark.parametrize("lang", sorted(DOCUMENTED), ids=str)
    def test_the_signature_itself_is_present(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Happy path] The paired control for the absence above. Both halves, or neither proves
        anything."""
        code, symbol, _ = DOCUMENTED[lang]
        assert "place" in parsers[lang].extract_symbol_signature(code, symbol).lower()


class TestExtractSymbolSignatureComposesTheDescription:
    def test_the_description_is_the_one_fr5_returns(self, parsers: dict[str, typing.Any]) -> None:
        """[Happy path] The composition, asserted rather than assumed.

        `FR-6` is `FR-5` plus an elision. Building the doc by hand here would leave the harder half
        untested — and the gap check, the marker stripping and the wrapper climb all live in that
        half.
        """
        code = (
            "public class B {\n"
            "  /**\n"
            "   * Places an order.\n"
            "   * Returns the venue id.\n"
            "   */\n"
            "  public int place(int a){ return a; }\n"
            "}\n"
        )
        doc = parsers["java"].extract_symbol_doc(code, "B.place")
        signature = parsers["java"].extract_symbol_signature(code, "B.place")
        assert doc == "Places an order.\nReturns the venue id."
        assert signature.startswith(doc)
        assert signature.endswith("public int place(int a)")

    def test_a_comment_that_does_not_attach_stays_out_of_the_signature(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Hostile] The gap rule reaches here too. A licence header must not end up prefixed to
        every first signature in the corpus."""
        code = (
            "package m\n"
            "\n"
            "// Copyright (c) 2026 sbula. All rights reserved.\n"
            "\n"
            "func Place(a int) int { return a }\n"
        )
        assert parsers["go"].extract_symbol_signature(code, "Place") == "func Place(a int) int"


class TestExtractSymbolSignatureEdges:
    def test_an_undocumented_symbol_yields_the_signature_alone(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Boundary] No description, and no blank line where one would have been."""
        code = "public class B {\n  public int place(int a){ return a; }\n}\n"
        assert (
            parsers["java"].extract_symbol_signature(code, "B.place") == "public int place(int a)"
        )

    def test_sql_has_no_body_so_the_declaration_is_the_signature(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Graceful degradation] `extract_symbol_body` RAISES for SQL — the declarative tier has
        no target block. `FR-6` is called once per symbol during a scan and must not raise, so the
        whole declaration is the answer rather than an error."""
        code = "CREATE TABLE public.orders (id INT);\n"
        assert (
            parsers["sql"].extract_symbol_signature(code, "public.orders")
            == "CREATE TABLE public.orders (id INT)"
        )

    def test_markdown_yields_its_heading_without_the_prose(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Boundary] A markdown section's body IS its prose, so eliding it leaves the heading."""
        result = parsers["markdown"].extract_symbol_signature("# Title\n\nSome prose.\n", "Title")
        assert "Some prose" not in result
        assert "Title" in result

    @pytest.mark.parametrize("lang", sorted(DOCUMENTED), ids=str)
    def test_a_type_yields_its_signature_without_its_members(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Boundary] The case SF-06's skeleton layer shows first. A class's body is its members,
        and a skeleton chunk that carried them would be the body chunk again."""
        code, symbol, _ = DOCUMENTED[lang]
        top = symbol.split(".")[0]
        result = parsers[lang].extract_symbol_signature(code, top)
        assert "return a" not in result

    @pytest.mark.parametrize("lang", ["java", "python", "go", "sql", "markdown"], ids=str)
    def test_a_name_that_is_not_there_yields_nothing(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Hostile] Answers rather than raises, for the same reason `FR-5` does."""
        assert parsers[lang].extract_symbol_signature("", "NoSuchSymbol") == ""

    @pytest.mark.parametrize("lang", ["java", "python", "go", "sql", "markdown"], ids=str)
    def test_unparseable_source_yields_nothing(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Graceful degradation] Never raises, whatever the file holds."""
        assert parsers[lang].extract_symbol_signature("<<<< %%% >>>>", "x") == ""
