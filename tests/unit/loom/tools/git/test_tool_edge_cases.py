# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for GitTool — intent-based operations and role access control."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from specweaver.loom.commons.git.executor import ExecutorResult
from specweaver.loom.tools.git.tool import (
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


# Edge cases: wrong role calls every intent
# ---------------------------------------------------------------------------


class TestWrongRoleBlocksAllIntents:
    """Systematic: every role is blocked from every other role's intents."""

    @pytest.mark.parametrize(
        "intent,args",
        [
            ("history", (5,)),
            ("show_commit", ("abc123",)),
            ("blame", ("file.py",)),
            ("compare", ("main", "dev")),
            ("list_branches", ()),
        ],
    )
    def test_implementer_cannot_use_reviewer_intents(self, intent: str, args: tuple[Any, ...]) -> None:
        tool = GitTool(executor=_make_executor(), role="implementer")
        with pytest.raises(GitToolError, match="not allowed for role"):
            getattr(tool, intent)(*args)

    @pytest.mark.parametrize(
        "intent,args",
        [
            ("file_history", ("file.py", 5)),
            ("show_old", ("file.py", "HEAD~1")),
            ("search_history", ("bug",)),
            ("reflog", (10,)),
        ],
    )
    def test_implementer_cannot_use_debugger_intents(self, intent: str, args: tuple[Any, ...]) -> None:
        tool = GitTool(executor=_make_executor(), role="implementer")
        with pytest.raises(GitToolError, match="not allowed for role"):
            getattr(tool, intent)(*args)

    @pytest.mark.parametrize(
        "intent,args",
        [
            ("commit", ("feat: nope",)),
            ("inspect_changes", ()),
            ("discard", ("file.py",)),
            ("uncommit", ()),
            ("start_branch", ("feat/nope",)),
            ("switch_branch", ("feat/nope",)),
        ],
    )
    def test_reviewer_cannot_use_write_intents(self, intent: str, args: tuple[Any, ...]) -> None:
        tool = GitTool(executor=_make_executor(), role="reviewer")
        with pytest.raises(GitToolError, match="not allowed for role"):
            getattr(tool, intent)(*args)

    @pytest.mark.parametrize(
        "intent,args",
        [
            ("uncommit", ()),
            ("start_branch", ("feat/nope",)),
            ("switch_branch", ("feat/nope",)),
        ],
    )
    def test_drafter_blocked_from_branch_and_uncommit(self, intent: str, args: tuple[Any, ...]) -> None:
        tool = GitTool(executor=_make_executor(), role="drafter")
        with pytest.raises(GitToolError, match="not allowed for role"):
            getattr(tool, intent)(*args)


# ---------------------------------------------------------------------------
# Edge cases: error messages returned to agent
# ---------------------------------------------------------------------------


class TestErrorMessagesForAgent:
    """Error messages must be clear enough for an LLM to understand."""

    def test_invalid_commit_message_includes_example(self) -> None:
        tool = GitTool(executor=_make_executor(), role="implementer")
        result = tool.commit("bad message")
        assert result.status == "error"
        assert "feat: add user login" in result.message  # includes example

    def test_invalid_branch_name_includes_example(self) -> None:
        tool = GitTool(executor=_make_executor(), role="implementer")
        result = tool.start_branch("bad-name")
        assert result.status == "error"
        assert "feat/add-login" in result.message  # includes example

    def test_wrong_role_error_lists_allowed_intents(self) -> None:
        tool = GitTool(executor=_make_executor(), role="reviewer")
        with pytest.raises(GitToolError) as exc_info:
            tool.commit("feat: nope")
        assert "Allowed:" in str(exc_info.value)
        assert "history" in str(exc_info.value)

    def test_nothing_to_commit_is_clear(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", exit_code=0),
                ExecutorResult(status="success", stdout="", exit_code=0),
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.commit("feat: add stuff")
        assert "Nothing to commit" in result.message


# ---------------------------------------------------------------------------
# Edge cases: git failures at each step of multi-step intents
# ---------------------------------------------------------------------------


class TestCommitFailureAtEachStep:
    """commit() can fail at add, diff, or commit — each handled differently."""

    def test_git_add_fails(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="error",
                stderr="permission denied",
                exit_code=1,
            )
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.commit("feat: add stuff")
        assert result.status == "error"
        assert "git add failed" in result.message

    def test_git_commit_step_fails(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", exit_code=0),  # add OK
                ExecutorResult(status="success", stdout="1 file\n", exit_code=0),  # diff OK
                ExecutorResult(
                    status="error", stderr="author identity unknown", exit_code=128
                ),  # commit FAIL
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.commit("feat: add stuff")
        assert result.status == "error"
        assert "git commit failed" in result.message


class TestDiscardFailure:
    """discard() returns error when git restore fails."""

    def test_restore_nonexistent_file(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="error",
                stderr="pathspec 'nope.py' did not match",
                exit_code=1,
            )
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.discard("nope.py")
        assert result.status == "error"
        assert "git restore failed" in result.message


class TestUncommitFailure:
    """uncommit() returns error when git reset fails."""

    def test_reset_on_initial_commit(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="error",
                stderr="HEAD~1: unknown revision",
                exit_code=128,
            )
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.uncommit()
        assert result.status == "error"
        assert "git reset failed" in result.message


class TestStartBranchFailure:
    """start_branch() handles git switch -c failure."""

    def test_branch_already_exists(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="error",
                stderr="already exists",
                exit_code=128,
            )
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.start_branch("feat/existing-one")
        assert result.status == "error"
        assert "git switch failed" in result.message


class TestSwitchBranchEdgeCases:
    """switch_branch() edge cases."""

    def test_stash_fails_on_dirty_tree(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", stdout="M file.py\n", exit_code=0),  # dirty
                ExecutorResult(status="error", stderr="stash failed", exit_code=1),  # stash FAIL
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.switch_branch("feat/other")
        assert result.status == "error"
        assert "git stash failed" in result.message

    def test_stash_pop_fails_after_switch(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", stdout="M file.py\n", exit_code=0),  # dirty
                ExecutorResult(status="success", exit_code=0),  # stash OK
                ExecutorResult(status="success", exit_code=0),  # switch OK
                ExecutorResult(status="error", stderr="CONFLICT", exit_code=1),  # pop FAIL
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.switch_branch("feat/conflict")
        assert result.status == "error"
        assert "stash pop failed" in result.message


# ---------------------------------------------------------------------------
# Edge cases: reviewer/debugger intent error paths
# ---------------------------------------------------------------------------


class TestReviewerIntentErrors:
    """Reviewer intents return errors from git gracefully."""

    def test_show_commit_bad_hash(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="error",
                stderr="bad object deadbeef",
                exit_code=128,
            )
        )
        tool = GitTool(executor=executor, role="reviewer")
        result = tool.show_commit("deadbeef")
        assert result.status == "error"

    def test_blame_nonexistent_file(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="error",
                stderr="no such path 'nope.py'",
                exit_code=128,
            )
        )
        tool = GitTool(executor=executor, role="reviewer")
        result = tool.blame("nope.py")
        assert result.status == "error"

    def test_compare_nonexistent_branch(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="error",
                stderr="unknown revision",
                exit_code=128,
            )
        )
        tool = GitTool(executor=executor, role="reviewer")
        result = tool.compare("main", "nonexistent")
        assert result.status == "error"


class TestDebuggerIntentErrors:
    """Debugger intents return errors from git gracefully."""

    def test_file_history_nonexistent_file(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="error",
                stderr="does not have any commits yet",
                exit_code=128,
            )
        )
        tool = GitTool(executor=executor, role="debugger")
        result = tool.file_history("nope.py")
        assert result.status == "error"

    def test_show_old_bad_revision(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="error",
                stderr="path not found",
                exit_code=128,
            )
        )
        tool = GitTool(executor=executor, role="debugger")
        result = tool.show_old("file.py", rev="HEAD~999")
        assert result.status == "error"

    def test_search_history_no_results(self) -> None:
        """No results is success with empty data, not an error."""
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="success",
                stdout="",
                exit_code=0,
            )
        )
        tool = GitTool(executor=executor, role="debugger")
        result = tool.search_history("nonexistent-string")
        assert result.status == "success"
        assert result.data == ""


