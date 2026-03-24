# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for ToolExecutor and tool definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from specweaver.loom.commons.research.boundaries import WorkspaceBoundary
from specweaver.loom.commons.research.definitions import ALL_TOOLS, FILE_TOOLS, WEB_TOOLS
from specweaver.loom.commons.research.executor import ToolExecutor


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """Create a minimal project fixture."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("def main():\n    print('hello')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test\nSome content.\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def executor(project: Path) -> ToolExecutor:
    """Create a ToolExecutor with web disabled."""
    boundary = WorkspaceBoundary(roots=[project])
    return ToolExecutor(boundary, web_enabled=False)


@pytest.fixture()
def executor_web(project: Path) -> ToolExecutor:
    """Create a ToolExecutor with web enabled."""
    boundary = WorkspaceBoundary(roots=[project])
    return ToolExecutor(boundary, web_enabled=True)


class TestDefinitions:
    """Tests for tool definition instances."""

    def test_all_tools_have_names(self) -> None:
        for tool in ALL_TOOLS:
            assert tool.name
            assert tool.description

    def test_file_tools_count(self) -> None:
        assert len(FILE_TOOLS) == 4

    def test_web_tools_count(self) -> None:
        assert len(WEB_TOOLS) == 2

    def test_all_tools_is_union(self) -> None:
        assert len(ALL_TOOLS) == len(FILE_TOOLS) + len(WEB_TOOLS)

    def test_tool_names_unique(self) -> None:
        names = [t.name for t in ALL_TOOLS]
        assert len(names) == len(set(names))

    def test_to_json_schema_works(self) -> None:
        for tool in ALL_TOOLS:
            schema = tool.to_json_schema()
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "required" in schema


class TestToolExecutorAvailableTools:
    """Tests for available_tools()."""

    def test_without_web(self, executor: ToolExecutor) -> None:
        tools = executor.available_tools()
        names = {t.name for t in tools}
        assert "grep" in names
        assert "find_files" in names
        assert "read_file" in names
        assert "list_directory" in names
        assert "web_search" not in names
        assert "read_url" not in names

    def test_with_web(self, executor_web: ToolExecutor) -> None:
        tools = executor_web.available_tools()
        names = {t.name for t in tools}
        assert "web_search" in names
        assert "read_url" in names
        assert len(tools) == 6


class TestToolExecutorExecute:
    """Tests for execute() dispatch."""

    @pytest.mark.asyncio()
    async def test_grep(self, executor: ToolExecutor) -> None:
        result = await executor.execute("grep", {"pattern": "hello"})
        assert "results" in result
        matches = [r for r in result["results"] if "file" in r]
        assert len(matches) >= 1

    @pytest.mark.asyncio()
    async def test_find_files(self, executor: ToolExecutor) -> None:
        result = await executor.execute("find_files", {"pattern": "*.py"})
        assert "results" in result
        files = [r for r in result["results"] if "path" in r]
        assert len(files) >= 1

    @pytest.mark.asyncio()
    async def test_read_file(self, executor: ToolExecutor) -> None:
        result = await executor.execute("read_file", {"path": "README.md"})
        assert "content" in result
        assert "# Test" in result["content"]

    @pytest.mark.asyncio()
    async def test_list_directory(self, executor: ToolExecutor) -> None:
        result = await executor.execute("list_directory", {"path": "."})
        assert "children" in result
        names = [c["path"] for c in result["children"] if "path" in c]
        assert "src" in names

    @pytest.mark.asyncio()
    async def test_unknown_tool(self, executor: ToolExecutor) -> None:
        result = await executor.execute("nonexistent_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio()
    async def test_web_search_disabled(self, executor: ToolExecutor) -> None:
        result = await executor.execute("web_search", {"query": "test"})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio()
    async def test_read_url_disabled(self, executor: ToolExecutor) -> None:
        result = await executor.execute("read_url", {"url": "https://example.com"})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio()
    async def test_tool_exception_handled(self, executor: ToolExecutor) -> None:
        # Missing required argument should be caught
        result = await executor.execute("grep", {})
        assert "error" in result
