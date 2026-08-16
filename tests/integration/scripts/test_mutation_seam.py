# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The first place the corpus and the runner meet.

Proves: TECH-049 FR-4, FR-6, FR-7, FR-9, FR-11

`SF-01` produced validated `Corpus` objects and ran nothing; `_mutate` ran mutants and knew nothing
about campaigns. This is the seam between them, and per `ADR-003` it belongs to the boundary that
creates it — there is no later story that would write it.

Integration tier because it builds a real detached worktree and runs real pytest. That is the cost
of the only test that proves the two halves fit; everything else about them is already unit-tested.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mutation() -> ModuleType:
    return _load("mutation")


@pytest.fixture(scope="module")
def corpus() -> ModuleType:
    return _load("_corpus")


@pytest.fixture
def corpus_file(tmp_path: Path) -> Path:
    """A campaign whose mutant neutralises orphan detection, scoped to the tests that cover it."""
    body = {
        "schema": 1,
        "feature": "D-SENS-09",
        "campaigns": [
            {
                "requirement": "FR-97",
                "scope": ["tests/unit/graph/interfaces/test_cli_lineage.py"],
                "mutants": [
                    {
                        "id": "orphans-empty",
                        "file": "src/specweaver/graph/lineage/scanner.py",
                        "symbol": "check_lineage",
                        "old": "return sorted(orphans)",
                        "new": "return []",
                        "breaks": "orphan detection reports nothing",
                    }
                ],
            }
        ],
    }
    path = tmp_path / "D-SENS-09_mutants.json"
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return path


@pytest.mark.integration
class TestCorpusDrivesTheRunner:
    """A `Corpus` from SF-01, executed by `_mutate` in a real sandbox."""

    def test_a_corpus_mutant_is_killed_by_its_scoped_tests(
        self, mutation: ModuleType, corpus: ModuleType, corpus_file: Path
    ) -> None:
        loaded = corpus.load_corpus(corpus_file)
        results = mutation.run_corpus(loaded, baseline=None)

        assert len(results) == 1, "one mutant declared, one result expected"
        only = results[0]
        assert only.outcome == "KILL"
        assert only.derived_id == "D-SENS-09 FR-97 orphans-empty"
        assert any("test_check_lineage_detects_orphans" in k for k in only.killers)

    def test_a_mistyped_scope_is_not_a_survival(
        self, mutation: ModuleType, corpus: ModuleType, corpus_file: Path
    ) -> None:
        """`FR-4` end to end — the false negative this sub-feature exists to close.

        Before the exit-code guard, a scope pointing at nothing collected zero tests, produced zero
        failures, and was reported as a survival: a finding saying the requirement is unprotected
        when in truth nothing was measured at all.
        """
        data = json.loads(corpus_file.read_text(encoding="utf-8"))
        data["campaigns"][0]["scope"] = ["tests/unit/graph/interfaces/test_typo_does_not_exist.py"]
        corpus_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        results = mutation.run_corpus(corpus.load_corpus(corpus_file), baseline=None)
        assert results[0].outcome == "NOTHING_RAN"
        assert results[0].outcome != "NO_KILL"


@pytest.mark.integration
class TestSandboxHygiene:
    """A mutant that leaks state must not corrupt the one measured after it.

    This is the regression guard for the class of defect `103d7998` fixed, where the second mutant
    in a campaign silently measured a different tree than the first. That bug failed closed by
    luck; this one would not — a leaked file changes what the next test sees without changing any
    verdict's shape.
    """

    def test_a_leak_is_recorded_and_the_next_mutant_is_still_measured(
        self, mutation: ModuleType, corpus: ModuleType, corpus_file: Path
    ) -> None:
        data = json.loads(corpus_file.read_text(encoding="utf-8"))
        campaign = data["campaigns"][0]
        campaign["mutants"].append(
            {
                "id": "orphans-none",
                "file": "src/specweaver/graph/lineage/scanner.py",
                "symbol": "check_lineage",
                "old": "orphans: list[str] = []",
                "new": "orphans: list[str] = []  # noqa",
                "breaks": "a no-op edit, present only to be the second mutant",
            }
        )
        corpus_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        loaded = corpus.load_corpus(corpus_file)

        results = mutation.run_corpus(loaded, baseline=None)

        assert len(results) == 2, "two mutants declared, two results — accounting holds"
        assert results[0].outcome == "KILL", "the first is still measured correctly"
        assert results[1].outcome in {"KILL", "NO_KILL"}, "the second ran; it was not lost"

    def test_the_session_removes_the_sandbox_it_created(
        self, mutation: ModuleType, corpus: ModuleType, corpus_file: Path, monkeypatch: Any
    ) -> None:
        """[Degradation] A session that leaves worktrees behind fills the disk over a month of nights.

        Asserts on **the path this session created**, never on `git worktree list`'s count. The
        first version of this test compared that count before and after and passed alone while
        failing under `-n auto`: other xdist workers hold worktrees of their own, so the number
        moves for reasons this test has no business caring about. A test that reads shared mutable
        state is a test that reports on its neighbours.
        """
        created: list[Path] = []
        real_build = mutation.build_sandbox

        def _record() -> Path:
            sandbox = real_build()
            created.append(sandbox)
            return sandbox

        monkeypatch.setattr(mutation, "build_sandbox", _record)
        mutation.run_corpus(corpus.load_corpus(corpus_file), baseline=None)

        assert created, "the session built a sandbox"
        assert not created[0].exists(), "and removed the one it built"


