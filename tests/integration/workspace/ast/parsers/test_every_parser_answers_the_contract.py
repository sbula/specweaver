# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every parser the factory ships answers the type and call contracts, whatever its language expresses.

Proves: TECH-068 FR-4, FR-1

`extract_supertypes` is abstract on `CodeStructureInterface`, so a parser that forgot it cannot be
instantiated — but nothing proved that the ones which DO implement it agree on the shape they return.
Each language's unit tests pass on their own; this is the claim about the set, which is the shape of
defect `TECH-056` and `TECH-058` both were.

A language with no such concept reports `{}` rather than raising or inventing. That is what makes the
graph's later question — "does this type extend anything?" — answerable for every file it collects
instead of only the four languages this ticket reached.
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.factory import get_default_parsers

_SOURCE = {
    ".py": "class Impl(Base):\n    pass\n",
    ".java": "class Impl extends Base {}",
    ".kt": "class Impl : Base() {}",
    ".ts": "class Impl extends Base {}",
    ".rs": "struct S;",
    ".go": "type S struct{}",
    ".c": "int main(void) { return 0; }",
    ".cpp": "class Impl : public Base {};",
    ".sql": "SELECT 1;",
    ".md": "# Title\n",
}


def test_every_shipped_parser_returns_the_declared_shape() -> None:
    """The set is the claim: each parser passing its own tests says nothing about the others."""
    for exts, parser in get_default_parsers().items():
        source = next((_SOURCE[e] for e in exts if e in _SOURCE), "")
        result = parser.extract_supertypes(source)
        assert isinstance(result, dict), f"{type(parser).__name__} returned {type(result)}"
        for name, kinds in result.items():
            assert isinstance(name, str)
            assert set(kinds) == {"extends", "implements"}, f"{type(parser).__name__}: {kinds}"
            assert all(isinstance(v, list) for v in kinds.values())


def test_a_language_without_the_concept_reports_nothing_rather_than_raising() -> None:
    """Graceful degradation: silence is an answer; an exception mid-build is not."""
    parsers = get_default_parsers()
    for ext in (".sql", ".md", ".c"):
        parser = next(p for exts, p in parsers.items() if ext in exts)
        assert parser.extract_supertypes(_SOURCE[ext]) == {}


def test_every_parser_survives_source_it_cannot_parse() -> None:
    """Hostile: one unreadable file must not take the whole build down."""
    for _exts, parser in get_default_parsers().items():
        assert isinstance(parser.extract_supertypes("!!! not source at all ((("), dict)


def test_every_shipped_parser_returns_call_sites_in_the_declared_shape() -> None:
    """The set is the claim. Four languages read calls from an upstream query and six report none;
    each passes its own tests, and none of them says the six stay silent rather than raising."""
    for exts, parser in get_default_parsers().items():
        source = next((_SOURCE[e] for e in exts if e in _SOURCE), "")
        result = parser.extract_call_sites(source)
        assert isinstance(result, dict), f"{type(parser).__name__} returned {type(result)}"
        for caller, callees in result.items():
            assert isinstance(caller, str)
            assert all(isinstance(c, str) for c in callees), f"{type(parser).__name__}: {callees}"


def test_a_language_with_no_upstream_call_query_is_silent_rather_than_raising() -> None:
    """Graceful degradation: SF-05 owns those four, and one file must not take down a build."""
    parsers = get_default_parsers()
    for ext in (".kt", ".ts", ".c", ".cpp"):
        parser = next(p for exts, p in parsers.items() if ext in exts)
        assert parser.extract_call_sites(_SOURCE.get(ext, "")) == {}
