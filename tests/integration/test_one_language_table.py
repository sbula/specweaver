# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every place that names a file's language, or a task's test file, agrees with the one table.

Proves: TECH-078 FR-6, TECH-078 FR-3

Real readers, real `task_files_for` over real project folders; nothing is doubled.

| Bucket | Case |
|---|---|
| Happy | the archetype rules match every ending the table holds; each language's task test file follows the convention |
| Boundary | `.pyi` and `.mjs` count as code for the archetype match (decision 1) |
| Degradation | an ending the table does not hold matches no archetype language |
| Hostile | not applicable — the readers take file names only |
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from specweaver.commons.languages import LANGUAGE_SUFFIXES, name_tests_for, root_of_tests

pytestmark = pytest.mark.integration

_ENDINGS = [(lang, e) for lang, suffixes in LANGUAGE_SUFFIXES.items() for e in suffixes]


@pytest.mark.parametrize(("language", "ending"), _ENDINGS)
def test_the_archetype_rules_know_every_ending(language: str, ending: str) -> None:
    from specweaver.core.flow.handlers.archetype_pipelines import LANGUAGE_SUFFIXES as ARCHETYPE

    assert ending in ARCHETYPE[language]


def test_an_unknown_ending_matches_no_archetype_language() -> None:
    from specweaver.core.flow.handlers.archetype_pipelines import LANGUAGE_SUFFIXES as ARCHETYPE

    assert not any(".sql" in suffixes for suffixes in ARCHETYPE.values())


@pytest.mark.parametrize("language", ["python", "java", "kotlin", "typescript", "rust"])
def test_the_tasks_test_file_follows_the_convention(language: str, tmp_path: Path) -> None:
    from specweaver.core.flow.engine.task_files import task_files_for

    spec = tmp_path / "specs" / "orders_spec.md"
    spec.parent.mkdir()
    spec.write_text("# Orders\n", encoding="utf-8")

    files = task_files_for(tmp_path, spec, language)
    code, tests = PurePosixPath(files.code), PurePosixPath(files.tests)

    assert tests.name == name_tests_for(code.name, language)
    assert files.tests.startswith(f"{root_of_tests(language)}/")
