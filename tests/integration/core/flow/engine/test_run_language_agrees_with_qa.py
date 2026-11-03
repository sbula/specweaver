# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The task's files and the QA runner name the same language when the run names none.

Proves: TECH-082 FR-3

`run_task_files` (the files generation writes) and the QA runner factory (the tools `lint_fix`
runs) each turn "no language" into one. They ask the same detector; this test says they must
also agree, so a project never gets Rust files linted by the Python tools. Real detector, real
runners; nothing is run.

| Bucket | Case |
|---|---|
| Happy | each of the five manifests gives one language to both |
| Boundary | a named language wins over the manifests for both |
| Degradation | no manifest at all: both fall back to Python |
| Hostile | two manifests at once: both take the same one |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.run_language import run_task_files
from specweaver.core.flow.handlers.lint_fix import LintFixHandler
from specweaver.core.flow.run_state.run_context import IsolationPolicy, RunContext
from specweaver.sandbox.language.core.java.runner import JavaRunner
from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner
from specweaver.sandbox.language.core.python.runner import PythonQARunner
from specweaver.sandbox.language.core.rust.runner import RustRunner
from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_RUNNERS = {
    "python": PythonQARunner,
    "java": JavaRunner,
    "kotlin": KotlinRunner,
    "typescript": TypeScriptRunner,
    "rust": RustRunner,
}
_MANIFESTS = {
    "pyproject.toml": ("[project]\nname = 'p'\n", "python"),
    "pom.xml": ("<project/>", "java"),
    "build.gradle.kts": ('plugins { kotlin("jvm") }\n', "kotlin"),
    "package.json": ("{}", "typescript"),
    "Cargo.toml": ('[package]\nname = "p"\n', "rust"),
}


def _context(root: Path, language: str | None) -> RunContext:
    return RunContext(
        project_path=root,
        spec_path=root / "s_spec.md",
        isolation=IsolationPolicy(language=language),
    )


def _both(context: RunContext) -> tuple[str, type]:
    runner = LintFixHandler()._get_atom(context)._runner
    return run_task_files(context).language, type(runner)


@pytest.mark.parametrize(
    ("manifest", "content", "language"), [(k, *v) for k, v in _MANIFESTS.items()]
)
def test_each_manifest_gives_both_one_language(
    tmp_path: Path, manifest: str, content: str, language: str
) -> None:
    (tmp_path / manifest).write_text(content, encoding="utf-8")

    assert _both(_context(tmp_path, None)) == (language, _RUNNERS[language])


def test_a_named_language_wins_for_both(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "p"\n', encoding="utf-8")

    assert _both(_context(tmp_path, "java")) == ("java", JavaRunner)


def test_no_manifest_is_python_for_both(tmp_path: Path) -> None:
    assert _both(_context(tmp_path, None)) == ("python", PythonQARunner)


def test_two_manifests_give_both_the_same_one(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "p"\n', encoding="utf-8")

    assert _both(_context(tmp_path, None)) == ("typescript", TypeScriptRunner)
