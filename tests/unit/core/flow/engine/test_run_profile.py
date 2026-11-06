# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run's profile: the one the run builder decided, or its refusal; decided once.

Proves: TECH-079 FR-7, TECH-082 FR-3

Every caller asks `run_profile`, so the task files, the QA runner and the sandbox get one answer.
A context nobody decided for (one a test built) decides from its project root, with no pins, and
keeps the answer.

| Bucket | Case |
|---|---|
| Happy | a stored profile comes back as is; the task files follow its language |
| Boundary | no profile and no refusal: the root decides once, and a second call reads nothing |
| Degradation | a stored refusal is raised with its message; an empty root is refused, never Python |
| Hostile | a mixed root is refused naming both build files; a bad `Package` line is refused |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.commons.project_profile import ProjectProfile, ProjectUndecidedError
from specweaver.core.flow.engine.run_profile import run_profile, run_task_files
from specweaver.core.flow.run_state.run_context import IsolationPolicy, RunContext

if TYPE_CHECKING:
    from pathlib import Path


def _context(
    root: Path, profile: ProjectProfile | None = None, undecided: str | None = None
) -> RunContext:
    return RunContext(
        project_path=root,
        spec_path=root / "specs" / "greet_service_spec.md",
        isolation=IsolationPolicy(profile=profile, undecided=undecided),
    )


def _cargo(root: Path) -> None:
    (root / "Cargo.toml").write_text('[package]\nname = "greet"\n', encoding="utf-8")


def test_a_stored_profile_comes_back(tmp_path: Path) -> None:
    _cargo(tmp_path)
    stored = ProjectProfile("typescript", "npm")

    assert run_profile(_context(tmp_path, stored)) == stored


def test_the_task_files_follow_the_stored_language(tmp_path: Path) -> None:
    _cargo(tmp_path)

    context = _context(tmp_path, ProjectProfile("typescript", "npm"))

    assert run_task_files(context).code == "src/greet_service.ts"


def test_without_a_decision_the_root_decides_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from specweaver.workspace.project import project_profile

    _cargo(tmp_path)
    reads: list[Path] = []
    real = project_profile.read_project_profile

    def counting(root: Path, **pins: str | None) -> ProjectProfile:
        reads.append(root)
        return real(root, **pins)

    monkeypatch.setattr(project_profile, "read_project_profile", counting)
    context = _context(tmp_path)

    first = run_profile(context)
    second = run_profile(context)

    assert first == second == ProjectProfile("rust", "cargo")
    assert reads == [tmp_path]
    assert context.isolation.profile == ProjectProfile("rust", "cargo")


def test_a_stored_refusal_is_raised(tmp_path: Path) -> None:
    _cargo(tmp_path)
    context = _context(tmp_path, undecided="set [implement] language in specweaver.toml")

    with pytest.raises(ProjectUndecidedError, match=r"set \[implement\] language"):
        run_profile(context)


def test_an_empty_root_is_refused_not_python(tmp_path: Path) -> None:
    with pytest.raises(ProjectUndecidedError, match="no build file and no code file"):
        run_profile(_context(tmp_path))


def test_a_mixed_root_is_refused_naming_both_files(tmp_path: Path) -> None:
    _cargo(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")

    with pytest.raises(
        ProjectUndecidedError, match=r"python \(pyproject\.toml\) and rust \(Cargo\.toml\)"
    ):
        run_profile(_context(tmp_path))


def test_a_bad_package_line_is_refused(tmp_path: Path) -> None:
    spec = tmp_path / "specs" / "greet_service_spec.md"
    spec.parent.mkdir()
    spec.write_text("> **Package**: ../evil\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"greet_service_spec\.md:1"):
        run_task_files(_context(tmp_path, ProjectProfile("java", "maven")))
