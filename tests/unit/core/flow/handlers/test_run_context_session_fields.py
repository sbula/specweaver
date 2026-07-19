# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C-EXEC-06 SF-01 (T1): RunContext gains allowed_paths + session_isolation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from specweaver.core.flow.handlers.base import RunContext

if TYPE_CHECKING:
    from pathlib import Path


def _ctx(tmp_path: Path, **kw) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "s.md", **kw)


# --- Happy / defaults -----------------------------------------------------


def test_defaults(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    assert ctx.allowed_paths == []
    assert ctx.session_isolation is False


def test_explicit_values(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, allowed_paths=["src/foo.py", "tests/test_foo.py"], session_isolation=True)
    assert ctx.allowed_paths == ["src/foo.py", "tests/test_foo.py"]
    assert ctx.session_isolation is True


# --- Boundary -------------------------------------------------------------


def test_allowed_paths_is_independent_per_instance(tmp_path: Path) -> None:
    """default_factory list must not be shared across instances."""
    a = _ctx(tmp_path)
    a.allowed_paths.append("src/x.py")
    b = _ctx(tmp_path)
    assert b.allowed_paths == []


# --- Hostile / wrong input ------------------------------------------------


def test_session_isolation_wrong_type_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        _ctx(tmp_path, session_isolation="yes-please")


def test_allowed_paths_wrong_type_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        _ctx(tmp_path, allowed_paths="src/foo.py")  # a bare str, not a list
