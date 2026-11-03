# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run's language: the one named, else the one the project's manifests show.

Proves: TECH-082 FR-3

The task-file code no longer detects; every caller asks here, so the API and the `sw implement`
CLI, which may not import `sandbox`, get the same answer as the flow handlers.

| Bucket | Case |
|---|---|
| Happy | a named language comes back as is; no name in a Cargo project → `rust`; the task files follow it |
| Boundary | no name and no manifest → the detector's default, `python` |
| Degradation | a project folder that does not exist → `python`, not an error |
| Hostile | an empty name counts as no name, never as a language called `""`; a bad `Package` line is refused |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.run_language import run_language, run_task_files
from specweaver.core.flow.run_state.run_context import IsolationPolicy, RunContext

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("language", ["python", "java", "kotlin", "typescript", "rust"])
def test_a_named_language_comes_back(tmp_path: Path, language: str) -> None:
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "greet"\n', encoding="utf-8")

    assert run_language(tmp_path, language) == language


def test_no_name_in_a_cargo_project_is_rust(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "greet"\n', encoding="utf-8")

    assert run_language(tmp_path, None) == "rust"


def test_no_name_and_no_manifest_is_python(tmp_path: Path) -> None:
    assert run_language(tmp_path, None) == "python"


def test_a_missing_folder_is_python(tmp_path: Path) -> None:
    assert run_language(tmp_path / "absent", None) == "python"


def test_an_empty_name_is_no_name(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "greet"\n', encoding="utf-8")

    assert run_language(tmp_path, "") == "rust"


def _context(root: Path, language: str | None) -> RunContext:
    return RunContext(
        project_path=root,
        spec_path=root / "specs" / "greet_service_spec.md",
        isolation=IsolationPolicy(language=language),
    )


def test_the_task_files_follow_the_named_language(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "greet"\n', encoding="utf-8")

    assert run_task_files(_context(tmp_path, "typescript")).code == "src/greet_service.ts"


def test_the_task_files_follow_the_manifests_without_a_name(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "greet"\n', encoding="utf-8")

    assert run_task_files(_context(tmp_path, None)).code == "src/greet_service.rs"


def test_a_bad_package_line_is_refused(tmp_path: Path) -> None:
    spec = tmp_path / "specs" / "greet_service_spec.md"
    spec.parent.mkdir()
    spec.write_text("> **Package**: ../evil\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"greet_service_spec\.md:1"):
        run_task_files(_context(tmp_path, "java"))
