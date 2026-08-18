# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""ContainerSubprocessExecutor — routes QA-runner execution into an ephemeral
Podman/Docker container instead of the host.

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
from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.tooling_sources import ToolingSource, declared_pytest

if TYPE_CHECKING:
    from specweaver.sandbox.execution.models import (
        ContainerMounts,
        ResourceLimits,
        SubprocessResult,
    )

logger = logging.getLogger(__name__)

_SUPPORTED_TAGS: tuple[str, ...] = ("3.11", "3.12", "3.13")
_DEFAULT_TAG = "3.13"
#: Where the prepare phase builds the target project's environment. On the rw cache mount,
#: because the source tree is mounted read-only and `uv`'s default `.venv` lands there.
_PREPARED_VENV = "/cache/venv"

#: The execute phase's `PATH`, written literally because `-e PATH=...` is not shell-expanded.
#: The prepared environment goes first so `python -m pytest` resolves to what the prepare phase
#: installed rather than to the image's own interpreter.
_CONTAINER_PATH = (
    f"{_PREPARED_VENV}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
)

#: The QA runner invokes `python -m pytest` and nothing else, so this is the entire predicate: a
#: group is worth syncing exactly when it puts pytest in the environment.
#:
#: `tox` and `nox` are deliberately absent even though both are test runners. They build their own
#: environments and would leave `python -m pytest` failing exactly as before, while installing the
#: rest of that group — and the prepare phase executes arbitrary sdist build code, so widening what
#: an untrusted project builds for no gain is the wrong trade. `coverage` is absent for the simpler
#: reason that it measures a run and cannot start one.
_TEST_RUNNERS: tuple[str, ...] = ("pytest",)

#: `uv sync` installs this group unasked. Requesting it again would be noise.
_DEFAULT_GROUP = "dev"

#: Installed only when the project names no runner anywhere. Bare: which plugins a suite needs
#: is exactly what the project failed to say, so guessing at them would add arbitrary packages
#: to an already arbitrary choice.
_LAST_RESORT_RUNNER = "pytest"


def _declares_a_runner(deps: list[object]) -> bool:
    """Whether a dependency-group's entries include something that can run a test suite."""
    for dep in deps:
        if not isinstance(dep, str):
            # A PEP 735 `{include-group = "..."}` table. The included group is judged on its own
            # entries, so following the reference here would only find it twice.
            continue
        name = re.split(r"[<>=!~;\[\s]", dep.strip(), maxsplit=1)[0].lower().replace("_", "-")
        if any(name == runner or name.startswith(f"{runner}-") for runner in _TEST_RUNNERS):
            return True
    return False


def _manifest_declares_a_runner(manifest_text: str) -> bool:
    """Whether `uv` can install pytest from this manifest alone, by group or at runtime.

    The gate on reading any other file. A project that declares pytest has pinned it, and layering a
    `tox.ini` block over that resolution would turn a reproducible run into a mixed one.
    """
    try:
        manifest = tomllib.loads(manifest_text)
    except (tomllib.TOMLDecodeError, ValueError):
        return False
    runtime = (manifest.get("project") or {}).get("dependencies")
    return bool(_groups_holding_a_runner(manifest_text)) or (
        isinstance(runtime, list) and _declares_a_runner(runtime)
    )


