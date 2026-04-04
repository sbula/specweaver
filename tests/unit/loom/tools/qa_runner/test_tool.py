# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for QARunnerTool and role-specific interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.loom.atoms.base import AtomResult, AtomStatus
from specweaver.loom.tools.qa_runner.interfaces import (
    ImplementerTestInterface,
    ReviewerTestInterface,
    create_qa_runner_interface,
)
from specweaver.loom.tools.qa_runner.tool import (
    ROLE_INTENTS,
    ToolResult,
)
from specweaver.loom.tools.qa_runner.tool import (
    QARunnerTool as _QARunnerTool,
)
from specweaver.loom.tools.qa_runner.tool import (
    QARunnerToolError as _QARunnerToolError,
)

# Alias back locally so tests don't break
QARunnerTool = _QARunnerTool
QARunnerTool.__test__ = False  # type: ignore[attr-defined]
QARunnerToolError = _QARunnerToolError
QARunnerToolError.__test__ = False  # type: ignore[attr-defined]

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Tool role gating
# ---------------------------------------------------------------------------


class TestToolRoleGating:
    """Tests that role gating on QARunnerTool works correctly."""

    def test_implementer_can_run_tests(self, tmp_path: Path) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"passed": 5, "failed": 0, "total": 5},
        )
        tool = QARunnerTool(atom=atom, role="implementer")
        result = tool.run_tests(target="tests/", kind="unit")
        assert result.status == "success"
        atom.run.assert_called_once()

    def test_implementer_can_run_linter_with_fix(self, tmp_path: Path) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"error_count": 0, "errors": []},
        )
        tool = QARunnerTool(atom=atom, role="implementer")
        result = tool.run_linter(target="src/", fix=True)
        assert result.status == "success"

    def test_implementer_can_run_architecture(self, tmp_path: Path) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"violation_count": 0, "violations": []},
        )
        tool = QARunnerTool(atom=atom, role="implementer")
        result = tool.run_architecture(target="src/")
        assert result.status == "success"

    def test_reviewer_can_run_tests(self, tmp_path: Path) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"passed": 3, "failed": 0, "total": 3},
        )
        tool = QARunnerTool(atom=atom, role="reviewer")
        result = tool.run_tests(target="tests/")
        assert result.status == "success"

    def test_reviewer_cannot_run_linter_fix(self, tmp_path: Path) -> None:
        atom = MagicMock()
        tool = QARunnerTool(atom=atom, role="reviewer")
        with pytest.raises(QARunnerToolError, match="not allowed"):
            tool.run_linter(target="src/", fix=True)

    def test_reviewer_can_run_linter_readonly(self, tmp_path: Path) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"error_count": 0, "errors": []},
        )
        tool = QARunnerTool(atom=atom, role="reviewer")
        result = tool.run_linter(target="src/", fix=False)
        assert result.status == "success"

    def test_drafter_cannot_run_tests(self, tmp_path: Path) -> None:
        atom = MagicMock()
        with pytest.raises(ValueError, match="Unknown role"):
            QARunnerTool(atom=atom, role="drafter")

    def test_unknown_role_raises(self, tmp_path: Path) -> None:
        atom = MagicMock()
        with pytest.raises(ValueError, match="Unknown role"):
            QARunnerTool(atom=atom, role="janitor")


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------


