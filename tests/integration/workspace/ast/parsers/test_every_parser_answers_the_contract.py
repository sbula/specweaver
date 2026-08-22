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

import pytest

from specweaver.workspace.ast.parsers.factory import get_default_parsers

_SOURCE = {
    ".py": "class Impl(Base):\n    pass\n",
    ".java": "class Impl extends Base {}",
    ".kt": "class Impl : Base() {}",
    ".ts": "class Impl extends Base {}",
    ".rs": "struct Impl;\ntrait Base {}\nimpl Base for Impl {}\n",
    ".go": "package m\ntype Impl struct {\n\tBase\n}\n",
    ".c": "int main(void) { return 0; }",
    ".cpp": "class Impl : public Base {};",
    ".sql": "SELECT 1;",
    ".md": "# Title\n",
}

# Named one by one, because a loop over a parser's EMPTY result runs its body zero times and reads
# as a pass. That is how Go and Rust reported no supertypes at all while this file "covered" them:
# both returned `{}`, both satisfied every assertion, and the gap was invisible until somebody went
# looking. Naming the languages turns silence into a failure.
_MUST_REPORT_A_TYPE = {".py", ".java", ".kt", ".ts", ".cpp", ".go", ".rs"}

# Silence here is the correct answer, and the reason is recorded so nobody "fixes" it later.
_NO_TYPE_CONCEPT = {
    ".c": "C has structs but no inheritance of any kind",
    ".sql": "not a language with user-declared types in this sense",
    ".md": "prose",
}


def _parser_for(ext: str):
    parsers = get_default_parsers()
    return next(p for exts, p in parsers.items() if ext in exts)


def test_the_declared_lists_cover_every_parser_the_factory_ships() -> None:
    """The subject-located guard: a hand-written list rots the moment a parser is added.

    Without this, adding a language would silently skip it here — which is the same vacuous pass,
    wearing a different hat.
    """
    shipped = {exts[0] for exts in get_default_parsers()}
    declared = _MUST_REPORT_A_TYPE | set(_NO_TYPE_CONCEPT)

    assert shipped <= declared, f"a shipped parser is in neither list: {sorted(shipped - declared)}"
    assert not (_MUST_REPORT_A_TYPE & set(_NO_TYPE_CONCEPT)), "a language cannot be in both"


@pytest.mark.parametrize("ext", sorted(_MUST_REPORT_A_TYPE))
def test_a_language_with_types_reports_at_least_one(ext: str) -> None:
    """The assertion the old loop could not make: a language with types must NAME one.

    Parametrized rather than looped, so a language that goes silent fails as itself instead of
    disappearing into a passing aggregate.
    """
    result = _parser_for(ext).extract_supertypes(_SOURCE[ext])

    assert result, f"{ext} declares a type in this fixture and reported none"
    assert "Impl" in result, f"{ext} did not report the type it was given: {sorted(result)}"


@pytest.mark.parametrize("ext", sorted(_MUST_REPORT_A_TYPE))
def test_a_language_with_types_reports_the_relationship(ext: str) -> None:
    """Every fixture above declares `Impl` built on `Base`, whatever its syntax for that is."""
    kinds = _parser_for(ext).extract_supertypes(_SOURCE[ext])["Impl"]

    assert "Base" in kinds["extends"] + kinds["implements"], (
        f"{ext} reported the type but not what it is built from: {kinds}"
    )


def test_every_shipped_parser_returns_the_declared_shape() -> None:
    """The shape half: whatever a parser reports, it reports it in the agreed structure."""
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
    for ext, reason in _NO_TYPE_CONCEPT.items():
        assert _parser_for(ext).extract_supertypes(_SOURCE[ext]) == {}, (
            f"{ext} is declared exempt because {reason} — it now reports something, so either the "
            f"exemption is wrong or the parser is"
        )


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


def test_a_language_with_no_call_concept_is_silent_rather_than_raising() -> None:
    """Graceful degradation: one file must not take down a build.

    Named the four `SF-05` owned until it gave each of them a query. `sql` and `markdown` have no
    calls to find, so the claim survives as a statement about the shape rather than about coverage.
    """
    parsers = get_default_parsers()
    for ext in (".sql", ".md"):
        parser = next(p for exts, p in parsers.items() if ext in exts)
        assert parser.extract_call_sites(_SOURCE.get(ext, "")) == {}