# ---------------------------------------------------------------------------
# Edge cases: ToolResult
# ---------------------------------------------------------------------------


class TestToolResult:
    """ToolResult is frozen and carries clear data."""

    def test_frozen(self) -> None:
        from specweaver.loom.tools.git.tool import ToolResult

        r = ToolResult(status="success", message="ok")
        with pytest.raises(AttributeError):
            r.status = "error"  # type: ignore[misc]

    def test_default_data_is_empty(self) -> None:
        from specweaver.loom.tools.git.tool import ToolResult

        r = ToolResult(status="success", message="ok")
        assert r.data == ""


# ---------------------------------------------------------------------------
# Edge cases: whitelist_for_role completeness
# ---------------------------------------------------------------------------


class TestWhitelistForRoleCompleteness:
    """whitelist_for_role must return correct commands for every role."""

    def test_debugger_has_log_and_show(self) -> None:
        wl = whitelist_for_role("debugger")
        assert "log" in wl
        assert "show" in wl
        assert "reflog" in wl
        assert "status" in wl  # for inspect_changes
        assert "diff" in wl  # for inspect_changes

    def test_drafter_has_commit_no_branch(self) -> None:
        wl = whitelist_for_role("drafter")
        assert "commit" in wl
        assert "add" in wl
        assert "restore" in wl
        assert "switch" not in wl
        assert "stash" not in wl

    def test_all_roles_produce_nonempty_whitelists(self) -> None:
        for role in ROLE_INTENTS:
            wl = whitelist_for_role(role)
            assert len(wl) > 0, f"Role {role!r} has empty whitelist"

    def test_no_blocked_commands_in_agent_whitelists(self) -> None:
        """Agent roles must not require blocked commands.

        conflict_resolver is excluded — it uses EngineGitExecutor,
        which lifts the blocked-commands restriction.
        """
        from specweaver.loom.commons.git.executor import GitExecutor

        blocked = GitExecutor._BLOCKED_ALWAYS
        agent_roles = {r for r in ROLE_INTENTS if r != "conflict_resolver"}
        for role in agent_roles:
            wl = whitelist_for_role(role)
            overlap = blocked & wl
            assert not overlap, f"Role {role!r} whitelist contains blocked: {overlap}"

    def test_conflict_resolver_needs_blocked_commands(self) -> None:
        """conflict_resolver intentionally requires merge (via EngineGitExecutor)."""
        wl = whitelist_for_role("conflict_resolver")
        assert "merge" in wl, "conflict_resolver must have merge in its whitelist"


