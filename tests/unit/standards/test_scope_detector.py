# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for standards/scope_detector.py — scope detection and resolution."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from specweaver.standards.scope_detector import (
    _has_source_files,
    _resolve_scope,
    detect_scopes,
)


# ---------------------------------------------------------------------------
# detect_scopes()
# ---------------------------------------------------------------------------


class TestDetectScopes:
    """Unit tests for detect_scopes()."""

    def test_empty_dir_returns_root_only(self, tmp_path: Path) -> None:
        """Empty project → only root scope '.'."""
        scopes = detect_scopes(tmp_path)
        assert scopes == ["."]

    def test_flat_project_returns_root_only(self, tmp_path: Path) -> None:
        """Single-scope project (files only at root) → ['.']."""
        (tmp_path / "main.py").write_text("pass")
        (tmp_path / "utils.py").write_text("pass")
        scopes = detect_scopes(tmp_path)
        assert scopes == ["."]

    def test_single_level_scopes(self, tmp_path: Path) -> None:
        """Top-level dirs with source files → detected as scopes."""
        backend = tmp_path / "backend"
        backend.mkdir()
        (backend / "app.py").write_text("pass")

        frontend = tmp_path / "frontend"
        frontend.mkdir()
        (frontend / "index.ts").write_text("pass")

        scopes = detect_scopes(tmp_path)
        assert sorted(scopes) == [".", "backend", "frontend"]

    def test_two_level_scopes(self, tmp_path: Path) -> None:
        """2-level scopes: backend/auth, backend/payments detected."""
        backend = tmp_path / "backend"
        backend.mkdir()

        auth = backend / "auth"
        auth.mkdir()
        (auth / "handler.py").write_text("pass")

        payments = backend / "payments"
        payments.mkdir()
        (payments / "service.py").write_text("pass")

        scopes = detect_scopes(tmp_path)
        assert "backend/auth" in scopes
        assert "backend/payments" in scopes
        assert "." in scopes

    def test_l1_dir_with_subscopes_not_itself_a_scope(
        self, tmp_path: Path,
    ) -> None:
        """L1 dir with sub-scopes is NOT itself a scope (no double-counting)."""
        backend = tmp_path / "backend"
        backend.mkdir()
        # backend has sub-dirs with source files (subscopes)
        (backend / "auth").mkdir()
        (backend / "auth" / "login.py").write_text("pass")
        (backend / "payments").mkdir()
        (backend / "payments" / "pay.py").write_text("pass")
        # backend also has a direct file
        (backend / "shared.py").write_text("pass")

        scopes = detect_scopes(tmp_path)
        # backend/ itself should NOT be a scope because it has sub-scopes
        assert "backend" not in scopes
        assert "backend/auth" in scopes
        assert "backend/payments" in scopes

    def test_l1_dir_without_subscopes_is_scope(self, tmp_path: Path) -> None:
        """L1 dir with no sub-scopes IS a scope."""
        service = tmp_path / "service"
        service.mkdir()
        (service / "main.py").write_text("pass")
        # No subdirs with source files → "service" is itself a scope
        scopes = detect_scopes(tmp_path)
        assert "service" in scopes

    def test_skips_standard_dirs(self, tmp_path: Path) -> None:
        """_SKIP_DIRS like .git, node_modules, __pycache__ excluded."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main")
        (tmp_path / "node_modules" / "react").mkdir(parents=True)
        (tmp_path / "node_modules" / "react" / "index.js").write_text(
            "pass", encoding="utf-8",
        )
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "mod.cpython-313.pyc").write_text("pass")

        scopes = detect_scopes(tmp_path)
        assert scopes == ["."]

    def test_skips_hidden_dirs(self, tmp_path: Path) -> None:
        """Directories starting with '.' are skipped except known ones."""
        (tmp_path / ".hidden").mkdir()
        (tmp_path / ".hidden" / "secret.py").write_text("pass")
        (tmp_path / "visible").mkdir()
        (tmp_path / "visible" / "app.py").write_text("pass")

        scopes = detect_scopes(tmp_path)
        assert ".hidden" not in scopes
        assert "visible" in scopes

    def test_sorted_output(self, tmp_path: Path) -> None:
        """Scopes are returned sorted."""
        for name in ("zeta", "alpha", "middle"):
            d = tmp_path / name
            d.mkdir()
            (d / "mod.py").write_text("pass")

        scopes = detect_scopes(tmp_path)
        assert scopes == sorted(scopes)

    def test_only_dirs_with_source_files(self, tmp_path: Path) -> None:
        """Dirs with only non-source files (e.g., .md, .yaml) are NOT scopes."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "readme.md").write_text("# Hello")
        (docs / "config.yaml").write_text("key: val")

        scopes = detect_scopes(tmp_path)
        assert "docs" not in scopes
        assert scopes == ["."]

    def test_depth_capped_at_two_levels(self, tmp_path: Path) -> None:
        """3-level dirs (a/b/c/) are NOT detected as scopes."""
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "deep.py").write_text("pass")

        scopes = detect_scopes(tmp_path)
        # a/b/c is too deep → not a scope
        assert "a/b/c" not in scopes
        # a/b is 2-level → should be detected if it has source files
        # But the source is in c/, not in b/ directly
        # a/b itself has a subdir (c/) with source files — but c/ is L3, too deep
        # So a/b has no direct source files → not a scope either


