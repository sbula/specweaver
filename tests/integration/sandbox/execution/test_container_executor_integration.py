# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Real-engine integration tests for ContainerSubprocessExecutor (B-EXEC-01).

Requires a live Podman or Docker engine on the host. Skips cleanly (per NFR-10)
when neither is detected, so this file is safe to run in environments without
a container runtime.

Uses the public ``python:3.13-slim`` image rather than SpecWeaver's own not-yet-
published sandbox image (Containerfile.sandbox's CI publish pipeline is Backlog,
per the implementation plan) — this keeps the test independent of that follow-up.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor
from specweaver.sandbox.execution.models import ContainerMounts
from specweaver.sandbox.language.core.python.runner import PythonQARunner

if TYPE_CHECKING:
    from pathlib import Path

_TEST_IMAGE = "python:3.13-slim"


def _detect_live_engine() -> str | None:
    for name in ("podman", "docker"):
        resolved = shutil.which(name)
        if not resolved:
            continue
        try:
            result = subprocess.run(
                [resolved, "info"], capture_output=True, timeout=10, check=False
            )
        except OSError:
            continue
        if result.returncode == 0:
            return resolved
    return None


_LIVE_ENGINE = _detect_live_engine()

pytestmark = pytest.mark.skipif(
    _LIVE_ENGINE is None, reason="no live podman/docker engine detected on this host"
)


def _mounts(tmp_path: Path) -> ContainerMounts:
    source_root = tmp_path / "project"
    source_root.mkdir()
    return ContainerMounts(
        source_root=source_root,
        scratch_root=source_root / ".specweaver" / ".sandbox" / "scratch",
        cache_root=source_root / ".specweaver" / ".sandbox" / "cache",
    )


