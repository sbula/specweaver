# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for GitAtom — Flow-level git operations for the Engine."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from specweaver.core.loom.atoms.base import AtomStatus
from specweaver.core.loom.atoms.git.atom import GitAtom
from specweaver.core.loom.commons.git.executor import ExecutorResult

if TYPE_CHECKING:
    from pathlib import Path


def _ok(stdout: str = "", stderr: str = "") -> ExecutorResult:
    return ExecutorResult(status="success", stdout=stdout, stderr=stderr, exit_code=0)


def _fail(stderr: str = "error", exit_code: int = 1) -> ExecutorResult:
    return ExecutorResult(status="error", stdout="", stderr=stderr, exit_code=exit_code)


# ---------------------------------------------------------------------------
# Dispatch / run()
# ---------------------------------------------------------------------------


class TestDispatch:
    """run() dispatches to intent handlers based on context."""

    def test_missing_intent_fails(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        result = atom.run({})
        assert result.status == AtomStatus.FAILED
        assert "Missing 'intent'" in result.message

    def test_unknown_intent_fails(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        result = atom.run({"intent": "nuke_everything"})
        assert result.status == AtomStatus.FAILED
        assert "Unknown intent" in result.message
        assert "nuke_everything" in result.message

    def test_known_intents_listed_in_error(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        result = atom.run({"intent": "bad"})
        assert "checkpoint" in result.message
        assert "integrate" in result.message

    def test_all_intents_are_known(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        expected = {
            "checkpoint",
            "isolate",
            "restore",
            "discard_all",
            "rollback",
            "publish",
            "integrate",
            "sync",
            "tag",
            "worktree_add",
            "worktree_teardown",
            "worktree_sync",
            "strip_merge",
            "is_tracked",
        }
        assert atom._known_intents() == expected


# ---------------------------------------------------------------------------
# checkpoint
# ---------------------------------------------------------------------------


class TestCheckpoint:
    """checkpoint stages all + commits with config message."""

    def test_success(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # add
                type(
                    "R", (), {"returncode": 1, "stdout": "", "stderr": ""}
                )(),  # diff --staged --quiet (changes exist)
                type(
                    "R", (), {"returncode": 0, "stdout": "[main abc] chk\n", "stderr": ""}
                )(),  # commit
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "checkpoint", "message": "flow checkpoint"})
        assert result.status == AtomStatus.SUCCESS
        assert "flow checkpoint" in result.message
        assert "commit_output" in result.exports

    def test_nothing_to_commit_is_success(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # add
                type(
                    "R", (), {"returncode": 0, "stdout": "", "stderr": ""}
                )(),  # diff --staged --quiet (no changes)
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "checkpoint"})
        assert result.status == AtomStatus.SUCCESS
        assert "idempotent" in result.message

    def test_add_fails(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type(
                "R", (), {"returncode": 1, "stdout": "", "stderr": "add err"}
            )()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "checkpoint", "message": "x"})
        assert result.status == AtomStatus.FAILED
        assert "git add failed" in result.message

    def test_commit_fails(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # add
                type(
                    "R", (), {"returncode": 1, "stdout": "", "stderr": ""}
                )(),  # diff (has changes)
                type(
                    "R", (), {"returncode": 1, "stdout": "", "stderr": "commit err"}
                )(),  # commit fails
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "checkpoint", "message": "x"})
        assert result.status == AtomStatus.FAILED
        assert "git commit failed" in result.message

    def test_default_message(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})(),
                type("R", (), {"returncode": 0, "stdout": "ok\n", "stderr": ""})(),
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "checkpoint"})
        assert result.status == AtomStatus.SUCCESS
        assert "checkpoint" in result.message


# ---------------------------------------------------------------------------
# isolate
# ---------------------------------------------------------------------------


