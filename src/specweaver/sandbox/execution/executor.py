# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""SubprocessExecutor — unified, cross-platform subprocess execution.

Provides structured output capture, timeout escalation, environment isolation,
credential stripping, path validation, and telemetry logging for all subprocess
calls within the sandbox.

Cross-platform: Windows 11 (26H2+), Linux (kernel 7.1+), macOS Tahoe (26+).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from typing import TYPE_CHECKING

from specweaver.commons.qa import OutputEvent

from ._signals import track_process
from .models import ResourceLimits, SubprocessResult
from .platform_limiter import get_platform_limiter

if TYPE_CHECKING:
    from pathlib import Path

    from .platform_limiter import PlatformLimiter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default environment allowlist (H-3: includes GIT_* vars)
# ---------------------------------------------------------------------------

_DEFAULT_ENV_ALLOWLIST: frozenset[str] = frozenset({
    "PATH", "HOME", "USERPROFILE", "LANG", "LC_ALL", "TERM",
    "PYTHONPATH", "PYTHONHASHSEED",
    "NODE_PATH", "CARGO_HOME", "JAVA_HOME", "GRADLE_HOME",
    "GOPATH", "GOROOT",
    "VIRTUAL_ENV", "CONDA_PREFIX",
    "TMPDIR", "TEMP", "TMP",
    "SystemRoot", "COMSPEC",
    "GIT_EXEC_PATH", "GIT_DIR",
})

# Credential env vars to ALWAYS strip — even from extra_env (red team cycle 1)
_CREDENTIAL_VARS: frozenset[str] = frozenset({
    "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "MISTRAL_API_KEY", "QWEN_API_KEY", "AWS_SECRET_ACCESS_KEY",
})

# Prefix-based credential stripping
_CREDENTIAL_PREFIXES: tuple[str, ...] = ("AZURE_",)