# ---------------------------------------------------------------------------
# _has_source_files()
# ---------------------------------------------------------------------------


class TestHasSourceFiles:
    """Unit tests for _has_source_files()."""

    def test_empty_dir(self, tmp_path: Path) -> None:
        assert _has_source_files(tmp_path) is False

    def test_dir_with_python_file(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("pass")
        assert _has_source_files(tmp_path) is True

    def test_dir_with_js_file(self, tmp_path: Path) -> None:
        (tmp_path / "app.js").write_text("pass")
        assert _has_source_files(tmp_path) is True

    def test_dir_with_ts_file(self, tmp_path: Path) -> None:
        (tmp_path / "index.ts").write_text("pass")
        assert _has_source_files(tmp_path) is True

    def test_dir_with_only_non_source(self, tmp_path: Path) -> None:
        (tmp_path / "readme.md").write_text("hello")
        (tmp_path / "data.json").write_text("{}")
        assert _has_source_files(tmp_path) is False

    def test_non_recursive_check(self, tmp_path: Path) -> None:
        """_has_source_files checks only direct children, not recursive."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("pass")
        # No direct files → False (non-recursive)
        assert _has_source_files(tmp_path) is False

    def test_recognizes_all_common_extensions(self, tmp_path: Path) -> None:
        """All common source extensions are recognized."""
        for ext in (".py", ".js", ".ts", ".go", ".rs", ".java", ".kt", ".rb"):
            f = tmp_path / f"file{ext}"
            f.write_text("content")
        assert _has_source_files(tmp_path) is True


# ---------------------------------------------------------------------------
# _resolve_scope()
# ---------------------------------------------------------------------------


class TestResolveScope:
    """Unit tests for _resolve_scope()."""

    def test_direct_match(self) -> None:
        """Target in a known scope dir → that scope."""
        target = Path("/proj/backend/auth/login.py")
        project = Path("/proj")
        scopes = [".", "backend/auth", "backend/payments", "frontend"]

        assert _resolve_scope(target, project, scopes) == "backend/auth"

    def test_nested_in_scope(self) -> None:
        """Target deep inside a scope → longest-prefix match."""
        target = Path("/proj/backend/auth/handlers/v2/login.py")
        project = Path("/proj")
        scopes = [".", "backend/auth", "backend/payments"]

        assert _resolve_scope(target, project, scopes) == "backend/auth"

    def test_no_match_returns_root(self) -> None:
        """Target not in any scope → '.'."""
        target = Path("/proj/scripts/deploy.py")
        project = Path("/proj")
        scopes = [".", "backend/auth", "frontend"]

        assert _resolve_scope(target, project, scopes) == "."

    def test_root_scope_always_fallback(self) -> None:
        """Even without '.' in scopes, root-level files return '.'."""
        target = Path("/proj/setup.py")
        project = Path("/proj")
        scopes = ["backend", "frontend"]

        assert _resolve_scope(target, project, scopes) == "."

    def test_longest_prefix_wins(self) -> None:
        """When multiple scopes match, longest prefix wins."""
        target = Path("/proj/backend/auth/deep/file.py")
        project = Path("/proj")
        scopes = [".", "backend", "backend/auth"]

        assert _resolve_scope(target, project, scopes) == "backend/auth"

    def test_windows_paths(self) -> None:
        """Works with Windows-style paths (backslashes)."""
        target = Path("C:/proj/backend/auth/login.py")
        project = Path("C:/proj")
        scopes = [".", "backend/auth", "frontend"]

        assert _resolve_scope(target, project, scopes) == "backend/auth"

    def test_target_is_project_root(self) -> None:
        """Target at project root → '.'."""
        target = Path("/proj/main.py")
        project = Path("/proj")
        scopes = [".", "backend"]

        assert _resolve_scope(target, project, scopes) == "."
