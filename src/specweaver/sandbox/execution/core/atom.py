# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""BashActionAtom — engine-level execution of a `.specweaver/scripts/` bash script.

Never agent-facing. Invoked only by the flow engine (via BashActionHandler, SF-2).
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.base import Atom, AtomResult, AtomStatus
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import ResourceLimits
from specweaver.sandbox.security import WorkspaceBoundary, WorkspaceBoundaryError

if TYPE_CHECKING:
    from pathlib import Path

_MAX_OUTPUT_BYTES = 1_048_576  # 1 MiB, FR-8
_MAX_TIMEOUT_SECONDS = 3600  # NFR-4 ceiling
_DEFAULT_RESOURCE_LIMITS = ResourceLimits(
    max_memory_bytes=2_147_483_648,  # 2 GiB, FR-11
    max_processes=128,
)


def _truncate(text: str) -> str:
    """Truncate `text` to `_MAX_OUTPUT_BYTES` (UTF-8 byte length), FR-8."""
    encoded = text.encode("utf-8")
    if len(encoded) <= _MAX_OUTPUT_BYTES:
        return text
    return encoded[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore") + "...[TRUNCATED]"


def _validate_cheap(
    script: str | None, timeout_seconds: int | None, env: dict[str, str],
) -> str | None:
    """In-memory checks that must pass before any filesystem/process I/O.

    Returns an error message, or None if all checks pass.
    """
    if not script:
        return "Missing 'script' in context."

    # FR-2 (part 1): bare-name-only, no separators/traversal
    if "/" in script or "\\" in script or ".." in script:
        return f"Invalid script name {script!r}: must be a bare filename, no path separators."

    if timeout_seconds is not None and timeout_seconds > _MAX_TIMEOUT_SECONDS:
        return f"timeout_seconds={timeout_seconds} exceeds the {_MAX_TIMEOUT_SECONDS}s ceiling."

    # FR-12: reject PATH override in the step-level env map, case-insensitively
    if any(key.upper() == "PATH" for key in env):
        return "The 'env' map may not set PATH (would hijack bash resolution)."

    return None


class BashActionAtom(Atom):
    """Runs a script from `.specweaver/scripts/` for an `action: bash` pipeline step."""

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd.resolve()
        self._scripts_root = self._cwd / ".specweaver" / "scripts"

    def run(self, context: dict[str, Any]) -> AtomResult:
        script = context.get("script")
        timeout_seconds = context.get("timeout_seconds")
        env: dict[str, str] = context.get("env", {})

        cheap_error = _validate_cheap(script, timeout_seconds, env)
        if cheap_error:
            return AtomResult(status=AtomStatus.FAILED, message=cheap_error)
        assert script is not None  # narrowed by _validate_cheap returning None

        try:
            # FR-2 (part 2): canonical containment check — this call IS the
            # "immediately before execution" checkpoint (research notes).
            boundary = WorkspaceBoundary(roots=[self._scripts_root])
            resolved = boundary.validate_path(self._scripts_root / script)
        except WorkspaceBoundaryError as exc:
            return AtomResult(status=AtomStatus.FAILED, message=str(exc))

        if not resolved.is_file():
            return AtomResult(status=AtomStatus.FAILED, message=f"Script not found: {resolved}")

        # Resolve to an absolute path, not the bare string "bash" — on Windows,
        # a bare command name goes through CreateProcess's default search order,
        # which checks C:\Windows\System32 (containing the WSL launcher stub)
        # BEFORE %PATH%, regardless of PATH order. shutil.which() searches %PATH%
        # directly, so it's the only reliable way to get the real interpreter.
        bash_path = shutil.which("bash")
        if not bash_path:
            return AtomResult(
                status=AtomStatus.FAILED, message="bash interpreter not found on PATH.",
            )

        args = context.get("args", [])
        working_dir = context.get("working_dir")
        cwd_override = (self._cwd / working_dir) if working_dir else None

        try:
            executor = SubprocessExecutor(cwd=self._cwd, resource_limits=_DEFAULT_RESOURCE_LIMITS)
            result = executor.execute(
                [bash_path, str(resolved), *args],
                timeout_seconds=timeout_seconds,
                extra_env=env,
                cwd_override=cwd_override,
            )
        except (ValueError, FileNotFoundError) as exc:
            # working_dir escapes project_path or doesn't exist (SubprocessExecutor._validate_cwd)
            return AtomResult(status=AtomStatus.FAILED, message=str(exc))
        except Exception as exc:  # FR-13: never propagate unhandled
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"bash script '{script}' crashed: {type(exc).__name__}: {exc}",
            )

        status = AtomStatus.SUCCESS if result.exit_code == 0 else AtomStatus.FAILED
        return AtomResult(
            status=status,
            message=f"bash script '{script}' exited {result.exit_code}.",
            exports={
                "exit_code": result.exit_code,
                "stdout": _truncate(result.stdout),
                "stderr": _truncate(result.stderr),
                "duration_seconds": result.duration_seconds,
            },
        )