class SubprocessExecutor:
    """Unified, cross-platform subprocess execution with security boundaries.

    Handles all OS-specific differences internally so callers see one
    consistent API across Windows 11, Linux, and macOS.

    Args:
        cwd: Working directory for all subprocesses.
        timeout_seconds: Default timeout (overridable per-call).
        resource_limits: Optional resource constraints.
        env_allowlist: Env vars to forward to child (default: safe set).
        strip_credentials: If True, remove known API key env vars.
    """

    def __init__(
        self,
        cwd: Path,
        timeout_seconds: int = 120,
        resource_limits: ResourceLimits | None = None,
        env_allowlist: frozenset[str] | None = None,
        strip_credentials: bool = True,
    ) -> None:
        self._cwd = cwd.resolve()
        self._timeout_seconds = timeout_seconds
        self._resource_limits = resource_limits or ResourceLimits()
        self._env_allowlist = env_allowlist if env_allowlist is not None else _DEFAULT_ENV_ALLOWLIST
        self._strip_credentials = strip_credentials
        self._limiter: PlatformLimiter = get_platform_limiter()

    def execute(
        self,
        cmd: list[str],
        *,
        timeout_seconds: int | None = None,
        extra_env: dict[str, str] | None = None,
        cwd_override: Path | None = None,
    ) -> SubprocessResult:
        """Execute a subprocess with full security and telemetry.

        Args:
            cmd: Command to execute as a list of strings.
            timeout_seconds: Override default timeout. Uses constructor default if None.
            extra_env: Additional env vars to inject into child.
            cwd_override: Override working directory for this execution.

        Returns:
            SubprocessResult with structured output and telemetry.

        Raises:
            ValueError: If cwd_override escapes the allowed boundary.
            FileNotFoundError: If cwd_override does not exist.
        """
        effective_timeout = timeout_seconds if timeout_seconds is not None else self._timeout_seconds
        effective_cwd = self._validate_cwd(cwd_override)
        env = self._build_env(extra_env)

        # Build preexec_fn for Unix resource limits
        preexec_fn = self._limiter.make_preexec_fn(self._resource_limits)

        # Popen kwargs — preexec_fn is Unix-only
        popen_kwargs: dict[str, object] = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "cwd": str(effective_cwd),
            "env": env,
        }
        if sys.platform != "win32" and preexec_fn is not None:
            popen_kwargs["preexec_fn"] = preexec_fn

        start = time.monotonic()
        timed_out = False
        stdout = ""
        stderr = ""
        exit_code = -1

        try:
            proc = subprocess.Popen(cmd, **popen_kwargs)
            track_process(proc)

            # Apply post-start limits (Windows Job Objects)
            self._limiter.apply_post_start(proc, self._resource_limits)

            stdout, stderr = proc.communicate(timeout=effective_timeout)
            exit_code = proc.returncode

        except subprocess.TimeoutExpired:
            timed_out = True
            self._kill_process(proc)
            # Collect any partial output
            try:
                stdout, stderr = proc.communicate(timeout=2)
            except (subprocess.TimeoutExpired, OSError):
                stdout = ""
                stderr = ""
            exit_code = proc.returncode if proc.returncode is not None else -1

        except OSError as exc:
            stderr = str(exc)

        duration = time.monotonic() - start

        # Build output events
        events = self._build_events(stdout, stderr)

        # Telemetry logging
        logger.debug(
            "subprocess_execute: cmd=%s cwd=%s timeout=%d exit_code=%d "
            "duration_seconds=%.3f timed_out=%s",
            cmd,
            effective_cwd,
            effective_timeout,
            exit_code,
            duration,
            timed_out,
        )

        return SubprocessResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
            timed_out=timed_out,
            events=events,
        )

    def _build_env(self, extra_env: dict[str, str] | None) -> dict[str, str]:
        """Build a clean child environment from allowlist.

        1. Start from empty dict
        2. Copy allowed vars from parent environment
        3. Merge extra_env
        4. Strip all credential vars (even if injected via extra_env)
        """
        env: dict[str, str] = {}

        # Copy allowed vars from parent
        for key in self._env_allowlist:
            val = os.environ.get(key)
            if val is not None:
                env[key] = val

        # Merge extra_env
        if extra_env:
            env.update(extra_env)

        # Strip credentials — ALWAYS, even if injected via extra_env
        if self._strip_credentials:
            for key in _CREDENTIAL_VARS:
                env.pop(key, None)
            for key in list(env.keys()):
                for prefix in _CREDENTIAL_PREFIXES:
                    if key.startswith(prefix):
                        del env[key]
                        break

        return env

    def _validate_cwd(self, cwd_override: Path | None) -> Path:
        """Validate and resolve the working directory.

        Follows symlinks via ``Path.resolve()`` and checks the resolved
        path is within the constructor-provided boundary.

        Raises:
            ValueError: If resolved path escapes the boundary.
            FileNotFoundError: If the path does not exist.
        """
        if cwd_override is None:
            return self._cwd

        resolved = cwd_override.resolve()
        if not resolved.exists():
            msg = f"cwd_override does not exist: {cwd_override}"
            raise FileNotFoundError(msg)

        # Check the resolved path is within the boundary
        boundary = self._cwd
        try:
            resolved.relative_to(boundary)
        except ValueError:
            msg = (
                f"Path traversal blocked: {cwd_override} resolves to "
                f"{resolved}, which is outside the boundary {boundary}"
            )
            raise ValueError(msg) from None

        return resolved

    @staticmethod
    def _kill_process(proc: subprocess.Popen[str]) -> None:
        """Kill a timed-out process with OS-appropriate escalation.

        H-1 decision:
        - Unix/macOS: SIGTERM → 2s grace → SIGKILL
        - Windows 11: proc.terminate() (TerminateProcess, immediate)
        """
        if sys.platform == "win32":
            # On Windows, terminate() IS the kill — no grace period
            proc.terminate()
        else:
            # Unix/macOS: SIGTERM, then SIGKILL after grace period
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

    @staticmethod
    def _build_events(stdout: str, stderr: str) -> list[OutputEvent]:
        """Convert stdout/stderr lines to OutputEvent objects."""
        events: list[OutputEvent] = []

        for line in stdout.splitlines():
            if line.strip():
                events.append(OutputEvent(category="stdout", output=line))

        for line in stderr.splitlines():
            if line.strip():
                events.append(OutputEvent(category="stderr", output=line))

        return events

