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
from specweaver.sandbox.execution.models import ResourceLimits, SubprocessResult
from specweaver.sandbox.security import WorkspaceBoundary, WorkspaceBoundaryError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

_MAX_OUTPUT_BYTES = 1_048_576  # 1 MiB, FR-8
_DEFAULT_TIMEOUT_SECONDS = 120  # NFR-4
_MAX_TIMEOUT_SECONDS = 3600  # NFR-4 ceiling
_DEFAULT_RESOURCE_LIMITS = ResourceLimits(
    max_memory_bytes=2_147_483_648,  # 2 GiB, FR-11
    max_processes=128,
)


#: How much of a failing script's stderr goes into the failure MESSAGE. The full text is still in
#: `exports`; this is the part an operator reads without going looking.
_MESSAGE_STDERR_CHARS = 200


def _first_line(text: str) -> str:
    """The first non-empty line of `text`, bounded — enough to name a cause, not to bury it."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:_MESSAGE_STDERR_CHARS]
    return ""


def _truncate(text: str) -> str:
    """Truncate `text` to `_MAX_OUTPUT_BYTES` (UTF-8 byte length), FR-8."""
    encoded = text.encode("utf-8")
    if len(encoded) <= _MAX_OUTPUT_BYTES:
        return text
    return encoded[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore") + "...[TRUNCATED]"


def bash_param_errors(params: Mapping[str, Any]) -> list[str]:
    """What is wrong with a bash step's params; checked at load and again before each run."""
    errors = []
    script = params.get("script")
    if script is not None and not isinstance(script, str):
        errors.append("'script' must be a file name.")
    elif script and ("/" in script or "\\" in script or ".." in script):  # FR-2
        errors.append(
            f"Invalid script name {script!r}: must be a bare filename, no path separators."
        )
    env = params.get("env")
    if env is not None and not isinstance(env, dict):
        errors.append("'env' must be a map of names to values.")
    elif env and any(str(key).upper() == "PATH" for key in env):  # FR-12
        errors.append("The 'env' map may not set PATH (would hijack bash resolution).")
    args = params.get("args")
    if args is not None and not isinstance(args, list):
        errors.append("'args' must be a list.")
    timeout = params.get("timeout_seconds")
    if timeout is not None and (not isinstance(timeout, int) or timeout > _MAX_TIMEOUT_SECONDS):
        errors.append(
            f"timeout_seconds={timeout!r} must be whole seconds up to {_MAX_TIMEOUT_SECONDS}."
        )
    return errors


class BashActionAtom(Atom):
    """Runs a script from `.specweaver/scripts/` for an `action: bash` pipeline step."""

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd.resolve()
        self._scripts_root = self._cwd / ".specweaver" / "scripts"

    def run(self, context: dict[str, Any]) -> AtomResult:
        script = context.get("script")
        if not script:
            return AtomResult(status=AtomStatus.FAILED, message="Missing 'script' in context.")
        errors = bash_param_errors(context)
        if errors:
            return AtomResult(status=AtomStatus.FAILED, message=" ".join(errors))
        timeout_seconds = context.get("timeout_seconds") or _DEFAULT_TIMEOUT_SECONDS
        env: dict[str, str] = context.get("env") or {}

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
                status=AtomStatus.FAILED,
                message="bash interpreter not found on PATH.",
            )

        args = context.get("args") or []
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

        return _result(script, result, timeout_seconds)


def _result(script: str, result: SubprocessResult, timeout_seconds: int) -> AtomResult:
    """A finished run as an `AtomResult`: passed on exit 0, else failed with its cause named."""
    status = (
        AtomStatus.SUCCESS if result.exit_code == 0 and not result.timed_out else AtomStatus.FAILED
    )
    # The exit code alone names nothing. `exports` has always carried stderr, but the message is
    # what reaches a step's `error_message` and the operator's terminal — so a script that died
    # for an environmental reason read as an ordinary script failure.
    detail = _first_line(result.stderr)
    message = f"bash script '{script}' exited {result.exit_code}."
    if result.timed_out:
        message = f"bash script '{script}' timed out after {timeout_seconds} s."
    elif status is AtomStatus.FAILED and detail:
        message = f"{message} stderr: {detail}"
    return AtomResult(
        status=status,
        message=message,
        exports={
            "exit_code": result.exit_code,
            "stdout": _truncate(result.stdout),
            "stdout_truncated": len(result.stdout.encode("utf-8")) > _MAX_OUTPUT_BYTES,
            "stderr": _truncate(result.stderr),
            "duration_seconds": result.duration_seconds,
            "timed_out": result.timed_out,
        },
    )
