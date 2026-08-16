# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The read-only-baselines guard is wired into the suite, not merely written. TECH-055 CB-1.

Proves: TECH-055 FR-1

`tests/unit/test_baseline_write_guard.py` proves the comparison is correct. It cannot prove the
comparison is **run**: delete the fixture from `tests/conftest.py` and all eleven of those tests
still pass while every test in the repo is free to rewrite a gate ratchet again. That gap is the
whole reason this file exists, and it is the same shape as the defect `TECH-055` repairs — logic
that was right and unreached.

Two things are checked, because either alone is satisfiable by an inert guard:

1. the fixture is registered **autouse**, so it applies to tests nobody has written yet;
2. its body actually fails the test when a rewrite is detected — driven through the real fixture
   function from `tests/conftest.py`, not a copy of it.

**Why not a real sub-run.** Running a child pytest that genuinely rewrites a baseline would need
`BASELINES` to be redirectable from the environment, and an environment variable that moves the
guard's target is an off-switch for the guard. A test that can only be written by weakening the
thing it tests is the wrong test.
"""

from __future__ import annotations

import pytest
from _pytest.outcomes import Failed

import tests.conftest as root_conftest
from tests.baseline_snapshot import BASELINES

pytestmark = pytest.mark.integration


class TestTheGuardIsRegistered:
    """`autouse` is the entire delivery mechanism — an opt-in guard guards the careful."""

    def test_the_fixture_is_autouse(self) -> None:
        """[Happy] without this, the guard protects only tests that ask to be protected."""
        marker = root_conftest._baselines_are_read_only._fixture_function_marker

        assert marker.autouse is True

    def test_it_watches_the_real_ratchet_directory(self) -> None:
        """[Boundary] a guard pointed at the wrong directory passes forever and proves nothing."""
        assert BASELINES.is_dir()
        assert BASELINES == root_conftest.BASELINES


class TestTheGuardFires:
    """The fixture's own body, driven with a rewrite in the middle of it."""

    def _run(self, monkeypatch: pytest.MonkeyPatch, before: dict, after: dict) -> None:
        """Drive the real generator: set-up sees `before`, teardown sees `after`."""
        seen = iter((before, after))
        monkeypatch.setattr(root_conftest, "snapshot", lambda _directory: next(seen))
        generator = root_conftest._baselines_are_read_only._get_wrapped_function()()
        next(generator)
        next(generator, None)

    def test_an_unchanged_directory_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """[Happy] the case that runs on every test in the suite; it must be silent."""
        self._run(monkeypatch, {"fr_uncited.json": "a"}, {"fr_uncited.json": "a"})

    def test_a_rewritten_baseline_fails_the_test(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """[Hostile] the defect's exact shape, with the file it actually happened to."""
        with pytest.raises(Failed) as failure:
            self._run(
                monkeypatch,
                {"mutation_findings.json": "before"},
                {"mutation_findings.json": "after"},
            )

        assert "mutation_findings.json" in str(failure.value)
        assert "scripts/baselines/" in str(failure.value)

    def test_the_failure_says_what_to_do_about_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """[Boundary] the message is read by whoever is least expecting it.

        A failure naming a file the test never mentions is a mystery unless it also names the fix,
        and the fix is nearly always the same: pass the tool a `--ledger`/`--baseline` under
        `tmp_path`.
        """
        with pytest.raises(Failed) as failure:
            self._run(monkeypatch, {"proof_tier.json": "x"}, {})

        message = str(failure.value)
        assert "proof_tier.json" in message
        assert "tmp_path" in message