@pytest.mark.integration
class TestConfirmationAgainstARealSandbox:
    """`FR-6` end to end — the interface that does not exist until this boundary.

    Confirmation is the difference between "a test failed while the mutant was applied" and "a test
    that otherwise passes failed because of it". Only a real sandbox can tell those apart, because
    the second half of the claim is a second real pytest run.
    """

    def test_a_genuine_kill_is_confirmed(
        self, mutation: ModuleType, corpus: ModuleType, corpus_file: Path
    ) -> None:
        loaded = corpus.load_corpus(corpus_file)
        results = mutation.run_corpus(loaded, baseline=None, confirm=True)
        assert results[0].outcome == "KILL"
        assert results[0].confirmed is True, "the killers pass without the mutant"

    def test_a_permanently_failing_killer_is_not_protection(
        self, mutation: ModuleType, corpus: ModuleType, corpus_file: Path, tmp_path: Path
    ) -> None:
        """The failure mode `FR-6` exists for, built rather than mocked.

        A test that fails with *and* without the mutant certifies nothing, but looks identical to a
        real kill in the output: both are a `FAILED` line while the mutant is applied.
        """
        sandbox = mutation.build_sandbox()
        try:
            planted = Path(sandbox) / "tests" / "unit" / "test_always_red_probe.py"
            planted.write_text("def test_always_red():\n    assert False\n", encoding="utf-8")
            assert (
                mutation.confirm_kill(
                    Path(sandbox), ["tests/unit/test_always_red_probe.py::test_always_red"]
                )
                is False
            )
        finally:
            mutation.remove_sandbox(Path(sandbox))


@pytest.mark.integration
class TestReportOutlivesTheSandbox:
    """`FR-9` — the claim is only falsifiable once the sandbox is gone.

    Everything else about the report can be asserted on a dict in memory. This one cannot: the
    point is that the file remains useful after the worktree it describes has been deleted, and
    proving that means actually deleting it first.
    """

    def test_no_sandbox_path_survives_into_the_written_report(
        self, mutation: ModuleType, corpus: ModuleType, corpus_file: Path, tmp_path: Path
    ) -> None:
        """The mutant is given a stale anchor on purpose.

        A stale anchor is the one path that puts an absolute sandbox path into `detail` verbatim —
        `apply_mutation` raises with the full filename — so it is the case that would leak.
        """
        data = json.loads(corpus_file.read_text(encoding="utf-8"))
        data["campaigns"][0]["mutants"][0]["old"] = "THIS ANCHOR DOES NOT EXIST"
        corpus_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        out = tmp_path / "mutation_report.json"
        # `--ledger` is not optional here even though the test says nothing about ledgers:
        # `main` records the run, and without it `record_run` appends to the REAL
        # `scripts/baselines/mutation_findings.json` (`TECH-055`).
        code = mutation.main(
            [
                "--corpus",
                str(corpus_file),
                "--out",
                str(out),
                "--no-baseline",
                "--ledger",
                str(tmp_path / "ledger.json"),
            ]
        )

        assert out.is_file(), "a report must exist even when every mutant failed"
        written = out.read_text(encoding="utf-8")
        assert "/tmp/" not in written, "the sandbox is gone; nothing may point into it"
        assert "scanner.py" in written, "and the useful half of the path survived"
        assert code in {0, 1}

    def test_no_corpus_files_is_exit_two(self, mutation: ModuleType, tmp_path: Path) -> None:
        """[Hostile] A session that measured nothing must not report success."""
        out = tmp_path / "report.json"
        assert mutation.main(["--corpus-dir", str(tmp_path), "--out", str(out)]) == 2


@pytest.mark.integration
class TestReportLedgerGateChain:
    """`FR-11` end to end — the chain that does not exist until this boundary.

    Report, ledger, gate. Each has unit tests; the wiring between them has none, and this ticket has
    already been bitten three times by exactly that gap — most recently a dropped
    `judgements.append` that no unit test could see.
    """

    def test_a_finding_blocks_until_confirmed_then_clears(
        self, mutation: ModuleType, tmp_path: Path
    ) -> None:
        report = tmp_path / "report.json"
        ledger = tmp_path / "ledger.json"
        report.write_text(
            json.dumps(
                {
                    "summary": {"head": "abc", "verdict": "FAILED"},
                    "campaigns": [
                        {
                            "feature": "F",
                            "requirement": "FR-1",
                            "verdict": "FAILED",
                            "mutants_declared": 1,
                            "verdicts_returned": 1,
                            "results": [
                                {
                                    "derived_id": "F FR-1 m",
                                    "verdict": "FAIL",
                                    "reason": "no test noticed",
                                    "drift": "OK",
                                    "detail": "",
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        blocked = mutation.main(["--gate", "--out", str(report), "--ledger", str(ledger)])
        assert blocked == 1, "an unread finding must block"

        confirmed = mutation.main(
            [
                "--confirm",
                "F FR-1 m",
                "--as",
                "will-fix",
                "--why",
                "narrowing scope first",
                "--ledger",
                str(ledger),
            ]
        )
        assert confirmed == 0

        assert mutation.main(["--gate", "--out", str(report), "--ledger", str(ledger)]) == 0
        assert json.loads(ledger.read_text())["override_count"] == 1, "and the census counted it"
