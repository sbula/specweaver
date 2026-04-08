# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for ToolExecutor and tool definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from specweaver.llm.models import ToolDispatcherProtocol
from specweaver.loom.dispatcher import ToolDispatcher
from specweaver.loom.security import WorkspaceBoundary
from specweaver.loom.tools.filesystem.definitions import INTENT_DEFINITIONS as FILE_DEFINITIONS
from specweaver.loom.tools.web.definitions import INTENT_DEFINITIONS as WEB_DEFINITIONS

FILE_TOOLS = list(FILE_DEFINITIONS.values())
WEB_TOOLS = list(WEB_DEFINITIONS.values())
ALL_TOOLS = FILE_TOOLS + WEB_TOOLS


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """Create a minimal project fixture."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("def main():\n    print('hello')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test\nSome content.\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def executor(project: Path) -> ToolDispatcher:
    """Create a ToolDispatcher with web disabled."""
    boundary = WorkspaceBoundary(roots=[project])
    return ToolDispatcher.create_standard_set(boundary, role="planner", allowed_tools=["fs"])


@pytest.fixture()
def executor_web(project: Path) -> ToolDispatcher:
    """Create a ToolDispatcher with web enabled."""
    boundary = WorkspaceBoundary(roots=[project])
    return ToolDispatcher.create_standard_set(boundary, role="planner", allowed_tools=["fs", "web"])


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

    def test_without_web(self, executor: ToolDispatcher) -> None:
        tools = executor.available_tools()
        names = {t.name for t in tools}
        assert "grep" in names
        assert "find_files" in names
        assert "read_file" in names
        assert "list_directory" in names
        assert "web_search" not in names
        assert "read_url" not in names

    def test_with_web(self, executor_web: ToolDispatcher) -> None:
        tools = executor_web.available_tools()
        names = {t.name for t in tools}
        assert "web_search" in names
        assert "read_url" in names
        assert len(tools) == 6


class TestToolExecutorExecute:
    """Tests for execute() dispatch."""

    @pytest.mark.asyncio()
    async def test_grep(self, executor: ToolDispatcher, project: Path) -> None:
        result = await executor.execute("grep", {"path": str(project), "pattern": "hello"})
        assert "results" in result
        matches = [r for r in result["results"] if "file" in r]
        assert len(matches) >= 1

    @pytest.mark.asyncio()
    async def test_find_files(self, executor: ToolDispatcher, project: Path) -> None:
        result = await executor.execute("find_files", {"path": str(project), "pattern": "*.py"})
        assert "results" in result
        files = [r for r in result["results"] if "path" in r]
        assert len(files) >= 1

    @pytest.mark.asyncio()
    async def test_read_file(self, executor: ToolDispatcher, project: Path) -> None:
        result = await executor.execute("read_file", {"path": "README.md"})
        assert "result" in result
        assert "# Test" in result["result"]

    @pytest.mark.asyncio()
    async def test_list_directory(self, executor: ToolDispatcher, project: Path) -> None:
        result = await executor.execute("list_directory", {"path": "."})
        assert "results" in result
        assert "src" in result["results"]

    @pytest.mark.asyncio()
    async def test_unknown_tool(self, executor: ToolDispatcher) -> None:
        result = await executor.execute("nonexistent_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio()
    async def test_web_search_disabled(self, executor: ToolDispatcher) -> None:
        result = await executor.execute("web_search", {"query": "test"})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio()
    async def test_read_url_disabled(self, executor: ToolDispatcher) -> None:
        result = await executor.execute("read_url", {"url": "https://example.com"})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio()
    async def test_tool_exception_handled(self, executor: ToolDispatcher) -> None:
        # Missing required argument should be caught
        result = await executor.execute("grep", {})
        assert "error" in result


class TestProtocolCompliance:
    """Verify ToolDispatcher satisfies ToolDispatcherProtocol."""

    def test_dispatcher_is_protocol_instance(self, executor: ToolDispatcher) -> None:
        """ToolDispatcher must be a runtime instance of ToolDispatcherProtocol."""
        assert isinstance(executor, ToolDispatcherProtocol)

    def test_has_available_tools(self, executor: ToolDispatcher) -> None:
        """available_tools() returns a non-empty list of ToolDefinitions."""
        tools = executor.available_tools()
        assert len(tools) > 0
        for t in tools:
            assert t.name
            assert t.description

    @pytest.mark.asyncio()
    async def test_execute_returns_dict(self, executor: ToolDispatcher) -> None:
        """execute() returns a dict (even for errors)."""
        result = await executor.execute("nonexistent_tool", {})
        assert isinstance(result, dict)


class TestMixedPathGrantMatching:
    """Tests that grant matching works with both relative and absolute paths."""

    @pytest.mark.asyncio()
    async def test_relative_path_matches_absolute_grant(
        self,
        executor: ToolDispatcher,
        project: Path,
    ) -> None:
        """A relative path like 'README.md' should match the absolute grant root."""
        result = await executor.execute("read_file", {"path": "README.md"})
        assert "error" not in result

    @pytest.mark.asyncio()
    async def test_absolute_path_matches_absolute_grant(
        self,
        executor: ToolDispatcher,
        project: Path,
    ) -> None:
        """An absolute path that matches the grant root should work for grep."""
        result = await executor.execute(
            "grep",
            {"path": str(project), "pattern": "hello"},
        )
        assert "results" in result

    @pytest.mark.asyncio()
    async def test_relative_subdir_matches_absolute_grant(
        self,
        executor: ToolDispatcher,
        project: Path,
    ) -> None:
        """A relative subdir path like 'src' should match the absolute grant."""
        result = await executor.execute(
            "find_files",
            {"path": "src", "pattern": "*.py"},
        )
        assert "results" in result
