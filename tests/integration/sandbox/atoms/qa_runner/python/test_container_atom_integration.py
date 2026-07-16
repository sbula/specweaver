# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Real-engine integration test for the container-mode QA-runner chain
(B-EXEC-01).

Exercises factory.resolve_runner() -> PythonQARunner -> ContainerSubprocessExecutor
-> a real, live Podman/Docker engine, end-to-end. Uses run_debugger (a bare
`python <script>` invocation) rather than run_tests/run_linter, since those need
pytest/ruff pre-installed and the public python:3.13-slim image (used here in
place of SpecWeaver's own not-yet-published sandbox image) doesn't have them.

Scoped one layer below QARunnerAtom.run()'s intent dispatch, which is already
thoroughly unit-tested against a mocked runner — this test's job is proving the
chain BELOW it is correctly assembled against a real engine, not re-testing
dispatch logic. Skips cleanly (per NFR-10) when no engine is detected+live.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor
from specweaver.sandbox.execution.models import ContainerMounts
from specweaver.sandbox.qa_runner.core.factory import resolve_runner

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


pytestmark = pytest.mark.skipif(
    _detect_live_engine() is None, reason="no live podman/docker engine detected on this host"
)


def test_full_chain_runs_real_script_inside_container(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "hello.py").write_text("print('hello from the assembled chain')")

    mounts = ContainerMounts(
        source_root=project_root,
        scratch_root=project_root / ".specweaver" / ".sandbox" / "scratch",
        cache_root=project_root / ".specweaver" / ".sandbox" / "cache",
    )
    executor = ContainerSubprocessExecutor(
        cwd=project_root, mounts=mounts, image=_TEST_IMAGE, run_id="chain-test"
    )

    runner = resolve_runner(project_root, executor=executor)

    result = runner.run_debugger(target=".", entrypoint="hello.py")

    assert result.exit_code == 0, f"stderr events: {[e.output for e in result.events]}"
    assert any("hello from the assembled chain" in e.output for e in result.events)
