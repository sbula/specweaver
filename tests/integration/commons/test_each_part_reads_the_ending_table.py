# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every part that asks "which language is this file" reads the one table in `commons`.

Proves: TECH-079 FR-12, FR-16

Real folders and files; each part through its own entry.

| Bucket | Case |
|---|---|
| Happy | a `.kts`, `.tsx` or `.pyi`-only folder gets its structure analyzer; `A.TS` gets the style analyzer; rename starts at a `.pyi` stub |
| Boundary | the scope and recency scans see `.cc`, `.mjs` and keep their own `.rb`; the `sw init` hint sees `.mjs`; an `index.mjs` is a package entry |
| Degradation | a folder of `.md` files gets no analyzer |
| Hostile | `[implement] language = "go"` is refused naming the five SpecWeaver generates |
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from specweaver.commons.project_profile import BUILD_TOOLS, GENERATED_LANGUAGES

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("name", "analyzer"),
    [
        ("build.kts", "KotlinAnalyzer"),
        ("App.tsx", "TypeScriptAnalyzer"),
        ("api.pyi", "PythonAnalyzer"),
        ("Main.JAVA", "JavaAnalyzer"),
    ],
)
def test_a_folder_of_any_ending_gets_its_structure_analyzer(
    tmp_path: Path, name: str, analyzer: str
) -> None:
    from specweaver.workspace.analyzers.factory import AnalyzerFactory

    (tmp_path / name).write_text("", encoding="utf-8")

    found = AnalyzerFactory.for_directory(tmp_path)

    assert type(found).__name__ == analyzer


def test_a_folder_without_code_gets_no_analyzer(tmp_path: Path) -> None:
    from specweaver.workspace.analyzers.factory import AnalyzerFactory

    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")

    assert AnalyzerFactory.for_directory(tmp_path) is None


def test_the_style_scan_reads_any_case(tmp_path: Path) -> None:
    from specweaver.assurance.standards.languages.typescript.analyzer import (
        TSStandardsAnalyzer,
    )
    from specweaver.assurance.standards.scanner import StandardsScanner

    upper = tmp_path / "A.TS"
    upper.write_text("export function greetUser(): number { return 1; }\n", encoding="utf-8")
    analyzer = TSStandardsAnalyzer()
    seen: list[list[Path]] = []
    analyzer.extract_all = lambda files, *a, **k: seen.append(list(files)) or []  # type: ignore[method-assign]

    StandardsScanner([analyzer]).scan([upper])

    assert seen == [[upper]]


def test_the_scope_and_recency_scans_read_the_table(tmp_path: Path) -> None:
    from specweaver.assurance.standards.recency import _find_oldest_source_mtime
    from specweaver.assurance.standards.scope_detector import _has_source_files

    for name, when in (("core.cc", 1_000_000), ("tool.mjs", 2_000_000), ("old.rb", 3_000_000)):
        (tmp_path / name).write_text("", encoding="utf-8")
        os.utime(tmp_path / name, (when, when))

    assert _find_oldest_source_mtime(tmp_path) == 1_000_000
    only_cc = tmp_path / "cpp"
    only_cc.mkdir()
    (only_cc / "core.cc").write_text("", encoding="utf-8")
    assert _has_source_files(only_cc)
    (tmp_path / "core.cc").unlink()
    (tmp_path / "tool.mjs").unlink()
    assert _has_source_files(tmp_path)  # .rb stays its own extra
    assert _find_oldest_source_mtime(tmp_path) == 3_000_000


def test_the_init_hint_sees_every_standards_ending(tmp_path: Path) -> None:
    from specweaver.workspace.project.interfaces.cli import has_standards_code

    assert not has_standards_code(tmp_path)
    (tmp_path / "tool.mjs").write_text("", encoding="utf-8")
    assert has_standards_code(tmp_path)


def test_rename_reads_a_python_stub() -> None:
    from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure
    from specweaver.workspace.ast.refactor.rename import plan_rename

    files = {"greet.pyi": "def greet() -> int: ...\n", "greet.py": "def greet():\n    return 1\n"}

    plan = plan_rename(files, "greet.pyi", "greet", "welcome", PythonCodeStructure())

    assert plan.changes["greet.pyi"] == "def welcome() -> int: ...\n"  # type: ignore[union-attr]


def test_an_index_mjs_is_a_package_entry() -> None:
    from specweaver.workspace.ast.refactor.imports import targets_for

    files = {
        "src/app.ts": "import { x } from './lib';\n",
        "src/lib/index.mjs": "export const x = 1;\n",
    }

    target = targets_for(files, "typescript")

    assert target is not None and target("src/app.ts", "./lib") == "src/lib"


def test_a_language_without_a_generator_is_refused_naming_the_five() -> None:
    from specweaver.core.config.implement_policy import parse_implement
    from specweaver.core.config.settings_file import SettingsFileError

    with pytest.raises(SettingsFileError) as caught:
        parse_implement('[implement]\nlanguage = "go"\n', "specweaver.toml")

    assert all(name in str(caught.value) for name in GENERATED_LANGUAGES)
    with pytest.raises(SettingsFileError) as caught:
        parse_implement('[implement]\nbuild_tool = "ant"\n', "specweaver.toml")
    assert all(name in str(caught.value) for name in BUILD_TOOLS)


def test_the_generators_and_contracts_use_the_one_list() -> None:
    from specweaver.workflows.implementation.contract_renderers import contract_extension
    from specweaver.workflows.implementation.languages import language_guide

    for language in GENERATED_LANGUAGES:
        assert language_guide(language).name
        assert f".{contract_extension(language)}" in (".py", ".java", ".kt", ".ts", ".rs")