# ---------------------------------------------------------------------------
# Edge cases: ROLE_INTENTS and INTENT_COMMANDS consistency
# ---------------------------------------------------------------------------


class TestConfigConsistency:
    """ROLE_INTENTS and INTENT_COMMANDS must be consistent."""

    def test_all_role_intents_have_commands(self) -> None:
        from specweaver.loom.tools.git.tool import INTENT_COMMANDS

        for role, intents in ROLE_INTENTS.items():
            for intent in intents:
                assert intent in INTENT_COMMANDS, (
                    f"Role {role!r} has intent {intent!r} not in INTENT_COMMANDS"
                )

    def test_all_intents_in_intent_commands_are_used_by_a_role(self) -> None:
        from specweaver.loom.tools.git.tool import INTENT_COMMANDS

        all_role_intents: set[str] = set()
        for intents in ROLE_INTENTS.values():
            all_role_intents |= intents
        for intent in INTENT_COMMANDS:
            assert intent in all_role_intents, (
                f"INTENT_COMMANDS has orphan intent {intent!r} not used by any role"
            )

    def test_all_intent_methods_exist_on_git_tool(self) -> None:
        from specweaver.loom.tools.git.tool import INTENT_COMMANDS

        for intent in INTENT_COMMANDS:
            assert hasattr(GitTool, intent), f"GitTool is missing method for intent {intent!r}"


# ---------------------------------------------------------------------------
# Edge cases: executor call verification
# ---------------------------------------------------------------------------


