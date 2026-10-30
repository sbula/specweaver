# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for EngineGitExecutor — unrestricted executor for the Engine."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.git.core.engine_executor import EngineGitExecutor
from specweaver.sandbox.git.core.executor import GitExecutor, GitExecutorError

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


class TestEngineExecutorInheritance:
    """EngineGitExecutor is a GitExecutor subclass."""

    def test_is_subclass_of_git_executor(self) -> None:
        assert issubclass(EngineGitExecutor, GitExecutor)

    def test_blocked_always_is_empty(self) -> None:
        assert frozenset() == EngineGitExecutor._BLOCKED_ALWAYS

    def test_agent_executor_still_blocks(self, tmp_path: Path) -> None:
        agent_exec = GitExecutor(
            cwd=tmp_path, whitelist={"status"}, subprocess_executor=SubprocessExecutor(cwd=tmp_path)
        )
        with pytest.raises(GitExecutorError, match="permanently blocked"):
            agent_exec.run("push")


# ---------------------------------------------------------------------------
# Lifted restrictions
# ---------------------------------------------------------------------------


class TestLiftedRestrictions:
    """Previously-blocked commands are allowed when whitelisted."""

    def test_push_allowed_when_whitelisted(self, tmp_path: Path) -> None:
        executor = EngineGitExecutor(
            cwd=tmp_path, whitelist={"push"}, subprocess_executor=SubprocessExecutor(cwd=tmp_path)
        )
        mock_result = SubprocessResult(exit_code=0, stdout="ok\n", stderr="", duration_seconds=0.0)
        with patch(
            "specweaver.sandbox.execution.executor.SubprocessExecutor.execute",
            return_value=mock_result,
        ):
            result = executor.run("push")
        assert result.status == "success"

    def test_merge_allowed_when_whitelisted(self, tmp_path: Path) -> None:
        executor = EngineGitExecutor(
            cwd=tmp_path, whitelist={"merge"}, subprocess_executor=SubprocessExecutor(cwd=tmp_path)
        )
        mock_result = SubprocessResult(exit_code=0, stdout="", stderr="", duration_seconds=0.0)
        with patch(
            "specweaver.sandbox.execution.executor.SubprocessExecutor.execute",
            return_value=mock_result,
        ):
            result = executor.run("merge", "feat/login")
        assert result.status == "success"

    def test_pull_allowed_when_whitelisted(self, tmp_path: Path) -> None:
        executor = EngineGitExecutor(
            cwd=tmp_path, whitelist={"pull"}, subprocess_executor=SubprocessExecutor(cwd=tmp_path)
        )
        mock_result = SubprocessResult(exit_code=0, stdout="", stderr="", duration_seconds=0.0)
        with patch(
            "specweaver.sandbox.execution.executor.SubprocessExecutor.execute",
            return_value=mock_result,
        ):
            result = executor.run("pull")
        assert result.status == "success"

    def test_fetch_allowed_when_whitelisted(self, tmp_path: Path) -> None:
        executor = EngineGitExecutor(
            cwd=tmp_path, whitelist={"fetch"}, subprocess_executor=SubprocessExecutor(cwd=tmp_path)
        )
        mock_result = SubprocessResult(exit_code=0, stdout="", stderr="", duration_seconds=0.0)
        with patch(
            "specweaver.sandbox.execution.executor.SubprocessExecutor.execute",
            return_value=mock_result,
        ):
            result = executor.run("fetch")
        assert result.status == "success"

    def test_rebase_allowed_when_whitelisted(self, tmp_path: Path) -> None:
        executor = EngineGitExecutor(
            cwd=tmp_path, whitelist={"rebase"}, subprocess_executor=SubprocessExecutor(cwd=tmp_path)
        )
        mock_result = SubprocessResult(exit_code=0, stdout="", stderr="", duration_seconds=0.0)
        with patch(
            "specweaver.sandbox.execution.executor.SubprocessExecutor.execute",
            return_value=mock_result,
        ):
            result = executor.run("rebase", "main")
        assert result.status == "success"

    def test_tag_allowed_when_whitelisted(self, tmp_path: Path) -> None:
        executor = EngineGitExecutor(
            cwd=tmp_path, whitelist={"tag"}, subprocess_executor=SubprocessExecutor(cwd=tmp_path)
        )
        mock_result = SubprocessResult(exit_code=0, stdout="", stderr="", duration_seconds=0.0)
        with patch(
            "specweaver.sandbox.execution.executor.SubprocessExecutor.execute",
            return_value=mock_result,
        ):
            result = executor.run("tag", "v1.0")
        assert result.status == "success"

    def test_construction_with_blocked_commands_succeeds(self, tmp_path: Path) -> None:
        """GitExecutor would raise here, EngineGitExecutor should not."""
        executor = EngineGitExecutor(
            cwd=tmp_path,
            whitelist={"push", "merge", "status"},
            subprocess_executor=SubprocessExecutor(cwd=tmp_path),
        )
        assert "push" in executor.whitelist
        assert "merge" in executor.whitelist


# ---------------------------------------------------------------------------
# Whitelist still enforced
# ---------------------------------------------------------------------------


class TestWhitelistStillEnforced:
    """Even the engine can't run commands not in its whitelist."""

    def test_non_whitelisted_raises(self, tmp_path: Path) -> None:
        executor = EngineGitExecutor(
            cwd=tmp_path, whitelist={"push"}, subprocess_executor=SubprocessExecutor(cwd=tmp_path)
        )
        with pytest.raises(GitExecutorError, match="not in the whitelist"):
            executor.run("status")

    def test_blocked_in_args_not_checked(self, tmp_path: Path) -> None:
        """EngineGitExecutor should NOT block 'merge' in args."""
        executor = EngineGitExecutor(
            cwd=tmp_path, whitelist={"log"}, subprocess_executor=SubprocessExecutor(cwd=tmp_path)
        )
        mock_result = SubprocessResult(exit_code=0, stdout="", stderr="", duration_seconds=0.0)
        with patch(
            "specweaver.sandbox.execution.executor.SubprocessExecutor.execute",
            return_value=mock_result,
        ):
            result = executor.run("log", "merge")
        assert result.status == "success"

    def test_cwd_is_passed(self, tmp_path: Path) -> None:
        executor = EngineGitExecutor(
            cwd=tmp_path, whitelist={"push"}, subprocess_executor=SubprocessExecutor(cwd=tmp_path)
        )
        assert executor.cwd == tmp_path

    def test_whitelist_is_immutable(self, tmp_path: Path) -> None:
        original = {"push", "merge"}
        executor = EngineGitExecutor(
            cwd=tmp_path, whitelist=original, subprocess_executor=SubprocessExecutor(cwd=tmp_path)
        )
        original.add("rebase")
        assert "rebase" not in executor.whitelist
