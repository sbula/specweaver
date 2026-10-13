# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Real child processes: a timed-out one is gone, an interrupt stops a running one, and a child
sees no variable it was not allowed.

Proves: E-EXEC-01 FR-2
Proves: E-EXEC-01 FR-6
Proves: E-EXEC-01 FR-7

| Bucket | Case |
|---|---|
| Happy | a process past its timeout no longer exists afterwards |
| Boundary | an allowed variable reaches the child |
| Degradation | an interrupt's cleanup stops a child that is still running |
| Hostile | a variable outside the allowlist never reaches the child |
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.execution import _signals
from specweaver.sandbox.execution.executor import SubprocessExecutor

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX process ids and signals")

_WRITE_PID_AND_SLEEP = (
    "import os, sys, time; open(sys.argv[1], 'w').write(str(os.getpid())); time.sleep(30)"
)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A killed child that nobody reaped yet is a zombie: gone for every purpose here.
    with open(f"/proc/{pid}/stat", encoding="utf-8") as stat:
        return stat.read().split()[2] != "Z"


def _pid(path: Path) -> int:
    for _ in range(200):
        if path.exists() and path.read_text():
            return int(path.read_text())
        time.sleep(0.02)
    raise AssertionError("the child never started")


def test_a_process_past_its_timeout_is_gone(tmp_path: Path) -> None:
    # Proves: E-EXEC-01 FR-2
    pid_file = tmp_path / "pid"
    result = SubprocessExecutor(cwd=tmp_path).execute(
        [sys.executable, "-c", _WRITE_PID_AND_SLEEP, str(pid_file)], timeout_seconds=1
    )

    assert result.timed_out is True
    assert not _alive(_pid(pid_file))


def test_an_interrupt_stops_a_running_child(tmp_path: Path) -> None:
    # Proves: E-EXEC-01 FR-7
    pid_file = tmp_path / "pid"
    executor = SubprocessExecutor(cwd=tmp_path, timeout_seconds=60)
    worker = threading.Thread(
        target=executor.execute,
        args=([sys.executable, "-c", _WRITE_PID_AND_SLEEP, str(pid_file)],),
    )
    worker.start()
    pid = _pid(pid_file)

    _signals._cleanup_active_processes()  # what SIGINT, SIGTERM and exit run
    worker.join(timeout=10)

    assert not worker.is_alive()
    assert not _alive(pid)


def test_a_child_sees_only_allowed_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Proves: E-EXEC-01 FR-6
    monkeypatch.setenv("SPECWEAVER_UNLISTED_FLAG", "leaked")
    monkeypatch.setenv("LANG", "C.UTF-8")
    show = "import os; print(os.environ.get('SPECWEAVER_UNLISTED_FLAG'), os.environ.get('LANG'))"

    result = SubprocessExecutor(cwd=tmp_path).execute([sys.executable, "-c", show])

    assert result.stdout.split() == ["None", "C.UTF-8"]
