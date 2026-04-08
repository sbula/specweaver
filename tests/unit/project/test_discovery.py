# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for specweaver.project.discovery — TDD (tests first)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.project.discovery import resolve_project_path

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestResolveProjectPath:
    """Test project path resolution from flag, env var, or default."""

    def test_from_explicit_path(self, tmp_path: Path) -> None:
        """Explicit --project flag path is used as-is."""
        result = resolve_project_path(project_arg=str(tmp_path))
        assert result == tmp_path.resolve()

    def test_from_env_var(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """SW_PROJECT env var is used when no --project flag."""
        monkeypatch.setenv("SW_PROJECT", str(tmp_path))
        result = resolve_project_path(project_arg=None)
        assert result == tmp_path.resolve()

    def test_explicit_overrides_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Explicit --project flag takes precedence over SW_PROJECT env var."""
        other = tmp_path / "other"
        other.mkdir()
        monkeypatch.setenv("SW_PROJECT", str(tmp_path))
        result = resolve_project_path(project_arg=str(other))
        assert result == other.resolve()

    def test_defaults_to_cwd(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """When neither flag nor env var is set, default to cwd."""
        monkeypatch.delenv("SW_PROJECT", raising=False)
        monkeypatch.chdir(tmp_path)
        result = resolve_project_path(project_arg=None)
        assert result == tmp_path.resolve()

    def test_relative_path_is_resolved(self, tmp_path: Path) -> None:
        """Relative paths are resolved to absolute."""
        sub = tmp_path / "sub"
        sub.mkdir()
        # Pass relative path
        result = resolve_project_path(project_arg="sub", cwd=tmp_path)
        assert result == sub.resolve()
        assert result.is_absolute()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestResolveProjectPathEdgeCases:
    """Edge cases for project path resolution."""

    def test_nonexistent_path_raises(self) -> None:
        """Path that doesn't exist raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="does not exist"):
            resolve_project_path(project_arg="/nonexistent/path/xyz123")

    def test_file_not_directory_raises(self, tmp_path: Path) -> None:
        """Path that points to a file (not dir) raises NotADirectoryError."""
        f = tmp_path / "somefile.txt"
        f.write_text("hello")
        with pytest.raises(NotADirectoryError, match="not a directory"):
            resolve_project_path(project_arg=str(f))

    def test_path_with_spaces(self, tmp_path: Path) -> None:
        """Paths with spaces are handled correctly."""
        spaced = tmp_path / "my project dir"
        spaced.mkdir()
        result = resolve_project_path(project_arg=str(spaced))
        assert result == spaced.resolve()
        assert result.exists()

    def test_path_with_unicode(self, tmp_path: Path) -> None:
        """Paths with unicode characters are handled correctly."""
        unicode_dir = tmp_path / "项目_données_αβγ"
        unicode_dir.mkdir()
        result = resolve_project_path(project_arg=str(unicode_dir))
        assert result == unicode_dir.resolve()

    def test_env_var_nonexistent_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SW_PROJECT pointing to nonexistent dir raises FileNotFoundError."""
        monkeypatch.setenv("SW_PROJECT", "/nonexistent/env/path")
        with pytest.raises(FileNotFoundError, match="does not exist"):
            resolve_project_path(project_arg=None)

    def test_env_var_is_file_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """SW_PROJECT pointing to a file raises NotADirectoryError."""
        f = tmp_path / "not_a_dir.txt"
        f.write_text("hi")
        monkeypatch.setenv("SW_PROJECT", str(f))
        with pytest.raises(NotADirectoryError, match="not a directory"):
            resolve_project_path(project_arg=None)
