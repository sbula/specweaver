# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A session classifies by pytest's exit code, not by reading its prose.

Proves: TECH-049 FR-3, FR-3a, FR-4, FR-5, FR-6, FR-7, FR-8

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
        self.symbol = "f"
        self.old = "a"
        self.new = "b"
        self.symbol_sha = None


class _FakeCampaign:
    def __init__(self, names: list[str]) -> None:
        self.requirement = "FR-1"
        self.scope = ["tests/a.py"]
        self.retired = None
        self.mutants = [_FakeMutant(n) for n in names]


class _FakeCorpus:
    def __init__(self, names: list[str]) -> None:
        self.feature = "X"
        self.campaigns = [_FakeCampaign(names)]


class TestVerdictOf:
    """The seven ordered rules. First match wins, and the order is the design.

    Proves the distinction this whole sub-feature exists for: `KILL` means *tests failed*, and
    `PASS` means *this requirement is protected*. A bystander test dying satisfies the first and
    not the second, and treating them as the same is how a campaign certifies a requirement nothing
    covers.
    """

    def _scope(self) -> list[str]:
        return ["tests/unit/a.py", "tests/unit/b.py"]

    def _run(self, mutation: ModuleType, **over: object) -> object:
        base = {"derived_id": "X FR-1 m", "outcome": "KILL", "killers": ["tests/unit/a.py::test_x"]}
        return mutation.MutantRun(**{**base, **over})  # type: ignore[arg-type]

    def test_rule_1_a_baseline_failure_inside_scope_is_indeterminate(
        self, mutation: ModuleType
    ) -> None:
        v = mutation.verdict_of(
            self._run(mutation),
            scope=self._scope(),
            baseline_failures=["tests/unit/a.py::test_old"],
        )
        assert v.verdict == "INDETERMINATE"

    def test_rule_1_a_baseline_failure_outside_scope_does_not_taint(
        self, mutation: ModuleType
    ) -> None:
        """`FR-3a`'s whole point: one unrelated red test must not void the session.

        Without the scope restriction a single failure anywhere in a 7,000-test suite would make
        every campaign unreadable, and the nightly run would report nothing on the night it was
        most worth reading.
        """
        v = mutation.verdict_of(
            self._run(mutation),
            scope=self._scope(),
            baseline_failures=["tests/unit/zzz.py::test_x"],
        )
        assert v.verdict != "INDETERMINATE"

    def test_rule_2_nothing_ran_is_a_failure(self, mutation: ModuleType) -> None:
        v = mutation.verdict_of(
            self._run(mutation, outcome="NOTHING_RAN", killers=[]), scope=self._scope()
        )
        assert v.verdict == "FAIL"

    def test_rule_3_broken_passes_through_unjudged(self, mutation: ModuleType) -> None:
        v = mutation.verdict_of(
            self._run(mutation, outcome="BROKEN", killers=[]), scope=self._scope()
        )
        assert v.verdict == "BROKEN"

    def test_rule_4_a_survival_is_a_failure(self, mutation: ModuleType) -> None:
        v = mutation.verdict_of(
            self._run(mutation, outcome="NO_KILL", killers=[]), scope=self._scope()
        )
        assert v.verdict == "FAIL"

    def test_rule_5_a_bystander_kill_is_a_failure(self, mutation: ModuleType) -> None:
        """The rule SF-03 exists for.

        Something noticed the behaviour disappear — but not a test the campaign named, so the
        requirement is exactly as unproven as it was before the mutant ran.
        """
        v = mutation.verdict_of(
            self._run(mutation, killers=["tests/unit/unrelated.py::test_y"]), scope=self._scope()
        )
        assert v.verdict == "FAIL"
        assert "scope" in v.reason

    def test_rule_6_an_in_scope_kill_passes(self, mutation: ModuleType) -> None:
        v = mutation.verdict_of(self._run(mutation), scope=self._scope(), confirmed=True)
        assert v.verdict == "PASS"

    def test_a_stale_mutant_still_carries_a_real_verdict(self, mutation: ModuleType) -> None:
        """`STALE` is a flag, not a verdict — collapsing them loses one of two answers.

        "The code moved" and "the requirement is unprotected" need different responses, and a
        result that can only say one of them makes the other invisible.
        """
        v = mutation.verdict_of(
            self._run(mutation, drift="STALE"), scope=self._scope(), confirmed=True
        )
        assert v.verdict == "PASS"
        assert v.drift == "STALE"

    def test_an_unhashed_mutant_is_not_drift(self, mutation: ModuleType) -> None:
        v = mutation.verdict_of(
            self._run(mutation, drift="UNHASHED"), scope=self._scope(), confirmed=True
        )
        assert v.verdict == "PASS"
        assert v.drift == "UNHASHED"


