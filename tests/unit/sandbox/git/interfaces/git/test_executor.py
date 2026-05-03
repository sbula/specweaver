# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for GitExecutor — low-level git command executor."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.sandbox.git.core.executor import ExecutorResult, GitExecutor, GitExecutorError

if TYPE_CHECKING:
    from pathlib import Path


class TestExecutorResult:
    """ExecutorResult is a simple frozen dataclass."""

    def test_success_result(self) -> None:
        r = ExecutorResult(status="success", stdout="ok\n", exit_code=0)
        assert r.status == "success"
        assert r.stdout == "ok\n"
        assert r.exit_code == 0
        assert r.stderr == ""

    def test_error_result(self) -> None:
        r = ExecutorResult(status="error", stderr="fatal: bad", exit_code=128)
        assert r.status == "error"
        assert r.exit_code == 128

    def test_frozen(self) -> None:
        r = ExecutorResult(status="success")
        with pytest.raises(AttributeError):
            r.status = "error"  # type: ignore[misc]


class TestGitExecutorWhitelist:
    """Whitelist enforcement is the core security feature."""

    def test_whitelisted_command_allowed(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"status"})
        assert "status" in executor.whitelist

    def test_non_whitelisted_command_raises(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"status"})
        with pytest.raises(GitExecutorError, match="not in the whitelist"):
            executor.run("commit", "-m", "sneaky")

    def test_blocked_command_always_raises(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"status"})
        with pytest.raises(GitExecutorError, match="permanently blocked"):
            executor.run("push")

    def test_blocked_command_in_whitelist_raises_at_construction(
        self,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(GitExecutorError, match="Cannot whitelist blocked commands"):
            GitExecutor(cwd=tmp_path, whitelist={"status", "push"})

    def test_blocked_command_in_args_raises(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"status", "add"})
        with pytest.raises(GitExecutorError, match="Blocked command"):
            executor.run("add", "push")

    def test_all_blocked_commands(self, tmp_path: Path) -> None:
        blocked = {"push", "pull", "fetch", "merge", "rebase", "tag"}
        executor = GitExecutor(cwd=tmp_path, whitelist={"status"})
        for cmd in blocked:
            with pytest.raises(GitExecutorError):
                executor.run(cmd)

    def test_empty_whitelist(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist=set())
        with pytest.raises(GitExecutorError, match="not in the whitelist"):
            executor.run("status")

    def test_cwd_is_read_only(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"status"})
        assert executor.cwd == tmp_path


class TestGitExecutorExecution:
    """Actual subprocess execution (mocked)."""

    def test_successful_command(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"status"})
        mock_result = type(
            "R",
            (),
            {
                "returncode": 0,
                "stdout": "nothing to commit\n",
                "stderr": "",
            },
        )()

        with patch("specweaver.sandbox.git.core.executor.subprocess.run", return_value=mock_result):
            result = executor.run("status")

        assert result.status == "success"
        assert result.stdout == "nothing to commit\n"
        assert result.exit_code == 0

    def test_failed_command(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"commit"})
        mock_result = type(
            "R",
            (),
            {
                "returncode": 1,
                "stdout": "",
                "stderr": "nothing to commit\n",
            },
        )()

        with patch("specweaver.sandbox.git.core.executor.subprocess.run", return_value=mock_result):
            result = executor.run("commit", "-m", "test")

        assert result.status == "error"
        assert result.exit_code == 1

    def test_timeout(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"log"})

        import subprocess as sp

        with patch(
            "specweaver.sandbox.git.core.executor.subprocess.run",
            side_effect=sp.TimeoutExpired(cmd="git", timeout=30),
        ):
            result = executor.run("log", timeout=30)

        assert result.status == "error"
        assert "timed out" in result.stderr

    def test_os_error(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"status"})

        with patch(
            "specweaver.sandbox.git.core.executor.subprocess.run",
            side_effect=OSError("git not found"),
        ):
            result = executor.run("status")

        assert result.status == "error"
        assert "OS error" in result.stderr

    def test_cwd_passed_to_subprocess(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"status"})
        mock_result = type(
            "R",
            (),
            {
                "returncode": 0,
                "stdout": "",
                "stderr": "",
            },
        )()

        with patch(
            "specweaver.sandbox.git.core.executor.subprocess.run", return_value=mock_result
        ) as mock_run:
            executor.run("status")

        cmd_args = mock_run.call_args[0][0]
        assert cmd_args[0] == "git"
        assert cmd_args[1] == "-C"
        assert cmd_args[2] == str(tmp_path)
        assert cmd_args[3] == "status"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestGitExecutorEdgeCases:
    """Edge cases for whitelist, error messages, and security."""

    def test_error_message_includes_command_name_on_block(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"status"})
        with pytest.raises(GitExecutorError) as exc_info:
            executor.run("push")
        assert "git push" in str(exc_info.value)

    def test_error_message_includes_allowed_list_on_deny(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"status", "diff"})
        with pytest.raises(GitExecutorError) as exc_info:
            executor.run("commit")
        error_msg = str(exc_info.value)
        assert "diff" in error_msg
        assert "status" in error_msg

    def test_error_message_on_blocked_arg(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"log"})
        with pytest.raises(GitExecutorError) as exc_info:
            executor.run("log", "merge")
        assert "git merge" in str(exc_info.value)

    def test_whitelist_is_immutable_after_construction(self, tmp_path: Path) -> None:
        original = {"status", "diff"}
        executor = GitExecutor(cwd=tmp_path, whitelist=original)
        # Mutating the original set should not affect the executor
        original.add("push")
        assert "push" not in executor.whitelist

    def test_multiple_blocked_commands_in_whitelist(self, tmp_path: Path) -> None:
        with pytest.raises(GitExecutorError, match="Cannot whitelist blocked commands"):
            GitExecutor(cwd=tmp_path, whitelist={"push", "merge", "status"})

    def test_exit_code_minus_one_on_timeout(self, tmp_path: Path) -> None:
        import subprocess as sp

        executor = GitExecutor(cwd=tmp_path, whitelist={"status"})
        with patch(
            "specweaver.sandbox.git.core.executor.subprocess.run",
            side_effect=sp.TimeoutExpired(cmd="git", timeout=5),
        ):
            result = executor.run("status", timeout=5)
        assert result.exit_code == -1

    def test_exit_code_minus_one_on_os_error(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"status"})
        with patch(
            "specweaver.sandbox.git.core.executor.subprocess.run",
            side_effect=OSError("No such file"),
        ):
            result = executor.run("status")
        assert result.exit_code == -1

    def test_args_are_passed_through(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"log"})
        mock_result = type(
            "R",
            (),
            {
                "returncode": 0,
                "stdout": "",
                "stderr": "",
            },
        )()
        with patch(
            "specweaver.sandbox.git.core.executor.subprocess.run", return_value=mock_result
        ) as mock_run:
            executor.run("log", "--oneline", "-n5", "--", "file.py")
        cmd_args = mock_run.call_args[0][0]
        assert cmd_args == ["git", "-C", str(tmp_path), "log", "--oneline", "-n5", "--", "file.py"]

    def test_stderr_preserved_on_failure(self, tmp_path: Path) -> None:
        executor = GitExecutor(cwd=tmp_path, whitelist={"status"})
        mock_result = type(
            "R",
            (),
            {
                "returncode": 128,
                "stdout": "",
                "stderr": "fatal: not a git repository",
            },
        )()
        with patch("specweaver.sandbox.git.core.executor.subprocess.run", return_value=mock_result):
            result = executor.run("status")
        assert result.stderr == "fatal: not a git repository"
        assert result.exit_code == 128
