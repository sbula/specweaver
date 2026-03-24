# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for research tool implementations (search module + executor dispatch)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from specweaver.loom.commons.filesystem.search import (
    READ_FILE_LINE_CAP,
    find_by_glob,
    grep_content,
)
from specweaver.loom.commons.research.boundaries import WorkspaceBoundary
from specweaver.loom.commons.research.executor import ToolExecutor


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """Create a minimal project fixture with known files."""
    # src/main.py
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text(
        "import os\n\ndef main():\n    print('hello world')\n\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    # src/utils.py
    (src / "utils.py").write_text(
        "def helper():\n    return 42\n\ndef another_helper():\n    return 'foo'\n",
        encoding="utf-8",
    )
    # config.yaml
    (tmp_path / "config.yaml").write_text(
        "name: test-project\nversion: 1.0\n",
        encoding="utf-8",
    )
    # README.md
    (tmp_path / "README.md").write_text(
        "# Test Project\n\nA test project for research tools.\n",
        encoding="utf-8",
    )
    # Nested: services/auth/handler.py
    auth = tmp_path / "services" / "auth"
    auth.mkdir(parents=True)
    (auth / "handler.py").write_text(
        "class AuthHandler:\n    def login(self, user, password):\n        pass\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def executor(project: Path) -> ToolExecutor:
    """Create a ToolExecutor for the project."""
    boundary = WorkspaceBoundary(roots=[project])
    return ToolExecutor(boundary, web_enabled=False)


class TestGrepContent:
    """Tests for the grep_content function."""

    def test_basic_match(self, project: Path) -> None:
        results = grep_content(project, "hello world")
        matches = [r for r in results if "file" in r]
        assert len(matches) >= 1
        assert any("main.py" in m["file"] for m in matches)

    def test_case_insensitive_default(self, project: Path) -> None:
        results = grep_content(project, "HELLO WORLD")
        matches = [r for r in results if "file" in r]
        assert len(matches) >= 1

    def test_case_sensitive(self, project: Path) -> None:
        results = grep_content(project, "HELLO WORLD", case_sensitive=True)
        matches = [r for r in results if "file" in r]
        assert len(matches) == 0

    def test_no_match(self, project: Path) -> None:
        results = grep_content(project, "nonexistent_string_xyz123")
        matches = [r for r in results if "file" in r]
        assert len(matches) == 0

    def test_scoped_to_subdirectory(self, project: Path) -> None:
        results = grep_content(project / "src", "helper")
        matches = [r for r in results if "file" in r]
        assert len(matches) >= 1
        # Should only find in src/
        for m in matches:
            assert "services" not in m["file"]

    def test_max_results_respected(self, project: Path) -> None:
        results = grep_content(project, "def", max_results=1)
        matches = [r for r in results if "file" in r]
        assert len(matches) <= 1

    def test_regex_pattern(self, project: Path) -> None:
        results = grep_content(project, r"def \w+\(self")
        matches = [r for r in results if "file" in r]
        assert len(matches) >= 1  # AuthHandler.login


class TestFindByGlob:
    """Tests for the find_by_glob function."""

    def test_find_python_files(self, project: Path) -> None:
        results = find_by_glob(project, "*.py")
        files = [r for r in results if "path" in r]
        assert len(files) >= 3  # main.py, utils.py, handler.py

    def test_find_yaml_files(self, project: Path) -> None:
        results = find_by_glob(project, "*.yaml")
        files = [r for r in results if "path" in r]
        assert len(files) >= 1

    def test_find_specific_file(self, project: Path) -> None:
        results = find_by_glob(project, "README.md")
        files = [r for r in results if "path" in r]
        assert len(files) == 1
        assert files[0]["type"] == "file"

    def test_filter_type_directory(self, project: Path) -> None:
        results = find_by_glob(project, "*", file_type="directory")
        dirs = [r for r in results if "path" in r]
        assert all(d["type"] == "directory" for d in dirs)

    def test_filter_type_file(self, project: Path) -> None:
        results = find_by_glob(project, "*", file_type="file")
        files = [r for r in results if "path" in r]
        assert all(f["type"] == "file" for f in files)

    def test_scoped_to_subdirectory(self, project: Path) -> None:
        results = find_by_glob(project / "services", "*.py")
        files = [r for r in results if "path" in r]
        assert len(files) >= 1
        assert all("handler" in f["path"] for f in files)

    def test_max_results(self, project: Path) -> None:
        results = find_by_glob(project, "*", max_results=2)
        items = [r for r in results if "path" in r]
        assert len(items) <= 2

    def test_includes_size(self, project: Path) -> None:
        results = find_by_glob(project, "README.md")
        files = [r for r in results if "path" in r]
        assert files[0]["size_bytes"] > 0


class TestReadFileViaExecutor:
    """Tests for read_file dispatched through the executor."""

    @pytest.mark.asyncio()
    async def test_read_entire_file(self, executor: ToolExecutor) -> None:
        result = await executor.execute("read_file", {"path": "README.md"})
        assert "error" not in result
        assert "# Test Project" in result["content"]
        assert result["total_lines"] == 3

    @pytest.mark.asyncio()
    async def test_read_with_line_range(self, executor: ToolExecutor) -> None:
        result = await executor.execute("read_file", {"path": "src/main.py", "start_line": 3, "end_line": 4})
        assert "error" not in result
        assert "def main" in result["content"]
        assert result["showing_lines"] == "3-4"

    @pytest.mark.asyncio()
    async def test_line_cap_enforced(self, tmp_path: Path) -> None:
        big_file = tmp_path / "big.py"
        lines = [f"line_{i}" for i in range(READ_FILE_LINE_CAP + 50)]
        big_file.write_text("\n".join(lines), encoding="utf-8")
        boundary = WorkspaceBoundary(roots=[tmp_path])
        exec_ = ToolExecutor(boundary, web_enabled=False)
        result = await exec_.execute("read_file", {"path": "big.py"})
        assert result.get("truncated") is True
        assert "warning" in result
        content_lines = result["content"].split("\n")
        assert len(content_lines) == READ_FILE_LINE_CAP

    @pytest.mark.asyncio()
    async def test_file_not_found(self, executor: ToolExecutor) -> None:
        result = await executor.execute("read_file", {"path": "nonexistent.py"})
        assert "error" in result

    @pytest.mark.asyncio()
    async def test_nested_path(self, executor: ToolExecutor) -> None:
        result = await executor.execute("read_file", {"path": "services/auth/handler.py"})
        assert "error" not in result
        assert "AuthHandler" in result["content"]


class TestListDirectoryViaExecutor:
    """Tests for list_directory dispatched through the executor."""

    @pytest.mark.asyncio()
    async def test_root_listing(self, executor: ToolExecutor) -> None:
        result = await executor.execute("list_directory", {"path": "."})
        assert result["type"] == "directory"
        assert "children" in result
        names = [c["path"] for c in result["children"] if "path" in c]
        assert "src" in names
        assert "README.md" in names

    @pytest.mark.asyncio()
    async def test_directories_first(self, executor: ToolExecutor) -> None:
        result = await executor.execute("list_directory", {"path": "."})
        children = result["children"]
        types = [c["type"] for c in children if "type" in c]
        dir_done = False
        for t in types:
            if t == "file":
                dir_done = True
            if t == "directory" and dir_done:
                pytest.fail("Directory found after file — should sort dirs first")

    @pytest.mark.asyncio()
    async def test_depth_limiting(self, executor: ToolExecutor) -> None:
        result = await executor.execute("list_directory", {"path": ".", "depth": 1})
        children = result["children"]
        for child in children:
            if child.get("type") == "directory":
                assert "children" not in child or child["children"] == []

    @pytest.mark.asyncio()
    async def test_subdirectory(self, executor: ToolExecutor) -> None:
        result = await executor.execute("list_directory", {"path": "src"})
        children = result["children"]
        names = [c["path"] for c in children if "path" in c]
        assert "main.py" in names
        assert "utils.py" in names

    @pytest.mark.asyncio()
    async def test_not_a_directory(self, executor: ToolExecutor) -> None:
        result = await executor.execute("list_directory", {"path": "README.md"})
        assert "error" in result

    @pytest.mark.asyncio()
    async def test_max_entries(self, executor: ToolExecutor) -> None:
        result = await executor.execute("list_directory", {"path": ".", "max_entries": 2, "depth": 3})

        def count_entries(children: list) -> int:  # type: ignore[type-arg]
            total = 0
            for c in children:
                if "path" in c:
                    total += 1
                    if "children" in c:
                        total += count_entries(c["children"])
            return total

        total = count_entries(result["children"])
        assert total <= 2

    @pytest.mark.asyncio()
    async def test_skips_hidden_and_pycache(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "visible.py").touch()
        boundary = WorkspaceBoundary(roots=[tmp_path])
        exec_ = ToolExecutor(boundary, web_enabled=False)
        result = await exec_.execute("list_directory", {"path": "."})
        names = [c["path"] for c in result["children"] if "path" in c]
        assert ".git" not in names
        assert "__pycache__" not in names
        assert "visible.py" in names
