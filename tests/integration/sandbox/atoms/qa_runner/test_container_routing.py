# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`execution_mode` decides whether QA runs in a container, and the atom is where that is decided.

Proves: B-EXEC-01 FR-1

FR-1 is the routing claim. The nearby live-engine test drives
`resolve_runner -> PythonQARunner -> ContainerSubprocessExecutor` and says in its own docstring that
it sits *one layer below* the atom's dispatch — so forcing `QARunnerAtom`'s `execution_mode ==
"container"` branch false leaves it green. It proves the chain is assembled correctly, not that
anything chooses to assemble it.

That is the whole of FR-1: a project asks for container mode, and the executor the runner is handed
is the container one. Both directions are asserted, because a router that always containerised would
satisfy a one-sided test while breaking the opt-in FR-9 guarantees.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.settings import SandboxSettings
from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor
from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _executor(atom: QARunnerAtom) -> object | None:
    """The executor the atom handed its runner."""
    return getattr(atom._runner, "_executor", None)


def test_container_mode_routes_through_the_container_executor(tmp_path: Path) -> None:
    atom = QARunnerAtom(cwd=tmp_path, sandbox_settings=SandboxSettings(execution_mode="container"))

    assert isinstance(_executor(atom), ContainerSubprocessExecutor)


def test_host_mode_does_not(tmp_path: Path) -> None:
    """The control. A router that always containerised would pass the test above."""
    atom = QARunnerAtom(cwd=tmp_path, sandbox_settings=SandboxSettings(execution_mode="host"))

    assert not isinstance(_executor(atom), ContainerSubprocessExecutor)


def test_no_settings_at_all_stays_on_the_host(tmp_path: Path) -> None:
    """`None` is the common case — a caller that never mentions sandboxing must not get one."""
    atom = QARunnerAtom(cwd=tmp_path)

    assert not isinstance(_executor(atom), ContainerSubprocessExecutor)