class TestInterfaces:
    """Tests for role-specific interfaces."""

    def test_implementer_interface(self, tmp_path: Path) -> None:
        with patch(
            "specweaver.loom.atoms.qa_runner.atom.QARunnerAtom",
        ) as mock_atom_cls:
            mock_atom = MagicMock()
            mock_atom.run.return_value = AtomResult(
                status=AtomStatus.SUCCESS,
                message="ok",
                exports={"passed": 5, "total": 5},
            )
            mock_atom_cls.return_value = mock_atom

            iface = create_qa_runner_interface("implementer", tmp_path)

        assert isinstance(iface, ImplementerTestInterface)

    def test_reviewer_interface(self, tmp_path: Path) -> None:
        with patch(
            "specweaver.loom.atoms.qa_runner.atom.QARunnerAtom",
        ) as mock_atom_cls:
            mock_atom_cls.return_value = MagicMock()
            iface = create_qa_runner_interface("reviewer", tmp_path)

        assert isinstance(iface, ReviewerTestInterface)

    def test_drafter_interface_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown role"):
            create_qa_runner_interface("drafter", tmp_path)

    def test_reviewer_interface_has_no_fix(self, tmp_path: Path) -> None:
        """ReviewerTestInterface.run_linter should NOT allow fix=True."""
        with patch(
            "specweaver.loom.atoms.qa_runner.atom.QARunnerAtom",
        ) as mock_atom_cls:
            mock_atom = MagicMock()
            mock_atom.run.return_value = AtomResult(
                status=AtomStatus.SUCCESS,
                message="ok",
                exports={"error_count": 0, "errors": []},
            )
            mock_atom_cls.return_value = mock_atom

            iface = create_qa_runner_interface("reviewer", tmp_path)
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
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"violation_count": 0, "max_complexity": 10, "violations": []},
        )
        tool = QARunnerTool(atom=atom, role="implementer")
        result = tool.run_complexity(target="src/")
        assert result.status == "success"

    def test_reviewer_can_run_complexity(self) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"violation_count": 0, "max_complexity": 10, "violations": []},
        )
        tool = QARunnerTool(atom=atom, role="reviewer")
        result = tool.run_complexity(target="src/")
        assert result.status == "success"

    def test_complexity_returns_error_on_violations(self) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.FAILED,
            message="2 violations",
            exports={"violation_count": 2, "max_complexity": 10, "violations": []},
        )
        tool = QARunnerTool(atom=atom, role="implementer")
        result = tool.run_complexity(target="src/")
        assert result.status == "error"

    def test_complexity_passes_threshold(self) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"violation_count": 0, "max_complexity": 5, "violations": []},
        )
        tool = QARunnerTool(atom=atom, role="implementer")
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
            "specweaver.loom.atoms.qa_runner.atom.QARunnerAtom",
        ) as mock_atom_cls:
            mock_atom = MagicMock()
            mock_atom.run.return_value = AtomResult(
                status=AtomStatus.SUCCESS,
                message="ok",
                exports={"violation_count": 0, "max_complexity": 10, "violations": []},
            )
            mock_atom_cls.return_value = mock_atom

            iface = create_qa_runner_interface("implementer", tmp_path)
            result = iface.run_complexity(target="src/")

        assert result.status == "success"

    def test_reviewer_has_run_complexity(self, tmp_path: Path) -> None:
        with patch(
            "specweaver.loom.atoms.qa_runner.atom.QARunnerAtom",
        ) as mock_atom_cls:
            mock_atom = MagicMock()
            mock_atom.run.return_value = AtomResult(
                status=AtomStatus.SUCCESS,
                message="ok",
                exports={"violation_count": 0, "max_complexity": 10, "violations": []},
            )
            mock_atom_cls.return_value = mock_atom

            iface = create_qa_runner_interface("reviewer", tmp_path)
            result = iface.run_complexity(target="src/")

        assert result.status == "success"


# ---------------------------------------------------------------------------
# Compiler & Debugger — role gating
# ---------------------------------------------------------------------------


class TestToolCompileDebugGating:
    """Tests that run_compiler and run_debugger are properly role-gated."""

    def test_implementer_can_run_compiler(self) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"error_count": 0, "warning_count": 0, "errors": []},
        )
        tool = QARunnerTool(atom=atom, role="implementer")
        result = tool.run_compiler(target="src/")
        assert result.status == "success"

    def test_reviewer_can_run_debugger(self) -> None:
        atom = MagicMock()
        atom.run.return_value = AtomResult(
            status=AtomStatus.SUCCESS,
            message="ok",
            exports={"exit_code": 0, "duration_seconds": 1.0, "events": []},
        )
        tool = QARunnerTool(atom=atom, role="reviewer")
        result = tool.run_debugger(target="src/", entrypoint="main.py")
        assert result.status == "success"

    def test_role_intents_include_compile_and_debug(self) -> None:
        """Both implementer and reviewer have compiler and debugger intents."""
        assert "run_compiler" in ROLE_INTENTS["implementer"]
        assert "run_debugger" in ROLE_INTENTS["implementer"]
        assert "run_compiler" in ROLE_INTENTS["reviewer"]
        assert "run_debugger" in ROLE_INTENTS["reviewer"]

    def test_role_intents_include_architecture(self) -> None:
        """implementer, reviewer, and planner have architecture intents."""
        assert "run_architecture" in ROLE_INTENTS["implementer"]
        assert "run_architecture" in ROLE_INTENTS["reviewer"]
        assert "run_architecture" in ROLE_INTENTS["planner"]


