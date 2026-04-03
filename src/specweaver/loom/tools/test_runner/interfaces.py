# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Role-specific interfaces for test runner operations.

Each interface class exposes ONLY the intents allowed for its role.
The agent receives one of these — it physically cannot call methods
that don't exist on its interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.loom.tools.test_runner.tool import TestRunnerTool, ToolResult

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.llm.models import ToolDefinition


# ---------------------------------------------------------------------------
# Role-specific interfaces
# ---------------------------------------------------------------------------


class ImplementerTestInterface:
    """Test runner interface for the Implementer role.

    Allowed: run_tests, run_linter (with fix), run_complexity.
    """

    def __init__(self, tool: TestRunnerTool) -> None:
        self._tool = tool

    def definitions(self) -> list[ToolDefinition]:
        return self._tool.definitions()

    def run_tests(
        self,
        target: str,
        kind: str = "unit",
        scope: str = "",
        timeout: int = 120,
        coverage: bool = False,
    ) -> ToolResult:
        """Run tests."""
        return self._tool.run_tests(
            target=target,
            kind=kind,
            scope=scope,
            timeout=timeout,
            coverage=coverage,
        )

    def run_linter(
        self,
        target: str,
        fix: bool = False,
    ) -> ToolResult:
        """Run linter with optional fix."""
        return self._tool.run_linter(target=target, fix=fix)

    def run_complexity(
        self,
        target: str,
        max_complexity: int = 10,
    ) -> ToolResult:
        """Run complexity checks."""
        return self._tool.run_complexity(target=target, max_complexity=max_complexity)

    def run_compiler(self, target: str) -> ToolResult:
        """Run compilation/build."""
        return self._tool.run_compiler(target=target)

    def run_debugger(self, target: str, entrypoint: str) -> ToolResult:
        """Run debugger."""
        return self._tool.run_debugger(target=target, entrypoint=entrypoint)


class ReviewerTestInterface:
    """Test runner interface for the Reviewer role.

    Allowed: run_tests, run_linter (read-only, no fix), run_complexity.
    """

    def __init__(self, tool: TestRunnerTool) -> None:
        self._tool = tool

    def definitions(self) -> list[ToolDefinition]:
        return self._tool.definitions()

    def run_tests(
        self,
        target: str,
        kind: str = "unit",
        scope: str = "",
        timeout: int = 120,
        coverage: bool = False,
    ) -> ToolResult:
        """Run tests."""
        return self._tool.run_tests(
            target=target,
            kind=kind,
            scope=scope,
            timeout=timeout,
            coverage=coverage,
        )

    def run_linter(self, target: str) -> ToolResult:
        """Run linter (read-only, fix is always False)."""
        return self._tool.run_linter(target=target, fix=False)

    def run_complexity(
        self,
        target: str,
        max_complexity: int = 10,
    ) -> ToolResult:
        """Run complexity checks."""
        return self._tool.run_complexity(target=target, max_complexity=max_complexity)

    def run_compiler(self, target: str) -> ToolResult:
        """Run compilation/build."""
        return self._tool.run_compiler(target=target)

    def run_debugger(self, target: str, entrypoint: str) -> ToolResult:
        """Run debugger."""
        return self._tool.run_debugger(target=target, entrypoint=entrypoint)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_ROLE_INTERFACE_MAP: dict[str, type[ImplementerTestInterface | ReviewerTestInterface]] = {
    "implementer": ImplementerTestInterface,
    "reviewer": ReviewerTestInterface,
    "planner": ReviewerTestInterface,
}

TestInterface = ImplementerTestInterface | ReviewerTestInterface


def create_test_runner_interface(
    role: str,
    cwd: Path,
    language: str = "python",
) -> ImplementerTestInterface | ReviewerTestInterface:
    """Create a role-specific test runner interface.

    Args:
        role: The agent's role ("implementer" or "reviewer").
        cwd: The target project's working directory.
        language: Programming language (default: "python").

    Returns:
        A role-specific interface with only the allowed methods.

    Raises:
        ValueError: If the role is unknown.
    """
    if role not in _ROLE_INTERFACE_MAP:
        msg = f"Unknown role: {role!r}. Known roles: {sorted(_ROLE_INTERFACE_MAP)}"
        raise ValueError(msg)

    from specweaver.loom.atoms.test_runner.atom import TestRunnerAtom

    atom = TestRunnerAtom(cwd=cwd, language=language)
    tool = TestRunnerTool(atom=atom, role=role)

    interface_cls = _ROLE_INTERFACE_MAP[role]
    return interface_cls(tool)
