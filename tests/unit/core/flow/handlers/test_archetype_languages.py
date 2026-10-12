# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An archetype's languages come from its evaluator schema; a file of another language is not its.

Proves: B-INTL-01 FR-5

| Bucket | Case |
|---|---|
| Happy | spring-boot names java and kotlin; `.java` and `.kt` are covered, `.py` is not |
| Boundary | an archetype whose schema names no languages covers any file |
| Degradation | an archetype without a schema covers any file |
| Hostile | a schema naming an unknown language is refused, naming the archetype |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.core.flow.handlers.archetype_pipelines import (
    LANGUAGE_SUFFIXES,
    covers,
    languages_of,
)


def test_spring_boot_covers_java_and_kotlin_only() -> None:
    languages = languages_of("spring-boot", None)

    assert sorted(languages) == ["java", "kotlin"]
    assert covers(languages, Path("A.java"))
    assert covers(languages, Path("A.KT"))
    assert not covers(languages, Path("a.py"))


def test_no_languages_covers_any_file() -> None:
    assert covers([], Path("a.py"))


def test_an_archetype_without_a_schema_names_no_languages() -> None:
    assert languages_of("no-such-archetype", None) == []


def test_an_unknown_language_is_refused(tmp_path: Path) -> None:
    (tmp_path / ".specweaver" / "evaluators").mkdir(parents=True)
    (tmp_path / ".specweaver" / "evaluators" / "in-house.yaml").write_text(
        "metadata:\n  supported_languages: [groovy]\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match=r"in-house.*groovy"):
        languages_of("in-house", tmp_path)


def test_every_language_has_a_parser() -> None:
    """The endings agree with the parsers', so a covered file can be read.

    JavaScript is the one exception: `nestjs` names it, and no JavaScript parser exists yet.
    """
    from specweaver.workspace.ast.parsers.factory import get_default_parsers

    parsed = {suffix for suffixes in get_default_parsers() for suffix in suffixes}
    named = {s for name, suffixes in LANGUAGE_SUFFIXES.items() for s in suffixes}

    assert named - parsed == set(LANGUAGE_SUFFIXES["javascript"])


def test_every_shipped_archetype_names_known_languages() -> None:
    from specweaver.workflows.evaluators.loader import load_evaluator_schemas

    for archetype in load_evaluator_schemas():
        languages_of(archetype, None)
