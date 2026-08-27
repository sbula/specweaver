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
