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


def test_a_language_declaring_type_nodes_without_a_hook_gets_the_empty_shape() -> None:
    """The base default is the safety net for the next language added, so it must be reachable.

    A mutation pass found it unreachable: all four languages that declare `TYPE_DECLARATION_NODES`
    also override `_supertypes_of`, so nothing exercised the fallback. Left untested it would be a
    branch that silently returns the wrong shape the first time someone leans on it.
    """
    from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure

    class HalfDeclared(PythonCodeStructure):
        """Declares where types live and says nothing about what they inherit."""

    HalfDeclared._supertypes_of = PythonCodeStructure.__mro__[1]._supertypes_of  # type: ignore[method-assign]
    assert HalfDeclared().extract_supertypes("class Impl(Base):\n    pass\n") == {
        "Impl": {"extends": [], "implements": []}
    }
