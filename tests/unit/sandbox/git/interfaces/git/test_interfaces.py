# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for git role interfaces and the factory function."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.loom.tools.git.interfaces import (
    ConflictResolverGitInterface,
    DebuggerGitInterface,
    DrafterGitInterface,
    ImplementerGitInterface,
    ReviewerGitInterface,
    create_git_interface,
)
from specweaver.core.loom.tools.git.tool import ROLE_INTENTS

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

    def test_implementer_has_no_debugger_methods(self) -> None:
        assert not hasattr(ImplementerGitInterface, "file_history")
        assert not hasattr(ImplementerGitInterface, "show_old")
        assert not hasattr(ImplementerGitInterface, "search_history")
        assert not hasattr(ImplementerGitInterface, "reflog")

    def test_implementer_has_no_conflict_resolver_methods(self) -> None:
        assert not hasattr(ImplementerGitInterface, "list_conflicts")
        assert not hasattr(ImplementerGitInterface, "show_conflict")
        assert not hasattr(ImplementerGitInterface, "mark_resolved")
        assert not hasattr(ImplementerGitInterface, "abort_merge")
        assert not hasattr(ImplementerGitInterface, "complete_merge")

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
        assert not hasattr(ReviewerGitInterface, "switch_branch")

    def test_reviewer_has_no_debugger_methods(self) -> None:
        assert not hasattr(ReviewerGitInterface, "file_history")
        assert not hasattr(ReviewerGitInterface, "show_old")
        assert not hasattr(ReviewerGitInterface, "search_history")
        assert not hasattr(ReviewerGitInterface, "reflog")
        assert not hasattr(ReviewerGitInterface, "inspect_changes")

    def test_reviewer_has_no_conflict_resolver_methods(self) -> None:
        assert not hasattr(ReviewerGitInterface, "list_conflicts")
        assert not hasattr(ReviewerGitInterface, "show_conflict")
        assert not hasattr(ReviewerGitInterface, "mark_resolved")
        assert not hasattr(ReviewerGitInterface, "abort_merge")
        assert not hasattr(ReviewerGitInterface, "complete_merge")

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
        assert not hasattr(DebuggerGitInterface, "uncommit")
        assert not hasattr(DebuggerGitInterface, "start_branch")
        assert not hasattr(DebuggerGitInterface, "switch_branch")

    def test_debugger_has_no_reviewer_only_methods(self) -> None:
        assert not hasattr(DebuggerGitInterface, "show_commit")
        assert not hasattr(DebuggerGitInterface, "blame")
        assert not hasattr(DebuggerGitInterface, "compare")
        assert not hasattr(DebuggerGitInterface, "list_branches")

    def test_debugger_has_no_conflict_resolver_methods(self) -> None:
        assert not hasattr(DebuggerGitInterface, "list_conflicts")
        assert not hasattr(DebuggerGitInterface, "show_conflict")
        assert not hasattr(DebuggerGitInterface, "mark_resolved")
        assert not hasattr(DebuggerGitInterface, "abort_merge")
        assert not hasattr(DebuggerGitInterface, "complete_merge")

    def test_drafter_has_minimal_write(self) -> None:
        assert hasattr(DrafterGitInterface, "commit")
        assert hasattr(DrafterGitInterface, "inspect_changes")
        assert hasattr(DrafterGitInterface, "discard")

    def test_drafter_has_no_branch_methods(self) -> None:
        assert not hasattr(DrafterGitInterface, "start_branch")
        assert not hasattr(DrafterGitInterface, "switch_branch")
        assert not hasattr(DrafterGitInterface, "uncommit")

    def test_drafter_has_no_reviewer_methods(self) -> None:
        assert not hasattr(DrafterGitInterface, "history")
        assert not hasattr(DrafterGitInterface, "show_commit")
        assert not hasattr(DrafterGitInterface, "blame")
        assert not hasattr(DrafterGitInterface, "compare")
        assert not hasattr(DrafterGitInterface, "list_branches")

    def test_drafter_has_no_debugger_methods(self) -> None:
        assert not hasattr(DrafterGitInterface, "file_history")
        assert not hasattr(DrafterGitInterface, "show_old")
        assert not hasattr(DrafterGitInterface, "search_history")
        assert not hasattr(DrafterGitInterface, "reflog")

    def test_drafter_has_no_conflict_resolver_methods(self) -> None:
        assert not hasattr(DrafterGitInterface, "list_conflicts")
        assert not hasattr(DrafterGitInterface, "show_conflict")
        assert not hasattr(DrafterGitInterface, "mark_resolved")
        assert not hasattr(DrafterGitInterface, "abort_merge")
        assert not hasattr(DrafterGitInterface, "complete_merge")

    def test_conflict_resolver_has_only_conflict_methods(self) -> None:
        assert hasattr(ConflictResolverGitInterface, "list_conflicts")
        assert hasattr(ConflictResolverGitInterface, "show_conflict")
        assert hasattr(ConflictResolverGitInterface, "mark_resolved")
        assert hasattr(ConflictResolverGitInterface, "abort_merge")
        assert hasattr(ConflictResolverGitInterface, "complete_merge")

    def test_conflict_resolver_has_no_implementer_methods(self) -> None:
        assert not hasattr(ConflictResolverGitInterface, "commit")
        assert not hasattr(ConflictResolverGitInterface, "inspect_changes")
        assert not hasattr(ConflictResolverGitInterface, "discard")
        assert not hasattr(ConflictResolverGitInterface, "uncommit")
        assert not hasattr(ConflictResolverGitInterface, "start_branch")
        assert not hasattr(ConflictResolverGitInterface, "switch_branch")

    def test_conflict_resolver_has_no_reviewer_methods(self) -> None:
        assert not hasattr(ConflictResolverGitInterface, "history")
        assert not hasattr(ConflictResolverGitInterface, "show_commit")
        assert not hasattr(ConflictResolverGitInterface, "blame")
        assert not hasattr(ConflictResolverGitInterface, "compare")
        assert not hasattr(ConflictResolverGitInterface, "list_branches")

    def test_conflict_resolver_has_no_debugger_methods(self) -> None:
        assert not hasattr(ConflictResolverGitInterface, "file_history")
        assert not hasattr(ConflictResolverGitInterface, "show_old")
        assert not hasattr(ConflictResolverGitInterface, "search_history")
        assert not hasattr(ConflictResolverGitInterface, "reflog")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TestFactory:
    """create_git_interface returns the correct interface per role."""

    @patch("specweaver.core.loom.tools.git.interfaces.GitExecutor")
    def test_implementer_returns_correct_type(
        self,
        mock_executor_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        iface = create_git_interface("implementer", tmp_path)
        assert isinstance(iface, ImplementerGitInterface)

    @patch("specweaver.core.loom.tools.git.interfaces.GitExecutor")
    def test_reviewer_returns_correct_type(
        self,
        mock_executor_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        iface = create_git_interface("reviewer", tmp_path)
        assert isinstance(iface, ReviewerGitInterface)

    @patch("specweaver.core.loom.tools.git.interfaces.GitExecutor")
    def test_debugger_returns_correct_type(
        self,
        mock_executor_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        iface = create_git_interface("debugger", tmp_path)
        assert isinstance(iface, DebuggerGitInterface)

    @patch("specweaver.core.loom.tools.git.interfaces.GitExecutor")
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

    @patch("specweaver.core.loom.tools.git.interfaces.GitExecutor")
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
        mock_tool.commit.return_value = MagicMock()
        iface = ImplementerGitInterface(mock_tool)
        result = iface.commit("feat: test")
        mock_tool.commit.assert_called_once_with("feat: test")
        assert result == mock_tool.commit.return_value

    def test_reviewer_history_delegates(self) -> None:
        mock_tool = MagicMock()
        mock_tool.history.return_value = MagicMock()
        iface = ReviewerGitInterface(mock_tool)
        result = iface.history(5)
        mock_tool.history.assert_called_once_with(5)
        assert result == mock_tool.history.return_value

    def test_debugger_file_history_delegates(self) -> None:
        mock_tool = MagicMock()
        mock_tool.file_history.return_value = MagicMock()
        iface = DebuggerGitInterface(mock_tool)
        result = iface.file_history("app.py", 3)
        mock_tool.file_history.assert_called_once_with("app.py", 3)
        assert result == mock_tool.file_history.return_value

    def test_drafter_discard_delegates(self) -> None:
        mock_tool = MagicMock()
        mock_tool.discard.return_value = MagicMock()
        iface = DrafterGitInterface(mock_tool)
        result = iface.discard("file.py")
        mock_tool.discard.assert_called_once_with("file.py")
        assert result == mock_tool.discard.return_value

    def test_reviewer_compare_delegates(self) -> None:
        mock_tool = MagicMock()
        mock_tool.compare.return_value = MagicMock()
        iface = ReviewerGitInterface(mock_tool)
        result = iface.compare("main", "dev")
        mock_tool.compare.assert_called_once_with("main", "dev")
        assert result == mock_tool.compare.return_value

    def test_implementer_switch_branch_delegates(self) -> None:
        mock_tool = MagicMock()
        mock_tool.switch_branch.return_value = MagicMock()
        iface = ImplementerGitInterface(mock_tool)
        result = iface.switch_branch("feat/other")
        mock_tool.switch_branch.assert_called_once_with("feat/other")
        assert result == mock_tool.switch_branch.return_value


# ---------------------------------------------------------------------------
# Factory edge cases
# ---------------------------------------------------------------------------


class TestFactoryEdgeCases:
    """Additional factory edge cases."""

    @patch("specweaver.core.loom.tools.git.interfaces.GitExecutor")
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

    @patch("specweaver.core.loom.tools.git.interfaces.GitExecutor")
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


# ---------------------------------------------------------------------------
# Exhaustive invisibility: data-driven from ROLE_INTENTS
# ---------------------------------------------------------------------------

# Map role name -> interface class
_ROLE_INTERFACE_CLASS = {
    "implementer": ImplementerGitInterface,
    "reviewer": ReviewerGitInterface,
    "debugger": DebuggerGitInterface,
    "drafter": DrafterGitInterface,
    "conflict_resolver": ConflictResolverGitInterface,
}

# Collect ALL intent method names across every role.
_ALL_INTENTS: set[str] = set()
for _intents in ROLE_INTENTS.values():
    _ALL_INTENTS |= _intents

# Build parametrize cases: (interface_class, forbidden_method)
_INVISIBLE_CASES: list[tuple[type, str]] = []
for _role, _iface_cls in _ROLE_INTERFACE_CLASS.items():
    _allowed = ROLE_INTENTS[_role]
    for _intent in sorted(_ALL_INTENTS - _allowed):
        _INVISIBLE_CASES.append((_iface_cls, _intent))


class TestExhaustiveInvisibility:
    """Every non-whitelisted intent MUST be invisible on every interface.

    This test is data-driven from ROLE_INTENTS so it automatically catches
    regressions when new intents are added. It guarantees agents never see
    methods they cannot use, saving tokens.
    """

    @pytest.mark.parametrize(
        "iface_cls,method",
        _INVISIBLE_CASES,
        ids=[f"{cls.__name__}.{m}" for cls, m in _INVISIBLE_CASES],
    )
    def test_method_is_invisible(
        self,
        iface_cls: type,
        method: str,
    ) -> None:
        assert not hasattr(iface_cls, method), (
            f"{iface_cls.__name__} exposes '{method}' but should not — "
            f"agents would waste tokens seeing a method they cannot use"
        )