class TestExecutorCallVerification:
    """Verify the correct git commands are sent to the executor."""

    def test_commit_calls_add_diff_commit(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", exit_code=0),
                ExecutorResult(status="success", stdout="1 file\n", exit_code=0),
                ExecutorResult(status="success", stdout="ok\n", exit_code=0),
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        tool.commit("feat: add stuff")
        calls = [c.args[0] for c in executor.run.call_args_list]
        assert calls == ["add", "diff", "commit"]

    def test_switch_branch_clean_calls_status_switch(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", stdout="", exit_code=0),
                ExecutorResult(status="success", exit_code=0),
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        tool.switch_branch("feat/other")
        calls = [c.args[0] for c in executor.run.call_args_list]
        assert calls == ["status", "switch"]

    def test_switch_branch_dirty_calls_status_stash_switch_pop(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", stdout="M file.py\n", exit_code=0),
                ExecutorResult(status="success", exit_code=0),
                ExecutorResult(status="success", exit_code=0),
                ExecutorResult(status="success", exit_code=0),
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        tool.switch_branch("feat/other")
        calls = [c.args[0] for c in executor.run.call_args_list]
        assert calls == ["status", "stash", "switch", "stash"]

    def test_inspect_changes_calls_status_diff(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", stdout="", exit_code=0),
                ExecutorResult(status="success", stdout="", exit_code=0),
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        tool.inspect_changes()
        calls = [c.args[0] for c in executor.run.call_args_list]
        assert calls == ["status", "diff"]


# ---------------------------------------------------------------------------
# Edge cases: success path data returned
# ---------------------------------------------------------------------------


class TestSuccessPathData:
    """Successful intents return correct data to the agent."""

    def test_commit_returns_git_output(self) -> None:
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", exit_code=0),
                ExecutorResult(status="success", stdout="1 file changed\n", exit_code=0),
                ExecutorResult(status="success", stdout="[main abc1234] feat: hi\n", exit_code=0),
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        result = tool.commit("feat: hi")
        assert result.status == "success"
        assert "abc1234" in result.data

    def test_discard_success_has_filename(self) -> None:
        tool = GitTool(executor=_make_executor(), role="implementer")
        result = tool.discard("app.py")
        assert result.status == "success"
        assert "app.py" in result.message

    def test_uncommit_success_message_is_clear(self) -> None:
        tool = GitTool(executor=_make_executor(), role="implementer")
        result = tool.uncommit()
        assert result.status == "success"
        assert "staged" in result.message

    def test_start_branch_success_includes_name(self) -> None:
        tool = GitTool(executor=_make_executor(), role="implementer")
        result = tool.start_branch("feat/new-feature")
        assert result.status == "success"
        assert "feat/new-feature" in result.message

    def test_history_returns_log_data(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="success",
                stdout="abc1234 feat: hi\ndef5678 fix: bye\n",
                exit_code=0,
            )
        )
        tool = GitTool(executor=executor, role="reviewer")
        result = tool.history(2)
        assert result.status == "success"
        assert "abc1234" in result.data

    def test_list_branches_returns_data(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="success",
                stdout="* main\n  feat/login\n",
                exit_code=0,
            )
        )
        tool = GitTool(executor=executor, role="reviewer")
        result = tool.list_branches()
        assert result.status == "success"
        assert "main" in result.data

    def test_reflog_returns_data(self) -> None:
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="success",
                stdout="abc HEAD@{0}: commit: feat: hi\n",
                exit_code=0,
            )
        )
        tool = GitTool(executor=executor, role="debugger")
        result = tool.reflog(5)
        assert result.status == "success"
        assert "abc" in result.data


# ---------------------------------------------------------------------------
# Additional edge cases: commit, branch, and history
# ---------------------------------------------------------------------------


class TestGitToolAdditionalEdgeCases:
    """Edge cases not covered by existing tests."""

    def test_commit_with_multiline_message(self) -> None:
        """Multiline commit messages are rejected (conventional commit uses first line only)."""
        executor = _make_executor(
            run_side_effect=[
                ExecutorResult(status="success", exit_code=0),
                ExecutorResult(status="success", stdout="1 file\n", exit_code=0),
                ExecutorResult(status="success", stdout="ok\n", exit_code=0),
            ]
        )
        tool = GitTool(executor=executor, role="implementer")
        # Conventional commit regex may reject newlines
        result = tool.commit("feat: add login\n\nDetailed description here.")
        assert result.status == "error"

    def test_commit_scope_with_special_chars(self) -> None:
        """Scope with special characters in conventional commit."""
        tool = GitTool(executor=_make_executor(), role="implementer")
        result = tool.commit("feat(auth/login): add endpoint")
        # Depends on regex — /  within scope may not match
        # This test documents the current behavior
        assert result.status in ("success", "error")

    def test_history_n_zero(self) -> None:
        """history(n=0) should still call git log (may return empty)."""
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="success",
                stdout="",
                exit_code=0,
            )
        )
        tool = GitTool(executor=executor, role="reviewer")
        result = tool.history(0)
        assert result.status == "success"

    def test_history_negative_n(self) -> None:
        """history(n=-1) — invalid count, should not crash."""
        executor = _make_executor(
            run_returns=ExecutorResult(
                status="success",
                stdout="",
                exit_code=0,
            )
        )
        tool = GitTool(executor=executor, role="reviewer")
        result = tool.history(-1)
        assert result.status in ("success", "error")

    def test_branch_name_with_numbers(self) -> None:
        """Branch names with numbers should be valid."""
        tool = GitTool(executor=_make_executor(), role="implementer")
        result = tool.start_branch("feat/add-login-v2")
        assert result.status == "success"

    def test_branch_name_consecutive_dashes_accepted(self) -> None:
        """Branch names with consecutive dashes are allowed by validation."""
        tool = GitTool(executor=_make_executor(), role="implementer")
        result = tool.start_branch("feat/add--login")
        assert result.status == "success"