class TestIsolate:
    """isolate creates and switches to a new branch."""

    def test_success(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "isolate", "branch": "flow/task-42"})
        assert result.status == AtomStatus.SUCCESS
        assert result.exports["branch"] == "flow/task-42"

    def test_missing_branch_fails(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        result = atom.run({"intent": "isolate"})
        assert result.status == AtomStatus.FAILED
        assert "Missing 'branch'" in result.message

    def test_branch_already_exists_fails(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type(
                "R", (), {"returncode": 128, "stdout": "", "stderr": "already exists"}
            )()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "isolate", "branch": "flow/existing"})
        assert result.status == AtomStatus.FAILED
        assert "git switch -c failed" in result.message


# ---------------------------------------------------------------------------
# restore
# ---------------------------------------------------------------------------


class TestRestore:
    """restore switches back to the original branch."""

    def test_success(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "restore", "branch": "main"})
        assert result.status == AtomStatus.SUCCESS
        assert "main" in result.message

    def test_missing_branch_fails(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        result = atom.run({"intent": "restore"})
        assert result.status == AtomStatus.FAILED

    def test_switch_fails(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type(
                "R", (), {"returncode": 1, "stdout": "", "stderr": "no such branch"}
            )()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "restore", "branch": "nonexistent"})
        assert result.status == AtomStatus.FAILED


# ---------------------------------------------------------------------------
# discard_all
# ---------------------------------------------------------------------------


class TestDiscardAll:
    """discard_all cleans the working tree."""

    def test_success(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "discard_all"})
        assert result.status == AtomStatus.SUCCESS

    def test_restore_fails(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type("R", (), {"returncode": 1, "stdout": "", "stderr": "err"})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "discard_all"})
        assert result.status == AtomStatus.FAILED


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------


class TestRollback:
    """rollback undoes the last commit."""

    def test_success(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "rollback"})
        assert result.status == AtomStatus.SUCCESS
        assert "staged" in result.message

    def test_no_commits_fails(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type(
                "R", (), {"returncode": 128, "stdout": "", "stderr": "unknown rev"}
            )()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "rollback"})
        assert result.status == AtomStatus.FAILED


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------


class TestPublish:
    """publish pushes the current branch to remote."""

    def test_success_default_remote(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "publish"})
        assert result.status == AtomStatus.SUCCESS
        assert "origin" in result.message

    def test_success_with_branch(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "publish", "remote": "upstream", "branch": "main"})
        assert result.status == AtomStatus.SUCCESS
        assert "upstream" in result.message
        assert "main" in result.message

    def test_push_rejected(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type(
                "R", (), {"returncode": 1, "stdout": "", "stderr": "rejected"}
            )()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "publish"})
        assert result.status == AtomStatus.FAILED
        assert "git push failed" in result.message


# ---------------------------------------------------------------------------
# integrate
# ---------------------------------------------------------------------------


class TestIntegrate:
    """integrate merges source branch into target."""

    def test_success(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # checkout
                type("R", (), {"returncode": 0, "stdout": "Merge made\n", "stderr": ""})(),  # merge
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "integrate",
                    "source": "feat/login",
                    "target": "main",
                }
            )
        assert result.status == AtomStatus.SUCCESS
        assert "Merged" in result.message
        assert "merge_output" in result.exports

    def test_missing_source_fails(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        result = atom.run({"intent": "integrate", "target": "main"})
        assert result.status == AtomStatus.FAILED
        assert "Missing" in result.message

    def test_missing_target_fails(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        result = atom.run({"intent": "integrate", "source": "feat/x"})
        assert result.status == AtomStatus.FAILED

    def test_checkout_fails(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type(
                "R", (), {"returncode": 1, "stdout": "", "stderr": "no such branch"}
            )()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "integrate",
                    "source": "feat/x",
                    "target": "nonexistent",
                }
            )
        assert result.status == AtomStatus.FAILED
        assert "git checkout" in result.message

    def test_conflict_default_fail(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # checkout
                type(
                    "R", (), {"returncode": 1, "stdout": "", "stderr": "CONFLICT"}
                )(),  # merge fails
                type(
                    "R", (), {"returncode": 0, "stdout": "app.py\n", "stderr": ""}
                )(),  # diff --name-only
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # merge --abort
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "integrate",
                    "source": "feat/x",
                    "target": "main",
                }
            )
        assert result.status == AtomStatus.FAILED
        assert "Merge conflict" in result.message
        assert "app.py" in result.exports.get("conflict_files", [])

    def test_conflict_resolve_returns_retry(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # checkout
                type(
                    "R", (), {"returncode": 1, "stdout": "", "stderr": "CONFLICT"}
                )(),  # merge fails
                type(
                    "R", (), {"returncode": 0, "stdout": "app.py\nutils.py\n", "stderr": ""}
                )(),  # diff
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # merge --abort
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "integrate",
                    "source": "feat/x",
                    "target": "main",
                    "on_conflict": "resolve",
                }
            )
        assert result.status == AtomStatus.RETRY
        assert result.exports["needs_conflict_resolver"] is True
        assert "app.py" in result.exports["conflict_files"]
        assert "utils.py" in result.exports["conflict_files"]
        assert result.exports["source"] == "feat/x"
        assert result.exports["target"] == "main"


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------


