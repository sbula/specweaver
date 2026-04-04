# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""QARunnerTool — agent-facing, role-gated test execution and linting.

Wraps the QARunnerAtom with role-based intent gating.
Agents receive a role-specific interface that exposes only allowed operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from specweaver.llm.models import ToolDefinition
    from specweaver.loom.atoms.qa_runner.atom import QARunnerAtom


# ---------------------------------------------------------------------------
# Role → allowed intents
# ---------------------------------------------------------------------------

ROLE_INTENTS: dict[str, frozenset[str]] = {
    "implementer": frozenset(
        {
            "run_tests",
            "run_linter",
            "run_linter_fix",
            "run_complexity",
            "run_compiler",
            "run_debugger",
            "run_architecture",
        }
    ),
    "reviewer": frozenset(
        {"run_tests", "run_linter", "run_complexity", "run_compiler", "run_debugger", "run_architecture"}
    ),
    "planner": frozenset({"run_tests", "run_linter", "run_complexity", "run_architecture"}),
    # drafter: no access — not in the map
}


# ---------------------------------------------------------------------------
# Tool result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolResult:
    """Result from a QARunnerTool operation."""

    status: str  # "success" or "error"
    message: str = ""
    data: Any = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class QARunnerToolError(Exception):
    """Raised when a QARunnerTool operation is blocked by role or config."""


# ---------------------------------------------------------------------------
# QARunnerTool
# ---------------------------------------------------------------------------


class QARunnerTool:
    """Agent-facing test runner with role-based intent gating.

    Args:
        atom: The QARunnerAtom instance.
        role: The agent's role (determines which intents are allowed).
    """

    def __init__(self, atom: QARunnerAtom, role: str) -> None:
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
        logger.debug("QARunnerTool.run_tests: target=%s, kind=%s", target, kind)

        result = self._atom.run(
            {
                "intent": "run_tests",
                "target": target,
                "kind": kind,
                "scope": scope,
                "timeout": timeout,
                "coverage": coverage,
            }
        )

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

        logger.debug("QARunnerTool.run_linter: target=%s, fix=%r", target, fix)

        result = self._atom.run(
            {
                "intent": "run_linter",
                "target": target,
                "fix": fix,
            }
        )

        return ToolResult(
            status="success" if result.status.value == "SUCCESS" else "error",
            message=result.message,
            data=result.exports,
        )

    # -------------------------------------------------------------------
    # Internal: role gating
    # -------------------------------------------------------------------
    def definitions(self) -> list[ToolDefinition]:
        from specweaver.loom.tools.qa_runner.definitions import INTENT_DEFINITIONS
        from specweaver.loom.tools.qa_runner.tool import ROLE_INTENTS

        return [d for name, d in INTENT_DEFINITIONS.items() if name in ROLE_INTENTS[self._role]]

    def _require_intent(self, intent: str) -> None:
        """Raise if the current role doesn't have this intent."""
        if intent not in ROLE_INTENTS[self._role]:
            msg = (
                f"Intent {intent!r} is not allowed for role {self._role!r}. "
                f"Allowed: {sorted(ROLE_INTENTS[self._role])}"
            )
            raise QARunnerToolError(msg)

    def run_complexity(
        self,
        target: str,
        max_complexity: int = 10,
    ) -> ToolResult:
        """Run complexity checks (requires run_complexity intent)."""
        self._require_intent("run_complexity")
        logger.debug("QARunnerTool.run_complexity: target=%s", target)

        result = self._atom.run(
            {
                "intent": "run_complexity",
                "target": target,
                "max_complexity": max_complexity,
            }
        )

        return ToolResult(
            status="success" if result.status.value == "SUCCESS" else "error",
            message=result.message,
            data=result.exports,
        )

    def run_compiler(self, target: str) -> ToolResult:
        """Run compilation/build (requires run_compiler intent)."""
        self._require_intent("run_compiler")
        logger.debug("QARunnerTool.run_compiler: target=%s", target)

        result = self._atom.run(
            {
                "intent": "run_compiler",
                "target": target,
            }
        )

        return ToolResult(
            status="success" if result.status.value == "SUCCESS" else "error",
            message=result.message,
            data=result.exports,
        )

    def run_debugger(self, target: str, entrypoint: str) -> ToolResult:
        """Run debugger (requires run_debugger intent)."""
        self._require_intent("run_debugger")
        logger.debug("QARunnerTool.run_debugger: target=%s entrypoint=%s", target, entrypoint)

        result = self._atom.run(
            {
                "intent": "run_debugger",
                "target": target,
                "entrypoint": entrypoint,
            }
        )

        return ToolResult(
            status="success" if result.status.value == "SUCCESS" else "error",
            message=result.message,
            data=result.exports,
        )

    def run_architecture(self, target: str) -> ToolResult:
        """Run architectural boundary checks (requires run_architecture intent)."""
        self._require_intent("run_architecture")
        logger.debug("QARunnerTool.run_architecture: target=%s", target)

        result = self._atom.run(
            {
                "intent": "run_architecture",
                "target": target,
            }
        )

        return ToolResult(
            status="success" if result.status.value == "SUCCESS" else "error",
            message=result.message,
            data=result.exports,
        )