class TestCampaignVerdict:
    """`FR-8` — accounting first, then the worst verdict present."""

    def _v(self, mutation: ModuleType, verdict: str, drift: str = "OK") -> object:
        return mutation.Verdict(derived_id="X FR-1 m", verdict=verdict, reason="", drift=drift)

    def test_a_lost_result_fails_the_campaign_before_anything_else(
        self, mutation: ModuleType
    ) -> None:
        """A campaign that lost a result cannot be scored on the results it kept."""
        got = mutation.campaign_verdict([self._v(mutation, "PASS")], declared=2)
        assert got == "FAILED"

    def test_any_fail_fails_the_campaign(self, mutation: ModuleType) -> None:
        verdicts = [self._v(mutation, "PASS"), self._v(mutation, "FAIL")]
        assert mutation.campaign_verdict(verdicts, declared=2) == "FAILED"

    def test_only_indeterminate_is_partial(self, mutation: ModuleType) -> None:
        verdicts = [self._v(mutation, "PASS"), self._v(mutation, "INDETERMINATE")]
        assert mutation.campaign_verdict(verdicts, declared=2) == "PARTIAL"

    def test_all_passing_is_passed(self, mutation: ModuleType) -> None:
        assert mutation.campaign_verdict([self._v(mutation, "PASS")], declared=1) == "PASSED"

    def test_an_empty_campaign_is_not_silently_passed(self, mutation: ModuleType) -> None:
        """[Hostile] Zero results against zero declared must not read as success."""
        assert mutation.campaign_verdict([], declared=0) == "FAILED"