class TestSync:
    """sync fetches and pulls from remote."""

    def test_success(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # fetch
                type("R", (), {"returncode": 0, "stdout": "Up to date\n", "stderr": ""})(),  # pull
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "sync"})
        assert result.status == AtomStatus.SUCCESS
        assert "origin" in result.message

    def test_fetch_fails(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type(
                "R", (), {"returncode": 1, "stdout": "", "stderr": "network err"}
            )()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "sync"})
        assert result.status == AtomStatus.FAILED
        assert "git fetch failed" in result.message

    def test_pull_conflict_aborts(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # fetch ok
                type(
                    "R", (), {"returncode": 1, "stdout": "", "stderr": "CONFLICT"}
                )(),  # pull fails
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # merge --abort
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "sync"})
        assert result.status == AtomStatus.FAILED
        assert "git pull failed" in result.message

    def test_custom_remote_and_branch(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "sync",
                    "remote": "upstream",
                    "branch": "develop",
                }
            )
        assert result.status == AtomStatus.SUCCESS
        assert "upstream" in result.message


# ---------------------------------------------------------------------------
# tag
# ---------------------------------------------------------------------------


class TestTag:
    """tag labels the current commit."""

    def test_success(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "tag", "name": "v1.0"})
        assert result.status == AtomStatus.SUCCESS
        assert result.exports["tag"] == "v1.0"

    def test_missing_name_fails(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        result = atom.run({"intent": "tag"})
        assert result.status == AtomStatus.FAILED
        assert "Missing 'name'" in result.message

    def test_tag_already_exists_fails(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type(
                "R", (), {"returncode": 128, "stdout": "", "stderr": "already exists"}
            )()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "tag", "name": "v1.0"})
        assert result.status == AtomStatus.FAILED


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Cross-cutting edge cases for GitAtom."""

    def test_cwd_property_is_readable(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        assert atom.cwd == tmp_path

    def test_cleanup_does_nothing(self, tmp_path: Path) -> None:
        """cleanup() is a no-op for GitAtom (no subprocess to kill)."""
        atom = GitAtom(cwd=tmp_path)
        atom.cleanup()  # Should not raise

    def test_engine_whitelist_contains_all_needed_commands(self, tmp_path: Path) -> None:
        expected = {
            "add",
            "commit",
            "diff",
            "status",
            "switch",
            "restore",
            "reset",
            "push",
            "checkout",
            "merge",
            "fetch",
            "pull",
            "rebase",
            "tag",
            "worktree",
            "ls-files",
        }
        assert expected == GitAtom._ENGINE_WHITELIST

    def test_empty_context_message_default(self, tmp_path: Path) -> None:
        """checkpoint without message uses default."""
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})(),
                type("R", (), {"returncode": 0, "stdout": "ok\n", "stderr": ""})(),
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "checkpoint"})
        assert result.status == AtomStatus.SUCCESS

    def test_integrate_on_conflict_unrecognized_defaults_to_fail(self, tmp_path: Path) -> None:
        """Unknown on_conflict value falls through to FAILED."""
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                type("R", (), {"returncode": 1, "stdout": "", "stderr": "CONFLICT"})(),
                type("R", (), {"returncode": 0, "stdout": "f.py\n", "stderr": ""})(),
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "integrate",
                    "source": "a",
                    "target": "b",
                    "on_conflict": "unknown_strategy",
                }
            )
        assert result.status == AtomStatus.FAILED


# ---------------------------------------------------------------------------
# worktree_add
# ---------------------------------------------------------------------------


class TestWorktreeAdd:
    """worktree_add creates a new worktree tracking a branch."""

    def test_success_with_defaults(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "worktree_add",
                    "path": ".worktrees/agent",
                    "branch": "feat/xyz",
                }
            )
        assert result.status == AtomStatus.SUCCESS
        assert result.exports["worktree_path"] == ".worktrees/agent"
        assert result.exports["branch"] == "feat/xyz"

    def test_missing_keys_fails(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        result1 = atom.run({"intent": "worktree_add", "branch": "feat"})
        result2 = atom.run({"intent": "worktree_add", "path": ".wt"})
        assert result1.status == AtomStatus.FAILED
        assert result2.status == AtomStatus.FAILED

    def test_git_failure(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type(
                "R", (), {"returncode": 128, "stdout": "", "stderr": "fatal"}
            )()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "worktree_add",
                    "path": ".wt",
                    "branch": "feat",
                }
            )
        assert result.status == AtomStatus.FAILED
        assert "fatal" in result.message


# ---------------------------------------------------------------------------
# is_tracked
# ---------------------------------------------------------------------------


class TestIsTracked:
    """is_tracked checks if a file is explicitly tracked in the git index."""

    def test_missing_path_fails(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        result = atom.run({"intent": "is_tracked"})
        assert result.status == AtomStatus.FAILED
        assert "Missing 'path'" in result.message

    def test_tracked_file_returns_true(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type(
                "R", (), {"returncode": 0, "stdout": "path/file.txt\n", "stderr": ""}
            )()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "is_tracked", "path": "path/file.txt"})
        assert result.status == AtomStatus.SUCCESS
        assert result.exports["is_tracked"] is True

    def test_untracked_file_returns_false(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run({"intent": "is_tracked", "path": "path/untracked.txt"})
        assert result.status == AtomStatus.SUCCESS
        assert result.exports["is_tracked"] is False


# ---------------------------------------------------------------------------
# worktree_teardown
# ---------------------------------------------------------------------------


class TestWorktreeTeardown:
    """worktree_teardown removes the worktree resiliently."""

    def test_success_clean_removal(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "worktree_teardown",
                    "path": ".worktrees/agent",
                }
            )
        assert result.status == AtomStatus.SUCCESS
        assert "Removed worktree" in result.message

    def test_missing_path_fails(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        result = atom.run({"intent": "worktree_teardown"})
        assert result.status == AtomStatus.FAILED
        assert "Missing 'path'" in result.message

    def test_windows_fallback_triggered_on_failure(self, tmp_path: Path) -> None:
        """If git worktree remove fails, it falls back to shutil.rmtree + prune."""
        worktree_path = tmp_path / ".worktrees" / "stub"
        worktree_path.mkdir(parents=True)

        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock_run:
            # First subproc fails (git worktree remove --force ...), second succeeds (git worktree prune)
            mock_run.side_effect = [
                type(
                    "R", (), {"returncode": 1, "stdout": "", "stderr": "Device or resource busy"}
                )(),
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "worktree_teardown",
                    "path": ".worktrees/stub",
                }
            )
        assert result.status == AtomStatus.SUCCESS
        assert "Fallback" in result.message
        assert not worktree_path.exists()

    @patch("specweaver.core.loom.atoms.git.worktree_ops.time.sleep")
    @patch("specweaver.core.loom.atoms.git.worktree_ops.shutil.rmtree")
    def test_windows_fallback_exhausts_retries_and_fails(
        self, mock_rmtree, mock_sleep, tmp_path: Path
    ) -> None:
        """If git worktree remove fails, and rmtree throws 5 times, it fails and sleeps."""
        worktree_path = tmp_path / ".worktrees" / "stub"
        worktree_path.mkdir(parents=True)

        mock_rmtree.side_effect = PermissionError("Locked")

        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "worktree_teardown",
                    "path": ".worktrees/stub",
                }
            )

        assert result.status == AtomStatus.FAILED
        assert "Fallback rmtree failed" in result.message
        assert mock_rmtree.call_count == 5
        assert mock_sleep.call_count == 4


# ---------------------------------------------------------------------------
# worktree_sync
# ---------------------------------------------------------------------------


class TestWorktreeSync:
    """worktree_sync pulls and rebases main into the active worktree."""

    def test_success_sync(self, tmp_path: Path) -> None:
        wt_dir = tmp_path / ".worktrees" / "agent"
        wt_dir.mkdir(parents=True)
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "worktree_sync",
                    "path": ".worktrees/agent",
                }
            )
        assert result.status == AtomStatus.SUCCESS

    def test_missing_path_fails(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        result = atom.run({"intent": "worktree_sync"})
        assert result.status == AtomStatus.FAILED


# ---------------------------------------------------------------------------
# strip_merge
# ---------------------------------------------------------------------------


class TestStripMerge:
    """strip_merge applies bounded allowed paths and merges using 'ours'."""

    def test_success_strip_allowed(self, tmp_path: Path) -> None:
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                # git merge
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                # git diff
                type(
                    "R",
                    (),
                    {
                        "returncode": 0,
                        "stdout": "src/good.py\nREADME.md\ndocs/arch.md\nsrc/bad.py\n",
                        "stderr": "",
                    },
                )(),
                # loops for README.md
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # reset
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # checkout
                # loops for docs/arch.md
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # reset
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # checkout
                # loops for src/bad.py
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # reset
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # checkout
                # git commit
                type("R", (), {"returncode": 0, "stdout": "committed strips", "stderr": ""})(),
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "strip_merge",
                    "branch": "sf-task-temp",
                    "allowed_paths": ["src/good.py"],
                }
            )
        assert result.status == AtomStatus.SUCCESS
        assert result.exports["stripped_files"] == ["README.md", "docs/arch.md", "src/bad.py"]

    def test_missing_keys_fails(self, tmp_path: Path) -> None:
        atom = GitAtom(cwd=tmp_path)
        assert atom.run({"intent": "strip_merge", "allowed_paths": []}).status == AtomStatus.FAILED
        assert atom.run({"intent": "strip_merge", "branch": "foo"}).status == AtomStatus.FAILED

    def test_strip_merge_preserves_doc_updates(self, tmp_path: Path) -> None:
        """doc_updates.md is explicitly preserved (FR-8) regardless of allowed_paths."""
        with patch("specweaver.core.loom.commons.git.executor.subprocess.run") as mock:
            mock.side_effect = [
                # git merge
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                # git diff
                type(
                    "R",
                    (),
                    {
                        "returncode": 0,
                        "stdout": "src/good.py\ncomponent/doc_updates.md\nsrc/bad.py\n",
                        "stderr": "",
                    },
                )(),
                # loops for src/bad.py ONLY (doc_updates is skipped)
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # reset
                type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),  # checkout
                # git commit
                type("R", (), {"returncode": 0, "stdout": "committed strips", "stderr": ""})(),
            ]
            atom = GitAtom(cwd=tmp_path)
            result = atom.run(
                {
                    "intent": "strip_merge",
                    "branch": "sf-task-temp",
                    "allowed_paths": ["src/good.py"],
                }
            )
        assert result.status == AtomStatus.SUCCESS
        assert result.exports["stripped_files"] == ["src/bad.py"]
