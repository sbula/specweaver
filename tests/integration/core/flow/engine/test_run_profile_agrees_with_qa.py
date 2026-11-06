# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The task's files and the QA runner name the same language: the run's one profile.

Proves: TECH-082 FR-3
Proves: TECH-079 FR-7

`run_task_files` (the files generation writes) and the QA runner (the tools `lint_fix` runs) both
take the run's profile; this test says they agree, so a project never gets Rust files linted by
the Python tools. Real profile decision, real runners; nothing is run.

| Bucket | Case |
|---|---|
| Happy | each of the five build files gives one language to both |
| Boundary | a pinned profile wins over the build files for both |
| Degradation | no build file at all: both refuse, neither falls back to Python |
| Hostile | two build files at once: both refuse |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.commons.project_profile import ProjectProfile, ProjectUndecidedError
from specweaver.core.flow.engine.run_profile import run_task_files
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
    "tsconfig.json": ("{}", "typescript"),
    "Cargo.toml": ('[package]\nname = "p"\n', "rust"),
}


def _context(root: Path, profile: ProjectProfile | None = None) -> RunContext:
    return RunContext(
        project_path=root,
        spec_path=root / "s_spec.md",
        isolation=IsolationPolicy(profile=profile),
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
    if manifest == "tsconfig.json":
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    assert _both(_context(tmp_path)) == (language, _RUNNERS[language])


def test_a_pinned_profile_wins_for_both(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "p"\n', encoding="utf-8")

    assert _both(_context(tmp_path, ProjectProfile("java", "maven"))) == ("java", JavaRunner)


def test_no_build_file_is_refused_by_both(tmp_path: Path) -> None:
    with pytest.raises(ProjectUndecidedError):
        run_task_files(_context(tmp_path))
    with pytest.raises(ProjectUndecidedError):
        LintFixHandler()._get_atom(_context(tmp_path))


def test_two_build_files_are_refused_by_both(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'p'\n", encoding="utf-8")
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "p"\n', encoding="utf-8")

    with pytest.raises(ProjectUndecidedError, match=r"Cargo\.toml"):
        run_task_files(_context(tmp_path))
    with pytest.raises(ProjectUndecidedError, match=r"Cargo\.toml"):
        LintFixHandler()._get_atom(_context(tmp_path))
