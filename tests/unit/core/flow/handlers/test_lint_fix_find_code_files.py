# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-03 SF-02 (T1): LintFixHandler._find_code_files honors an explicit target.

The Phase-2 LLM reflection loop needs to locate the code file to fix. `sw implement`
leaves ``output_dir`` unset, so the finder must accept the explicit ``params["target"]``
(the generated ``src/<stem>.py``); otherwise it falls back to the legacy output_dir glob.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.lint_fix import LintFixHandler

if TYPE_CHECKING:
    from pathlib import Path


# --- Happy path -----------------------------------------------------------


def test_explicit_target_file_returns_that_file(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "greeter.py").write_text("x = 1\n")
    (src / "decoy.py").write_text("y = 2\n")  # a glob would also grab this
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "s.md", output_dir=src)

    files = LintFixHandler()._find_code_files(ctx, "src/greeter.py")
    assert [f.name for f in files] == ["greeter.py"]


# --- Boundary / backward-compatible fallback ------------------------------


def test_no_target_uses_output_dir_glob(tmp_path: Path) -> None:
    out = tmp_path / "output"
    out.mkdir()
    (out / "only.py").write_text("x = 1\n")
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "s.md", output_dir=out)

    files = LintFixHandler()._find_code_files(ctx, None)
    assert [f.name for f in files] == ["only.py"]


def test_directory_target_falls_back_to_output_dir_glob(tmp_path: Path) -> None:
    """A directory target (e.g. the default "src/") is not a file → glob fallback."""
    out = tmp_path / "output"
    out.mkdir()
    (out / "only.py").write_text("x = 1\n")
    (tmp_path / "src").mkdir()
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "s.md", output_dir=out)

    files = LintFixHandler()._find_code_files(ctx, "src/")
    assert [f.name for f in files] == ["only.py"]


# --- Graceful degradation -------------------------------------------------


def test_missing_target_and_no_output_dir_returns_empty(tmp_path: Path) -> None:
    ctx = SimpleNamespace(project_path=tmp_path, output_dir=None)
    files = LintFixHandler()._find_code_files(ctx, "src/nope.py")
    assert files == []


# --- Hostile / wrong input ------------------------------------------------


def test_path_traversal_target_not_resolved_outside_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "secret.py"
    outside.write_text("secret = 1\n")
    ctx = SimpleNamespace(project_path=project, output_dir=None)

    files = LintFixHandler()._find_code_files(ctx, "../secret.py")
    assert files == []


def test_target_set_but_no_project_path_falls_back_to_glob(tmp_path: Path) -> None:
    """[Boundary] project_path falsy → the target branch is skipped → output_dir glob."""
    out = tmp_path / "output"
    out.mkdir()
    (out / "only.py").write_text("x = 1\n")
    ctx = SimpleNamespace(project_path=None, output_dir=out)

    files = LintFixHandler()._find_code_files(ctx, "src/only.py")
    assert [f.name for f in files] == ["only.py"]


def test_missing_file_target_falls_back_to_glob(tmp_path: Path) -> None:
    """[Graceful degradation] an explicit file target that doesn't exist falls back to
    the output_dir glob (lint still runs on whatever code is present) — unlike code
    validation, lint is happy to lint the available files."""
    out = tmp_path / "output"
    out.mkdir()
    (out / "only.py").write_text("x = 1\n")
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "s.md", output_dir=out)

    files = LintFixHandler()._find_code_files(ctx, "src/does_not_exist.py")
    assert [f.name for f in files] == ["only.py"]
