# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""TestRunnerTool — agent-facing, role-gated test execution and linting.

Wraps the TestRunnerAtom with role-based intent gating.
Agents receive a role-specific interface that exposes only allowed operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specweaver.llm.models import ToolDefinition
    from specweaver.loom.atoms.test_runner.atom import TestRunnerAtom


# ---------------------------------------------------------------------------
# Role → allowed intents
# ---------------------------------------------------------------------------

ROLE_INTENTS: dict[str, frozenset[str]] = {
    "implementer": frozenset({"run_tests", "run_linter", "run_linter_fix", "run_complexity"}),
    "reviewer": frozenset({"run_tests", "run_linter", "run_complexity"}),
    "planner": frozenset({"run_tests", "run_linter", "run_complexity"}),
    # drafter: no access — not in the map
}


# ---------------------------------------------------------------------------
# Tool result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolResult:
    """Result from a TestRunnerTool operation."""

    status: str  # "success" or "error"
    message: str = ""
    data: Any = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TestRunnerToolError(Exception):
    """Raised when a TestRunnerTool operation is blocked by role or config."""


# ---------------------------------------------------------------------------
# TestRunnerTool
# ---------------------------------------------------------------------------


class TestRunnerTool:
    """Agent-facing test runner with role-based intent gating.

    Args:
        atom: The TestRunnerAtom instance.
        role: The agent's role (determines which intents are allowed).
    """

    def __init__(self, atom: TestRunnerAtom, role: str) -> None:
        if role not in ROLE_INTENTS:
            msg = f"Unknown role: {role!r}. Known roles: {sorted(ROLE_INTENTS)}"
            raise ValueError(msg)
        self._atom = atom
        self._role = role

    @property
    def role(self) -> str:
        """The agent's role."""
        return self._role

    def run_tests(
        self,
        target: str,
        kind: str = "unit",
        scope: str = "",
        timeout: int = 120,
        coverage: bool = False,
    ) -> ToolResult:
        """Run tests (requires run_tests intent)."""
        self._require_intent("run_tests")

        result = self._atom.run({
            "intent": "run_tests",
            "target": target,
            "kind": kind,
            "scope": scope,
            "timeout": timeout,
            "coverage": coverage,
        })

        return ToolResult(
            status="success" if result.status.value == "SUCCESS" else "error",
            message=result.message,
            data=result.exports,
        )

    def run_linter(
        self,
        target: str,
        fix: bool = False,
    ) -> ToolResult:
        """Run linter (requires run_linter; fix=True requires run_linter_fix)."""
        if fix:
            self._require_intent("run_linter_fix")
        else:
            self._require_intent("run_linter")

        result = self._atom.run({
            "intent": "run_linter",
            "target": target,
            "fix": fix,
        })

        return ToolResult(
            status="success" if result.status.value == "SUCCESS" else "error",
            message=result.message,
            data=result.exports,
        )

    # -------------------------------------------------------------------
    # Internal: role gating
    # -------------------------------------------------------------------
    def definitions(self) -> list[ToolDefinition]:
        from specweaver.loom.tools.test_runner.definitions import INTENT_DEFINITIONS
        from specweaver.loom.tools.test_runner.tool import ROLE_INTENTS
        return [d for name, d in INTENT_DEFINITIONS.items() if name in ROLE_INTENTS[self._role]]


    def _require_intent(self, intent: str) -> None:
        """Raise if the current role doesn't have this intent."""
        if intent not in ROLE_INTENTS[self._role]:
            msg = (
                f"Intent {intent!r} is not allowed for role {self._role!r}. "
                f"Allowed: {sorted(ROLE_INTENTS[self._role])}"
            )
            raise TestRunnerToolError(msg)

    def run_complexity(
        self,
        target: str,
        max_complexity: int = 10,
    ) -> ToolResult:
        """Run complexity checks (requires run_complexity intent)."""
        self._require_intent("run_complexity")

        result = self._atom.run({
            "intent": "run_complexity",
            "target": target,
            "max_complexity": max_complexity,
        })

        return ToolResult(
            status="success" if result.status.value == "SUCCESS" else "error",
            message=result.message,
            data=result.exports,
        )
