# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A parser reports what each symbol calls, attributed to the caller by its qualified name.

Proves: TECH-068 FR-1, FR-2

The query is the grammar's own `TAGS_QUERY` constant, so python, rust, java and go need no query
maintained here and `ast.parsers` stays pure-logic — a module constant is an import, not file I/O.

`captures()` is the wrong API: the `name` capture is shared between the `@definition.*` and
`@reference.call` patterns, so it returns definition names mixed with call names and nothing tells
them apart. `matches()` keeps the per-match grouping, so a name is taken only from a match that also
carries `reference.call`.

The caller must be QUALIFIED. Walking up from a call yields `go`, while `list_symbols` names the same
symbol `Impl.go` and the node hash is built from that. Attributing a method's calls to `go` would
attach them to a node that does not exist.
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.factory import get_default_parsers


def _parser(ext: str) -> object:
    return next(parser for exts, parser in get_default_parsers().items() if ext in exts)


class TestExtractCallSites:
    def test_a_function_reports_what_it_calls(self) -> None:
        """Happy path."""
        result = _parser(".py").extract_call_sites("def a():\n    helper()\n")
        assert result["a"] == ["helper"]

    def test_a_method_is_reported_under_its_qualified_name(self) -> None:
        """The caller key must match what `list_symbols` returns, or the node hash will not exist."""
        code = "class Impl:\n    def go(self):\n        helper()\n"
        assert _parser(".py").extract_call_sites(code) == {"Impl.go": ["helper"]}

    def test_an_attribute_call_reports_the_bare_name(self) -> None:
        """Boundary: `self.other()` is a call to `other`; the receiver is not resolvable here."""
        code = "class Impl:\n    def go(self):\n        self.other()\n"
        assert _parser(".py").extract_call_sites(code) == {"Impl.go": ["other"]}

    def test_a_call_outside_any_function_is_attributed_to_the_file(self) -> None:
        """Boundary: module-level code is a real dependency and must not be dropped."""
        result = _parser(".py").extract_call_sites("VALUE = build()\n")
        assert result[""] == ["build"]

    def test_a_recursive_call_is_reported(self) -> None:
        """Boundary: a function calling itself is a real dependency."""
        assert _parser(".py").extract_call_sites("def a():\n    a()\n")["a"] == ["a"]

    def test_definitions_are_not_mistaken_for_calls(self) -> None:
        """Hostile: `captures()` would return the definition's own name here."""
        assert _parser(".py").extract_call_sites("def a():\n    pass\n") == {}

    def test_rust_reports_calls(self) -> None:
        assert _parser(".rs").extract_call_sites("fn a() { helper(); }")["a"] == ["helper"]

    def test_java_reports_calls(self) -> None:
        code = "class K { void a() { helper(); } }"
        assert _parser(".java").extract_call_sites(code)["K.a"] == ["helper"]

    def test_go_reports_calls(self) -> None:
        code = "package m\nfunc a() { helper() }"
        assert _parser(".go").extract_call_sites(code)["a"] == ["helper"]

    def test_a_language_with_no_call_concept_reports_nothing(self) -> None:
        """Graceful degradation: silence is better than an exception mid-build.

        This named Kotlin until `SF-05` gave it a locally-held query. `sql` and `markdown` have no
        calls to find at all, so they keep the property Kotlin only had while it was unsupported.
        """
        assert _parser(".sql").extract_call_sites("SELECT 1;") == {}
        assert _parser(".md").extract_call_sites("# Title\n") == {}

    def test_empty_source_reports_nothing(self) -> None:
        assert _parser(".py").extract_call_sites("") == {}
