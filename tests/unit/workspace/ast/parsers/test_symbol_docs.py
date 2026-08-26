# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The description attached to one symbol, in every language that has one.

Proves: B-SENS-03 FR-5

`extract_symbol` drops the doc comment in every language but Python, which passes only by accident:
a docstring lives *inside* the body, so extracting the body takes it along. Everywhere else the
comment sits above the declaration and was thrown away, which is why "signature plus description"
did not work for the language it was designed around.

**`SCM_COMMENT_QUERY` cannot answer this.** It returns every comment in a file with no relation to
any declaration — the right shape for `extract_traceability_tags` and the wrong one here. What this
needs is *attachment*, and attachment is a position in the tree plus a line gap.

The expected values below are the requirement, not a measurement: this file is written before the
accessor exists and fails on attribute lookup until it does.
"""

from __future__ import annotations

import typing

import pytest

from specweaver.workspace.ast.parsers.factory import get_default_parsers

from .test_visibility_vocabulary import _BY_CLASS


@pytest.fixture(scope="module")
def parsers() -> dict[str, typing.Any]:
    return {_BY_CLASS[type(p).__name__]: p for p in get_default_parsers().values()}


#: (source, symbol, expected description). One documented symbol per language.
DOCUMENTED: dict[str, tuple[str, str, str]] = {
    "java": (
        "public class B {\n  /** Places an order. */\n  public int place(){return 1;}\n}\n",
        "B.place",
        "Places an order.",
    ),
    "kotlin": (
        "class B {\n  /** Places an order. */\n  fun place()=1\n}\n",
        "B.place",
        "Places an order.",
    ),
    "typescript": (
        "export class B {\n  /** Places an order. */\n  place(){return 1}\n}\n",
        "B.place",
        "Places an order.",
    ),
    "rust": (
        "pub struct B;\nimpl B {\n  /// Places an order.\n  pub fn place(&self)->i32{1}\n}\n",
        "B.place",
        "Places an order.",
    ),
    "go": (
        "package m\n// Places an order.\nfunc Place() int {return 1}\n",
        "Place",
        "Places an order.",
    ),
    "python": (
        'class B:\n    def place(self):\n        """Places an order."""\n        return 1\n',
        "B.place",
        "Places an order.",
    ),
    # C and C++ sit one level deeper: `name_node.parent` is a `function_declarator`, and the
    # comment precedes the enclosing `function_definition`.
    "c": ("/** Places an order. */\nint place(void){return 1;}\n", "place", "Places an order."),
    "cpp": (
        "class B {\npublic:\n  /** Places an order. */\n  int place(){return 1;}\n};\n",
        "B.place",
        "Places an order.",
    ),
}

#: Languages with no doc-comment concept at all. SQL's `SCM_COMMENT_QUERY` is empty; markdown's
#: captures `html_block`, which is not a comment node by any reading.
NO_DOC_CONCEPT: dict[str, tuple[str, str]] = {
    # `public.orders`, not `orders`. Keyed on the bare name this asserted `""` for a symbol
    # that does not exist -- true, and nothing to do with SQL having no doc-comment concept.
    "sql": ("CREATE TABLE public.orders (id INT);\n", "public.orders"),
    "markdown": ("# Title\n\nSome prose.\n", "Title"),
}


class TestExtractSymbolDocHappyPath:
    @pytest.mark.parametrize("lang", sorted(DOCUMENTED), ids=str)
    def test_a_documented_symbol_yields_its_description(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Happy path] Marker-free, in all eight languages that have the concept."""
        code, symbol, expected = DOCUMENTED[lang]
        assert parsers[lang].extract_symbol_doc(code, symbol) == expected

    def test_stacked_line_comments_are_returned_whole_and_in_order(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Happy path] `///` lines arrive as SEPARATE siblings.

        Taking only the nearest would return the last line of a doc block and silently drop the
        rest — a description that reads as a fragment and gives no sign it was truncated.
        """
        code = "pub struct B;\nimpl B {\n  /// Places an order.\n  /// Returns the venue id.\n  pub fn place(&self)->i32{1}\n}\n"
        assert (
            parsers["rust"].extract_symbol_doc(code, "B.place")
            == "Places an order.\nReturns the venue id."
        )

    def test_stacked_go_comments_are_returned_whole(self, parsers: dict[str, typing.Any]) -> None:
        """[Happy path] Go has no doc marker, so consecutive `//` lines ARE the doc block."""
        code = "package m\n// Places an order.\n// Returns the venue id.\nfunc Place() int {return 1}\n"
        assert (
            parsers["go"].extract_symbol_doc(code, "Place")
            == "Places an order.\nReturns the venue id."
        )

    def test_a_block_comments_continuation_stars_are_stripped(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Happy path] The common Javadoc shape. Every interior line begins ` * `, which would
        otherwise reach the index as bullet points on every documented symbol in the language."""
        code = (
            "public class B {\n"
            "  /**\n"
            "   * Places an order.\n"
            "   * Returns the venue id.\n"
            "   */\n"
            "  public int place(){return 1;}\n"
            "}\n"
        )
        assert (
            parsers["java"].extract_symbol_doc(code, "B.place")
            == "Places an order.\nReturns the venue id."
        )


