# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for standards/discovery.py — file discovery priority chain."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from specweaver.standards.discovery import discover_files

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Basic discovery (non-git fallback)
# ---------------------------------------------------------------------------


class TestWalkWithSkips:
    """Tests for os.walk fallback when .git/ does not exist."""

    def test_discovers_python_files(self, tmp_path: Path) -> None:
        """Should find .py files in subdirectories."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("pass")
        (tmp_path / "src" / "utils.py").write_text("pass")

        files = discover_files(tmp_path)
        py_files = [f for f in files if f.suffix == ".py"]
        assert len(py_files) == 2

    def test_skips_pycache(self, tmp_path: Path) -> None:
        """Should skip __pycache__ directories."""
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "main.cpython-313.pyc").write_text("compiled")
        (tmp_path / "main.py").write_text("pass")

        files = discover_files(tmp_path)
        rels = [str(f.relative_to(tmp_path)) for f in files]
        assert not any("__pycache__" in r for r in rels)

    def test_skips_node_modules(self, tmp_path: Path) -> None:
        """Should skip node_modules."""
        nm = tmp_path / "node_modules" / "lodash"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {};")
        (tmp_path / "app.js").write_text("const x = 1;")

        files = discover_files(tmp_path)
        rels = [str(f.relative_to(tmp_path)) for f in files]
        assert not any("node_modules" in r for r in rels)

    def test_skips_venv(self, tmp_path: Path) -> None:
        """Should skip venv and .venv directories."""
        venv = tmp_path / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "site.py").write_text("pass")
        (tmp_path / "app.py").write_text("pass")

        files = discover_files(tmp_path)
        rels = [str(f.relative_to(tmp_path)) for f in files]
        assert not any(".venv" in r for r in rels)

    def test_skips_dot_git(self, tmp_path: Path) -> None:
        """Should skip .git directory itself when walking."""
        git = tmp_path / ".git" / "objects"
        git.mkdir(parents=True)
        (git / "pack").write_text("binary")
        (tmp_path / "main.py").write_text("pass")

        files = discover_files(tmp_path)
        rels = [str(f.relative_to(tmp_path)) for f in files]
        assert not any(".git" in r for r in rels)

    def test_discovers_multiple_languages(self, tmp_path: Path) -> None:
        """Should discover files across multiple languages."""
        (tmp_path / "main.py").write_text("pass")
        (tmp_path / "app.ts").write_text("const x: number = 1;")
        (tmp_path / "index.js").write_text("module.exports = {};")

        files = discover_files(tmp_path)
        extensions = {f.suffix for f in files}
        assert ".py" in extensions
        assert ".ts" in extensions
        assert ".js" in extensions

    def test_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        """Empty directory produces no files."""
        files = discover_files(tmp_path)
        assert files == []

    def test_skips_build_and_dist(self, tmp_path: Path) -> None:
        """Should skip build/ and dist/ directories."""
        (tmp_path / "build").mkdir()
        (tmp_path / "build" / "lib.py").write_text("pass")
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist" / "app.py").write_text("pass")
        (tmp_path / "src.py").write_text("pass")

        files = discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "src.py"


# ---------------------------------------------------------------------------
# .specweaverignore
# ---------------------------------------------------------------------------


class TestSpecweaverIgnore:
    """Tests for .specweaverignore pattern filtering."""

    def test_respects_specweaverignore_patterns(self, tmp_path: Path) -> None:
        """Files matching .specweaverignore should be excluded."""
        (tmp_path / "main.py").write_text("pass")
        (tmp_path / "generated.py").write_text("pass")
        (tmp_path / ".specweaverignore").write_text("generated.py\n")

        files = discover_files(tmp_path)
        names = [f.name for f in files]
        assert "main.py" in names
        assert "generated.py" not in names

    def test_specweaverignore_glob_patterns(self, tmp_path: Path) -> None:
        """Glob patterns in .specweaverignore should work."""
        gen = tmp_path / "generated"
        gen.mkdir()
        (gen / "auto.py").write_text("pass")
        (tmp_path / "main.py").write_text("pass")
        (tmp_path / ".specweaverignore").write_text("generated/\n")

        files = discover_files(tmp_path)
        rels = [str(f.relative_to(tmp_path)) for f in files]
        assert not any("generated" in r for r in rels)

    def test_no_specweaverignore_file_is_fine(self, tmp_path: Path) -> None:
        """Missing .specweaverignore is not an error."""
        (tmp_path / "main.py").write_text("pass")
        files = discover_files(tmp_path)
        assert len(files) == 1


# ---------------------------------------------------------------------------
# Git ls-files
# ---------------------------------------------------------------------------


class TestGitLsFiles:
    """Tests for git ls-files integration (when .git/ exists)."""

    def test_git_discovered_files_respect_gitignore(
        self,
        tmp_path: Path,
    ) -> None:
        """In a git repo, gitignored files should be excluded."""
        # Initialize a real git repo
        os.system(f'git init "{tmp_path}" > nul 2>&1')
        (tmp_path / "tracked.py").write_text("pass")
        (tmp_path / ".gitignore").write_text("ignored.py\n")
        (tmp_path / "ignored.py").write_text("pass")
        os.system(
            f'cd /d "{tmp_path}" && git add tracked.py .gitignore > nul 2>&1',
        )

        files = discover_files(tmp_path)
        names = [f.name for f in files]
        assert "tracked.py" in names
        assert "ignored.py" not in names

    def test_falls_back_to_walk_when_git_unavailable(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """If git is not available, should fall back to os.walk."""
        # Create a .git dir (looks like git repo) but mock git command to fail
        (tmp_path / ".git").mkdir()
        (tmp_path / "main.py").write_text("pass")

        import subprocess

        def mock_run(*args, **kwargs):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(subprocess, "run", mock_run)

        files = discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "main.py"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestDiscoveryEdgeCases:
    """Edge cases for file discovery."""

    def test_returns_absolute_paths(self, tmp_path: Path) -> None:
        """All returned paths should be absolute."""
        (tmp_path / "main.py").write_text("pass")
        files = discover_files(tmp_path)
        assert all(f.is_absolute() for f in files)

    def test_returns_only_files_not_directories(self, tmp_path: Path) -> None:
        """Should never include directories in results."""
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "main.py").write_text("pass")

        files = discover_files(tmp_path)
        assert all(f.is_file() for f in files)

    def test_deeply_nested_files(self, tmp_path: Path) -> None:
        """Should discover files in deeply nested structures."""
        deep = tmp_path / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / "deep.py").write_text("pass")

        files = discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "deep.py"

    def test_result_is_sorted(self, tmp_path: Path) -> None:
        """discover_files() must return a sorted list."""
        for name in ("z.py", "a.py", "m.py"):
            (tmp_path / name).write_text("pass")

        files = discover_files(tmp_path)
        assert files == sorted(files)

    def test_skips_all_dot_directories(self, tmp_path: Path) -> None:
        """Any directory starting with '.' should be skipped by the walker."""
        hidden = tmp_path / ".hidden_dir"
        hidden.mkdir()
        (hidden / "secret.py").write_text("pass")
        (tmp_path / "visible.py").write_text("pass")

        files = discover_files(tmp_path)
        names = [f.name for f in files]
        assert "secret.py" not in names
        assert "visible.py" in names

    def test_skips_ruff_cache_and_nox(self, tmp_path: Path) -> None:
        """Ensure .ruff_cache and .nox are in _SKIP_DIRS and pruned."""
        for dirname in (".ruff_cache", ".nox"):
            d = tmp_path / dirname
            d.mkdir()
            (d / "file.py").write_text("pass")
        (tmp_path / "real.py").write_text("pass")

        files = discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "real.py"


# ---------------------------------------------------------------------------
# _git_ls_files — isolated scenarios
# ---------------------------------------------------------------------------


class TestGitLsFilesIsolated:
    """Test _git_ls_files edge cases via monkeypatching subprocess."""

    def test_git_nonzero_exit_returns_none(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """git ls-files exits non-zero → returns None, falls back to walk."""
        import subprocess as sp

        (tmp_path / ".git").mkdir()
        (tmp_path / "main.py").write_text("pass")

        def mock_run(*_args, **_kw):
            result = sp.CompletedProcess(args=[], returncode=128, stdout="", stderr="")
            return result

        monkeypatch.setattr(sp, "run", mock_run)

        # discover_files should fall back to walk
        files = discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "main.py"

    def test_git_timeout_returns_none(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """git ls-files times out → falls back to walk."""
        import subprocess as sp

        (tmp_path / ".git").mkdir()
        (tmp_path / "main.py").write_text("pass")

        def mock_run(*_args, **_kw):
            raise sp.TimeoutExpired(cmd="git", timeout=30)

        monkeypatch.setattr(sp, "run", mock_run)

        # After fix: TimeoutExpired is now caught → falls back to walk
        files = discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "main.py"

    def test_git_oserror_returns_none(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """git raises OSError (e.g. permission denied) → returns None."""
        import subprocess as sp

        (tmp_path / ".git").mkdir()
        (tmp_path / "main.py").write_text("pass")

        def mock_run(*_args, **_kw):
            raise OSError("Permission denied")

        monkeypatch.setattr(sp, "run", mock_run)

        files = discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "main.py"

    def test_git_output_with_deleted_file(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """git ls-files reports a file that no longer exists → skipped."""
        import subprocess as sp

        (tmp_path / ".git").mkdir()
        (tmp_path / "exists.py").write_text("pass")
        # Don't create "deleted.py" — git reports it but it's gone

        def mock_run(*_args, **_kw):
            return sp.CompletedProcess(
                args=[],
                returncode=0,
                stdout="exists.py\ndeleted.py\n",
                stderr="",
            )

        monkeypatch.setattr(sp, "run", mock_run)

        files = discover_files(tmp_path)
        names = [f.name for f in files]
        assert "exists.py" in names
        assert "deleted.py" not in names

    def test_git_output_with_blank_lines(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Blank lines in git ls-files output are ignored."""
        import subprocess as sp

        (tmp_path / ".git").mkdir()
        (tmp_path / "main.py").write_text("pass")

        def mock_run(*_args, **_kw):
            return sp.CompletedProcess(
                args=[],
                returncode=0,
                stdout="\n  \nmain.py\n\n",
                stderr="",
            )

        monkeypatch.setattr(sp, "run", mock_run)

        files = discover_files(tmp_path)
        assert len(files) == 1

    def test_git_success_returns_resolved_paths(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Successful git ls-files returns resolved absolute paths."""
        import subprocess as sp

        (tmp_path / ".git").mkdir()
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "app.py").write_text("pass")

        def mock_run(*_args, **_kw):
            return sp.CompletedProcess(
                args=[],
                returncode=0,
                stdout="src/app.py\n",
                stderr="",
            )

        monkeypatch.setattr(sp, "run", mock_run)

        files = discover_files(tmp_path)
        assert len(files) == 1
        assert files[0].is_absolute()
        assert files[0].name == "app.py"


# ---------------------------------------------------------------------------
# _apply_specweaverignore — isolated scenarios
# ---------------------------------------------------------------------------


class TestApplySpecweaverignoreIsolated:
    """Test .specweaverignore edge cases."""

    def test_pathspec_not_installed_returns_files_unchanged(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """If pathspec is not installed, files are returned unfiltered."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pathspec":
                raise ImportError("No module named 'pathspec'")
            return original_import(name, *args, **kwargs)

        (tmp_path / "main.py").write_text("pass")
        (tmp_path / "generated.py").write_text("pass")
        (tmp_path / ".specweaverignore").write_text("generated.py\n")

        monkeypatch.setattr(builtins, "__import__", mock_import)

        files = discover_files(tmp_path)
        names = [f.name for f in files]
        # Both should be included since pathspec can't filter
        assert "main.py" in names
        assert "generated.py" in names

    def test_file_outside_project_root_is_kept(
        self,
        tmp_path: Path,
    ) -> None:
        """Files not relative to project root survive the filter (ValueError)."""

        from specweaver.standards.discovery import _apply_specweaverignore

        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".specweaverignore").write_text("*.log\n")

        # An external file that can't be made relative to project_root
        external = tmp_path / "external.py"
        external.write_text("pass")

        # Internal file
        internal = project_root / "main.py"
        internal.write_text("pass")

        result = _apply_specweaverignore(
            [external.resolve(), internal.resolve()],
            project_root,
        )
        names = [f.name for f in result]
        assert "external.py" in names
        assert "main.py" in names

    def test_specweaverignore_with_directory_pattern(
        self,
        tmp_path: Path,
    ) -> None:
        """Directory glob patterns in .specweaverignore work."""
        gen = tmp_path / "generated"
        gen.mkdir()
        (gen / "auto.py").write_text("pass")
        (gen / "manual.py").write_text("pass")
        (tmp_path / "main.py").write_text("pass")
        (tmp_path / ".specweaverignore").write_text("generated/**\n")

        files = discover_files(tmp_path)
        names = [f.name for f in files]
        assert "main.py" in names
        assert "auto.py" not in names
        assert "manual.py" not in names

    def test_specweaverignore_negation_pattern(
        self,
        tmp_path: Path,
    ) -> None:
        """Negation patterns (!pattern) should re-include files."""
        (tmp_path / "a.log").write_text("log")
        (tmp_path / "important.log").write_text("keep")
        (tmp_path / "main.py").write_text("pass")
        (tmp_path / ".specweaverignore").write_text(
            "*.log\n!important.log\n",
        )

        files = discover_files(tmp_path)
        names = [f.name for f in files]
        assert "main.py" in names
        assert "a.log" not in names
        assert "important.log" in names
