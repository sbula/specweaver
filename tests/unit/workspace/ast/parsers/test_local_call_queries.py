# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The four grammars that ship no call query get one held here.

Proves: TECH-068 FR-3

`SF-04` read `@reference.call` from each grammar's own `TAGS_QUERY`. These four ship none, so the
query lives in this repository — original work written from the grammars by inspection, which is
what keeps the design's `T-OBLIGATION` note from firing.

The mechanism is unchanged: a language points `TAGS_QUERY` at a local string and
`extract_call_sites` does the rest. What differs is how safely each query can be written.
TypeScript, C and C++ address the callee by FIELD — `function:` — so the pattern says what it means.
Kotlin exposes no field names at all, so its pattern is positional and is pinned by `CB-2`.

The receiver is never a call. `obj.deep()` contributes `deep`; which `obj` is out of scope for this
ticket entirely.
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.factory import get_default_parsers


def _parser(ext: str) -> object:
    return next(parser for exts, parser in get_default_parsers().items() if ext in exts)


class TestTypeScriptCallSites:
    def test_a_plain_call_is_reported(self) -> None:
        assert _parser(".ts").extract_call_sites("function f() { helper(); }")["f"] == ["helper"]

    def test_a_method_call_reports_the_property_not_the_receiver(self) -> None:
        """Hostile: `obj.deep()` is a call to `deep`. Reporting `obj` invents a dependency."""
        result = _parser(".ts").extract_call_sites("function f() { obj.deep(); }")
        assert result["f"] == ["deep"]

    def test_arguments_are_not_calls(self) -> None:
        """Boundary: `build(x, y)` calls `build` and nothing else."""
        assert _parser(".ts").extract_call_sites("function f() { build(x, y); }")["f"] == ["build"]


class TestCCallSites:
    def test_a_plain_call_is_reported(self) -> None:
        assert _parser(".c").extract_call_sites("void f(void) { helper(); }")["f"] == ["helper"]

    def test_a_file_with_no_calls_reports_nothing(self) -> None:
        """Boundary."""
        assert _parser(".c").extract_call_sites("int x = 1;") == {}


class TestCppCallSites:
    def test_a_plain_call_is_reported(self) -> None:
        assert _parser(".cpp").extract_call_sites("void f() { helper(); }")["f"] == ["helper"]

    def test_a_method_body_call_is_attributed_to_the_qualified_method(self) -> None:
        """Boundary: the caller must be the name the node carries."""
        result = _parser(".cpp").extract_call_sites("class K { void go() { helper(); } };")
        assert result["K.go"] == ["helper"]


def test_empty_source_reports_nothing() -> None:
    """Graceful degradation, across all three."""
    for ext in (".ts", ".c", ".cpp"):
        assert _parser(ext).extract_call_sites("") == {}
