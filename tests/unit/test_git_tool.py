# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for GitTool — low-level git command executor."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.tools.git_tool import GitTool, GitToolError, ToolResult

if TYPE_CHECKING:
    from pathlib import Path


class TestToolResult:
    """ToolResult is a simple frozen dataclass."""

    def test_success_result(self) -> None:
        r = ToolResult(status="success", stdout="ok\n", exit_code=0)
        assert r.status == "success"
        assert r.stdout == "ok\n"
        assert r.exit_code == 0
        assert r.stderr == ""

    def test_error_result(self) -> None:
        r = ToolResult(status="error", stderr="fatal: bad", exit_code=128)
        assert r.status == "error"
        assert r.exit_code == 128

    def test_frozen(self) -> None:
        r = ToolResult(status="success")
        with pytest.raises(AttributeError):
            r.status = "error"  # type: ignore[misc]


class TestGitToolWhitelist:
    """Whitelist enforcement is the core security feature."""

    def test_whitelisted_command_allowed(self, tmp_path: Path) -> None:
        tool = GitTool(cwd=tmp_path, whitelist={"status"})
        assert "status" in tool.whitelist

    def test_non_whitelisted_command_raises(self, tmp_path: Path) -> None:
        tool = GitTool(cwd=tmp_path, whitelist={"status"})
        with pytest.raises(GitToolError, match="not in the whitelist"):
            tool.run("commit", "-m", "sneaky")

    def test_blocked_command_always_raises(self, tmp_path: Path) -> None:
        tool = GitTool(cwd=tmp_path, whitelist={"status"})
        with pytest.raises(GitToolError, match="permanently blocked"):
            tool.run("push")

    def test_blocked_command_in_whitelist_raises_at_construction(
        self,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(GitToolError, match="Cannot whitelist blocked commands"):
            GitTool(cwd=tmp_path, whitelist={"status", "push"})

    def test_blocked_command_in_args_raises(self, tmp_path: Path) -> None:
        tool = GitTool(cwd=tmp_path, whitelist={"status", "add"})
        with pytest.raises(GitToolError, match="Blocked command"):
            tool.run("add", "push")

    def test_all_blocked_commands(self, tmp_path: Path) -> None:
        blocked = {"push", "pull", "fetch", "merge", "rebase", "tag"}
        tool = GitTool(cwd=tmp_path, whitelist={"status"})
        for cmd in blocked:
            with pytest.raises(GitToolError):
                tool.run(cmd)

    def test_empty_whitelist(self, tmp_path: Path) -> None:
        tool = GitTool(cwd=tmp_path, whitelist=set())
        with pytest.raises(GitToolError, match="not in the whitelist"):
            tool.run("status")

    def test_cwd_is_read_only(self, tmp_path: Path) -> None:
        tool = GitTool(cwd=tmp_path, whitelist={"status"})
        assert tool.cwd == tmp_path


class TestGitToolExecution:
    """Actual subprocess execution (mocked)."""

    def test_successful_command(self, tmp_path: Path) -> None:
        tool = GitTool(cwd=tmp_path, whitelist={"status"})
        mock_result = type("R", (), {
            "returncode": 0,
            "stdout": "nothing to commit\n",
            "stderr": "",
        })()

        with patch("specweaver.tools.git_tool.subprocess.run", return_value=mock_result):
            result = tool.run("status")

        assert result.status == "success"
        assert result.stdout == "nothing to commit\n"
        assert result.exit_code == 0

    def test_failed_command(self, tmp_path: Path) -> None:
        tool = GitTool(cwd=tmp_path, whitelist={"commit"})
        mock_result = type("R", (), {
            "returncode": 1,
            "stdout": "",
            "stderr": "nothing to commit\n",
        })()

        with patch("specweaver.tools.git_tool.subprocess.run", return_value=mock_result):
            result = tool.run("commit", "-m", "test")

        assert result.status == "error"
        assert result.exit_code == 1

    def test_timeout(self, tmp_path: Path) -> None:
        tool = GitTool(cwd=tmp_path, whitelist={"log"})

        import subprocess as sp

        with patch(
            "specweaver.tools.git_tool.subprocess.run",
            side_effect=sp.TimeoutExpired(cmd="git", timeout=30),
        ):
            result = tool.run("log", timeout=30)

        assert result.status == "error"
        assert "timed out" in result.stderr

    def test_os_error(self, tmp_path: Path) -> None:
        tool = GitTool(cwd=tmp_path, whitelist={"status"})

        with patch(
            "specweaver.tools.git_tool.subprocess.run",
            side_effect=OSError("git not found"),
        ):
            result = tool.run("status")

        assert result.status == "error"
        assert "OS error" in result.stderr

    def test_cwd_passed_to_subprocess(self, tmp_path: Path) -> None:
        tool = GitTool(cwd=tmp_path, whitelist={"status"})
        mock_result = type("R", (), {
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        })()

        with patch("specweaver.tools.git_tool.subprocess.run", return_value=mock_result) as mock_run:
            tool.run("status")

        cmd_args = mock_run.call_args[0][0]
        assert cmd_args[0] == "git"
        assert cmd_args[1] == "-C"
        assert cmd_args[2] == str(tmp_path)
        assert cmd_args[3] == "status"
