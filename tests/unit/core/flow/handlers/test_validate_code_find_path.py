# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-03 SF-01 (T1): ValidateCodeHandler._find_code_path honors params['target'].

An explicit ``target`` in the step params is authoritative — it points the code
validation at a specific generated file (``src/<stem>.py``) rather than the
``output_dir`` glob, which returns an arbitrary first file. When no target is set,
the existing ``output_dir`` glob behavior is preserved (backward compatible).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.validation import ValidateCodeHandler

if TYPE_CHECKING:
    from pathlib import Path


def _step(target: str | None = None) -> PipelineStep:
    params = {"target": target} if target is not None else {}
    return PipelineStep(
        name="validate_code",
        action=StepAction.VALIDATE,
        target=StepTarget.CODE,
        params=params,
    )


# --- Happy path -----------------------------------------------------------


def test_explicit_target_returns_that_file(tmp_path: Path) -> None:
    spec = tmp_path / "greeter_spec.md"
    spec.write_text("# spec\n")
    src = tmp_path / "src"
    src.mkdir()
    (src / "greeter.py").write_text("x = 1\n")
    # A decoy file that the old glob-first-match could wrongly pick.
    (src / "aaa_decoy.py").write_text("y = 2\n")

    ctx = RunContext(project_path=tmp_path, spec_path=spec, output_dir=src)
    handler = ValidateCodeHandler()

    found = handler._find_code_path(_step("src/greeter.py"), ctx)
    assert found is not None
    assert found.name == "greeter.py"


# --- Boundary / backward-compatible fallback ------------------------------


def test_no_target_falls_back_to_output_dir_glob(tmp_path: Path) -> None:
    spec = tmp_path / "s_spec.md"
    spec.write_text("# spec\n")
    src = tmp_path / "src"
    src.mkdir()
    (src / "only.py").write_text("x = 1\n")

    ctx = RunContext(project_path=tmp_path, spec_path=spec, output_dir=src)
    handler = ValidateCodeHandler()

    found = handler._find_code_path(_step(None), ctx)
    assert found is not None
    assert found.name == "only.py"


def test_no_target_no_output_dir_returns_none(tmp_path: Path) -> None:
    spec = tmp_path / "s_spec.md"
    spec.write_text("# spec\n")
    ctx = RunContext(project_path=tmp_path, spec_path=spec, output_dir=None)
    handler = ValidateCodeHandler()
    assert handler._find_code_path(_step(None), ctx) is None


# --- Graceful degradation -------------------------------------------------


def test_explicit_target_missing_file_returns_none(tmp_path: Path) -> None:
    """An explicit target is authoritative: if it doesn't exist, do NOT silently
    fall back to an arbitrary output_dir file — return None (→ 'no code' path)."""
    spec = tmp_path / "s_spec.md"
    spec.write_text("# spec\n")
    src = tmp_path / "src"
    src.mkdir()
    (src / "unrelated.py").write_text("x = 1\n")  # would be picked by a glob fallback

    ctx = RunContext(project_path=tmp_path, spec_path=spec, output_dir=src)
    handler = ValidateCodeHandler()

    assert handler._find_code_path(_step("src/does_not_exist.py"), ctx) is None


def test_explicit_target_pointing_at_dir_returns_none(tmp_path: Path) -> None:
    spec = tmp_path / "s_spec.md"
    spec.write_text("# spec\n")
    (tmp_path / "src").mkdir()
    ctx = RunContext(project_path=tmp_path, spec_path=spec)
    handler = ValidateCodeHandler()
    assert handler._find_code_path(_step("src"), ctx) is None


# --- Hostile / wrong input ------------------------------------------------


def test_path_traversal_target_returns_none(tmp_path: Path) -> None:
    """A target escaping the project root must not resolve to an outside file."""
    project = tmp_path / "project"
    project.mkdir()
    spec = project / "s_spec.md"
    spec.write_text("# spec\n")
    # A real file outside the project that a traversal string would reach.
    outside = tmp_path / "secret.py"
    outside.write_text("secret = 1\n")

    ctx = RunContext(project_path=project, spec_path=spec)
    handler = ValidateCodeHandler()

    assert handler._find_code_path(_step("../secret.py"), ctx) is None


def test_target_set_but_no_project_path_falls_back_to_glob(tmp_path: Path) -> None:
    """[Boundary] The ``and context.project_path`` guard: when project_path is falsy,
    an explicit target cannot be resolved, so the legacy output_dir glob is used.
    Uses a lightweight fake context because RunContext.project_path is a required Path."""
    from types import SimpleNamespace

    src = tmp_path / "src"
    src.mkdir()
    (src / "only.py").write_text("x = 1\n")

    ctx = SimpleNamespace(project_path=None, output_dir=src)
    handler = ValidateCodeHandler()

    found = handler._find_code_path(_step("src/only.py"), ctx)
    assert found is not None
    assert found.name == "only.py"


def test_empty_string_target_falls_back_to_glob(tmp_path: Path) -> None:
    """[Boundary] An empty-string target is falsy (like None) → the guard is not
    taken and the legacy output_dir glob is used (not treated as project root)."""
    spec = tmp_path / "s_spec.md"
    spec.write_text("# spec\n")
    src = tmp_path / "src"
    src.mkdir()
    (src / "only.py").write_text("x = 1\n")

    ctx = RunContext(project_path=tmp_path, spec_path=spec, output_dir=src)
    handler = ValidateCodeHandler()

    found = handler._find_code_path(_step(""), ctx)
    assert found is not None
    assert found.name == "only.py"