class TestExtractSymbolDocDoesNotAttachWhatIsNotAttached:
    """The half that decides whether this feature reads documentation or invents it."""

    def test_a_comment_separated_by_a_blank_line_does_not_attach(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Hostile] Measured 2026-08-26: a comment THREE lines above a Go function is still its
        `prev_sibling`. Tree position alone cannot tell a description from an unrelated note.

        Without this check every file's licence header becomes the description of its first
        declaration — and every assertion about a *present* doc still passes, which is exactly why
        this case carries a required mutant.
        """
        code = "package m\n// Unrelated note about the package.\n\n\nfunc Place() int {return 1}\n"
        assert parsers["go"].extract_symbol_doc(code, "Place") == ""

    def test_a_licence_header_does_not_become_the_first_declarations_doc(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Hostile] The real-world shape, in a language that DOES walk siblings.

        Written in Go rather than Python on purpose. The Python form of this case passes whatever
        the gap check does, because Python reads a docstring and never looks at a sibling comment
        at all -- it would have proved Python's mechanism while reading as proof of this rule. The
        mutant said so: neutralising the gap check left the Python version green.

        The header sits AFTER `package m` for the same reason. Placed before it, `func`'s previous
        sibling is the package clause rather than a comment, so the walk stops without ever
        reaching the gap check -- passing by construction a second time, which the mutant also
        caught.
        """
        code = (
            "package m\n"
            "\n"
            "// Copyright (c) 2026 sbula. All rights reserved.\n"
            "// Licensed under the Apache License, Version 2.0.\n"
            "\n"
            "func Place() int {return 1}\n"
        )
        assert parsers["go"].extract_symbol_doc(code, "Place") == ""

    def test_python_reads_a_docstring_and_never_a_preceding_comment(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Hostile] Python's own protection, stated as what it actually is.

        A comment above a Python function is never its description -- not because of the gap rule,
        but because Python's description is the docstring inside the body.
        """
        code = "# Not a docstring, and never was.\ndef place():\n    return 1\n"
        assert parsers["python"].extract_symbol_doc(code, "place") == ""

    def test_an_adjacent_comment_still_attaches(self, parsers: dict[str, typing.Any]) -> None:
        """[Happy path] The control. A gap check that rejected everything would satisfy both
        assertions above and look like a fix."""
        code = "package m\n// Places an order.\nfunc Place() int {return 1}\n"
        assert parsers["go"].extract_symbol_doc(code, "Place") == "Places an order."


class TestExtractSymbolDocEdges:
    @pytest.mark.parametrize("lang", sorted(NO_DOC_CONCEPT), ids=str)
    def test_a_language_with_no_doc_concept_says_nothing(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Graceful degradation] Nothing to read, and nothing invented in its place."""
        code, symbol = NO_DOC_CONCEPT[lang]
        assert parsers[lang].extract_symbol_doc(code, symbol) == ""

    def test_an_undocumented_symbol_yields_an_empty_description(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Boundary] Most symbols have no doc. That is not an error."""
        code = "public class B {\n  public int place(){return 1;}\n}\n"
        assert parsers["java"].extract_symbol_doc(code, "B.place") == ""

    def test_an_empty_doc_comment_yields_nothing_not_whitespace(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Boundary] `/** */` carries no description. Returning `"  "` would put an empty string
        into the index that reads as a description to everything downstream."""
        code = "public class B {\n  /** */\n  public int place(){return 1;}\n}\n"
        assert parsers["java"].extract_symbol_doc(code, "B.place") == ""

    def test_stars_and_slashes_inside_the_text_survive(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Boundary] Only LEADING markers may be stripped. A greedy strip eats the content, and
        the damage is invisible unless the fixture contains the characters being stripped."""
        code = "public class B {\n  /** Multiply a*b, then a/b. */\n  public int place(){return 1;}\n}\n"
        assert parsers["java"].extract_symbol_doc(code, "B.place") == "Multiply a*b, then a/b."

    @pytest.mark.parametrize("lang", sorted({**DOCUMENTED, **NO_DOC_CONCEPT}), ids=str)
    def test_an_empty_file_yields_an_empty_description(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Boundary] Nothing in, nothing out."""
        assert parsers[lang].extract_symbol_doc("", "anything") == ""

    @pytest.mark.parametrize("lang", sorted({**DOCUMENTED, **NO_DOC_CONCEPT}), ids=str)
    def test_a_name_that_is_not_there_yields_an_empty_description(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Hostile] Called once per symbol during a whole-repository scan. One bad name must not
        take the scan down, so this answers rather than raises."""
        code = DOCUMENTED.get(lang, NO_DOC_CONCEPT.get(lang, ("", "")))[0]
        assert parsers[lang].extract_symbol_doc(code, "NoSuchSymbol") == ""

    @pytest.mark.parametrize("lang", sorted({**DOCUMENTED, **NO_DOC_CONCEPT}), ids=str)
    def test_an_empty_name_yields_an_empty_description(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Hostile] An empty name matches nothing, and must not match everything."""
        code = DOCUMENTED.get(lang, NO_DOC_CONCEPT.get(lang, ("", "")))[0]
        assert parsers[lang].extract_symbol_doc(code, "") == ""

    @pytest.mark.parametrize("lang", sorted({**DOCUMENTED, **NO_DOC_CONCEPT}), ids=str)
    def test_unparseable_source_yields_an_empty_description(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Graceful degradation] tree-sitter is error-tolerant; this must be too."""
        assert parsers[lang].extract_symbol_doc("<<<< %%% >>>>", "x") == ""


class TestExtractSymbolDocLeavesTraceabilityTagsAlone:
    """`extract_traceability_tags` reads comments too, by a different route and for a different
    claim. It must keep working, and the two must not be confused for one job."""

    def test_traceability_still_reads_comments_anywhere_in_the_file(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        code = "package m\n// @trace(FR-9)\n\n\nfunc Place() int {return 1}\n"
        assert parsers["go"].extract_traceability_tags(code) == {"FR-9"}
        # ...and the very same comment is NOT this function's description, because of the gap.
        assert parsers["go"].extract_symbol_doc(code, "Place") == ""


#: (source, symbol, expected). A documented TYPE rather than a method — the case SF-06's skeleton
#: layer shows first, and the one whose tree shape differs most between languages.
DOCUMENTED_TYPES: dict[str, tuple[str, str, str]] = {
    "java": (
        "/** An order. */\npublic class B {\n  public int p(){return 1;}\n}\n",
        "B",
        "An order.",
    ),
    "kotlin": ("/** An order. */\nclass B {\n  fun p()=1\n}\n", "B", "An order."),
    "typescript": ("/** An order. */\nexport class B {\n  p(){return 1}\n}\n", "B", "An order."),
    "rust": ("/// An order.\npub struct B;\n", "B", "An order."),
    "go": ("package m\n// An order.\ntype B struct{}\n", "B", "An order."),
    "python": (
        'class B:\n    """An order."""\n\n    def p(self):\n        return 1\n',
        "B",
        "An order.",
    ),
    "c": ("/** A point. */\nstruct Point { int x; };\n", "Point", "A point."),
    "cpp": ("/** A widget. */\nclass W {\npublic:\n  int f(){return 1;}\n};\n", "W", "A widget."),
}


class TestExtractSymbolDocOnTypesNotOnlyMethods:
    """A type's description, which is the first thing a retrieval hit shows.

    Every other fixture in this file documents a method. A type declaration sits differently in the
    tree — most obviously in TypeScript, where `export class B` wraps the declaration in an
    `export_statement` and the comment precedes the wrapper rather than the class.
    """

    @pytest.mark.parametrize("lang", sorted(DOCUMENTED_TYPES), ids=str)
    def test_a_documented_type_yields_its_description(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Happy path] Class, struct or record, in all eight."""
        code, symbol, expected = DOCUMENTED_TYPES[lang]
        assert parsers[lang].extract_symbol_doc(code, symbol) == expected

    def test_a_documented_java_interface(self, parsers: dict[str, typing.Any]) -> None:
        """[Happy path] An interface, where the members are implicitly public — so this is the doc
        that travels with the contract SF-06 indexes."""
        code = "/** A shape. */\npublic interface S {\n  int area();\n}\n"
        assert parsers["java"].extract_symbol_doc(code, "S") == "A shape."

    def test_a_documented_rust_trait(self, parsers: dict[str, typing.Any]) -> None:
        """[Happy path] The Rust equivalent, and the one SF-03 is about to start reporting members
        for."""
        code = "/// A shape.\npub trait T {\n  fn area(&self) -> i32;\n}\n"
        assert parsers["rust"].extract_symbol_doc(code, "T") == "A shape."

    def test_an_undocumented_type_yields_nothing(self, parsers: dict[str, typing.Any]) -> None:
        """[Boundary] The control: a rule that returned the nearest comment regardless would find
        the licence header three files up."""
        assert parsers["java"].extract_symbol_doc("public class B {}\n", "B") == ""
