# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Whether a session record is evidence at all, before asking what it says.

Proves: TECH-049 FR-11

Split out of `test_mutation_gate.py` when that file passed the 900-line ceiling its own
`file_sizes` gate enforces. The seam is real rather than arithmetic: every other class there asks
what the gate concludes **from** a record, and every class here asks whether the record may be
read at all.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
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


#: The real producer. No record shape is spelled in this file.
_record = _load("_session_record")


@pytest.fixture(scope="module")
def gate() -> ModuleType:
    return _load("_mutation_gate")


class TestGateVerdictAdmissibility:
    """Whether this record is evidence at all, before asking what it says.

    Proves: TECH-049 FR-11

    Two ways a record can be perfectly readable and still answer the wrong question.

    **It covered part of the corpus.** `--corpus <one file>` writes a record shaped exactly like
    the nightly's. The gate read whichever file was at the path and judged 51 mutants as though
    they were 187 — measured 2026-08-27, where a by-hand run at 05:13 had overwritten a 03:00
    nightly and `--gate` answered CLEAR from it.

    **Its tree is gone.** `_build_sandbox` measures HEAD plus your uncommitted work, on purpose. A
    verdict over HEAD-plus-a-diff names no commit, so it is reproducible only while that diff is
    still in the tree. `dirty` is not the fault — being unable to reproduce it is `[agreed
    2026-08-27]` — so the record carries a fingerprint and the gate re-takes it.

    A **missing** scope blocks. An old record cannot say what it covered, and a gate that read
    silence as "everything" would accept exactly the records this rule exists to refuse.
    """

    @staticmethod
    def _record(tmp_path: Path, **session: Any) -> Path:
        document = _record.build_session_record(
            scope={"kind": "full"}, campaigns=[], head="abc1234", dirty=False, baseline=None
        )
        document["session"].update(session)
        path = tmp_path / "mutation_session.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        now = time.time()
        os.utime(path, (now, now))
        return path

    def test_a_scoped_record_blocks_and_names_what_it_got(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Hostile] the 05:13 run that answered for the 03:00 one."""
        report = self._record(
            tmp_path, scope={"kind": "scoped", "corpora": ["B-SENS-03_mutants.json"]}
        )

        result = gate.gate_verdict(report, tmp_path / "ledger.json", current_tree_sha="x")

        assert result.blocked, "a record covering one campaign answered for the whole corpus"
        assert "B-SENS-03_mutants.json" in result.reason, result.reason

    def test_a_full_sweep_record_is_admissible(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Happy] the control — the nightly's own record must pass."""
        report = self._record(tmp_path, scope={"kind": "full"})

        assert not gate.gate_verdict(report, tmp_path / "ledger.json", current_tree_sha="x").blocked

    def test_a_record_that_cannot_say_what_it_covered_blocks(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Graceful degradation] silence is not a claim of completeness.

        The producer always writes `scope` now, so this shape can only reach the gate from a record
        written before it did — which is exactly the record that must not be trusted.
        """
        report = self._record(tmp_path)
        document = json.loads(report.read_text())
        del document["session"]["scope"]
        report.write_text(json.dumps(document), encoding="utf-8")
        now = time.time()
        os.utime(report, (now, now))

        result = gate.gate_verdict(report, tmp_path / "ledger.json", current_tree_sha="x")

        assert result.blocked, "a record with no scope was read as a full sweep"

    def test_a_dirty_record_is_admissible_while_the_tree_still_matches(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Happy] uncommitted work is a designed input, not a fault.

        `_mutate.py` builds the sandbox as HEAD plus the diff *so that* it measures the tree you
        have. Blocking on `dirty` alone would kill the gate every morning after an evening's work.
        """
        report = self._record(tmp_path, scope={"kind": "full"}, dirty=True, tree_sha="sha256:abc")

        assert not gate.gate_verdict(
            report, tmp_path / "ledger.json", current_tree_sha="sha256:abc"
        ).blocked

    def test_a_dirty_record_blocks_once_the_tree_has_moved(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Hostile] the verdict now describes a tree that no longer exists anywhere."""
        report = self._record(tmp_path, scope={"kind": "full"}, dirty=True, tree_sha="sha256:abc")

        result = gate.gate_verdict(
            report, tmp_path / "ledger.json", current_tree_sha="sha256:different"
        )

        assert result.blocked
        assert "tree" in result.reason.lower(), result.reason

    def test_a_dirty_record_blocks_when_the_tree_cannot_be_read(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Hostile] no fingerprint to compare against is not a match.

        The caller supplies the current hash. If it could not take one — not a repository, `git`
        missing — the honest answer is that admissibility is unknown, and unknown fails closed
        here like every other missing measurement in this gate.
        """
        report = self._record(tmp_path, scope={"kind": "full"}, dirty=True, tree_sha="sha256:abc")

        assert gate.gate_verdict(report, tmp_path / "ledger.json", current_tree_sha=None).blocked

    def test_a_clean_record_never_consults_the_tree(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Boundary] a record naming a commit is reproducible from the commit.

        Comparing the working tree against a clean record would block every morning somebody
        started editing, for a verdict that does not depend on the working tree at all.
        """
        report = self._record(tmp_path, scope={"kind": "full"}, dirty=False)

        assert not gate.gate_verdict(
            report, tmp_path / "ledger.json", current_tree_sha="anything at all"
        ).blocked

    def test_a_full_sweep_stays_admissible_after_the_corpus_grows(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] the `TECH-056` NFR-1 control, and the reason coverage is not counted.

        A rule comparing the record's mutants against the corpus *now* would block all day every
        day somebody adds a mutant — the corpus grew by 7 on 2026-08-27 while the nightly's record
        held 187 — and a gate that blocks on ordinary work is one that gets switched off in a week.

        Coverage is the scope the run was pointed at `[agreed 2026-08-27]`. A full sweep stays a
        full sweep when a file inside it gains a row.
        """
        report = self._record(tmp_path, scope={"kind": "full"})

        assert not gate.gate_verdict(report, tmp_path / "ledger.json", current_tree_sha="x").blocked