def _groups_holding_a_runner(manifest_text: str) -> list[str]:
    """Every PEP 735 group that declares pytest, `dev` included.

    `dev` is returned rather than filtered here because the two prepare paths disagree about it:
    `uv sync` installs it unasked, while `uv pip install` installs nothing it is not given. Dropping
    it at the source would silently strip the most common runner location from the second path.

    Detection is by content because the names are a long tail: `test`, `tests`, `testing`, `ci`,
    `test-core` and `dev-base` all carry pytest across the measured corpus, while
    `tests-postgresql` and `tests-mysql` carry database drivers and none. A name list would miss
    the first set and install the second.

    It is also the only safe rule. `uv sync --group <undeclared>` exits 2 rather than warning, so a
    speculative name would break the prepare phase for every project that does not use it; only
    groups this manifest actually declares are ever returned.

    A manifest that cannot be parsed yields no groups. Group detection improves the sync; it is
    never a new way for it to fail.
    """
    try:
        manifest = tomllib.loads(manifest_text)
    except (tomllib.TOMLDecodeError, ValueError):
        return []
    groups = manifest.get("dependency-groups")
    if not isinstance(groups, dict):
        return []
    return sorted(
        name for name, deps in groups.items() if isinstance(deps, list) and _declares_a_runner(deps)
    )


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
            logger.debug(
                "ContainerSubprocessExecutor: could not parse %s for requires-python", pyproject
            )
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
            'Install Podman or Docker, or set [sandbox] execution_mode = "host" '
            "in specweaver.toml."
        )
        raise ContainerEngineUnavailableError(msg)

    def _baseline_flags(self, engine: str) -> list[str]:
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
            # Rootless podman maps the invoking user to container UID 0, so `--user <host uid>`
            # selects an unmapped subuid rather than the host user — and a bind-mounted directory
            # owned by that user becomes unwritable. Measured: the RW scratch mount failed with
            # `Permission denied` until `keep-id` was added, which maps the host uid through so
            # `--user` means what it says.
            #
            # Conditional rather than always-on: `keep-id` is podman-only (docker rejects it) and
            # is an error when not rootless, since there is then no mapping to keep. Docker's own
            # rootless mode maps the host user directly, so the mismatch does not arise there.
            if "podman" in Path(engine).name and os.getuid() != 0:
                flags.append("--userns=keep-id")
        else:
            logger.warning(
                "ContainerSubprocessExecutor: running as the container image's default user "
                "on Windows — non-root enforcement (NFR-4) is Linux/macOS-only for now (NFR-11)."
            )
        return flags

    def _ensure_prepared(self) -> None:
        """Network-enabled `uv sync` prepare phase, gated by a lockfile-hash stamp (AD-7, AD-9)."""
        manifest = self._mounts.source_root / "pyproject.toml"
        lockfile = self._mounts.source_root / "uv.lock"
        stamped = lockfile if lockfile.exists() else manifest
        if not stamped.exists():
            return

        manifest_text = (
            manifest.read_text(encoding="utf-8", errors="replace") if manifest.is_file() else ""
        )
        runner_groups = _groups_holding_a_runner(manifest_text)

        # Two thirds of real projects never name pytest in the manifest. Most of them declare it
        # somewhere `uv` will not look — `tox.ini`, a `requirements` file — and reading those is the
        # difference between an environment and none. Only when the manifest is silent: a project
        # that declares its runner has pinned it, and a second unpinned set over the top of a
        # locked resolution is worse than nothing.
        declared = _manifest_declares_a_runner(manifest_text)
        fallback = None if declared else declared_pytest(self._mounts.source_root)
        # Last resort, and deliberately last: the project has named no runner anywhere this can
        # read, so the sandbox installs one. Recorded rather than merely logged, because a green
        # result then attests to a suite run against a version nobody chose.
        self.supplied_toolchain = () if declared or fallback else (_LAST_RESORT_RUNNER,)
        if self.supplied_toolchain:
            logger.warning(
                "ContainerSubprocessExecutor: %s declares no test runner in pyproject.toml, "
                "tox.ini or any requirements file. Installing %s so the suite can run at all — "
                "the version is the sandbox's choice, not the project's, and any plugins its "
                "tests need are absent.",
                self._mounts.source_root,
                _LAST_RESORT_RUNNER,
            )

        # Every input to the command belongs in the digest, or a changed input serves a stale
        # environment for ever: the manifest decides which `--group` flags are sent, and the
        # fallback decides whether anything is installed on top at all.
        digest = hashlib.sha256(
            stamped.read_bytes()
            + manifest_text.encode("utf-8")
            + self._fallback_fingerprint(fallback)
        ).hexdigest()
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
        for step, uv_cmd in self._prepare_steps(runner_groups, fallback, locked=lockfile.exists()):
            name = f"specweaver-prepare-{self._run_id}-{uuid.uuid4().hex[:8]}"
            super().execute([engine, "rm", "-f", name], timeout_seconds=10)
            try:
                result = super().execute(
                    self._prepare_container(engine, name, *uv_cmd), timeout_seconds=300
                )
            finally:
                super().execute([engine, "rm", "-f", name], timeout_seconds=10)
            if result.exit_code != 0:
                # A warning is why this survived unnoticed: the phase failed on every run for years,
                # the QA runner then reported an absent toolchain as an empty test suite, and both
                # looked like nothing happening. Raise, so the caller learns the environment was
                # never built rather than discovering it as a test result that makes no sense.
                raise RuntimeError(
                    f"container prepare phase failed at the {step} step (exit={result.exit_code}). "
                    f"The sandbox has no prepared environment, so any QA run inside it would report "
                    f"against the image's own interpreter. "
                    f"stderr: {result.stderr.strip() or '(empty)'}"
                )
        stamp_file.write_text(digest)

    def _fallback_fingerprint(self, fallback: ToolingSource | None) -> bytes:
        """The fallback's own contribution to the stamp, contents included.

        The parsed packages travel in the repr, but a `requirements` file is installed by reference
        — `uv pip install -r` reads it inside the container — so its *contents* never reach the
        command and a repr-only digest would miss an edited pin.
        """
        if fallback is None:
            return b""
        parts = [repr(fallback).encode("utf-8")]
        for relative in fallback.requirement_files:
            path = self._mounts.source_root / relative
            if path.is_file():
                parts.append(path.read_bytes())
        return b"".join(parts)

    def _prepare_steps(
        self, runner_groups: list[str], fallback: ToolingSource | None, *, locked: bool
    ) -> list[tuple[str, list[str]]]:
        """The container invocations that build the environment, in order.

        Two routes, chosen by whether the project committed a lockfile:

        * **locked** — `uv sync --frozen`, which installs exactly what the lock pins. `dev` is
          dropped from the group flags because sync installs it anyway.
        * **unlocked** — `uv venv` then `uv pip install`, which resolves from the manifest and
          writes nothing into the read-only source tree. Every group is named explicitly, `dev`
          included, and `/workspace` is installed too so the tests can import what they test.

        The unlocked route is a deliberate trade: it produces a working environment for a project
        that would otherwise get none, and it does **not** reproduce the project's own pinned set.
        A committed lockfile is always preferred when one exists.
        """
        group_flags = [arg for group in runner_groups for arg in ("--group", group)]
        if locked:
            # `uv sync` installs `dev` and nothing else, so a project whose runner sits in `tests`
            # gets a venv the QA runner cannot use. Naming `dev` again would only be noise.
            synced = [arg for arg in group_flags if arg != _DEFAULT_GROUP]
            if synced[-1:] == ["--group"]:
                synced = synced[:-1]
            return [
                (
                    "sync",
                    # A lockfile that has drifted from its manifest makes `uv` re-resolve and
                    # rewrite `/workspace/uv.lock`, which hits the same read-only mount and reports
                    # an error naming the lockfile rather than the sandbox. `--frozen` installs what
                    # the lock already says.
                    ["uv", "sync", "--frozen", *synced],
                ),
                *self._fallback_step(fallback),
            ]
        logger.warning(
            "ContainerSubprocessExecutor: %s has no uv.lock, so the prepared environment was "
            "resolved fresh from pyproject.toml and does NOT reproduce the project's pinned "
            "dependency set.",
            self._mounts.source_root,
        )
        return [
            ("venv", ["uv", "venv", _PREPARED_VENV]),
            (
                "install",
                ["uv", "pip", "install", "--python", _PREPARED_VENV, *group_flags, "/workspace"],
            ),
            *self._fallback_step(fallback),
        ]

    def _fallback_step(self, fallback: ToolingSource | None) -> list[tuple[str, list[str]]]:
        """Install what the project declared outside its manifest — or, failing that, a runner."""
        if fallback is None:
            if not self.supplied_toolchain:
                return []
            return [
                (
                    "runner",
                    [
                        "uv",
                        "pip",
                        "install",
                        "--python",
                        _PREPARED_VENV,
                        *self.supplied_toolchain,
                    ],
                )
            ]
        logger.info(
            "ContainerSubprocessExecutor: pyproject.toml declares no test runner; installing the "
            "one declared in %s (%d package(s), %d file(s))",
            fallback.path,
            len(fallback.packages),
            len(fallback.requirement_files),
        )
        if fallback.skipped:
            # Silence here would make a partial environment look like a complete one, and these are
            # the lines most likely to hold the plugins a suite needs.
            logger.warning(
                "ContainerSubprocessExecutor: %d line(s) of %s need tox's own substitution engine "
                "and were NOT installed: %s",
                len(fallback.skipped),
                fallback.path,
                "; ".join(fallback.skipped[:5]),
            )
        references = [
            arg
            for relative in fallback.requirement_files
            for arg in ("-r", f"/workspace/{relative}")
        ]
        return [
            (
                "tooling",
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    _PREPARED_VENV,
                    *references,
                    *fallback.packages,
                ],
            )
        ]

    def _prepare_container(self, engine: str, name: str, *cmd: str) -> list[str]:
        """A prepare-phase container running `cmd`."""
        return [
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
            *self._baseline_flags(engine),
            "-e",
            "UV_CACHE_DIR=/cache",
            # `uv` builds `.venv` in the workdir by default, and the workdir is `/workspace:ro`
            # inside a `--read-only` container. Without redirecting it the phase fails for EVERY
            # project on every layout, before the manifest is read:
            #   failed to create directory `/workspace/.venv`: Read-only file system (os error 30)
            "-e",
            f"UV_PROJECT_ENVIRONMENT={_PREPARED_VENV}",
            "--workdir",
            "/workspace",
            self._image,
            *cmd,
        ]

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
            # The prepared environment lives on the cache mount, and the execute phase did not
            # attach it at all — so even with a correct `PATH` there was nothing at `/cache/venv`
            # to find. Mounted READ-ONLY here: execution runs untrusted code and has no business
            # writing into an environment the next run will reuse.
            "-v",
            f"{self._mounts.cache_root}:/cache:ro",
            "--tmpfs",
            "/tmp:size=100m,mode=1777",
            "--network",
            "none",
            "-e",
            f"PATH={_CONTAINER_PATH}",
            *self._baseline_flags(engine),
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
