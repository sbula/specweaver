# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The nightly real-model run: its timer, its key, and a verdict nobody can miss.

Proves: B-FLOW-05 NFR-4

| Bucket | Case |
|---|---|
| Happy | a fresh passing result is OK; the nightly session runs the live tests before the mutants |
| Boundary | `KEY=value`, `export KEY=value` and quoted values are read; comments and blanks are not |
| Degradation | no result, a failed one, or one older than two days is NOT OK, and says which |
| Hostile | a key already set in the environment is not overwritten; a value is never printed |
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def live() -> ModuleType:
    spec = importlib.util.spec_from_file_location("live", REPO_ROOT / "scripts" / "live.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["live"] = module
    spec.loader.exec_module(module)
    return module


def test_the_nightly_session_runs_the_live_tests_first() -> None:
    spec = importlib.util.spec_from_file_location(
        "_mutation_timer", REPO_ROOT / "scripts" / "_mutation_timer.py"
    )
    assert spec is not None and spec.loader is not None
    timer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(timer)

    service = timer.timer_units()["service"]

    live_line, mutation_line = (
        line for line in service.splitlines() if line.startswith("ExecStart")
    )
    assert live_line.startswith("ExecStart=-") and live_line.endswith("scripts/live.py")
    assert "scripts/mutation.py" in mutation_line


def test_env_lines_are_read_without_overwriting(
    live: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = tmp_path / ".env"
    env.write_text(
        '# a comment\n\nGEMINI_API_KEY="abc"\nexport OTHER=x y\nALREADY=file\n', encoding="utf-8"
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OTHER", raising=False)
    monkeypatch.setenv("ALREADY", "shell")

    names = live.load_env(env)

    assert names == ["GEMINI_API_KEY", "OTHER"]
    assert (live.os.environ["GEMINI_API_KEY"], live.os.environ["OTHER"]) == ("abc", "x y")
    assert live.os.environ["ALREADY"] == "shell"


def _result(path: Path, *, passed: bool, age_hours: float = 0) -> Path:
    path.write_text(
        json.dumps({"at": time.time() - age_hours * 3600, "passed": passed, "summary": "1 passed"}),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("setup", "ok", "says"),
    [
        (lambda p: _result(p, passed=True), True, "passed"),
        (lambda p: _result(p, passed=False), False, "FAILED"),
        (lambda p: _result(p, passed=True, age_hours=49), False, "older than"),
        (lambda p: p, False, "never ran"),
    ],
)
def test_status(live: ModuleType, tmp_path: Path, setup, ok: bool, says: str) -> None:
    path = setup(tmp_path / "last.json")

    is_ok, line = live.status(path)

    assert is_ok is ok
    assert says in line


def test_the_handover_shows_the_live_verdict() -> None:
    spec = importlib.util.spec_from_file_location(
        "session_handover", REPO_ROOT / "scripts" / "session_handover.py"
    )
    assert spec is not None and spec.loader is not None
    handover = importlib.util.module_from_spec(spec)
    sys.modules["session_handover"] = handover
    spec.loader.exec_module(handover)

    (line,) = handover._live_state()

    assert line.startswith("- **Live** ")
    assert "live run:" in line
