# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which files get to teach the agent what this project's conventions are.

Proves: E-VAL-02 FR-1
Proves: TECH-087 FR-16

Cited under `specweaver-dev` §3.2c, from `INT-US-01-SF03-MIG`. `E-VAL-02` shipped with an
implementation plan and no design document, so no requirement of it existed in the ledger's form.

Mutant: `.specweaverignore` no longer applied — **41 test files fail**, the widest in this capability.
The discovery set swells with everything the project deliberately excluded, and vendored or generated
code starts voting on the conventions the agent will imitate. Discovery is upstream of every other FR
here, and the blast radius says so.

Previously documented here:

Standards discovery, and the exclusions it must honour before touching disk.

Proves: C-SENS-02 FR-5

Cited from `INT-US-05-SF03-MIG`. Mutant-verified: dropping the `_apply_specweaverignore` call from
discovery — so excluded files are walked and read anyway — fails 4 tests.

FR-5's claim is interception *before deep I/O*, which is a performance and token-context property as
much as a correctness one: the files are still findable, they simply must not be opened.
"""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

from specweaver.assurance.standards.discovery import discover_files
from specweaver.workspace.analyzers.factory import AnalyzerFactory

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

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

        files = discover_files(tmp_path, AnalyzerFactory)
        py_files = [f for f in files if f.suffix == ".py"]
        assert len(py_files) == 2

    def test_skips_pycache(self, tmp_path: Path) -> None:
        """Should skip __pycache__ directories."""
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "main.cpython-313.pyc").write_text("compiled")
        (tmp_path / "main.py").write_text("pass")

        files = discover_files(tmp_path, AnalyzerFactory)
        rels = [str(f.relative_to(tmp_path)) for f in files]
        assert not any("__pycache__" in r for r in rels)

    def test_skips_node_modules(self, tmp_path: Path) -> None:
        """Should skip node_modules."""
        nm = tmp_path / "node_modules" / "lodash"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {};")
        (tmp_path / "app.js").write_text("const x = 1;")

        files = discover_files(tmp_path, AnalyzerFactory)
        rels = [str(f.relative_to(tmp_path)) for f in files]
        assert not any("node_modules" in r for r in rels)

    def test_skips_venv(self, tmp_path: Path) -> None:
        """Should skip venv and .venv directories."""
        venv = tmp_path / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "site.py").write_text("pass")
        (tmp_path / "app.py").write_text("pass")

        files = discover_files(tmp_path, AnalyzerFactory)
        rels = [str(f.relative_to(tmp_path)) for f in files]
        assert not any(".venv" in r for r in rels)

    def test_skips_dot_git(self, tmp_path: Path) -> None:
        """Should skip .git directory itself when walking."""
        git = tmp_path / ".git" / "objects"
        git.mkdir(parents=True)
        (git / "pack").write_text("binary")
        (tmp_path / "main.py").write_text("pass")

        files = discover_files(tmp_path, AnalyzerFactory)
        rels = [str(f.relative_to(tmp_path)) for f in files]
        assert not any(".git" in r for r in rels)

    def test_discovers_multiple_languages(self, tmp_path: Path) -> None:
        """Should discover files across multiple languages."""
        (tmp_path / "main.py").write_text("pass")
        (tmp_path / "app.ts").write_text("const x: number = 1;")
        (tmp_path / "index.js").write_text("module.exports = {};")

        files = discover_files(tmp_path, AnalyzerFactory)
        extensions = {f.suffix for f in files}
        assert ".py" in extensions
        assert ".ts" in extensions
        assert ".js" in extensions

    def test_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        """Empty directory produces no files."""
        files = discover_files(tmp_path, AnalyzerFactory)
        assert files == []

    def test_skips_build_and_dist(self, tmp_path: Path) -> None:
        """Should skip build/ and dist/ directories."""
        (tmp_path / "build").mkdir()
        (tmp_path / "build" / "lib.py").write_text("pass")
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist" / "app.py").write_text("pass")
        (tmp_path / "src.py").write_text("pass")

        files = discover_files(tmp_path, AnalyzerFactory)
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

        files = discover_files(tmp_path, AnalyzerFactory)
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

        files = discover_files(tmp_path, AnalyzerFactory)
        rels = [str(f.relative_to(tmp_path)) for f in files]
        assert not any("generated" in r for r in rels)

    def test_no_specweaverignore_file_is_fine(self, tmp_path: Path) -> None:
        """Missing .specweaverignore is not an error."""
        (tmp_path / "main.py").write_text("pass")
        files = discover_files(tmp_path, AnalyzerFactory)
        assert len(files) == 1


# ---------------------------------------------------------------------------
# Git ls-files
# ---------------------------------------------------------------------------


class TestGitignore:
    """The project's `.gitignore` files, root and nested, decide what is skipped (TECH-087 FR-16).

    | Bucket | Case |
    |---|---|
    | Happy | a root pattern hides a file anywhere below it |
    | Boundary | a nested file applies only under its own folder; `/x` anchors to that folder; `!` re-includes; an ignored folder is not entered |
    | Degradation | a `.gitignore` that cannot be read is skipped with a warning |
    | Hostile | a `.git` folder and a broken `git` change nothing: no process runs |
    """

    @staticmethod
    def _found(root: Path) -> set[str]:
        return {
            p.relative_to(root.resolve()).as_posix() for p in discover_files(root, AnalyzerFactory)
        }

    @staticmethod
    def _write(root: Path, files: dict[str, str]) -> None:
        for rel, body in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(body, encoding="utf-8")

    def test_a_root_pattern_hides_matching_files_at_any_depth(self, tmp_path: Path) -> None:
        self._write(tmp_path, {".gitignore": "*.log\n", "a.py": "", "a.log": "", "d/b.log": ""})

        assert self._found(tmp_path) == {".gitignore", "a.py"}

    def test_a_nested_file_applies_only_under_its_folder(self, tmp_path: Path) -> None:
        self._write(tmp_path, {"pkg/.gitignore": "gen.py\n", "gen.py": "", "pkg/gen.py": ""})

        assert self._found(tmp_path) == {"pkg/.gitignore", "gen.py"}

    def test_a_leading_slash_anchors_to_the_folder_of_its_file(self, tmp_path: Path) -> None:
        self._write(
            tmp_path, {"pkg/.gitignore": "/local.py\n", "pkg/local.py": "", "pkg/sub/local.py": ""}
        )

        assert self._found(tmp_path) == {"pkg/.gitignore", "pkg/sub/local.py"}

    def test_a_nested_negation_re_includes_a_file(self, tmp_path: Path) -> None:
        self._write(
            tmp_path,
            {
                ".gitignore": "*.log\n",
                "pkg/.gitignore": "!keep.log\n",
                "pkg/keep.log": "",
                "x.log": "",
            },
        )

        assert self._found(tmp_path) == {".gitignore", "pkg/.gitignore", "pkg/keep.log"}

    def test_an_ignored_folder_is_not_entered(self, tmp_path: Path) -> None:
        self._write(
            tmp_path,
            {".gitignore": "out/\n!out/a.py\n", "out/a.py": "", "out/.gitignore": "!a.py\n"},
        )

        assert self._found(tmp_path) == {".gitignore"}

    def test_an_unreadable_gitignore_is_skipped_with_a_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        self._write(tmp_path, {"a.py": "", "pkg/b.py": ""})
        (tmp_path / "pkg" / ".gitignore").write_bytes(b"\xff\xfe\x00not utf-8 b.py\n")

        with caplog.at_level(logging.WARNING):
            found = self._found(tmp_path)

        assert found == {"a.py", "pkg/.gitignore", "pkg/b.py"}
        assert any("pkg/.gitignore" in r.getMessage().replace("\\", "/") for r in caplog.records)

    def test_no_process_runs_even_in_a_git_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(*args: object, **kwargs: object) -> None:
            raise AssertionError(f"a process was started: {args}")

        monkeypatch.setattr(subprocess, "Popen", refuse)
        monkeypatch.setattr(subprocess, "run", refuse)
        (tmp_path / ".git").mkdir()
        self._write(tmp_path, {".gitignore": "skip.py\n", "main.py": "", "skip.py": ""})

        assert self._found(tmp_path) == {".gitignore", "main.py"}

    def test_the_module_does_not_import_subprocess(self) -> None:
        import ast
        import inspect

        from specweaver.assurance.standards import discovery

        tree = ast.parse(inspect.getsource(discovery))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in node.names
        } | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}

        assert "subprocess" not in imported


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestDiscoveryEdgeCases:
    """Edge cases for file discovery."""

    def test_returns_absolute_paths(self, tmp_path: Path) -> None:
        """All returned paths should be absolute."""
        (tmp_path / "main.py").write_text("pass")
        files = discover_files(tmp_path, AnalyzerFactory)
        assert all(f.is_absolute() for f in files)

    def test_returns_only_files_not_directories(self, tmp_path: Path) -> None:
        """Should never include directories in results."""
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "main.py").write_text("pass")

        files = discover_files(tmp_path, AnalyzerFactory)
        assert all(f.is_file() for f in files)

    def test_deeply_nested_files(self, tmp_path: Path) -> None:
        """Should discover files in deeply nested structures."""
        deep = tmp_path / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / "deep.py").write_text("pass")

        files = discover_files(tmp_path, AnalyzerFactory)
        assert len(files) == 1
        assert files[0].name == "deep.py"

    def test_result_is_sorted(self, tmp_path: Path) -> None:
        """discover_files() must return a sorted list."""
        for name in ("z.py", "a.py", "m.py"):
            (tmp_path / name).write_text("pass")

        files = discover_files(tmp_path, AnalyzerFactory)
        assert files == sorted(files)

    def test_skips_all_dot_directories(self, tmp_path: Path) -> None:
        """Any directory starting with '.' should be skipped by the walker."""
        hidden = tmp_path / ".hidden_dir"
        hidden.mkdir()
        (hidden / "secret.py").write_text("pass")
        (tmp_path / "visible.py").write_text("pass")

        files = discover_files(tmp_path, AnalyzerFactory)
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

        files = discover_files(tmp_path, AnalyzerFactory)
        assert len(files) == 1
        assert files[0].name == "real.py"


# ---------------------------------------------------------------------------
# _apply_specweaverignore — isolated scenarios
# ---------------------------------------------------------------------------


class TestApplySpecweaverignoreIsolated:
    """Test .specweaverignore edge cases."""

    def test_file_outside_project_root_is_kept(
        self,
        tmp_path: Path,
    ) -> None:
        """Files not relative to project root survive the filter (ValueError)."""

        from specweaver.assurance.standards.discovery import _apply_specweaverignore

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
            AnalyzerFactory,
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

        files = discover_files(tmp_path, AnalyzerFactory)
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

        files = discover_files(tmp_path, AnalyzerFactory)
        names = [f.name for f in files]
        assert "main.py" in names
        assert "a.log" not in names
        assert "important.log" in names
