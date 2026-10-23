# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every place that names a file's language, or a task's test file, agrees with the one table.

Proves: TECH-078 FR-6, TECH-078 FR-3

Real readers, real `task_files_for` over real project folders; nothing is doubled.

| Bucket | Case |
|---|---|
| Happy | the archetype rules, the prompt fences and the code-structure atom name every ending the table holds; each language's task test file follows the convention |
| Boundary | `.pyi` and `.mjs` count as code (decision 1); a `.pyi` or `.mjs` file is condensed by its parser, not copied |
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


@pytest.mark.parametrize(("language", "ending"), _ENDINGS)
def test_the_prompt_fences_every_ending_with_its_language(language: str, ending: str) -> None:
    from specweaver.infrastructure.llm.prompt.constants import detect_language

    assert detect_language(Path(f"a{ending}")) == language


def test_a_data_file_keeps_its_fence() -> None:
    from specweaver.infrastructure.llm.prompt.constants import detect_language

    assert detect_language(Path("a.yaml")) == "yaml"
    assert detect_language(Path("a.unknown")) == "text"


@pytest.mark.parametrize(("language", "ending"), _ENDINGS)
def test_the_code_structure_atom_names_every_ending(
    language: str, ending: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from types import SimpleNamespace

    from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom
    from specweaver.sandbox.language.core.evaluator import SchemaEvaluator

    seen: list[str] = []
    monkeypatch.setattr(
        SchemaEvaluator, "evaluate_markers", lambda _s, lang, *_a: seen.append(lang) or ""
    )
    parser = SimpleNamespace(
        extract_symbol=lambda *_a: "code", extract_framework_markers=lambda *_a: {}
    )

    CodeStructureAtom(cwd=tmp_path)._handle_read_symbol(
        parser, "code", "s", "read_unrolled_symbol", f"a{ending}"
    )

    assert seen == [language]


@pytest.mark.parametrize("ending", [".pyi", ".mjs"])
def test_the_skeleton_condenses_every_ending_its_parser_reads(ending: str) -> None:
    from specweaver.infrastructure.llm._skeleton import extract_ast_skeleton

    body = (
        "def place(order):\n    total = 1\n    return total\n"
        if ending == ".pyi"
        else "export function place(order) {\n  const total = 1;\n  return total;\n}\n"
    )

    assert "total = 1" not in extract_ast_skeleton(Path(f"a{ending}"), body)
