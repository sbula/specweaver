# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for GitAtom — intent-based operations and role access control."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from specweaver.tools.git_atom import (
    ROLE_INTENTS,
    GitAtom,
    GitAtomError,
    whitelist_for_role,
)
from specweaver.tools.git_tool import ToolResult


def _make_tool(
    *,
    run_returns: ToolResult | None = None,
    run_side_effect: list[ToolResult] | None = None,
) -> MagicMock:
    """Create a mock GitTool."""
    tool = MagicMock()
    if run_side_effect is not None:
        tool.run.side_effect = run_side_effect
    elif run_returns is not None:
        tool.run.return_value = run_returns
    else:
        tool.run.return_value = ToolResult(status="success", stdout="ok\n", exit_code=0)
    return tool


# ---------------------------------------------------------------------------
# Role / intent access control
# ---------------------------------------------------------------------------


class TestRoleAccessControl:
    """The role determines which intents are available."""

    def test_unknown_role_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown role"):
            GitAtom(tool=_make_tool(), role="admin")

    def test_implementer_intents(self) -> None:
        atom = GitAtom(tool=_make_tool(), role="implementer")
        assert atom.allowed_intents == ROLE_INTENTS["implementer"]

    def test_reviewer_cannot_commit(self) -> None:
        atom = GitAtom(tool=_make_tool(), role="reviewer")
        with pytest.raises(GitAtomError, match="not allowed for role"):
            atom.commit("feat: should fail")

    def test_drafter_cannot_start_branch(self) -> None:
        atom = GitAtom(tool=_make_tool(), role="drafter")
        with pytest.raises(GitAtomError, match="not allowed for role"):
            atom.start_branch("feat/new")

    def test_debugger_cannot_commit(self) -> None:
        atom = GitAtom(tool=_make_tool(), role="debugger")
        with pytest.raises(GitAtomError, match="not allowed for role"):
            atom.commit("fix: nope")

    def test_reviewer_can_read(self) -> None:
        atom = GitAtom(tool=_make_tool(), role="reviewer")
        result = atom.history(5)
        assert result.status == "success"

    def test_debugger_can_inspect(self) -> None:
        atom = GitAtom(tool=_make_tool(), role="debugger")
        result = atom.inspect_changes()
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

    @pytest.mark.parametrize("msg", [
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
    ])
    def test_valid_messages(self, msg: str) -> None:
        tool = _make_tool(run_side_effect=[
            ToolResult(status="success", exit_code=0),  # git add
            ToolResult(status="success", stdout="1 file\n", exit_code=0),  # git diff --staged
            ToolResult(status="success", stdout="committed\n", exit_code=0),  # git commit
        ])
        atom = GitAtom(tool=tool, role="implementer")
        result = atom.commit(msg)
        assert result.status == "success"

    @pytest.mark.parametrize("msg", [
        "added login",
        "Fix bug",
        "FEAT: caps",
        "",
        "feat:",
        "feat:missing space",
        "random message",
    ])
    def test_invalid_messages(self, msg: str) -> None:
        atom = GitAtom(tool=_make_tool(), role="implementer")
        result = atom.commit(msg)
        assert result.status == "error"
        assert "Invalid commit message" in result.message


# ---------------------------------------------------------------------------
# Branch naming validation
# ---------------------------------------------------------------------------


class TestBranchNaming:
    """Branch names must follow <type>/<kebab-case> format."""

    @pytest.mark.parametrize("name", [
        "feat/add-login",
        "fix/null-pointer",
        "docs/update-readme",
        "chore/bump-deps",
        "refactor/extract-helper",
    ])
    def test_valid_names(self, name: str) -> None:
        atom = GitAtom(tool=_make_tool(), role="implementer")
        result = atom.start_branch(name)
        assert result.status == "success"

    @pytest.mark.parametrize("name", [
        "main",
        "feature/CamelCase",
        "my-branch",
        "feat/",
        "feat/under_score",
        "FEAT/caps",
    ])
    def test_invalid_names(self, name: str) -> None:
        atom = GitAtom(tool=_make_tool(), role="implementer")
        result = atom.start_branch(name)
        assert result.status == "error"
        assert "Invalid branch name" in result.message


# ---------------------------------------------------------------------------
# Intent behavior
# ---------------------------------------------------------------------------


class TestCommitIntent:
    """commit() stages all, validates, and commits."""

    def test_nothing_to_commit(self) -> None:
        tool = _make_tool(run_side_effect=[
            ToolResult(status="success", exit_code=0),  # git add
            ToolResult(status="success", stdout="", exit_code=0),  # git diff --staged (empty)
        ])
        atom = GitAtom(tool=tool, role="implementer")
        result = atom.commit("feat: add stuff")
        assert result.status == "error"
        assert "Nothing to commit" in result.message

    def test_add_fails(self) -> None:
        tool = _make_tool(run_returns=ToolResult(
            status="error", stderr="add failed", exit_code=1,
        ))
        atom = GitAtom(tool=tool, role="implementer")
        result = atom.commit("feat: add stuff")
        assert result.status == "error"
        assert "git add failed" in result.message


class TestSwitchBranchIntent:
    """switch_branch() auto-stashes, switches, then pops."""

    def test_clean_switch(self) -> None:
        tool = _make_tool(run_side_effect=[
            ToolResult(status="success", stdout="", exit_code=0),  # status (clean)
            ToolResult(status="success", exit_code=0),  # switch
        ])
        atom = GitAtom(tool=tool, role="implementer")
        result = atom.switch_branch("feat/existing")
        assert result.status == "success"

    def test_dirty_switch_auto_stashes(self) -> None:
        tool = _make_tool(run_side_effect=[
            ToolResult(status="success", stdout="M file.py\n", exit_code=0),  # status (dirty)
            ToolResult(status="success", exit_code=0),  # stash
            ToolResult(status="success", exit_code=0),  # switch
            ToolResult(status="success", exit_code=0),  # stash pop
        ])
        atom = GitAtom(tool=tool, role="implementer")
        result = atom.switch_branch("feat/other")
        assert result.status == "success"
        assert tool.run.call_count == 4

    def test_switch_fails_restores_stash(self) -> None:
        tool = _make_tool(run_side_effect=[
            ToolResult(status="success", stdout="M file.py\n", exit_code=0),  # status
            ToolResult(status="success", exit_code=0),  # stash
            ToolResult(status="error", stderr="no such branch", exit_code=1),  # switch fails
            ToolResult(status="success", exit_code=0),  # stash pop (restore)
        ])
        atom = GitAtom(tool=tool, role="implementer")
        result = atom.switch_branch("feat/nonexistent")
        assert result.status == "error"
        # Verify stash pop was called to restore
        assert tool.run.call_count == 4


class TestInspectChangesIntent:
    """inspect_changes() shows status and diff."""

    def test_clean_tree(self) -> None:
        tool = _make_tool(run_side_effect=[
            ToolResult(status="success", stdout="", exit_code=0),  # status
            ToolResult(status="success", stdout="", exit_code=0),  # diff
        ])
        atom = GitAtom(tool=tool, role="implementer")
        result = atom.inspect_changes()
        assert result.status == "success"
        assert "clean" in result.message

    def test_dirty_tree(self) -> None:
        tool = _make_tool(run_side_effect=[
            ToolResult(status="success", stdout="M file.py\n", exit_code=0),  # status
            ToolResult(status="success", stdout="+line\n", exit_code=0),  # diff
        ])
        atom = GitAtom(tool=tool, role="implementer")
        result = atom.inspect_changes()
        assert "Status" in result.data
        assert "Diff" in result.data
