# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A finding closes for the right reason, through the real chain.

Stories 3 and 5. `withdrawn` and `unreachable` are the two closure reasons whose difference is the
entire point of deriving them rather than letting anyone claim a fix: a mutant somebody deleted and
a mutant that failed to run look identical in a ledger that only records "gone".

The unit tests for `fold_session` hand it a `declared` set directly. That proves the rule and not
the wiring — and if `declared` ever arrived empty, every withdrawal would be misfiled as
`unreachable` and every unit test would still pass. This drives `_declared_ids` → `record_run` →
`fold_session` over real files.
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

pytestmark = pytest.mark.integration

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
def gate() -> ModuleType:
    return _load("_mutation_gate")


def _corpus_file(tmp_path: Path, mutant_id: str = "slug") -> Path:
    path = tmp_path / "F-EXEC-01_mutants.json"
    path.write_text(
        json.dumps(
            {
                "schema": 2,
                "feature": "F-EXEC-01",
                "campaigns": [
                    {
                        "requirement": "FR-1",
                        "title": "t",
                        "scope": ["tests/unit/scripts/test_mutate.py"],
                        "mutants": [
                            {
                                "id": mutant_id,
                                "origin": "authored",
                                "file": "scripts/_mutate.py",
                                "symbol": "killers",
                                "old": 'return [str(record["nodeid"]) for record in killer_records(path)]',
                                "new": "return []",
                                "breaks": "nothing objects",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _record(tmp_path: Path, *mutants: dict[str, Any]) -> Path:
    path = tmp_path / "record.json"
    path.write_text(
        json.dumps({"schema": 1, "session": {"head": "abc"}, "mutants": list(mutants)}),
        encoding="utf-8",
    )
    return path


def _ledger_with_open_finding(gate: ModuleType, tmp_path: Path, mutant_id: str) -> Path:
    path = tmp_path / "ledger.json"
    gate.write_ledger(
        path,
        gate.fold_session(
            {"schema": 1, "findings": {}},
            judged={mutant_id: "UNPROTECTED"},
            reasons={mutant_id: "no-killer"},
            declared={mutant_id},
            now=0.0,
        ),
    )
    return path


class TestDeclaredIdsFromRealCorpus:
    """Story 3."""

    def test_a_real_corpus_declares_its_mutant_ids(
        self, mutation: ModuleType, tmp_path: Path
    ) -> None:
        ids = mutation._declared_ids(_corpus_file(tmp_path))

        assert ids == {"F-EXEC-01 FR-1 slug"}

    def test_an_unreadable_corpus_declares_nothing_rather_than_raising(
        self, mutation: ModuleType, tmp_path: Path
    ) -> None:
        """[Graceful] A corpus file being malformed must not take the session down — the run has
        already happened and the ledger still needs writing."""
        broken = tmp_path / "broken_mutants.json"
        broken.write_text("{not json", encoding="utf-8")

        assert mutation._declared_ids(broken) == set()

    def test_a_missing_corpus_declares_nothing(self, mutation: ModuleType, tmp_path: Path) -> None:
        assert mutation._declared_ids(tmp_path / "absent.json") == set()


class TestClosureReasonThroughTheRealChain:
    """Story 5 — the one the unit tests cannot see."""

    def test_a_mutant_still_declared_but_unjudged_closes_as_unreachable(
        self, mutation: ModuleType, gate: ModuleType, tmp_path: Path
    ) -> None:
        corpus = _corpus_file(tmp_path)
        mutant_id = next(iter(mutation._declared_ids(corpus)))
        ledger = _ledger_with_open_finding(gate, tmp_path, mutant_id)

        gate.record_run(_record(tmp_path), ledger, declared=mutation._declared_ids(corpus))

        entry = json.loads(ledger.read_text(encoding="utf-8"))["findings"][mutant_id]
        assert entry["history"][-1]["reason"] == "unreachable"

    def test_a_mutant_deleted_from_the_corpus_closes_as_withdrawn(
        self, mutation: ModuleType, gate: ModuleType, tmp_path: Path
    ) -> None:
        """Tidying a campaign away must never read like a year of diligent fixing."""
        corpus = _corpus_file(tmp_path)
        mutant_id = next(iter(mutation._declared_ids(corpus)))
        ledger = _ledger_with_open_finding(gate, tmp_path, mutant_id)
        corpus.unlink()

        gate.record_run(_record(tmp_path), ledger, declared=mutation._declared_ids(corpus))

        entry = json.loads(ledger.read_text(encoding="utf-8"))["findings"][mutant_id]
        assert entry["history"][-1]["reason"] == "withdrawn"

    def test_a_mutant_now_protected_closes_as_fixed(
        self, mutation: ModuleType, gate: ModuleType, tmp_path: Path
    ) -> None:
        corpus = _corpus_file(tmp_path)
        mutant_id = next(iter(mutation._declared_ids(corpus)))
        ledger = _ledger_with_open_finding(gate, tmp_path, mutant_id)

        gate.record_run(
            _record(tmp_path, {"id": mutant_id, "verdict": "PROTECTED", "reason": None}),
            ledger,
            declared=mutation._declared_ids(corpus),
        )

        entry = json.loads(ledger.read_text(encoding="utf-8"))["findings"][mutant_id]
        assert entry["history"][-1]["reason"] == "fixed"

    def test_an_empty_declared_set_does_not_silently_call_everything_withdrawn(
        self, mutation: ModuleType, gate: ModuleType, tmp_path: Path
    ) -> None:
        """The failure this seam exists to catch.

        If `declared` never reaches `record_run`, every unjudged finding closes as `withdrawn` —
        the reason that means *somebody deleted it* — and the lifetime statistic silently becomes a
        measure of tidying. Every unit test passes either way, because they pass `declared` by hand.
        """
        corpus = _corpus_file(tmp_path)
        mutant_id = next(iter(mutation._declared_ids(corpus)))
        ledger = _ledger_with_open_finding(gate, tmp_path, mutant_id)

        gate.record_run(_record(tmp_path), ledger, declared=mutation._declared_ids(corpus))

        entry = json.loads(ledger.read_text(encoding="utf-8"))["findings"][mutant_id]
        assert entry["history"][-1]["reason"] != "withdrawn", (
            "the corpus still declares this mutant, so it was not withdrawn"
        )
