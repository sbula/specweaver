# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The nightly real-toolchain run: what it runs, the verdict it keeps, and who reads it.

Proves: D-INTL-08 NFR-3

| Bucket | Case |
|---|---|
| Happy | the run selects `-m toolchain` and records a pass; the nightly session runs it after the live run and before the mutants |
| Boundary | a result exactly at the age limit still counts |
| Degradation | a failing run is recorded as failed; no result, or one older than two days, is NOT OK and says which |
| Hostile | not applicable — the runner takes no input but its own result file |
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def toolchain() -> ModuleType:
    return _load("toolchain")


def _completed(returncode: int, stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


@pytest.mark.parametrize(("returncode", "passed"), [(0, True), (1, False)])
def test_the_run_selects_the_tier_and_keeps_the_verdict(
    toolchain: ModuleType, tmp_path: Path, returncode: int, passed: bool
) -> None:
    result = tmp_path / "last.json"
    with patch("subprocess.run", return_value=_completed(returncode, "3 passed, 2 skipped")) as run:
        assert toolchain.run(result) == returncode

    command = run.call_args[0][0]
    selections = [command[i + 1] for i, part in enumerate(command[:-1]) if part == "-m"]
    assert selections == ["pytest", "toolchain"]
    verdict = json.loads(result.read_text(encoding="utf-8"))
    assert verdict["passed"] is passed
    assert verdict["summary"] == "3 passed, 2 skipped"


def _result(path: Path, *, passed: bool, age_hours: float = 0) -> Path:
    at = time.time() - age_hours * 3600
    path.write_text(json.dumps({"at": at, "passed": passed, "summary": "5 passed"}), "utf-8")
    return path


@pytest.mark.parametrize(
    ("setup", "ok", "says"),
    [
        (lambda p: _result(p, passed=True), True, "passed"),
        (lambda p: _result(p, passed=True, age_hours=47.9), True, "passed"),
        (lambda p: _result(p, passed=False), False, "FAILED"),
        (lambda p: _result(p, passed=True, age_hours=49), False, "older than"),
        (lambda p: p, False, "never ran"),
    ],
)
def test_status(toolchain: ModuleType, tmp_path: Path, setup, ok: bool, says: str) -> None:
    is_ok, line = toolchain.status(setup(tmp_path / "last.json"))

    assert is_ok is ok
    assert says in line
    assert line.startswith("toolchain run:")


def test_the_nightly_session_runs_it_after_the_live_run() -> None:
    service = _load("_mutation_timer").timer_units()["service"]

    starts = [line for line in service.splitlines() if line.startswith("ExecStart")]

    assert [re.search(r"scripts/(\w+\.py)", line).group(1) for line in starts] == [
        "live.py",
        "toolchain.py",
        "mutation.py",
    ]
    assert starts[1].startswith("ExecStart=-")


def test_the_handover_shows_the_toolchain_verdict() -> None:
    (line,) = _load("session_handover")._toolchain_state()

    assert line.startswith("- **Toolchain** ")
    assert "toolchain run:" in line
