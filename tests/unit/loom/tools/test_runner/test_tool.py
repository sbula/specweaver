# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for TestRunnerTool and role-specific interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.loom.atoms.base import AtomResult, AtomStatus
from specweaver.loom.tools.test_runner.interfaces import (
    ImplementerTestInterface,
    ReviewerTestInterface,
    create_test_runner_interface,
)
from specweaver.loom.tools.test_runner.tool import (
    ROLE_INTENTS,
    TestRunnerTool,
    TestRunnerToolError,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Tool role gating
# ---------------------------------------------------------------------------


class TestToolRoleGating:
    """Tests that role gating on TestRunnerTool works correctly."""

    def test_implementer_can_run_tests(self, tmp_path: Path) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS, message="ok",
            exports={"passed": 5, "failed": 0, "total": 5},
        )
        tool = TestRunnerTool(atom=atom, role="implementer")
        result = tool.run_tests(target="tests/", kind="unit")
        assert result.status == "success"
        atom.run.assert_called_once()

    def test_implementer_can_run_linter_with_fix(self, tmp_path: Path) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS, message="ok",
            exports={"error_count": 0, "errors": []},
        )
        tool = TestRunnerTool(atom=atom, role="implementer")
        result = tool.run_linter(target="src/", fix=True)
        assert result.status == "success"

    def test_reviewer_can_run_tests(self, tmp_path: Path) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS, message="ok",
            exports={"passed": 3, "failed": 0, "total": 3},
        )
        tool = TestRunnerTool(atom=atom, role="reviewer")
        result = tool.run_tests(target="tests/")
        assert result.status == "success"

    def test_reviewer_cannot_run_linter_fix(self, tmp_path: Path) -> None:
        atom = MagicMock()
        tool = TestRunnerTool(atom=atom, role="reviewer")
        with pytest.raises(TestRunnerToolError, match="not allowed"):
            tool.run_linter(target="src/", fix=True)

    def test_reviewer_can_run_linter_readonly(self, tmp_path: Path) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS, message="ok",
            exports={"error_count": 0, "errors": []},
        )
        tool = TestRunnerTool(atom=atom, role="reviewer")
        result = tool.run_linter(target="src/", fix=False)
        assert result.status == "success"

    def test_drafter_cannot_run_tests(self, tmp_path: Path) -> None:
        atom = MagicMock()
        with pytest.raises(ValueError, match="Unknown role"):
            TestRunnerTool(atom=atom, role="drafter")

    def test_unknown_role_raises(self, tmp_path: Path) -> None:
        atom = MagicMock()
        with pytest.raises(ValueError, match="Unknown role"):
            TestRunnerTool(atom=atom, role="janitor")


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------


class TestInterfaces:
    """Tests for role-specific interfaces."""

    def test_implementer_interface(self, tmp_path: Path) -> None:
        with patch(
            "specweaver.loom.atoms.test_runner.atom.TestRunnerAtom",
        ) as mock_atom_cls:
            mock_atom = MagicMock()
            mock_atom.run.return_value = AtomResult(
                status=AtomStatus.SUCCESS, message="ok",
                exports={"passed": 5, "total": 5},
            )
            mock_atom_cls.return_value = mock_atom

            iface = create_test_runner_interface("implementer", tmp_path)

        assert isinstance(iface, ImplementerTestInterface)

    def test_reviewer_interface(self, tmp_path: Path) -> None:
        with patch(
            "specweaver.loom.atoms.test_runner.atom.TestRunnerAtom",
        ) as mock_atom_cls:
            mock_atom_cls.return_value = MagicMock()
            iface = create_test_runner_interface("reviewer", tmp_path)

        assert isinstance(iface, ReviewerTestInterface)

    def test_drafter_interface_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown role"):
            create_test_runner_interface("drafter", tmp_path)

    def test_reviewer_interface_has_no_fix(self, tmp_path: Path) -> None:
        """ReviewerTestInterface.run_linter should NOT allow fix=True."""
        with patch(
            "specweaver.loom.atoms.test_runner.atom.TestRunnerAtom",
        ) as mock_atom_cls:
            mock_atom = MagicMock()
            mock_atom.run.return_value = AtomResult(
                status=AtomStatus.SUCCESS, message="ok",
                exports={"error_count": 0, "errors": []},
            )
            mock_atom_cls.return_value = mock_atom

            iface = create_test_runner_interface("reviewer", tmp_path)
            # ReviewerTestInterface.run_linter should force fix=False
            result = iface.run_linter(target="src/")

        assert result.status == "success"


# ---------------------------------------------------------------------------
# Complexity — role gating
# ---------------------------------------------------------------------------


class TestToolComplexityGating:
    """Tests that run_complexity is properly role-gated."""

    def test_implementer_can_run_complexity(self) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS, message="ok",
            exports={"violation_count": 0, "max_complexity": 10, "violations": []},
        )
        tool = TestRunnerTool(atom=atom, role="implementer")
        result = tool.run_complexity(target="src/")
        assert result.status == "success"

    def test_reviewer_can_run_complexity(self) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS, message="ok",
            exports={"violation_count": 0, "max_complexity": 10, "violations": []},
        )
        tool = TestRunnerTool(atom=atom, role="reviewer")
        result = tool.run_complexity(target="src/")
        assert result.status == "success"

    def test_complexity_returns_error_on_violations(self) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.FAILED, message="2 violations",
            exports={"violation_count": 2, "max_complexity": 10, "violations": []},
        )
        tool = TestRunnerTool(atom=atom, role="implementer")
        result = tool.run_complexity(target="src/")
        assert result.status == "error"

    def test_complexity_passes_threshold(self) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS, message="ok",
            exports={"violation_count": 0, "max_complexity": 5, "violations": []},
        )
        tool = TestRunnerTool(atom=atom, role="implementer")
        tool.run_complexity(target="src/", max_complexity=5)

        # Verify atom.run was called with the right context
        call_ctx = atom.run.call_args[0][0]
        assert call_ctx["intent"] == "run_complexity"
        assert call_ctx["max_complexity"] == 5

    def test_role_intents_include_complexity(self) -> None:
        """Both implementer and reviewer have run_complexity."""
        assert "run_complexity" in ROLE_INTENTS["implementer"]
        assert "run_complexity" in ROLE_INTENTS["reviewer"]


class TestInterfaceComplexity:
    """Tests that role-specific interfaces expose run_complexity."""

    def test_implementer_has_run_complexity(self, tmp_path: Path) -> None:
        with patch(
            "specweaver.loom.atoms.test_runner.atom.TestRunnerAtom",
        ) as mock_atom_cls:
            mock_atom = MagicMock()
            mock_atom.run.return_value = AtomResult(
                status=AtomStatus.SUCCESS, message="ok",
                exports={"violation_count": 0, "max_complexity": 10, "violations": []},
            )
            mock_atom_cls.return_value = mock_atom

            iface = create_test_runner_interface("implementer", tmp_path)
            result = iface.run_complexity(target="src/")

        assert result.status == "success"

    def test_reviewer_has_run_complexity(self, tmp_path: Path) -> None:
        with patch(
            "specweaver.loom.atoms.test_runner.atom.TestRunnerAtom",
        ) as mock_atom_cls:
            mock_atom = MagicMock()
            mock_atom.run.return_value = AtomResult(
                status=AtomStatus.SUCCESS, message="ok",
                exports={"violation_count": 0, "max_complexity": 10, "violations": []},
            )
            mock_atom_cls.return_value = mock_atom

            iface = create_test_runner_interface("reviewer", tmp_path)
            result = iface.run_complexity(target="src/")

        assert result.status == "success"

