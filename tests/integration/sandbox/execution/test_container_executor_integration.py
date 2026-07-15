# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Real-engine integration tests for ContainerSubprocessExecutor (INT-US-09 SF-01).

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

    def test_result_contract_matches_subprocess_result_from_real_run(
        self, tmp_path: Path
    ) -> None:
        mounts = _mounts(tmp_path)
        executor = ContainerSubprocessExecutor(
            cwd=tmp_path, mounts=mounts, image=_TEST_IMAGE, run_id="result-test"
        )

        result = executor.execute(["python", "-c", "print('hello from container')"])

        assert result.exit_code == 0
        assert "hello from container" in result.stdout
        assert result.timed_out is False
