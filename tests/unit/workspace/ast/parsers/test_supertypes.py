# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A parser reports a type's supertypes, separating extension from implementation.

Proves: TECH-068 FR-4

`extract_framework_markers` returns one flat `extends` list, so Java's
`class Impl extends Base implements Runner` arrives as `["Base", "Runner"]` and the kinds are lost
even though the syntax distinguishes them. Three callers outside this feature depend on that shape,
one an agent-facing tool intent, so `NFR-7` and `AD-2` make this a NEW method beside it rather than
a widening.

Measured against the real grammars: Java gives `superclass` and `super_interfaces`, TypeScript gives
`extends_clause` and `implements_clause` — both clean. **Kotlin gives neither**: one
`delegation_specifiers` list holds both, and only a parenthesis convention separates them, which
`by` delegation and a base with no explicit constructor call both break. Settled with the user:
Kotlin reports extension only, so a reader querying `IMPLEMENTS` gets nothing there rather than
something right most of the time.
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.factory import get_default_parsers


def _parser(ext: str) -> object:
    return next(parser for exts, parser in get_default_parsers().items() if ext in exts)


class TestExtractSupertypes:
    def test_java_separates_extension_from_implementation(self) -> None:
        """Happy path: the grammar says which is which, so the graph can too."""
        result = _parser(".java").extract_supertypes(
            "class Impl extends Base implements Runner, Other {}"
        )
        assert result["Impl"] == {"extends": ["Base"], "implements": ["Runner", "Other"]}

    def test_typescript_separates_extension_from_implementation(self) -> None:
        """Happy path: a second language whose grammar is unambiguous."""
        result = _parser(".ts").extract_supertypes("class Impl extends Base implements Runner {}")
        assert result["Impl"] == {"extends": ["Base"], "implements": ["Runner"]}

    def test_kotlin_reports_extension_only(self) -> None:
        """Graceful degradation: the grammar cannot tell them apart, so neither do we."""
        result = _parser(".kt").extract_supertypes("class Impl : Base(), Runner {}")
        assert result["Impl"]["extends"] == ["Base", "Runner"]
        assert result["Impl"]["implements"] == []

    def test_python_reports_every_base_as_extension(self) -> None:
        """Graceful degradation: the language has no such distinction to lose."""
        result = _parser(".py").extract_supertypes("class Impl(Base, Mixin):\n    pass\n")
        assert result["Impl"] == {"extends": ["Base", "Mixin"], "implements": []}

    def test_a_type_with_no_supertypes_reports_empty_lists(self) -> None:
        """Boundary: absent and empty must not be the same, or a reader cannot tell them apart."""
        result = _parser(".java").extract_supertypes("class Plain {}")
        assert result["Plain"] == {"extends": [], "implements": []}

    def test_a_generic_base_reports_its_name(self) -> None:
        """Boundary: `Base<T>` is a dependency on `Base`, not on `Base<T>`."""
        result = _parser(".java").extract_supertypes("class Impl extends Base<T> {}")
        assert result["Impl"]["extends"] == ["Base"]

    def test_empty_source_reports_nothing(self) -> None:
        """Graceful degradation."""
        assert _parser(".java").extract_supertypes("") == {}

    def test_a_function_is_not_a_type(self) -> None:
        """Hostile: only types have supertypes, so a function must not appear at all."""
        result = _parser(".py").extract_supertypes("def f(a, b):\n    return a\n")
        assert "f" not in result


def test_a_language_declaring_type_nodes_without_a_hook_is_refused() -> None:
    """The base default is not a safety net — it is a wrong answer waiting for a caller.

    **This test asserted the empty shape until 2026-08-22**, and its own reasoning is why it was
    replaced. Mutation found the branch unreachable in `SF-03`; the response was to reach it from a
    test and pin what it returned, on the grounds that otherwise it *"would be a branch that
    silently returns the wrong shape the first time someone leans on it"*.

    That names the defect exactly and then preserves it. A test can make a branch reachable; it
    cannot make a silent wrong answer into a right one. The branch is now a refusal, so leaning on
    it fails loudly instead of reporting a language with no inheritance.
    """
    from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure

    class HalfDeclared(PythonCodeStructure):
        """Declares where types live and says nothing about what they inherit."""

    HalfDeclared._supertypes_of = PythonCodeStructure.__mro__[1]._supertypes_of  # type: ignore[method-assign]

    with pytest.raises(NotImplementedError, match="TYPE_DECLARATION_NODES"):
        HalfDeclared().extract_supertypes("class Impl(Base):\n    pass\n")


class TestBaseTreeSitterParserRefusesToGuess:
    """Declaring types without saying what they inherit is a mistake, not a default.

    Proves: TECH-068 FR-4

    The base `_supertypes_of` returned `{"extends": [], "implements": []}` — a silent "this type
    inherits nothing" for any language that declared `TYPE_DECLARATION_NODES` and forgot to
    implement the other half. Measured 2026-08-22 across all ten shipped parsers: **every one that
    declares types overrides it, and every one that does not returns before reaching it**, so the
    body was unreachable. Surfaced by mutation during `SF-03` and left in place.

    Unreachable code is not harmless here. The moment somebody adds a language and declares its
    type nodes, the default answers for them — wrongly, quietly, and in a shape that looks exactly
    like a language with no inheritance. Replacing it with a refusal turns a dead branch into the
    one thing it can usefully be: a contract that fails loudly when half of it is missing.
    """

    def _half_configured_parser(self):
        """A parser that declares C structs as types and never says what they inherit."""
        from specweaver.workspace.ast.parsers.c.codestructure import CCodeStructure

        class HalfConfigured(CCodeStructure):
            TYPE_DECLARATION_NODES = ("struct_specifier",)

        return HalfConfigured()

    def test_declaring_types_without_the_other_half_is_refused(self) -> None:
        """Happy path for the guardrail: the mistake is reported, not absorbed."""
        with pytest.raises(NotImplementedError, match="_supertypes_of"):
            self._half_configured_parser().extract_supertypes("struct S { int x; };")

    def test_the_refusal_names_the_class_that_must_fix_it(self) -> None:
        """Boundary: an error that does not say who must act is a puzzle, not a message."""
        with pytest.raises(NotImplementedError, match="HalfConfigured"):
            self._half_configured_parser().extract_supertypes("struct S { int x; };")

    def test_a_language_that_declares_no_types_never_reaches_it(self) -> None:
        """Boundary: C, SQL and markdown must stay silent rather than start raising.

        `extract_supertypes` returns before the walk when `TYPE_DECLARATION_NODES` is empty, so the
        refusal cannot reach a language that never claimed to have types.
        """
        from specweaver.workspace.ast.parsers.factory import get_default_parsers

        for ext in (".c", ".sql", ".md"):
            parser = next(p for exts, p in get_default_parsers().items() if ext in exts)
            assert parser.extract_supertypes("struct S { int x; };") == {}

    def test_every_shipped_parser_is_fully_configured(self) -> None:
        """Hostile: the guardrail must not be firing on anything we actually ship.

        This is the assertion that would have caught the change being wrong — if any shipped parser
        relied on the old silent default, it fails here rather than in a user's build.
        """
        from specweaver.workspace.ast.parsers.base import BaseTreeSitterParser
        from specweaver.workspace.ast.parsers.factory import get_default_parsers

        half_done = [
            type(p).__name__
            for _exts, p in get_default_parsers().items()
            if getattr(p, "TYPE_DECLARATION_NODES", ())
            and type(p)._supertypes_of is BaseTreeSitterParser._supertypes_of
        ]
        assert half_done == [], f"these declare types and never say what they inherit: {half_done}"
