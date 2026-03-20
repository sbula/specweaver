# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for standards/discovery.py — file discovery priority chain."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specweaver.standards.discovery import discover_files


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
        self, tmp_path: Path,
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
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        """If git is not available, should fall back to os.walk."""
        # Create a .git dir (looks like git repo) but mock git command to fail
        (tmp_path / ".git").mkdir()
        (tmp_path / "main.py").write_text("pass")

        import subprocess

        original_run = subprocess.run

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
