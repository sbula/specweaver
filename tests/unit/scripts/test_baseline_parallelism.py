# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The nightly's baseline runs the suite in parallel, like every other full-suite run.

Proves: TECH-058 FR-1, NFR-1

`run_baseline` built its pytest command without `-n auto` while `_mutate.run_one` adds it on the
very same path — the unscoped, whole-suite run. Measured 2026-08-16 in a real sandbox:

| run | seconds |
|---|---|
| as shipped, serial | 291.2 |
| same sandbox, warm `__pycache__`, serial | 291.7 |
| same sandbox, `-n auto` | 77.3 |

**3.8x, and the warm run rules out the obvious alternative explanation** — a fresh worktree has no
bytecode cache, and that turns out to cost 0.4s, not minutes. The baseline was 69% of a 6m51s
session that did 129.5s of actual mutant work.

Asserting on the command rather than on a stopwatch is deliberate: a timing assertion here would be
flaky on a loaded box and would be deleted the first week it went red. The command is what
`run_baseline` produces, and the second test pins the thing that actually went wrong — the two
places that run the whole suite disagreeing about how.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def mutation() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mutation", REPO_ROOT / "scripts" / "mutation.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["mutation"] = module
    spec.loader.exec_module(module)
    return module


def _captured_command(mutation: ModuleType, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Run `run_baseline` with the subprocess stubbed, and return the command it built."""
    seen: dict[str, Any] = {}

    def _fake(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> tuple[str, int]:
        seen["cmd"] = cmd
        return ("1 passed in 0.1s", 0)

    monkeypatch.setattr(mutation, "_run_rc", _fake)
    mutation.run_baseline(Path("/nonexistent-sandbox"))
    return seen["cmd"]


class TestRunBaseline:
    """FR-1 — the whole suite, run the way the whole suite is meant to be run."""

    def test_the_baseline_runs_under_xdist(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """[Happy] 3.8x of the nightly's wall clock, for two argv entries."""
        cmd = _captured_command(mutation, monkeypatch)

        assert "-n" in cmd, f"no xdist flag in {cmd}"
        assert cmd[cmd.index("-n") + 1] == "auto"

    def test_it_agrees_with_the_other_whole_suite_runner(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """[Boundary] the actual defect: two runners of the same thing, disagreeing.

        `_mutate.run_one` appends `-n auto` when it is given no scope, because that is a whole-suite
        run. `run_baseline` is *always* a whole-suite run and did not. Nothing compared them, so the
        asymmetry sat there — visible in both files, in neither test.
        """
        source = (REPO_ROOT / "scripts" / "_mutate.py").read_text(encoding="utf-8")
        assert 'cmd += ["-n", "auto"]' in source, (
            "the unscoped path in `_mutate.run_one` no longer adds xdist; if that changed "
            "deliberately, this agreement test is what needs rereading"
        )

        assert "-n" in _captured_command(mutation, monkeypatch)

    def test_a_failing_baseline_is_still_reported(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """[Graceful] parallelism must not swallow the verdict.

        A red baseline is context rather than a gate — `verdict_of` turns it into `INDETERMINATE`
        — so losing it would silently convert "the tree was already broken" into "this requirement
        is unprotected", which is the one reading the corpus must never produce.
        """
        monkeypatch.setattr(
            mutation,
            "_run_rc",
            lambda cmd, cwd, env=None: ("FAILED tests/unit/test_thing.py::test_it\n1 failed", 1),
        )

        baseline = mutation.run_baseline(Path("/nonexistent-sandbox"))

        assert baseline.green is False
        assert baseline.code == 1
        assert "tests/unit/test_thing.py::test_it" in baseline.failures

    def test_the_target_is_still_configurable(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """[Boundary] `tests` is a keyword argument; adding flags must not displace it."""
        seen: dict[str, Any] = {}
        monkeypatch.setattr(
            mutation,
            "_run_rc",
            lambda cmd, cwd, env=None: (seen.__setitem__("cmd", cmd), ("1 passed", 0))[1],
        )

        mutation.run_baseline(Path("/nonexistent-sandbox"), tests="tests/unit")

        assert seen["cmd"][-1] == "tests/unit" or "tests/unit" in seen["cmd"]