class TestInterfaceCompileDebug:
    """Tests that role-specific interfaces expose compilation and debugging."""

    def test_implementer_has_run_compiler(self, tmp_path: Path) -> None:
        with patch("specweaver.loom.atoms.qa_runner.atom.QARunnerAtom") as mock_atom_cls:
            mock_atom = MagicMock()
            mock_atom.run.return_value = AtomResult(
                status=AtomStatus.SUCCESS,
                message="ok",
                exports={"error_count": 0, "warning_count": 0, "errors": []},
            )
            mock_atom_cls.return_value = mock_atom

            iface = create_qa_runner_interface("implementer", tmp_path)
            result = iface.run_compiler(target="src/")

        assert result.status == "success"

    def test_implementer_has_run_debugger(self, tmp_path: Path) -> None:
        with patch("specweaver.loom.atoms.qa_runner.atom.QARunnerAtom") as mock_atom_cls:
            mock_atom = MagicMock()
            mock_atom.run.return_value = AtomResult(
                status=AtomStatus.SUCCESS,
                message="ok",
                exports={"exit_code": 0, "duration_seconds": 1.0, "events": []},
            )
            mock_atom_cls.return_value = mock_atom

            iface = create_qa_runner_interface("implementer", tmp_path)
            result = iface.run_debugger(target="src/", entrypoint="main.py")

        assert result.status == "success"

    def test_interfaces_has_run_architecture(self, tmp_path: Path) -> None:
        with patch("specweaver.loom.atoms.qa_runner.atom.QARunnerAtom") as mock_atom_cls:
            mock_atom = MagicMock()
            mock_atom.run.return_value = AtomResult(
                status=AtomStatus.SUCCESS,
                message="ok",
                exports={"violation_count": 0, "violations": []},
            )
            mock_atom_cls.return_value = mock_atom

            iface = create_qa_runner_interface("implementer", tmp_path)
            result = iface.run_architecture(target="src/")
            assert result.status == "success"


# ---------------------------------------------------------------------------
# Legacy Proxy Gaps — QARunnerTool & Interfaces
# ---------------------------------------------------------------------------


class TestToolLegacyProxyGaps:
    """Tests that cover pre-existing gaps in the Tool and Interface layers."""

    def test_tool_definitions_mapping(self) -> None:
        """Tool generates correct LLM definitions based on the assigned role."""
        atom = MagicMock()
        tool = QARunnerTool(atom=atom, role="implementer")

        # Override the definitions map purely for test determinism
        with patch(
            "specweaver.loom.tools.qa_runner.definitions.INTENT_DEFINITIONS",
            {"run_tests": {"name": "run_tests"}, "dummy": {"name": "dummy"}},
        ), patch.dict(
            "specweaver.loom.tools.qa_runner.tool.ROLE_INTENTS",
            {"implementer": frozenset({"run_tests"})},
        ):
            defs = tool.definitions()
            assert len(defs) == 1
            assert getattr(defs[0], "name", defs[0].get("name") if isinstance(defs[0], dict) else None) == "run_tests"

    def test_require_intent_blocks_disallowed_intent(self) -> None:
        """Tool blocks execution if role lacks intent (covering line 92 gap)."""
        atom = MagicMock()
        tool = QARunnerTool(atom=atom, role="implementer")

        with patch.dict(
            "specweaver.loom.tools.qa_runner.tool.ROLE_INTENTS", {"implementer": frozenset()}
        ), pytest.raises(QARunnerToolError, match="not allowed for role"):
            tool.run_tests(target="src/")

    def test_implementer_proxy_passthrough(self, tmp_path: Path) -> None:
        """Implementer interface preserves arguments perfectly when delegating to the tool."""
        tool = MagicMock()
        iface = ImplementerTestInterface(tool=tool)

        # 1. definitions
        tool.definitions.return_value = [MagicMock(name="fake")]
        assert iface.definitions() == tool.definitions.return_value

        tool.run_tests.return_value = ToolResult(status="success")
        iface.run_tests(target="src/", kind="e2e", scope="auth", timeout=60, coverage=True)
        tool.run_tests.assert_called_once_with(
            target="src/", kind="e2e", scope="auth", timeout=60, coverage=True
        )

        # 3. run_linter
        tool.run_linter.return_value = ToolResult(status="success")
        iface.run_linter(target="src/", fix=True)
        tool.run_linter.assert_called_once_with(target="src/", fix=True)

    def test_reviewer_proxy_passthrough(self, tmp_path: Path) -> None:
        """Reviewer interface preserves arguments except for run_linter fix."""
        tool = MagicMock()
        iface = ReviewerTestInterface(tool=tool)

        # 1. definitions
        tool.definitions.return_value = [MagicMock(name="fake")]
        assert iface.definitions() == tool.definitions.return_value

        # 2. run_tests
        tool.run_tests.return_value = ToolResult(status="success")
        iface.run_tests(target="src/", kind="unit", scope="", timeout=120, coverage=False)
        tool.run_tests.assert_called_once_with(
            target="src/", kind="unit", scope="", timeout=120, coverage=False
        )

    def test_factory_invalid_role(self, tmp_path: Path) -> None:
        """Factory triggers value error for invalid roles directly (missing path)."""
        with pytest.raises(ValueError, match="Unknown role"):
            create_qa_runner_interface("non_existent_role", tmp_path, language="python")
