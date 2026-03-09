# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for git role interfaces and the factory function."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.tools.git.interfaces import (
    DebuggerGitInterface,
    DrafterGitInterface,
    ImplementerGitInterface,
    ReviewerGitInterface,
    create_git_interface,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Interface method exposure
# ---------------------------------------------------------------------------


class TestInterfaceMethodExposure:
    """Each interface class exposes ONLY the allowed methods."""

    def test_implementer_has_commit(self) -> None:
        assert hasattr(ImplementerGitInterface, "commit")
        assert hasattr(ImplementerGitInterface, "inspect_changes")
        assert hasattr(ImplementerGitInterface, "discard")
        assert hasattr(ImplementerGitInterface, "uncommit")
        assert hasattr(ImplementerGitInterface, "start_branch")
        assert hasattr(ImplementerGitInterface, "switch_branch")

    def test_implementer_has_no_reviewer_methods(self) -> None:
        assert not hasattr(ImplementerGitInterface, "history")
        assert not hasattr(ImplementerGitInterface, "blame")
        assert not hasattr(ImplementerGitInterface, "compare")
        assert not hasattr(ImplementerGitInterface, "show_commit")
        assert not hasattr(ImplementerGitInterface, "list_branches")

    def test_reviewer_has_read_only(self) -> None:
        assert hasattr(ReviewerGitInterface, "history")
        assert hasattr(ReviewerGitInterface, "show_commit")
        assert hasattr(ReviewerGitInterface, "blame")
        assert hasattr(ReviewerGitInterface, "compare")
        assert hasattr(ReviewerGitInterface, "list_branches")

    def test_reviewer_has_no_write_methods(self) -> None:
        assert not hasattr(ReviewerGitInterface, "commit")
        assert not hasattr(ReviewerGitInterface, "discard")
        assert not hasattr(ReviewerGitInterface, "uncommit")
        assert not hasattr(ReviewerGitInterface, "start_branch")

    def test_debugger_has_investigation(self) -> None:
        assert hasattr(DebuggerGitInterface, "history")
        assert hasattr(DebuggerGitInterface, "file_history")
        assert hasattr(DebuggerGitInterface, "show_old")
        assert hasattr(DebuggerGitInterface, "search_history")
        assert hasattr(DebuggerGitInterface, "reflog")
        assert hasattr(DebuggerGitInterface, "inspect_changes")

    def test_debugger_has_no_write_methods(self) -> None:
        assert not hasattr(DebuggerGitInterface, "commit")
        assert not hasattr(DebuggerGitInterface, "discard")
        assert not hasattr(DebuggerGitInterface, "start_branch")

    def test_drafter_has_minimal_write(self) -> None:
        assert hasattr(DrafterGitInterface, "commit")
        assert hasattr(DrafterGitInterface, "inspect_changes")
        assert hasattr(DrafterGitInterface, "discard")

    def test_drafter_has_no_branch_methods(self) -> None:
        assert not hasattr(DrafterGitInterface, "start_branch")
        assert not hasattr(DrafterGitInterface, "switch_branch")
        assert not hasattr(DrafterGitInterface, "uncommit")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestFactory:
    """create_git_interface returns the correct interface per role."""

    @patch("specweaver.tools.git.interfaces.GitExecutor")
    def test_implementer_returns_correct_type(
        self,
        mock_executor_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        iface = create_git_interface("implementer", tmp_path)
        assert isinstance(iface, ImplementerGitInterface)

    @patch("specweaver.tools.git.interfaces.GitExecutor")
    def test_reviewer_returns_correct_type(
        self,
        mock_executor_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        iface = create_git_interface("reviewer", tmp_path)
        assert isinstance(iface, ReviewerGitInterface)

    @patch("specweaver.tools.git.interfaces.GitExecutor")
    def test_debugger_returns_correct_type(
        self,
        mock_executor_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        iface = create_git_interface("debugger", tmp_path)
        assert isinstance(iface, DebuggerGitInterface)

    @patch("specweaver.tools.git.interfaces.GitExecutor")
    def test_drafter_returns_correct_type(
        self,
        mock_executor_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        iface = create_git_interface("drafter", tmp_path)
        assert isinstance(iface, DrafterGitInterface)

    def test_unknown_role_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown role"):
            create_git_interface("admin", tmp_path)

    @patch("specweaver.tools.git.interfaces.GitExecutor")
    def test_cwd_passed_to_executor(
        self,
        mock_executor_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        create_git_interface("implementer", tmp_path)
        mock_executor_cls.assert_called_once()
        call_kwargs = mock_executor_cls.call_args
        assert call_kwargs.kwargs["cwd"] == tmp_path


# ---------------------------------------------------------------------------
# Delegation: interfaces pass through to GitTool
# ---------------------------------------------------------------------------


class TestInterfaceDelegation:
    """Interface methods must delegate to the underlying GitTool."""

    def test_implementer_commit_delegates(self) -> None:
        mock_tool = MagicMock()
        mock_tool.commit.return_value = "result"
        iface = ImplementerGitInterface(mock_tool)
        result = iface.commit("feat: test")
        mock_tool.commit.assert_called_once_with("feat: test")
        assert result == "result"

    def test_reviewer_history_delegates(self) -> None:
        mock_tool = MagicMock()
        mock_tool.history.return_value = "result"
        iface = ReviewerGitInterface(mock_tool)
        result = iface.history(5)
        mock_tool.history.assert_called_once_with(5)
        assert result == "result"

    def test_debugger_file_history_delegates(self) -> None:
        mock_tool = MagicMock()
        mock_tool.file_history.return_value = "result"
        iface = DebuggerGitInterface(mock_tool)
        result = iface.file_history("app.py", 3)
        mock_tool.file_history.assert_called_once_with("app.py", 3)
        assert result == "result"

    def test_drafter_discard_delegates(self) -> None:
        mock_tool = MagicMock()
        mock_tool.discard.return_value = "result"
        iface = DrafterGitInterface(mock_tool)
        result = iface.discard("file.py")
        mock_tool.discard.assert_called_once_with("file.py")
        assert result == "result"

    def test_reviewer_compare_delegates(self) -> None:
        mock_tool = MagicMock()
        mock_tool.compare.return_value = "result"
        iface = ReviewerGitInterface(mock_tool)
        result = iface.compare("main", "dev")
        mock_tool.compare.assert_called_once_with("main", "dev")
        assert result == "result"

    def test_implementer_switch_branch_delegates(self) -> None:
        mock_tool = MagicMock()
        mock_tool.switch_branch.return_value = "result"
        iface = ImplementerGitInterface(mock_tool)
        result = iface.switch_branch("feat/other")
        mock_tool.switch_branch.assert_called_once_with("feat/other")
        assert result == "result"


# ---------------------------------------------------------------------------
# Factory edge cases
# ---------------------------------------------------------------------------


class TestFactoryEdgeCases:
    """Additional factory edge cases."""

    @patch("specweaver.tools.git.interfaces.GitExecutor")
    def test_factory_passes_correct_whitelist_for_implementer(
        self,
        mock_executor_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        create_git_interface("implementer", tmp_path)
        whitelist = mock_executor_cls.call_args.kwargs["whitelist"]
        assert "commit" in whitelist
        assert "add" in whitelist
        assert "switch" in whitelist

    @patch("specweaver.tools.git.interfaces.GitExecutor")
    def test_factory_passes_correct_whitelist_for_reviewer(
        self,
        mock_executor_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        create_git_interface("reviewer", tmp_path)
        whitelist = mock_executor_cls.call_args.kwargs["whitelist"]
        assert "log" in whitelist
        assert "commit" not in whitelist

    def test_factory_error_message_lists_known_roles(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError) as exc_info:
            create_git_interface("admin", tmp_path)
        error_msg = str(exc_info.value)
        assert "implementer" in error_msg
        assert "reviewer" in error_msg
        assert "debugger" in error_msg
        assert "drafter" in error_msg