class TestRunMutantDrift:
    """`STALE` has two sources, and only one of them was wired before SF-03.

    Hash drift comes from `_corpus.drift_of`, which `mutation.py` never called. An anchor that will
    not apply came out as `BROKEN` — wrong, because `BROKEN` must keep meaning *pytest itself
    broke*. The two need different responses: one says re-read the claim, the other says the runner
    could not run.
    """

    def test_an_anchor_that_will_not_apply_is_stale_not_broken(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def _no_anchor(*_a: object, **_k: object) -> dict[str, object]:
            raise ValueError("anchor not found in /x/y.py: 'return sorted(orphans)'")

        monkeypatch.setattr(mutation._mutate, "run_one", _no_anchor)
        run = mutation._run_mutant(tmp_path, _FakeMutant("m"), "tests/a.py", drift="OK")
        assert run.outcome == "STALE"

    def test_a_genuine_runner_failure_is_still_broken(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def _boom(*_a: object, **_k: object) -> dict[str, object]:
            raise RuntimeError("not isolated: specweaver imported from the working tree")

        monkeypatch.setattr(mutation._mutate, "run_one", _boom)
        run = mutation._run_mutant(tmp_path, _FakeMutant("m"), "tests/a.py", drift="OK")
        assert run.outcome == "BROKEN"

    def test_drift_is_carried_onto_the_result(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            mutation._mutate,
            "run_one",
            lambda *a, **k: {"verdict": "KILLED", "killers": ["t::x"], "detail": "", "code": 1},
        )
        run = mutation._run_mutant(tmp_path, _FakeMutant("m"), "tests/a.py", drift="STALE")
        assert run.drift == "STALE"
        assert run.outcome == "KILL", "a drifted mutant still runs and still reports its outcome"


class TestConfirmKill:
    """`FR-6` — a killer only counts if it passes without the mutant.

    A test that fails either way protects nothing: it was already broken, and the mutant merely
    arrived to take the blame. Without this check a permanently red test in scope would certify
    every requirement it touches, forever, and the corpus would report its healthiest numbers on
    exactly the campaigns worth distrusting.
    """

    def test_a_killer_that_passes_unmutated_is_confirmed(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(mutation, "_run_rc", lambda *a, **k: ("1 passed\n", 0))
        assert mutation.confirm_kill(tmp_path, ["tests/a.py::test_x"]) is True

    def test_a_killer_that_fails_unmutated_is_not_confirmed(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            mutation, "_run_rc", lambda *a, **k: ("FAILED tests/a.py::test_x\n1 failed\n", 1)
        )
        assert mutation.confirm_kill(tmp_path, ["tests/a.py::test_x"]) is False

    def test_confirmation_runs_only_the_killers_not_the_scope(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The cost control: one to three node ids, never the whole scope."""
        seen: list[list[str]] = []
        monkeypatch.setattr(
            mutation, "_run_rc", lambda cmd, *a, **k: (seen.append(cmd), ("1 passed\n", 0))[1]
        )
        mutation.confirm_kill(tmp_path, ["tests/a.py::test_x", "tests/b.py::test_y"])
        assert "tests/a.py::test_x" in seen[0]
        assert "tests/b.py::test_y" in seen[0]
        assert not any(arg == "tests/a.py" for arg in seen[0]), "the file, not the node id"

    def test_no_killers_cannot_be_confirmed(self, mutation: ModuleType, tmp_path: Path) -> None:
        """[Boundary] Nothing to re-run is not evidence of protection."""
        assert mutation.confirm_kill(tmp_path, []) is False

    def test_a_run_that_collects_nothing_is_not_confirmation(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """[Hostile] A node id that no longer exists exits 4 and must not read as a green re-run."""
        monkeypatch.setattr(mutation, "_run_rc", lambda *a, **k: ("no tests ran\n", 4))
        assert mutation.confirm_kill(tmp_path, ["tests/gone.py::test_x"]) is False

    def test_the_session_uses_confirmations_answer_rather_than_assuming_it(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Found by a surviving mutant: replacing the call with `confirmed=True` changed nothing.

        Every existing test asserted `confirmed is True` on a genuine kill, which is true whether
        the session asks or assumes. Only a run where confirmation says *no* can tell the two
        apart — and that is the case the whole check exists for.
        """
        monkeypatch.setattr(
            mutation._mutate,
            "run_one",
            lambda *a, **k: {"verdict": "KILLED", "killers": ["t::x"], "detail": "", "code": 1},
        )
        monkeypatch.setattr(mutation, "_run_rc", lambda *a, **k: ("", 0))
        monkeypatch.setattr(mutation, "confirm_kill", lambda *a, **k: False)

        results = mutation.run_corpus(_FakeCorpus(["a"]), sandbox=tmp_path, confirm=True)
        assert results[0].confirmed is False


class TestJudge:
    """`_judge` — the wiring between a run and its campaign verdict.

    Untested until the first real campaign ran and reported every campaign `FAILED` while every
    mutant inside it `PASS`ed. The cause was a dropped `judgements.append`, so `campaign_verdict`
    received an empty list and hit its "a campaign that lost a result cannot be scored" guard.

    `campaign_verdict` was unit-tested with populated lists and `verdict_of` with single runs; the
    line joining them was covered by neither. End-to-end use is what found it.
    """

    def test_a_campaign_whose_only_mutant_passes_is_passed(
        self, mutation: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            mutation._mutate,
            "run_one",
            lambda *a, **k: {
                "verdict": "KILLED",
                "killers": ["tests/a.py::test_x"],
                "detail": "",
                "code": 1,
            },
        )
        monkeypatch.setattr(mutation, "_run_rc", lambda *a, **k: ("", 0))
        monkeypatch.setattr(mutation, "confirm_kill", lambda *a, **k: True)
        monkeypatch.setattr(mutation._corpus, "load_corpus", lambda _p: _FakeCorpus(["m"]))

        judged = mutation._judge(tmp_path / "X_mutants.json", tmp_path, None, confirm=True)

        assert len(judged) == 1
        assert judged[0]["verdicts_returned"] == judged[0]["mutants_declared"] == 1
        assert judged[0]["results"][0]["verdict"] == "PASS"
        assert judged[0]["verdict"] == "PASSED", "the campaign must agree with its own results"
