# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for specweaver.loom.commons.filesystem.executor — TDD (tests first).

Test structure:
- Happy-path: every operation works correctly
- Protected patterns: context.yaml, .env, .git/ blocked for write/delete/move
- Path traversal: ../ escape, symlinks, Windows ADS
- OS permission errors: read-only, locked, missing dirs
- Atomic writes: temp file cleanup on failure
- Edge cases: empty files, max size, binary, unicode
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# We import AFTER writing the implementation — these will fail until then.
# ---------------------------------------------------------------------------
from specweaver.loom.commons.filesystem.executor import (
    EngineFileExecutor,
    ExecutorResult,
    FileExecutor,
    FileExecutorError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Create a minimal project directory."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "src" / "utils.py").write_text("def add(a, b): return a + b", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=abc", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]", encoding="utf-8")
    (tmp_path / "context.yaml").write_text("name: test\nlevel: system\n", encoding="utf-8")
    (tmp_path / ".specweaver").mkdir()
    (tmp_path / ".specweaver" / "config.yaml").write_text("llm:\n  model: test\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def executor(project: Path) -> FileExecutor:
    """Standard FileExecutor locked to the project directory."""
    return FileExecutor(cwd=project)


@pytest.fixture
def engine_executor(project: Path) -> EngineFileExecutor:
    """Engine-level executor (bypasses protected patterns)."""
    return EngineFileExecutor(cwd=project)


# ===========================================================================
# FileExecutor — Happy Path
# ===========================================================================


class TestFileExecutorRead:
    """Tests for read operation."""

    def test_read_existing_file(self, executor: FileExecutor) -> None:
        """Read an existing UTF-8 file."""
        result = executor.read("src/main.py")
        assert result.status == "success"
        assert result.data == "print('hello')"

    def test_read_file_not_found(self, executor: FileExecutor) -> None:
        """Read a file that does not exist returns error result."""
        result = executor.read("nonexistent.py")
        assert result.status == "error"

    def test_read_empty_file(self, executor: FileExecutor, project: Path) -> None:
        """Read an empty file returns empty string."""
        (project / "empty.txt").write_text("", encoding="utf-8")
        result = executor.read("empty.txt")
        assert result.status == "success"
        assert result.data == ""

    def test_read_max_bytes_exceeded(self, executor: FileExecutor, project: Path) -> None:
        """File exceeding max_bytes limit is rejected."""
        (project / "big.txt").write_text("x" * 200, encoding="utf-8")
        result = executor.read("big.txt", max_bytes=100)
        assert result.status == "error"

    def test_read_binary_file_rejected(self, executor: FileExecutor, project: Path) -> None:
        """Binary file (not valid UTF-8) returns error."""
        (project / "binary.bin").write_bytes(b"\x80\x81\x82\xff")
        result = executor.read("binary.bin")
        assert result.status == "error"

    def test_read_unicode_content(self, executor: FileExecutor, project: Path) -> None:
        """Read a file with unicode content."""
        (project / "unicode.txt").write_text("Ünïcödé 日本語 émojis 🎉", encoding="utf-8")
        result = executor.read("unicode.txt")
        assert result.status == "success"
        assert "🎉" in result.data


class TestFileExecutorWrite:
    """Tests for write operation."""

    def test_write_new_file(self, executor: FileExecutor, project: Path) -> None:
        """Write creates a new file."""
        result = executor.write("src/new_file.py", "content")
        assert result.status == "success"
        assert (project / "src" / "new_file.py").read_text() == "content"

    def test_write_overwrites_existing(self, executor: FileExecutor, project: Path) -> None:
        """Write overwrites an existing file."""
        result = executor.write("src/main.py", "new content")
        assert result.status == "success"
        assert (project / "src" / "main.py").read_text() == "new content"

    def test_write_creates_parent_dirs(self, executor: FileExecutor, project: Path) -> None:
        """Write creates intermediate directories if needed."""
        result = executor.write("src/deep/nested/file.py", "deep content")
        assert result.status == "success"
        assert (project / "src" / "deep" / "nested" / "file.py").read_text() == "deep content"

    def test_write_atomic_no_partial(self, executor: FileExecutor, project: Path) -> None:
        """After a successful write, no temp files remain."""
        executor.write("src/atomic.py", "content")
        tmp_files = list(project.glob("src/*.tmp.*"))
        assert len(tmp_files) == 0

    def test_write_unicode_content(self, executor: FileExecutor, project: Path) -> None:
        """Write file with unicode content."""
        executor.write("unicode.py", "# Ünïcödé 日本語 🎉")
        assert "🎉" in (project / "unicode.py").read_text(encoding="utf-8")


class TestFileExecutorDelete:
    """Tests for delete operation."""

    def test_delete_existing_file(self, executor: FileExecutor, project: Path) -> None:
        """Delete removes an existing file."""
        result = executor.delete("src/utils.py")
        assert result.status == "success"
        assert not (project / "src" / "utils.py").exists()

    def test_delete_nonexistent_file(self, executor: FileExecutor) -> None:
        """Delete a file that doesn't exist returns error."""
        result = executor.delete("nonexistent.py")
        assert result.status == "error"

    def test_delete_directory_rejected(self, executor: FileExecutor) -> None:
        """Delete refuses to remove a directory (use rmdir or explicit intent)."""
        result = executor.delete("src")
        assert result.status == "error"


class TestFileExecutorMkdir:
    """Tests for mkdir operation."""

    def test_mkdir_creates_directory(self, executor: FileExecutor, project: Path) -> None:
        """Mkdir creates a new directory."""
        result = executor.mkdir("src/newpkg")
        assert result.status == "success"
        assert (project / "src" / "newpkg").is_dir()

    def test_mkdir_with_parents(self, executor: FileExecutor, project: Path) -> None:
        """Mkdir creates intermediate parent directories."""
        result = executor.mkdir("src/deep/nested/pkg")
        assert result.status == "success"
        assert (project / "src" / "deep" / "nested" / "pkg").is_dir()

    def test_mkdir_idempotent(self, executor: FileExecutor) -> None:
        """Mkdir on existing directory does not error."""
        executor.mkdir("src/newpkg")
        result = executor.mkdir("src/newpkg")
        assert result.status == "success"


class TestFileExecutorListDir:
    """Tests for list_dir operation."""

    def test_list_dir_returns_entries(self, executor: FileExecutor) -> None:
        """List directory returns file and subdirectory names."""
        result = executor.list_dir("src")
        assert result.status == "success"
        assert "main.py" in result.data
        assert "utils.py" in result.data

    def test_list_dir_nonexistent(self, executor: FileExecutor) -> None:
        """List a nonexistent directory returns error."""
        result = executor.list_dir("nonexistent")
        assert result.status == "error"

    def test_list_dir_on_file(self, executor: FileExecutor) -> None:
        """List a file (not directory) returns error."""
        result = executor.list_dir("src/main.py")
        assert result.status == "error"

    def test_list_dir_empty(self, executor: FileExecutor, project: Path) -> None:
        """List an empty directory returns empty list."""
        (project / "empty_dir").mkdir()
        result = executor.list_dir("empty_dir")
        assert result.status == "success"
        assert result.data == []

    def test_list_dir_root(self, executor: FileExecutor) -> None:
        """List the project root (empty string path)."""
        result = executor.list_dir("")
        assert result.status == "success"
        assert "src" in result.data


class TestFileExecutorExists:
    """Tests for exists operation."""

    def test_exists_file(self, executor: FileExecutor) -> None:
        result = executor.exists("src/main.py")
        assert result.status == "success"
        assert result.data is True

    def test_exists_directory(self, executor: FileExecutor) -> None:
        result = executor.exists("src")
        assert result.status == "success"
        assert result.data is True

    def test_exists_nonexistent(self, executor: FileExecutor) -> None:
        result = executor.exists("nope.txt")
        assert result.status == "success"
        assert result.data is False


class TestFileExecutorStat:
    """Tests for stat operation."""

    def test_stat_file(self, executor: FileExecutor, project: Path) -> None:
        result = executor.stat("src/main.py")
        assert result.status == "success"
        assert result.data["size"] == len("print('hello')")
        assert result.data["is_file"] is True
        assert result.data["is_dir"] is False

    def test_stat_directory(self, executor: FileExecutor) -> None:
        result = executor.stat("src")
        assert result.status == "success"
        assert result.data["is_dir"] is True
        assert result.data["is_file"] is False

    def test_stat_nonexistent(self, executor: FileExecutor) -> None:
        result = executor.stat("nope.txt")
        assert result.status == "error"


class TestFileExecutorMove:
    """Tests for move operation."""

    def test_move_file(self, executor: FileExecutor, project: Path) -> None:
        """Move a file to a new location."""
        result = executor.move("src/utils.py", "src/helpers.py")
        assert result.status == "success"
        assert not (project / "src" / "utils.py").exists()
        assert (project / "src" / "helpers.py").read_text() == "def add(a, b): return a + b"

    def test_move_nonexistent_source(self, executor: FileExecutor) -> None:
        result = executor.move("nope.py", "dst.py")
        assert result.status == "error"

    def test_move_creates_parent_dirs(self, executor: FileExecutor, project: Path) -> None:
        """Move creates destination parent directories."""
        result = executor.move("src/utils.py", "src/moved/utils.py")
        assert result.status == "success"
        assert (project / "src" / "moved" / "utils.py").is_file()


# ===========================================================================
# Protected Patterns
# ===========================================================================


class TestProtectedPatterns:
    """context.yaml, .env, .git/, .specweaver/ are blocked for mutation."""

    def test_write_context_yaml_blocked(self, executor: FileExecutor) -> None:
        """Cannot write to context.yaml."""
        result = executor.write("context.yaml", "hacked: true")
        assert result.status == "error"

    def test_write_nested_context_yaml_blocked(self, executor: FileExecutor) -> None:
        """Cannot write to context.yaml in subdirectory."""
        result = executor.write("src/context.yaml", "hacked: true")
        assert result.status == "error"

    def test_delete_context_yaml_blocked(self, executor: FileExecutor) -> None:
        """Cannot delete context.yaml."""
        result = executor.delete("context.yaml")
        assert result.status == "error"

    def test_move_to_context_yaml_blocked(self, executor: FileExecutor) -> None:
        """Cannot move a file to context.yaml."""
        result = executor.move("src/main.py", "src/context.yaml")
        assert result.status == "error"

    def test_move_context_yaml_blocked(self, executor: FileExecutor) -> None:
        """Cannot move context.yaml (source is protected)."""
        result = executor.move("context.yaml", "backup.yaml")
        assert result.status == "error"

    def test_read_context_yaml_allowed(self, executor: FileExecutor) -> None:
        """Reading context.yaml is allowed (protection is write-only)."""
        result = executor.read("context.yaml")
        assert result.status == "success"

    def test_write_env_blocked(self, executor: FileExecutor) -> None:
        """Cannot write to .env."""
        result = executor.write(".env", "hacked")
        assert result.status == "error"

    def test_delete_env_blocked(self, executor: FileExecutor) -> None:
        """Cannot delete .env."""
        result = executor.delete(".env")
        assert result.status == "error"

    def test_write_inside_git_dir_blocked(self, executor: FileExecutor) -> None:
        """Cannot write to files inside .git/."""
        result = executor.write(".git/config", "hacked")
        assert result.status == "error"

    def test_write_inside_specweaver_dir_blocked(self, executor: FileExecutor) -> None:
        """Cannot write to files inside .specweaver/."""
        result = executor.write(".specweaver/config.yaml", "hacked")
        assert result.status == "error"

    def test_mkdir_inside_git_blocked(self, executor: FileExecutor) -> None:
        """Cannot create directories inside .git/."""
        result = executor.mkdir(".git/hooks")
        assert result.status == "error"


# ===========================================================================
# Path Traversal & Security
# ===========================================================================


class TestPathTraversal:
    """Path traversal prevention — agents must stay inside cwd."""

    def test_relative_escape_blocked(self, executor: FileExecutor) -> None:
        """../escape attempts are blocked."""
        result = executor.read("../../../etc/passwd")
        assert result.status == "error"

    def test_relative_escape_in_middle_blocked(self, executor: FileExecutor) -> None:
        """src/../../escape attempts are blocked."""
        result = executor.read("src/../../outside.txt")
        assert result.status == "error"

    def test_absolute_path_blocked(self, executor: FileExecutor) -> None:
        """Absolute paths are blocked."""
        result = executor.read("/etc/passwd")
        assert result.status == "error"

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only")
    def test_windows_absolute_blocked(self, executor: FileExecutor) -> None:
        """Windows absolute paths are blocked."""
        result = executor.read("C:\\Windows\\System32\\config")
        assert result.status == "error"

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only")
    def test_windows_ads_blocked(self, executor: FileExecutor) -> None:
        """Windows Alternate Data Streams are blocked."""
        result = executor.read("src/main.py:hidden")
        assert result.status == "error"


class TestSymlinkBlocking:
    """Symlinks are blocked to prevent escape."""

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require admin on Windows")
    def test_symlink_file_blocked(self, executor: FileExecutor, project: Path) -> None:
        """Symlinked files are blocked."""
        target = Path("/tmp/dangerous.txt")
        target.write_text("dangerous", encoding="utf-8")
        link = project / "src" / "sneaky_link.py"
        link.symlink_to(target)
        result = executor.read("src/sneaky_link.py")
        assert result.status == "error"
        target.unlink()

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require admin on Windows")
    def test_symlink_dir_blocked(self, executor: FileExecutor, project: Path) -> None:
        """Symlinked directories are blocked."""
        link = project / "src" / "sneaky_dir"
        link.symlink_to("/tmp")
        result = executor.list_dir("src/sneaky_dir")
        assert result.status == "error"


# ===========================================================================
# OS Permission Errors
# ===========================================================================


class TestOSPermissionErrors:
    """Handle OS-level permission errors gracefully."""

    @pytest.mark.skipif(os.name == "nt", reason="chmod doesn't work the same on Windows")
    def test_read_permission_denied(self, executor: FileExecutor, project: Path) -> None:
        """Read a file with no read permission returns error."""
        target = project / "src" / "locked.py"
        target.write_text("secret", encoding="utf-8")
        target.chmod(0o000)
        try:
            result = executor.read("src/locked.py")
            assert result.status == "error"
        finally:
            target.chmod(stat.S_IRUSR | stat.S_IWUSR)

    @pytest.mark.skipif(os.name == "nt", reason="chmod doesn't work the same on Windows")
    def test_write_permission_denied(self, executor: FileExecutor, project: Path) -> None:
        """Write to a read-only directory returns error."""
        ro_dir = project / "readonly"
        ro_dir.mkdir()
        ro_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
        try:
            result = executor.write("readonly/file.py", "content")
            assert result.status == "error"
        finally:
            ro_dir.chmod(stat.S_IRWXU)

    @pytest.mark.skipif(os.name == "nt", reason="chmod doesn't work the same on Windows")
    def test_delete_permission_denied(self, executor: FileExecutor, project: Path) -> None:
        """Delete a file in a read-only directory returns error."""
        ro_dir = project / "readonly"
        ro_dir.mkdir()
        (ro_dir / "file.py").write_text("content", encoding="utf-8")
        ro_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
        try:
            result = executor.delete("readonly/file.py")
            assert result.status == "error"
        finally:
            ro_dir.chmod(stat.S_IRWXU)


# ===========================================================================
# Constructor Validation
# ===========================================================================


class TestConstructorValidation:
    """FileExecutor constructor must validate inputs."""

    def test_cwd_must_exist(self) -> None:
        """Constructor rejects nonexistent cwd."""
        with pytest.raises(FileExecutorError):
            FileExecutor(cwd=Path("/nonexistent/path/xyz"))

    def test_cwd_must_be_directory(self, tmp_path: Path) -> None:
        """Constructor rejects cwd that is a file."""
        f = tmp_path / "somefile.txt"
        f.write_text("content")
        with pytest.raises(FileExecutorError):
            FileExecutor(cwd=f)

    def test_cwd_is_readonly_property(self, project: Path) -> None:
        """cwd property is read-only."""
        exe = FileExecutor(cwd=project)
        assert exe.cwd == project


# ===========================================================================
# EngineFileExecutor — bypasses protected patterns
# ===========================================================================


class TestEngineFileExecutor:
    """EngineFileExecutor bypasses protected patterns but keeps security."""

    def test_write_context_yaml_allowed(self, engine_executor: EngineFileExecutor, project: Path) -> None:
        """Engine can write to context.yaml."""
        result = engine_executor.write("context.yaml", "name: updated\nlevel: system\n")
        assert result.status == "success"
        assert "updated" in (project / "context.yaml").read_text()

    def test_delete_context_yaml_allowed(self, engine_executor: EngineFileExecutor, project: Path) -> None:
        """Engine can delete context.yaml."""
        result = engine_executor.delete("context.yaml")
        assert result.status == "success"
        assert not (project / "context.yaml").exists()

    def test_write_env_allowed(self, engine_executor: EngineFileExecutor, project: Path) -> None:
        """Engine can write to .env."""
        result = engine_executor.write(".env", "NEW_SECRET=xyz")
        assert result.status == "success"

    def test_traversal_still_blocked(self, engine_executor: EngineFileExecutor) -> None:
        """Engine still cannot escape cwd (traversal is always blocked)."""
        result = engine_executor.read("../../../etc/passwd")
        assert result.status == "error"

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require admin on Windows")
    def test_symlinks_still_blocked(self, engine_executor: EngineFileExecutor, project: Path) -> None:
        """Engine still blocks symlinks (always a security risk)."""
        target = Path("/tmp/engine_test.txt")
        target.write_text("test", encoding="utf-8")
        link = project / "link.txt"
        link.symlink_to(target)
        result = engine_executor.read("link.txt")
        assert result.status == "error"
        target.unlink()