class TestLatestCoveringRecord:
    """Which record in the store answers this morning's question.

    Proves: TECH-049 FR-9, FR-11

    One file at one path meant the last writer won, and the last writer is usually a by-hand run.
    On 2026-08-27 a 05:13 run overwrote the 03:00 nightly and the nightly's 187-mutant result was
    simply gone — not stale, not refused, **absent**, with no way to get it back.

    A store fixes the loss. The selection is what stops it becoming a new way to answer wrongly: the
    newest record is not the answer, the newest record that **covers the corpus** is. A scoped run
    five minutes ago says nothing about the campaigns it skipped, however recent it is.
    """

    @staticmethod
    def _store(tmp_path: Path, *records: tuple[str, dict[str, Any]]) -> Path:
        store = tmp_path / "sessions"
        store.mkdir()
        for name, scope in records:
            document = _record.build_session_record(
                campaigns=[], head="abc1234", dirty=False, scope=scope
            )
            (store / name).write_text(json.dumps(document), encoding="utf-8")
        return store

    def test_the_newest_full_sweep_is_chosen(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Happy] two nightlies in the store; this morning's is the one that answers."""
        store = self._store(
            tmp_path,
            ("2026-08-26T03-00-00_full.json", {"kind": "full"}),
            ("2026-08-27T03-00-00_full.json", {"kind": "full"}),
        )

        chosen = gate.latest_covering_record(store)

        assert chosen is not None
        assert chosen.name == "2026-08-27T03-00-00_full.json"

    def test_a_newer_scoped_record_does_not_win(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Hostile] the 05:13 run, exactly. Recency is not coverage.

        Under one-file-one-path this record did not merely win — it destroyed the other one.
        """
        store = self._store(
            tmp_path,
            ("2026-08-27T03-00-00_full.json", {"kind": "full"}),
            (
                "2026-08-27T05-13-05_b-sens-03.json",
                {"kind": "scoped", "corpora": ["B-SENS-03_mutants.json"]},
            ),
        )

        chosen = gate.latest_covering_record(store)

        assert chosen is not None
        assert chosen.name == "2026-08-27T03-00-00_full.json", (
            "a scoped run answered for the corpus because it happened to be newer"
        )

    def test_a_store_of_only_scoped_records_answers_nothing(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] plenty of records, none of them evidence about the corpus."""
        store = self._store(
            tmp_path,
            ("2026-08-27T05-13-05_a.json", {"kind": "scoped", "corpora": ["A.json"]}),
            ("2026-08-27T06-13-05_b.json", {"kind": "scoped", "corpora": ["B.json"]}),
        )

        assert gate.latest_covering_record(store) is None

    def test_an_empty_store_answers_nothing(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Boundary] a first run, or a cleared `.tmp`."""
        assert gate.latest_covering_record(self._store(tmp_path)) is None

    def test_a_missing_store_answers_nothing(self, gate: ModuleType, tmp_path: Path) -> None:
        """[Graceful degradation] the directory need not exist yet, and that is not a crash."""
        assert gate.latest_covering_record(tmp_path / "never-created") is None

    def test_an_unreadable_record_does_not_hide_the_rest(
        self, gate: ModuleType, tmp_path: Path
    ) -> None:
        """[Hostile] a half-written file in the store must not take the store down with it.

        A run killed mid-write leaves one. If selection raised, one corrupt file would make every
        good record unreachable — the whole store answering nothing because of the newest byte.
        """
        store = self._store(tmp_path, ("2026-08-27T03-00-00_full.json", {"kind": "full"}))
        (store / "2026-08-27T09-00-00_full.json").write_text('{"schema": 1, "sess', "utf-8")

        chosen = gate.latest_covering_record(store)

        assert chosen is not None
        assert chosen.name == "2026-08-27T03-00-00_full.json"


class TestRecordName:
    """A filename per run, and two runs in one second must not become one record."""

    @staticmethod
    def _named(started_at: str, scope: dict[str, Any]) -> str:
        """The name the producer would give a record with this timestamp and this reach."""
        document = _record.build_session_record(
            campaigns=[], head="abc1234", dirty=False, scope=scope
        )
        document["session"]["started_at"] = started_at
        return str(_record.record_name(document))

    def test_two_runs_in_the_same_second_get_different_names(self) -> None:
        """[Boundary] the nightly and a by-hand run can start in the same second.

        `started_at` carries microseconds, so this is not a hypothetical guard bolted on — it is
        the reason the timestamp is used whole rather than truncated to seconds for tidiness.
        """
        a = self._named("2026-08-27T03:00:00.000001+00:00", {"kind": "full"})
        b = self._named("2026-08-27T03:00:00.900002+00:00", {"kind": "full"})

        assert a != b

    def test_the_name_says_what_the_run_covered(self) -> None:
        """[Happy] a human reading `ls` must be able to tell a nightly from a by-hand run."""
        full = self._named("2026-08-27T03:00:00.000001+00:00", {"kind": "full"})
        scoped = self._named(
            "2026-08-27T05:13:05.000001+00:00",
            {"kind": "scoped", "corpora": ["B-SENS-03_mutants.json"]},
        )

        assert "full" in full
        assert "full" not in scoped
        assert "B-SENS-03" in scoped

    def test_the_name_is_a_usable_filename(self) -> None:
        """[Hostile] an ISO timestamp carries `:` and `+`, and a corpus name carries a path.

        Neither may reach the filesystem as-is: `:` is illegal on Windows and a separator in a
        scope, and an unsanitised corpus name could walk out of the store entirely.
        """
        name = self._named(
            "2026-08-27T05:13:05.000001+00:00",
            {"kind": "scoped", "corpora": ["../../etc/passwd"]},
        )

        assert ":" not in name
        assert "/" not in name
        assert ".." not in name
        assert name.endswith(".json")

    def test_a_scope_with_no_corpora_still_names_a_file(self) -> None:
        """[Graceful degradation] an odd scope must not produce an empty or dangling name."""
        name = self._named("2026-08-27T05:13:05.000001+00:00", {"kind": "scoped"})

        assert name.endswith(".json")
        assert len(name) > len(".json")
