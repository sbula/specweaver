# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for GitTool — intent-based operations and role access control."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.git.core.executor import ExecutorResult
from specweaver.sandbox.git.interfaces.tool import (
    ROLE_INTENTS,
    GitTool,
    GitToolError,
    whitelist_for_role,
)


def _make_executor(
    *,
    run_returns: ExecutorResult | None = None,
    run_side_effect: list[ExecutorResult] | None = None,
) -> MagicMock:
    """Create a mock GitExecutor."""
    executor = MagicMock()
    if run_side_effect is not None:
        executor.run.side_effect = run_side_effect
    elif run_returns is not None:
        executor.run.return_value = run_returns
    else:
        executor.run.return_value = ExecutorResult(status="success", stdout="ok\n", exit_code=0)
    return executor


# ---------------------------------------------------------------------------
# Role / intent access control
# ---------------------------------------------------------------------------


class TestRoleAccessControl:
    """The role determines which intents are available."""

    def test_unknown_role_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown role"):
            GitTool(executor=_make_executor(), role="admin")

    def test_implementer_intents(self) -> None:
        tool = GitTool(executor=_make_executor(), role="implementer")
        assert tool.allowed_intents == ROLE_INTENTS["implementer"]

    def test_reviewer_cannot_commit(self) -> None:
        tool = GitTool(executor=_make_executor(), role="reviewer")
        with pytest.raises(GitToolError, match="not allowed for role"):
            tool.commit("feat: should fail")

    def test_drafter_cannot_start_branch(self) -> None:
        tool = GitTool(executor=_make_executor(), role="drafter")
        with pytest.raises(GitToolError, match="not allowed for role"):
            tool.start_branch("feat/new")

    def test_debugger_cannot_commit(self) -> None:
        tool = GitTool(executor=_make_executor(), role="debugger")
        with pytest.raises(GitToolError, match="not allowed for role"):
            tool.commit("fix: nope")

    def test_reviewer_can_read(self) -> None:
        tool = GitTool(executor=_make_executor(), role="reviewer")
        result = tool.history(5)
        assert result.status == "success"

    def test_debugger_can_inspect(self) -> None:
        tool = GitTool(executor=_make_executor(), role="debugger")
        result = tool.inspect_changes()
        assert result.status == "success"


class TestWhitelistForRole:
    """whitelist_for_role computes the git commands needed for a role."""

    def test_implementer_has_commit_commands(self) -> None:
        wl = whitelist_for_role("implementer")
        assert "commit" in wl
        assert "add" in wl
        assert "diff" in wl

    def test_reviewer_has_no_write_commands(self) -> None:
        wl = whitelist_for_role("reviewer")
        assert "commit" not in wl
        assert "add" not in wl
        assert "log" in wl

    def test_unknown_role_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown role"):
            whitelist_for_role("superadmin")


# ---------------------------------------------------------------------------
# Conventional commit validation
# ---------------------------------------------------------------------------


class TestConventionalCommits:
    """Commit messages must follow conventional commits format."""

    @pytest.mark.parametrize(
        "msg",
        [
            "feat: add login endpoint",
            "fix: correct null pointer",
            "docs: update README",
            "test: add coverage tests",
            "chore: bump dependencies",
            "refactor: extract helper",
            "style: fix whitespace",
            "perf: optimize query",
            "ci: add GitHub Actions",
            "build: update pyproject",
            "feat(auth): add OAuth support",
        ],
    )
    def test_valid_messages(self, msg: str) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", exit_code=0),  # git add
                ExecutorResult(
                    status="success", stdout="1 file\n", exit_code=0
                ),  # git diff --staged
                ExecutorResult(status="success", stdout="committed\n", exit_code=0),  # git commit
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.commit(msg)
        assert result.status == "success"

    @pytest.mark.parametrize(
        "msg",
        [
            "added login",
            "Fix bug",
            "FEAT: caps",
            "",
            "feat:",
            "feat:missing space",
            "random message",
        ],
    )
    def test_invalid_messages(self, msg: str) -> None:
        tool = GitTool(executor=_make_executor(), role="implementer")
        result = tool.commit(msg)
        assert result.status == "error"
        assert "Invalid commit message" in result.message


# ---------------------------------------------------------------------------
# Branch naming validation
# ---------------------------------------------------------------------------


class TestBranchNaming:
    """Branch names must follow <type>/<kebab-case> format."""

    @pytest.mark.parametrize(
        "name",
        [
            "feat/add-login",
            "fix/null-pointer",
            "docs/update-readme",
            "chore/bump-deps",
            "refactor/extract-helper",
        ],
    )
    def test_valid_names(self, name: str) -> None:
        tool = GitTool(executor=_make_executor(), role="implementer")
        result = tool.start_branch(name)
        assert result.status == "success"

    @pytest.mark.parametrize(
        "name",
        [
            "main",
            "feature/CamelCase",
            "my-branch",
            "feat/",
            "feat/under_score",
            "FEAT/caps",
        ],
    )
    def test_invalid_names(self, name: str) -> None:
        tool = GitTool(executor=_make_executor(), role="implementer")
        result = tool.start_branch(name)
        assert result.status == "error"
        assert "Invalid branch name" in result.message


# ---------------------------------------------------------------------------
# Intent behavior
# ---------------------------------------------------------------------------


class TestCommitIntent:
    """commit() stages all, validates, and commits."""

    def test_nothing_to_commit(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", exit_code=0),  # git add
                ExecutorResult(
                    status="success", stdout="", exit_code=0
                ),  # git diff --staged (empty)
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.commit("feat: add stuff")
        assert result.status == "error"
        assert "Nothing to commit" in result.message

    def test_add_fails(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="error",
                stderr="add failed",
                exit_code=1,
            )
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.commit("feat: add stuff")
        assert result.status == "error"
        assert "git add failed" in result.message


class TestSwitchBranchIntent:
    """switch_branch() auto-stashes, switches, then pops."""

    def test_clean_switch(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", stdout="", exit_code=0),  # status (clean)
                ExecutorResult(status="success", exit_code=0),  # switch
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.switch_branch("feat/existing")
        assert result.status == "success"

    def test_dirty_switch_auto_stashes(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(
                    status="success", stdout="M file.py\n", exit_code=0
                ),  # status (dirty)
                ExecutorResult(status="success", exit_code=0),  # stash
                ExecutorResult(status="success", exit_code=0),  # switch
                ExecutorResult(status="success", exit_code=0),  # stash pop
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.switch_branch("feat/other")
        assert result.status == "success"
        assert executor.run.call_count == 4

    def test_switch_fails_restores_stash(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", stdout="M file.py\n", exit_code=0),  # status
                ExecutorResult(status="success", exit_code=0),  # stash
                ExecutorResult(
                    status="error", stderr="no such branch", exit_code=1
                ),  # switch fails
                ExecutorResult(status="success", exit_code=0),  # stash pop (restore)
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.switch_branch("feat/nonexistent")
        assert result.status == "error"
        # Verify stash pop was called to restore
        assert executor.run.call_count == 4


class TestInspectChangesIntent:
    """inspect_changes() shows status and diff."""

    def test_clean_tree(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", stdout="", exit_code=0),  # status
                ExecutorResult(status="success", stdout="", exit_code=0),  # diff
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.inspect_changes()
        assert result.status == "success"
        assert "clean" in result.message

    def test_dirty_tree(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", stdout="M file.py\n", exit_code=0),  # status
                ExecutorResult(status="success", stdout="+line\n", exit_code=0),  # diff
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.inspect_changes()
        assert "Status" in result.data
        assert "Diff" in result.data


# ---------------------------------------------------------------------------
