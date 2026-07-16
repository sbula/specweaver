# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""ContainerSubprocessExecutor — routes QA-runner execution into an ephemeral
Podman/Docker container instead of the host (B-EXEC-01).

A ``SubprocessExecutor`` subclass: overrides ``execute()`` to wrap the incoming
``cmd`` into a ``podman``/``docker run`` invocation and delegates the actual
process spawning, timeout handling, and result contract to the parent class.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import sys
import tomllib
import uuid
from typing import TYPE_CHECKING

from specweaver.sandbox.execution.executor import SubprocessExecutor

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.sandbox.execution.models import (
        ContainerMounts,
        ResourceLimits,
        SubprocessResult,
    )

logger = logging.getLogger(__name__)

_SUPPORTED_TAGS: tuple[str, ...] = ("3.11", "3.12", "3.13")
_DEFAULT_TAG = "3.13"
_DEFAULT_IMAGE_REPO = "ghcr.io/sbula/specweaver-sandbox-python"

# NFR-5 / AD-4: reuse BashActionAtom's resource-limit defaults verbatim (2 GiB / 128 procs)
# rather than inventing a second limits schema for the same underlying concern.
_CONTAINER_MEMORY_BYTES = 2_147_483_648
_CONTAINER_PIDS_LIMIT = 128

_ENGINES: tuple[str, ...] = ("podman", "docker")  # AD-6: podman preferred, docker fallback


class ContainerEngineUnavailableError(Exception):
    """Raised when neither podman nor docker is detected and live on the host (FR-7)."""


def _resolve_image(source_root: Path) -> str:
    """Pick an image tag from ``requires-python``, defaulting to the newest supported."""
    version = _DEFAULT_TAG
    pyproject = source_root / "pyproject.toml"
    if pyproject.exists():
        try:
            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            requires_python = data.get("project", {}).get("requires-python", "")
            match = re.search(r"3\.(\d+)", requires_python)
            if match:
                minor = int(match.group(1))
                candidate = f"3.{minor}"
                if candidate in _SUPPORTED_TAGS:
                    version = candidate
                elif minor < 11:
                    version = _SUPPORTED_TAGS[0]
                else:
                    version = _DEFAULT_TAG
        except (OSError, tomllib.TOMLDecodeError, AttributeError, TypeError):
            logger.debug("ContainerSubprocessExecutor: could not parse %s for requires-python", pyproject)
    return f"{_DEFAULT_IMAGE_REPO}:{version}"


