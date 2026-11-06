# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The profile decision agrees with the one language table and, where today is not a guess, with
today's build-tool detector.

Proves: TECH-079 FR-3, TECH-079 FR-5, TECH-079 FR-6

Real project folders in `tmp_path`; `detect_toolchain` runs unchanged. SF-02 CB-3 removes it, and
the second half of this file with it.

| Bucket | Case |
|---|---|
| Happy | each one-language root: the same build tool as today (npm aside: today names none) |
| Boundary | every ending the table holds: a generatable language is named, any other refused by name |
| Degradation | — (pure decision over fixed folders) |
| Hostile | — (fixed folders; the hostile roots are in the unit tests) |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.commons.languages import LANGUAGE_SUFFIXES
from specweaver.commons.project_profile import (
    GENERATED_LANGUAGES,
    ProjectUndecidedError,
    decide_profile,
)
from specweaver.workspace.project.prepare_plan import detect_toolchain

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.commons.project_profile import ProjectProfile

pytestmark = pytest.mark.integration

_ENDINGS = [(lang, e) for lang, suffixes in LANGUAGE_SUFFIXES.items() for e in suffixes]

#: One-language roots whose answer today is not a guess.
ROOTS = {
    "uv": {"pyproject.toml": "[project]\nname = 'x'\n", "main.py": ""},
    "python-plain": {"main.py": ""},
    "cargo": {"Cargo.toml": "[package]\nname = 'x'\n"},
    "maven": {"pom.xml": "<project/>"},
    "gradle": {"build.gradle": "plugins { id 'java' }"},
    "gradle-kotlin": {"build.gradle.kts": 'plugins { kotlin("jvm") }'},
    "maven-kotlin-sources": {"pom.xml": "<project/>", "src/main/kotlin/App.kt": ""},
    "typescript": {"package.json": "{}", "tsconfig.json": "{}"},
}


def _decide(root: Path) -> ProjectProfile:
    names = frozenset(p.name for p in root.iterdir() if p.is_file())
    return decide_profile(
        names,
        lambda name: (root / name).read_text(encoding="utf-8"),
        kotlin_sources=(root / "src/main/kotlin").is_dir(),
    )


@pytest.mark.parametrize("name", sorted(ROOTS))
def test_a_one_language_root_gets_todays_answer(tmp_path: Path, name: str) -> None:
    for relative, text in ROOTS[name].items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(text, encoding="utf-8")

    profile = _decide(tmp_path)

    expected_tool = "npm" if profile.language == "typescript" else detect_toolchain(tmp_path)
    assert profile.build_tool == expected_tool


@pytest.mark.parametrize(("language", "ending"), _ENDINGS)
def test_every_table_ending_is_decided_by_the_table(
    tmp_path: Path, language: str, ending: str
) -> None:
    code = "main" + ending
    (tmp_path / code).write_text("", encoding="utf-8")

    if language in GENERATED_LANGUAGES:
        assert _decide(tmp_path).language == language
    else:
        with pytest.raises(ProjectUndecidedError, match=rf"^{language} \({code}\) cannot"):
            _decide(tmp_path)
