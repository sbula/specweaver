# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A session classifies by pytest's exit code, not by reading its prose.

Proves: TECH-049 FR-3, FR-4, FR-7

Measured 2026-08-15: pytest exits `4` for a path that does not exist and `5` when everything is
deselected, and prints no `FAILED` line in either case. The runner read that as "nothing objected"
— a mis-typed scope reported a survival, which is the exact false negative `FR-4` exists to close.

Exit codes are a documented contract and an escape sequence cannot break them, which is more than
the text parsing offered: that is what the colour defect broke. The output is still read, but only
to learn *which* tests died.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mutation() -> ModuleType:
    return _load("mutation")


@pytest.fixture(scope="module")
def mut() -> ModuleType:
    return _load("_mutate")


class TestRunRc:
    """`_run_rc` — the exit code the old `_run` threw away."""

    def test_it_returns_output_and_a_zero_code_on_success(
        self, mut: ModuleType, tmp_path: Path
    ) -> None:
        out, code = mut._run_rc([sys.executable, "-c", "print('hi')"], tmp_path)
        assert "hi" in out
        assert code == 0

    def test_it_returns_a_nonzero_code_on_failure(self, mut: ModuleType, tmp_path: Path) -> None:
        _out, code = mut._run_rc([sys.executable, "-c", "raise SystemExit(5)"], tmp_path)
        assert code == 5


class TestOutcomeOf:
    """The exit code, mapped to what it means for a mutant run."""

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            (0, "NO_KILL"),
            (1, "KILL"),
            (2, "BROKEN"),
            (3, "BROKEN"),
            (4, "NOTHING_RAN"),
            (5, "NOTHING_RAN"),
        ],
    )
    def test_each_documented_exit_code_maps(
        self, mutation: ModuleType, code: int, expected: str
    ) -> None:
        assert mutation.outcome_of(code) == expected

    def test_nothing_ran_is_not_a_survival(self, mutation: ModuleType) -> None:
        """The whole point of FR-4.

        A mis-typed scope and a genuinely unprotected requirement both produce zero failures. Only
        the exit code separates them, and conflating the two is a false negative that reads as a
        finding nobody needs to act on.
        """
        assert mutation.outcome_of(4) != mutation.outcome_of(0)
        assert mutation.outcome_of(5) != mutation.outcome_of(0)

    def test_an_unknown_code_is_broken_not_silently_fine(self, mutation: ModuleType) -> None:
        """[Hostile] A code this mapping has never seen must not default to 'nothing objected'."""
        assert mutation.outcome_of(99) == "BROKEN"


class TestBaseline:
    """`FR-3` — the suite runs once and records what failed, by node id."""

    def test_a_green_baseline_records_no_failures(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(mutation, "_run_rc", lambda *a, **k: ("6968 passed\n", 0))
        result = mutation.run_baseline(tmp_path, tests="tests")
        assert result.green is True
        assert result.failures == []

    def test_a_red_baseline_records_the_failing_node_ids(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Node ids, not a count — `FR-3a` needs to know whether a failure is inside a scope."""
        out = "FAILED tests/unit/a.py::test_one\nFAILED tests/unit/b.py::test_two\n1 failed\n"
        monkeypatch.setattr(mutation, "_run_rc", lambda *a, **k: (out, 1))
        result = mutation.run_baseline(tmp_path, tests="tests")
        assert result.green is False
        assert result.failures == ["tests/unit/a.py::test_one", "tests/unit/b.py::test_two"]

    def test_a_baseline_that_collected_nothing_is_not_green(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """[Degradation] A baseline over a bad path would otherwise certify a tree it never ran."""
        monkeypatch.setattr(mutation, "_run_rc", lambda *a, **k: ("no tests ran\n", 4))
        result = mutation.run_baseline(tmp_path, tests="nope")
        assert result.green is False


class TestCleanliness:
    """`FR-7` — the sandbox must look the same before each mutant as it did after it was built.

    The design said "verify `git status --porcelain` is empty". It never will be: `_build_sandbox`
    deliberately copies untracked files in, so a freshly built sandbox is already dirty by that
    measure and the check would fire on every mutant. Cleanliness is therefore measured against a
    **snapshot taken once after the build**, and only a *new* entry means a mutant leaked state.
    """

    def test_the_snapshot_is_what_the_build_left_behind(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(mutation, "_run_rc", lambda *a, **k: ("?? new_helper.py\n", 0))
        assert mutation.snapshot_cleanliness(tmp_path) == {"?? new_helper.py"}

    def test_an_unchanged_sandbox_reports_no_leak(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The case that would have fired on every mutant had the design's wording been taken."""
        monkeypatch.setattr(mutation, "_run_rc", lambda *a, **k: ("?? new_helper.py\n", 0))
        assert mutation.leaked_since(tmp_path, {"?? new_helper.py"}) == []

    def test_a_new_entry_is_reported_as_a_leak(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            mutation, "_run_rc", lambda *a, **k: ("?? new_helper.py\n?? junk.db\n", 0)
        )
        assert mutation.leaked_since(tmp_path, {"?? new_helper.py"}) == ["?? junk.db"]

    def test_a_disappearing_baseline_entry_is_not_a_leak(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """[Boundary] Only additions matter. A file the build left and a test consumed is not a leak."""
        monkeypatch.setattr(mutation, "_run_rc", lambda *a, **k: ("", 0))
        assert mutation.leaked_since(tmp_path, {"?? new_helper.py"}) == []


class TestRunCorpusAccounting:
    """`FR-8` upheld here even though verdicts are SF-03's: N declared, N returned.

    A leak is recorded against the mutant that caused it and the run continues. Aborting would turn
    one leaky test into a night with no data, and would fail the accounting rule for a reason that
    is not the corpus's fault.
    """

    def test_every_declared_mutant_returns_a_result_when_one_leaks(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        calls = {"n": 0}

        def _leak_once(*_a: object, **_k: object) -> tuple[str, int]:
            calls["n"] += 1
            return ("?? junk.db\n" if calls["n"] == 2 else "", 0)

        monkeypatch.setattr(mutation, "_run_rc", _leak_once)
        monkeypatch.setattr(
            mutation._mutate,
            "run_one",
            lambda *a, **k: {"verdict": "KILLED", "killers": ["t::x"], "detail": "", "code": 1},
        )
        corpus = _FakeCorpus(["a", "b", "c"])
        results = mutation.run_corpus(corpus, sandbox=tmp_path)

        assert len(results) == 3, "one result per declared mutant, leak or no leak"
        assert any(r.leaked for r in results), "the leak is recorded, not swallowed"


class _FakeMutant:
    def __init__(self, name: str) -> None:
        self.derived_id = f"X FR-1 {name}"
        self.file = "src/x.py"
        self.old = "a"
        self.new = "b"


class _FakeCampaign:
    def __init__(self, names: list[str]) -> None:
        self.scope = ["tests/a.py"]
        self.retired = None
        self.mutants = [_FakeMutant(n) for n in names]


class _FakeCorpus:
    def __init__(self, names: list[str]) -> None:
        self.campaigns = [_FakeCampaign(names)]