class ContainerSubprocessExecutor(SubprocessExecutor):
    """Runs commands inside an ephemeral, auto-removed Podman/Docker container.

    Args:
        cwd: Project root (passed through to ``SubprocessExecutor`` — the local
            engine CLI's own working directory, not the container's).
        mounts: Host paths for the RO source mount and RW scratch/cache mounts.
        image: Explicit image reference. Defaults to a tag resolved from the
            target project's ``requires-python``.
        run_id: Used to build a deterministic, collision-resistant container name.
        timeout_seconds: Default timeout, forwarded to ``SubprocessExecutor``.
        resource_limits: Forwarded to ``SubprocessExecutor`` — applies to the
            *local* engine CLI client process, not the containerized process
            (container-side limits are the separate ``--memory``/``--pids-limit``
            flags built in ``_build_container_cmd``).
    """

    def __init__(
        self,
        cwd: Path,
        mounts: ContainerMounts,
        image: str | None = None,
        run_id: str | None = None,
        timeout_seconds: int = 120,
        resource_limits: ResourceLimits | None = None,
    ) -> None:
        super().__init__(cwd=cwd, timeout_seconds=timeout_seconds, resource_limits=resource_limits)

        mounts.scratch_root.mkdir(parents=True, exist_ok=True)
        mounts.cache_root.mkdir(parents=True, exist_ok=True)

        self._mounts = mounts
        self._run_id = run_id or uuid.uuid4().hex[:12]
        self._image = image or _resolve_image(mounts.source_root)
        self._engine: str | None = None

    def _ensure_engine(self) -> str:
        """Lazily detect and memoize a live container engine (FR-6, FR-7, Finding #2)."""
        if self._engine is not None:
            return self._engine

        attempted: list[str] = []
        for name in _ENGINES:
            resolved = shutil.which(name)
            if not resolved:
                attempted.append(name)
                continue
            probe = super().execute([resolved, "info"], timeout_seconds=5)
            if probe.exit_code == 0:
                self._engine = resolved
                return resolved
            attempted.append(name)

        msg = (
            f"No live container engine found (tried: {', '.join(attempted)}). "
            "Install Podman or Docker, or set [sandbox] execution_mode = \"host\" "
            "in specweaver.toml."
        )
        raise ContainerEngineUnavailableError(msg)

    def _baseline_flags(self) -> list[str]:
        """Security/resource flags shared by BOTH the prepare and execute phases (Red/Blue
        fix — the prepare phase runs `uv sync`, which can execute arbitrary sdist build code
        from PyPI, so it gets the same cap-drop/resource/user hardening as the execute phase,
        everything except `--network none` and `--read-only`, which the prepare phase's callers
        add themselves since only the execute phase needs `--read-only` on this shared set)."""
        flags = [
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--memory",
            str(_CONTAINER_MEMORY_BYTES),
            "--pids-limit",
            str(_CONTAINER_PIDS_LIMIT),
        ]
        if sys.platform != "win32":
            flags.extend(["--user", f"{os.getuid()}:{os.getgid()}"])
        else:
            logger.warning(
                "ContainerSubprocessExecutor: running as the container image's default user "
                "on Windows — non-root enforcement (NFR-4) is Linux/macOS-only for now (NFR-11)."
            )
        return flags

    def _ensure_prepared(self) -> None:
        """Network-enabled `uv sync` prepare phase, gated by a lockfile-hash stamp (AD-7, AD-9)."""
        lockfile = self._mounts.source_root / "uv.lock"
        if not lockfile.exists():
            lockfile = self._mounts.source_root / "pyproject.toml"
        if not lockfile.exists():
            return

        digest = hashlib.sha256(lockfile.read_bytes()).hexdigest()
        # Sibling of cache_root, NOT inside it — uv itself owns/may reorganize cache_root's
        # contents, so a stamp file living inside it could be silently wiped (Red/Blue fix).
        stamp_file = self._mounts.cache_root.parent / ".prepared_hash"
        if stamp_file.exists() and stamp_file.read_text().strip() == digest:
            return

        engine = self._ensure_engine()
        # Deterministic name + pre/post idempotent cleanup (AD-8) — applies equally to the
        # prepare-phase container, not just the execute-phase one (Red/Blue fix: `--rm` alone
        # is the exact anti-pattern AD-8 exists to avoid, and a 300s prepare timeout is long
        # enough for a host-side SIGKILL to leave one orphaned).
        name = f"specweaver-prepare-{self._run_id}-{uuid.uuid4().hex[:8]}"
        super().execute([engine, "rm", "-f", name], timeout_seconds=10)
        prepare_cmd = [
            engine,
            "run",
            "--rm",
            "--name",
            name,
            "--read-only",
            "-v",
            f"{self._mounts.source_root}:/workspace:ro",
            "-v",
            f"{self._mounts.cache_root}:/cache:rw",
            "--tmpfs",
            "/tmp:size=100m,mode=1777",
            *self._baseline_flags(),
            "-e",
            "UV_CACHE_DIR=/cache",
            "--workdir",
            "/workspace",
            self._image,
            "uv",
            "sync",
        ]
        try:
            result = super().execute(prepare_cmd, timeout_seconds=300)
        finally:
            super().execute([engine, "rm", "-f", name], timeout_seconds=10)

        if result.exit_code == 0:
            stamp_file.write_text(digest)
        else:
            logger.warning(
                "ContainerSubprocessExecutor: prepare-phase 'uv sync' failed (exit=%d): %s",
                result.exit_code,
                result.stderr,
            )

    def _build_container_cmd(
        self,
        engine: str,
        name: str,
        cmd: list[str],
        extra_env: dict[str, str] | None,
    ) -> list[str]:
        """Build the `<engine> run ...` argv wrapping `cmd` (FR-2, FR-3, NFR-2..NFR-5)."""
        argv = [
            engine,
            "run",
            "--rm",
            "--name",
            name,
            "--read-only",
            "-v",
            f"{self._mounts.source_root}:/workspace:ro",
            "-v",
            f"{self._mounts.scratch_root}:/scratch:rw",
            "--tmpfs",
            "/tmp:size=100m,mode=1777",
            "--network",
            "none",
            *self._baseline_flags(),
        ]

        for key, value in (extra_env or {}).items():
            argv.extend(["-e", f"{key}={value}"])

        argv.extend(["--workdir", "/workspace", self._image, *cmd])
        return argv

    def execute(
        self,
        cmd: list[str],
        *,
        timeout_seconds: int | None = None,
        extra_env: dict[str, str] | None = None,
        cwd_override: Path | None = None,
        input_text: str | None = None,
    ) -> SubprocessResult:
        """Run `cmd` inside an ephemeral container instead of directly on the host."""
        if cwd_override is not None:
            logger.warning(
                "ContainerSubprocessExecutor.execute: cwd_override is ignored in container "
                "mode; the container always runs against its constructor-provided source_root."
            )

        engine = self._ensure_engine()
        self._ensure_prepared()

        name = f"specweaver-qa-{self._run_id}-{uuid.uuid4().hex[:8]}"

        # AD-8: idempotent pre-run cleanup — a prior crashed run may have left a
        # same-named container behind. Result is intentionally ignored (no-op if absent).
        super().execute([engine, "rm", "-f", name], timeout_seconds=10)

        wrapped = self._build_container_cmd(engine, name, cmd, extra_env)

        try:
            return super().execute(wrapped, timeout_seconds=timeout_seconds, input_text=input_text)
        finally:
            # AD-8: unconditional post-run cleanup — never relies on --rm alone, which only
            # guarantees removal on graceful container exit, not on a host-side SIGKILL.
            super().execute([engine, "rm", "-f", name], timeout_seconds=10)
