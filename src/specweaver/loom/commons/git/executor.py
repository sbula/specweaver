# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""GitExecutor — low-level git command executor with whitelist enforcement.

All commands run on the target project directory, never on SpecWeaver's own repo.
The working directory is set at construction time by the setup/config, not by the agent.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class ExecutorResult:
    """Standardized result from a raw git command execution."""

    status: str  # "success" or "error"
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


class GitExecutorError(Exception):
    """Raised when a git command is blocked or fails."""


class GitExecutor:
    """Low-level git command executor with whitelist enforcement.

    Args:
        cwd: Working directory for git commands (the target project).
              Set by setup/config — the agent cannot change this.
        whitelist: Set of allowed git subcommands (e.g., {"status", "diff", "add"}).
    """

    # Commands that are NEVER allowed, regardless of whitelist.
    _BLOCKED_ALWAYS: frozenset[str] = frozenset(
        {
            "push",
            "pull",
            "fetch",
            "merge",
            "rebase",
            "tag",
        }
    )

    def __init__(self, cwd: Path, whitelist: set[str]) -> None:
        # Validate no blocked commands snuck into the whitelist
        violations = self._BLOCKED_ALWAYS & whitelist
        if violations:
            msg = f"Cannot whitelist blocked commands: {violations}"
            raise GitExecutorError(msg)

        self._cwd = cwd
        self._whitelist = frozenset(whitelist)

    @property
    def cwd(self) -> Path:
        """The working directory for git commands (read-only)."""
        return self._cwd

    @property
    def whitelist(self) -> frozenset[str]:
        """The set of allowed git subcommands (read-only)."""
        return self._whitelist

    def run(self, command: str, *args: str, timeout: int = 30) -> ExecutorResult:
        """Execute a whitelisted git command.

        Args:
            command: Git subcommand (e.g., "status", "diff", "add").
            *args: Additional arguments for the command.
            timeout: Subprocess timeout in seconds.

        Returns:
            ExecutorResult with stdout, stderr, exit_code, and status.

        Raises:
            GitExecutorError: If the command is not whitelisted or blocked.
        """
        if command in self._BLOCKED_ALWAYS:
            msg = f"Command 'git {command}' is permanently blocked"
            logger.error("GitExecutor.run: blocked command attempted: %s", command)
            raise GitExecutorError(msg)

        if command not in self._whitelist:
            msg = (
                f"Command 'git {command}' is not in the whitelist. "
                f"Allowed: {sorted(self._whitelist)}"
            )
            logger.error("GitExecutor.run: non-whitelisted command attempted: %s", command)
            raise GitExecutorError(msg)

        # Reject any args that try to sneak in blocked commands
        # e.g., git -C /somewhere push
        for arg in args:
            if arg in self._BLOCKED_ALWAYS:
                msg = f"Blocked command 'git {arg}' found in arguments"
                logger.error("GitExecutor.run: blocked arg attempted: %s", arg)
                raise GitExecutorError(msg)

        logger.debug("GitExecutor.run: executing 'git %s %s'", command, " ".join(args))

        cmd = ["git", "-C", str(self._cwd), command, *args]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ExecutorResult(
                status="error",
                stderr=f"Command timed out after {timeout}s",
                exit_code=-1,
            )
        except OSError as exc:
            return ExecutorResult(
                status="error",
                stderr=f"OS error: {exc}",
                exit_code=-1,
            )

        return ExecutorResult(
            status="success" if result.returncode == 0 else "error",
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
        )
