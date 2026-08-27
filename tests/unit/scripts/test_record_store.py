# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for scripts/_record_store.py — what the store keeps and what it throws away.

Proves: TECH-049 FR-9

Retention here is tied to **state, not age** `[agreed 2026-08-27]`: a record is deleted only when a
later `PASSED` record supersedes it. A record of a failure is kept until the failure is fixed and a
clean run of covering scope proves it, however old it gets.

That is the opposite of the usual rule and it is deliberate. Age says nothing about whether anyone
acted on what a record found; a fourteen-day sweep deletes the evidence of a fault nobody has
looked at yet, which is exactly the evidence worth keeping.

The cost is that an unfixed repo grows the store for ever. There is no cap, by decision — a cap
deletes evidence of an unfixed fault, which is the one thing this rule exists to prevent — so the
run warns past twenty unsuperseded records instead.
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
SCRIPT = REPO_ROOT / "scripts" / "_record_store.py"

FULL: dict[str, Any] = {"kind": "full"}


def _scoped(*corpora: str) -> dict[str, Any]:
    return {"kind": "scoped", "corpora": list(corpora)}


@pytest.fixture(scope="module")
def store() -> ModuleType:
    assert SCRIPT.exists(), f"script not found: {SCRIPT}"
    spec = importlib.util.spec_from_file_location("_record_store", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_record_store"] = module
    spec.loader.exec_module(module)
    return module


class TestCovers:
    """Whether one run's reach contains another's."""

    def test_a_full_sweep_covers_a_scoped_run(self, store: ModuleType) -> None:
        """[Happy] the ordinary case: the nightly answers for what a by-hand run touched."""
        assert store.covers(FULL, _scoped("A_mutants.json")) is True

    def test_a_full_sweep_covers_another_full_sweep(self, store: ModuleType) -> None:
        """[Happy] two nightlies. The newer answers for the older."""
        assert store.covers(FULL, FULL) is True

    def test_a_scoped_run_does_not_cover_a_full_sweep(self, store: ModuleType) -> None:
        """[Hostile] the whole reason coverage is asked rather than recency.

        A clean run over one campaign says nothing about the 186 mutants it skipped, so it cannot
        retire the record of a sweep that found something in them.
        """
        assert store.covers(_scoped("A_mutants.json"), FULL) is False

    def test_a_scoped_run_covers_a_narrower_scoped_run(self, store: ModuleType) -> None:
        """[Boundary] subset, not equality — a wider by-hand run may retire a narrower one."""
        assert store.covers(_scoped("A_mutants.json", "B_mutants.json"), _scoped("A_mutants.json"))

    def test_a_scoped_run_does_not_cover_a_disjoint_one(self, store: ModuleType) -> None:
        """[Boundary] overlapping is not covering."""
        assert store.covers(_scoped("A_mutants.json"), _scoped("B_mutants.json")) is False

    def test_an_unknown_scope_covers_nothing(self, store: ModuleType) -> None:
        """[Graceful degradation] a record that cannot say what it covered may not retire anything.

        Reading silence as "everything" is the mistake the gate refuses one level up, and it would
        be worse here — there it blocks a morning, here it deletes evidence.
        """
        assert store.covers({}, _scoped("A_mutants.json")) is False
        assert store.covers({"kind": "scoped"}, _scoped("A_mutants.json")) is False


class TestSuperseded:
    """Which records a later clean run has made redundant."""

    def test_a_failure_is_deleted_by_a_later_covering_pass(self, store: ModuleType) -> None:
        """[Happy] the rule: fixed, and proven fixed by a run that looked at it."""
        entries = [
            ("01_full.json", "FAILED", FULL),
            ("02_full.json", "PASSED", FULL),
        ]

        assert store.superseded(entries) == ["01_full.json"]

    def test_a_failure_survives_a_later_narrower_pass(self, store: ModuleType) -> None:
        """[Hostile] `Q6`. A clean scoped run must not retire a wide failure.

        This is the deletion that would silently destroy the only record of a fault, and it looks
        exactly like progress: a green run, more recent, and the red one gone.
        """
        entries = [
            ("01_full.json", "FAILED", FULL),
            ("02_a.json", "PASSED", _scoped("A_mutants.json")),
        ]

        assert store.superseded(entries) == []

    def test_a_not_run_record_is_kept_exactly_as_a_failure(self, store: ModuleType) -> None:
        """[Boundary] a session that judged nothing is an error, and errors are kept.

        `STATE.md` already says a run that leaves no record is an alarm, not a pass. A run that
        leaves an empty one is the same alarm with a file attached.
        """
        entries = [
            ("01_full.json", "NOT_RUN", FULL),
            ("02_a.json", "PASSED", _scoped("A_mutants.json")),
        ]

        assert store.superseded(entries) == []

    def test_a_pass_is_superseded_by_a_later_pass(self, store: ModuleType) -> None:
        """[Boundary] clean records are not sacred; a newer clean sweep replaces an older one."""
        entries = [
            ("01_full.json", "PASSED", FULL),
            ("02_full.json", "PASSED", FULL),
        ]

        assert store.superseded(entries) == ["01_full.json"]

    def test_the_newest_record_is_never_superseded(self, store: ModuleType) -> None:
        """[Boundary] nothing is later than the latest, so the store can never empty itself."""
        entries = [("01_full.json", "PASSED", FULL)]

        assert store.superseded(entries) == []

    def test_a_later_failure_does_not_retire_anything(self, store: ModuleType) -> None:
        """[Hostile] only a PASS supersedes. A newer red run is more evidence, not less."""
        entries = [
            ("01_full.json", "FAILED", FULL),
            ("02_full.json", "FAILED", FULL),
        ]

        assert store.superseded(entries) == []

    def test_order_is_by_name_not_by_position(self, store: ModuleType) -> None:
        """[Hostile] the caller may hand these over in any order.

        Names lead with the timestamp, so sorting them IS chronology. A function trusting list
        order would delete the newest record the day a caller globbed without sorting.
        """
        entries = [
            ("02_full.json", "PASSED", FULL),
            ("01_full.json", "FAILED", FULL),
        ]

        assert store.superseded(entries) == ["01_full.json"]

    def test_an_empty_store_supersedes_nothing(self, store: ModuleType) -> None:
        """[Graceful degradation] no records, no deletions, no crash."""
        assert store.superseded([]) == []


class TestOvergrown:
    """The warning that replaces a cap."""

    def test_it_is_quiet_at_twenty(self, store: ModuleType) -> None:
        """[Boundary] twenty is the agreed threshold, and a threshold fires ABOVE itself."""
        entries = [(f"{i:02d}_full.json", "FAILED", FULL) for i in range(20)]

        assert store.overgrown(entries) is None

    def test_it_warns_past_twenty(self, store: ModuleType) -> None:
        """[Happy] twenty-one unsuperseded records is a store nobody is draining."""
        entries = [(f"{i:02d}_full.json", "FAILED", FULL) for i in range(21)]

        warning = store.overgrown(entries)

        assert warning is not None
        assert "21" in warning

    def test_superseded_records_do_not_count_toward_it(self, store: ModuleType) -> None:
        """[Boundary] the warning is about a backlog, not about disk.

        Counting records due for deletion would fire on a healthy store the moment somebody ran
        the corpus twenty-one times, which is a Tuesday.
        """
        entries = [(f"{i:02d}_full.json", "PASSED", FULL) for i in range(30)]

        assert store.overgrown(entries) is None

    def test_it_never_asks_for_a_deletion(self, store: ModuleType) -> None:
        """[Hostile] `Q7`. The warning exists BECAUSE there is no cap.

        A cap deletes the evidence of an unfixed fault, which is the one thing the retention rule
        is for. So `overgrown` returns prose and nothing else — it has no path that names a file.
        """
        entries = [(f"{i:02d}_full.json", "FAILED", FULL) for i in range(50)]

        warning = store.overgrown(entries)

        assert isinstance(warning, str)
        assert store.superseded(entries) == []


class TestSweep:
    """The I/O edge: what actually leaves the disk."""

    @staticmethod
    def _write(tmp_path: Path, name: str, verdict: str, scope: dict[str, Any]) -> Path:
        """A record on disk, built by the producer so no shape is spelled here."""
        import json

        record = sys.modules["_record_store"]._record
        document = record.build_session_record(
            campaigns=[{"results": [{"id": "F FR-1 m", "verdict": verdict}]}] if verdict else [],
            head="abc1234",
            dirty=False,
            scope=scope,
        )
        store_dir = tmp_path / "sessions"
        store_dir.mkdir(exist_ok=True)
        (store_dir / name).write_text(json.dumps(document), encoding="utf-8")
        (store_dir / name).with_suffix(".md").write_text("summary", encoding="utf-8")
        return store_dir

    def test_a_superseded_record_and_its_summary_both_go(
        self, store: ModuleType, tmp_path: Path
    ) -> None:
        """[Happy] the summary is a view of the record, so it goes when the record goes.

        Leaving it would make `ls` show a session whose evidence no longer exists.
        """
        self._write(tmp_path, "01_full.json", "UNPROTECTED", FULL)
        store_dir = self._write(tmp_path, "02_full.json", "PROTECTED", FULL)

        removed, _ = store.sweep(store_dir)

        assert removed == ["01_full.json"]
        assert not (store_dir / "01_full.json").exists()
        assert not (store_dir / "01_full.md").exists()
        assert (store_dir / "02_full.json").exists()

    def test_a_failure_with_no_later_pass_stays_on_disk(
        self, store: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] the whole rule, at the edge that can actually lose something."""
        store_dir = self._write(tmp_path, "01_full.json", "UNPROTECTED", FULL)

        removed, _ = store.sweep(store_dir)

        assert removed == []
        assert (store_dir / "01_full.json").exists()

    def test_a_missing_store_is_not_an_error(self, store: ModuleType, tmp_path: Path) -> None:
        """[Graceful degradation] the first run sweeps before anything has been written."""
        assert store.sweep(tmp_path / "never-created") == ([], None)

    def test_an_unreadable_record_does_not_take_the_store_down(
        self, store: ModuleType, tmp_path: Path
    ) -> None:
        """[Hostile] a run killed mid-write leaves a half-file.

        Raising here would be worse than in selection: there it blocks a morning, here it aborts
        the sweep and the store grows for ever behind one corrupt byte.
        """
        store_dir = self._write(tmp_path, "01_full.json", "PROTECTED", FULL)
        (store_dir / "02_full.json").write_text('{"schema": 1, "sess', encoding="utf-8")

        removed, warning = store.sweep(store_dir)

        assert removed == []
        assert warning is None
        assert (store_dir / "02_full.json").exists(), "and it is not deleted either"

    def test_a_wide_failure_survives_a_later_narrow_pass_on_disk(
        self, store: ModuleType, tmp_path: Path
    ) -> None:
        """[Hostile] the deletion that would destroy the only record of a fault.

        Every other sweep test here has either one record, or two where the older one is genuinely
        superseded — so a `sweep` that deleted *everything but the newest* passed all of them.
        A mutant said so, SILENT. This is the case that tells the two apart: an older record that
        must stay, with a newer one sitting after it.
        """
        self._write(tmp_path, "01_full.json", "UNPROTECTED", FULL)
        store_dir = self._write(tmp_path, "02_a.json", "PROTECTED", _scoped("A_mutants.json"))

        removed, _ = store.sweep(store_dir)

        assert removed == []
        assert (store_dir / "01_full.json").exists(), (
            "a clean run over one campaign deleted the record of a sweep that found something in "
            "the 186 mutants it never looked at"
        )
        assert (store_dir / "01_full.md").exists(), "and its summary went with it"