class TestContainerExecutorRealEngine:
    """Round-trip tests against a real, live Podman/Docker engine."""

    def test_read_only_source_mount_blocks_writes(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=mounts, image=_TEST_IMAGE, run_id="ro-test"
        )

        result = executor.execute(["sh", "-c", "echo bad > /workspace/hack.txt"])

        assert result.exit_code != 0
        assert not (mounts.source_root / "hack.txt").exists()

    def test_writable_scratch_mount_allows_writes(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=mounts, image=_TEST_IMAGE, run_id="rw-test"
        )

        result = executor.execute(["sh", "-c", "echo ok > /scratch/output.txt"])

        assert result.exit_code == 0
        output_file = mounts.scratch_root / "output.txt"
        assert output_file.is_file()
        assert output_file.read_text().strip() == "ok"

    def test_network_none_blocks_egress(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=mounts, image=_TEST_IMAGE, run_id="net-test"
        )

        result = executor.execute(
            [
                "python",
                "-c",
                "import socket; socket.create_connection(('8.8.8.8', 53), timeout=3)",
            ]
        )

        assert result.exit_code != 0

    def test_container_removed_after_execution(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        run_id = "cleanup-test"
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=mounts, image=_TEST_IMAGE, run_id=run_id
        )

        executor.execute(["sh", "-c", "echo hi"])

        ps = subprocess.run(
            [
                _LIVE_ENGINE,
                "ps",
                "-a",
                "--filter",
                f"name=specweaver-qa-{run_id}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert ps.stdout.strip() == ""

    def test_result_contract_matches_subprocess_result_from_real_run(self, tmp_path: Path) -> None:
        mounts = _mounts(tmp_path)
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=mounts, image=_TEST_IMAGE, run_id="result-test"
        )

        result = executor.execute(["python", "-c", "print('hello from container')"])

        assert result.exit_code == 0
        assert "hello from container" in result.stdout
        assert result.timed_out is False


#: An image that ships `uv`. The prepare phase invokes `uv sync`, so `python:3.13-slim` — fine for
#: every other test in this file — cannot exercise it at all, and cannot install `uv` either because
#: the container is `--read-only`.
_UV_IMAGE = "ghcr.io/astral-sh/uv:python3.12-bookworm"


def _uv_image_available() -> bool:
    if _LIVE_ENGINE is None:
        return False
    try:
        probe = subprocess.run(
            [_LIVE_ENGINE, "image", "exists", _UV_IMAGE], capture_output=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


class TestPrepareAndExecuteShareAnEnvironment:
    """`TECH-031`: the prepare phase builds a toolchain and the execute phase actually uses it.

    This is the journey `INT-US-09-SF01-MIG` is held on — container execution *actually exercised*
    rather than asserted through mocks. It runs the real executor against a real engine; every other
    proof of this path built the podman argv by hand, which tests podman rather than this code.

    Until 2026-08-18 it could not have passed. Three walls, each re-measured against live podman:
    `uv` wrote `.venv` into a read-only workdir; a drifted lockfile made it rewrite a read-only
    `uv.lock`; and the execute phase never mounted the cache the environment lives on, so even a
    correct `PATH` pointed at nothing.
    """

    def _project(self, tmp_path: Path, groups: str = 'dev = ["pytest"]') -> ContainerMounts:
        mounts = _mounts(tmp_path)
        (mounts.source_root / "pyproject.toml").write_text(
            '[project]\nname = "t"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n'
            f"dependencies = []\n\n[dependency-groups]\n{groups}\n",
            encoding="utf-8",
        )
        assert _LIVE_ENGINE is not None
        subprocess.run(  # one-off fixture setup, writable on purpose
            [
                _LIVE_ENGINE,
                "run",
                "--rm",
                "-v",
                f"{mounts.source_root}:/w:rw",
                "--workdir",
                "/w",
                _UV_IMAGE,
                "uv",
                "lock",
            ],
            capture_output=True,
            timeout=180,
            check=True,
        )
        return mounts

    @pytest.mark.skipif(not _uv_image_available(), reason=f"{_UV_IMAGE} not present locally")
    def test_the_toolchain_prepare_installed_is_the_one_execute_finds(self, tmp_path: Path) -> None:
        """pytest is declared by the project, installed by prepare, and found by execute."""
        mounts = self._project(tmp_path)
        executor = ContainerSubprocessExecutor(
            cwd=mounts.source_root, mounts=mounts, image=_UV_IMAGE
        )

        result = executor.execute(["python", "-m", "pytest", "--version"], timeout_seconds=300)

        assert result.exit_code == 0, (
            f"the prepared toolchain was not usable from the execute phase:\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
        assert "pytest" in result.stdout.lower(), result.stdout

    @pytest.mark.skipif(not _uv_image_available(), reason=f"{_UV_IMAGE} not present locally")
    def test_a_runner_declared_outside_dev_is_installed_for_real(self, tmp_path: Path) -> None:
        """`uv sync` installs `dev` and nothing else, and 26 of 121 measured repositories put the
        runner in `test`/`tests` instead.

        The unit tests prove the argv carries `--group tests`. They cannot prove uv then installs
        anything — only a real `uv sync` against a real lockfile can, which is what this does. It is
        also the check that a name list would have passed and a real project would have failed:
        `uv sync --group <undeclared>` exits 2, so the flag is only ever safe when it is derived
        from the manifest in front of it.
        """
        mounts = self._project(tmp_path, groups='dev = ["iniconfig"]\ntests = ["pytest"]')
        executor = ContainerSubprocessExecutor(
            cwd=mounts.source_root, mounts=mounts, image=_UV_IMAGE
        )

        result = executor.execute(["python", "-m", "pytest", "--version"], timeout_seconds=300)

        assert result.exit_code == 0, (
            f"the runner sits in `tests`, which a default `uv sync` skips, so the prepared "
            f"environment has no pytest:\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
        assert "pytest" in result.stdout.lower(), result.stdout

    @pytest.mark.skipif(not _uv_image_available(), reason=f"{_UV_IMAGE} not present locally")
    def test_a_project_that_declares_no_toolchain_fails_loudly(self, tmp_path: Path) -> None:
        """The control, and the half that used to look identical to success.

        A project declaring no test runner must not produce a run that merely reports nothing. The
        QA runner's own vacuous-success defect is fixed; this checks the layer beneath it, where the
        prepare phase either builds an environment without pytest or fails outright — either way the
        caller must be able to tell, which is exactly what a `logger.warning` denied it.
        """
        mounts = _mounts(tmp_path)
        (mounts.source_root / "pyproject.toml").write_text(
            '[project]\nname = "t"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n'
            "dependencies = []\n",
            encoding="utf-8",
        )
        assert _LIVE_ENGINE is not None
        subprocess.run(
            [
                _LIVE_ENGINE,
                "run",
                "--rm",
                "-v",
                f"{mounts.source_root}:/w:rw",
                "--workdir",
                "/w",
                _UV_IMAGE,
                "uv",
                "lock",
            ],
            capture_output=True,
            timeout=180,
            check=True,
        )
        executor = ContainerSubprocessExecutor(
            cwd=mounts.source_root, mounts=mounts, image=_UV_IMAGE
        )

        result = executor.execute(["python", "-m", "pytest", "--version"], timeout_seconds=300)

        assert result.exit_code != 0, (
            "a project with no test runner reported success — the shape that let an absent "
            f"toolchain read as an empty suite: {result.stdout!r}"
        )

    @pytest.mark.skipif(not _uv_image_available(), reason=f"{_UV_IMAGE} not present locally")
    def test_the_absent_toolchain_is_explained_to_the_caller(self, tmp_path: Path) -> None:
        """Failing loudly is not the same as failing usefully, and this is the majority path.

        Measured across the corpus, 101 of 121 resolvable repositories reach the sandbox without
        pytest installed, so this message is what most first runs against a new target will say. It
        used to be the interpreter's own line forwarded verbatim — naming `/cache/venv`, a path
        inside our container that appears nowhere in the reader's project.

        Driven through `PythonQARunner` rather than the executor, because the wiring is the claim:
        the pure explainer has its own unit tests and passing them proves nothing about what a
        caller is handed.
        """
        mounts = self._project(tmp_path, groups='dev = ["iniconfig"]')
        runner = PythonQARunner(
            cwd=mounts.source_root,
            executor=ContainerSubprocessExecutor(
                cwd=mounts.source_root, mounts=mounts, image=_UV_IMAGE
            ),
        )

        result = runner.run_tests(".")

        assert result.errors == 1 and result.passed == 0, (
            f"an absent toolchain did not report as an error: {result}"
        )
        message = result.failures[0].message
        assert "/cache" not in message, f"an internal container path reached the user:\n{message}"
        assert "not a test failure" in message.lower(), message
        assert "Declare pytest" in message, message
