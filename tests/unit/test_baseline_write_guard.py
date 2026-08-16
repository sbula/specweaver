# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The suite must not rewrite the ratchet baselines it is measured against.

Proves: TECH-055 FR-1, NFR-1

`scripts/baselines/` holds sixteen version-controlled files, one per gate: the uncited-FR count, the
duplication clone count, the delivered-claims ratchet, the mutation ledger. **A test that writes one
of them edits the standard the repo is judged by**, in a commit whose diff looks like ordinary test
work, and no gate compares a baseline against what it was.

That is not hypothetical. `tests/integration/scripts/test_mutation_seam.py` called
`mutation.main(["--corpus", …, "--out", …])` without `--ledger`, so `record_run` appended a finding
to the **real** `scripts/baselines/mutation_findings.json` on every suite run — inventing a
`D-SENS-09 FR-97 orphans-empty` finding that the morning gate would then ask somebody to read, for a
mutant that only ever existed inside a fixture. Found 2026-08-16 by noticing an unexplained
modification in `git status` after a full run.

This file proves the guard's logic. The guard itself is `tests/conftest.py::_baselines_are_read_only`
— autouse, suite-wide, so it protects **tests nobody has written yet**, which is the same reason the
colour block at the top of that file is set at import rather than in a fixture.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

from tests.baseline_snapshot import BASELINES, rewrites, snapshot

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def baselines(tmp_path: Path) -> Path:
    directory = tmp_path / "baselines"
    directory.mkdir()
    (directory / "fr_uncited.json").write_text('{"count": 234}\n', encoding="utf-8")
    (directory / "duplication.json").write_text('{"clones": 123}\n', encoding="utf-8")
    return directory


class TestSnapshot:
    """What the guard compares."""

    def test_it_reads_every_file_in_the_directory(self, baselines: Path) -> None:
        """[Happy] one entry per file, keyed by name."""
        assert set(snapshot(baselines)) == {"fr_uncited.json", "duplication.json"}

    def test_reading_a_baseline_is_not_a_write(self, baselines: Path) -> None:
        """[Happy] the guard must be silent for the thing tests legitimately do.

        Gate-script tests read these files constantly. If inspection registered, the guard would
        fail hundreds of tests on its first run and be removed the same day.

        Asserting `snapshot() == snapshot()` would not prove this — it is a self-comparison, which
        `check_useless_asserts.py` flags precisely because it cannot fail. Reading the file first is
        what makes the assertion mean something.
        """
        before = snapshot(baselines)
        (baselines / "fr_uncited.json").read_bytes()

        assert snapshot(baselines) == before

    def test_a_rewrite_with_identical_bytes_is_still_a_write(self, baselines: Path) -> None:
        """[Boundary] the case a content-only snapshot cannot see, and it is not academic.

        `record_run` rewrites the mutation ledger byte-identically whenever it has nothing to
        report, so `test_mutation_nightly.py` overwrote it on every suite run and a content-only
        guard stayed silent — until the day a finding existed, which is the one day the file's
        contents matter. That writer was found by hand, which is what this guard exists to replace.
        """
        before = snapshot(baselines)
        target = baselines / "fr_uncited.json"
        target.write_bytes(target.read_bytes())

        reported = rewrites(before, snapshot(baselines))

        assert len(reported) == 1
        assert "fr_uncited.json" in reported[0]
        assert "identical content" in reported[0]

    def test_a_nested_file_is_not_missed(self, baselines: Path) -> None:
        """[Boundary] the directory is flat today; a guard that assumes so is one `mkdir` from
        blind, and the file it would stop seeing is the one somebody moved there for tidiness."""
        nested = baselines / "per_gate"
        nested.mkdir()
        (nested / "proof_tier.json").write_text("{}\n", encoding="utf-8")

        assert "per_gate/proof_tier.json" in snapshot(baselines)

    def test_content_that_is_not_text_is_still_read(self, baselines: Path) -> None:
        """[Hostile] hashing bytes, not decoded text — a stray binary must not crash every test."""
        (baselines / "odd.bin").write_bytes(b"\xff\xfe\x00garbage")

        assert "odd.bin" in snapshot(baselines)

    def test_a_missing_directory_is_an_error_not_an_empty_snapshot(self, tmp_path: Path) -> None:
        """[Hostile] `TECH-032`: a guard that cannot find its subject says so rather than passing.

        Returning `{}` would make every comparison trivially equal, so deleting `scripts/baselines/`
        would silently disarm the guard instead of failing loudly.
        """
        with pytest.raises(FileNotFoundError):
            snapshot(tmp_path / "nowhere")


class TestRewrites:
    """What it reports, and to whom — the message is the whole value of the failure."""

    def test_an_untouched_directory_reports_nothing(self, baselines: Path) -> None:
        """[Happy] the case that runs 7356 times, so it must be silent."""
        assert rewrites(snapshot(baselines), snapshot(baselines)) == []

    def test_a_changed_file_is_reported_by_name(self, baselines: Path) -> None:
        """[Happy] the real defect's shape: same file, different content."""
        before = snapshot(baselines)
        (baselines / "fr_uncited.json").write_text('{"count": 0}\n', encoding="utf-8")

        reported = rewrites(before, snapshot(baselines))

        assert len(reported) == 1
        assert "fr_uncited.json" in reported[0]
        assert "changed" in reported[0]

    def test_a_new_file_is_reported(self, baselines: Path) -> None:
        """[Boundary] a gate's first baseline is written by a person, never by a test run."""
        before = snapshot(baselines)
        (baselines / "brand_new.json").write_text("{}\n", encoding="utf-8")

        reported = rewrites(before, snapshot(baselines))

        assert len(reported) == 1
        assert "brand_new.json" in reported[0]
        assert "added" in reported[0]

    def test_a_deleted_file_is_reported(self, baselines: Path) -> None:
        """[Hostile] the worst case, and the one a content-only check would miss entirely:
        a gate whose baseline has vanished has nothing to ratchet against."""
        before = snapshot(baselines)
        (baselines / "duplication.json").unlink()

        reported = rewrites(before, snapshot(baselines))

        assert len(reported) == 1
        assert "duplication.json" in reported[0]
        assert "deleted" in reported[0]

    def test_every_affected_file_is_named_not_just_the_first(self, baselines: Path) -> None:
        """[Boundary] one report per file. A run that rewrote three baselines and named one
        sends whoever reads it back for two more runs."""
        before = snapshot(baselines)
        (baselines / "fr_uncited.json").write_text("{}\n", encoding="utf-8")
        (baselines / "duplication.json").unlink()
        (baselines / "third.json").write_text("{}\n", encoding="utf-8")

        assert len(rewrites(before, snapshot(baselines))) == 3


class TestSnapshotCost:
    """NFR-1 — cheap enough to run twice per test, or it acquires an opt-out and guards nothing."""

    def test_a_snapshot_of_the_real_directory_is_fast(self) -> None:
        """Measured at ~0.12 ms for 100 KB across 16 files; the bar is 50 ms.

        Deliberately loose. This is not a benchmark — it is a tripwire for the change that makes
        the guard expensive enough to be disabled: hashing the repo instead of the directory,
        shelling out to `git`, or walking a tree somebody symlinked in. A tight threshold would
        fail on a loaded CI box and be deleted within a week.
        """
        started = time.perf_counter()
        snapshot(BASELINES)
        elapsed = time.perf_counter() - started

        assert elapsed < 0.05, (
            f"snapshotting the ratchets took {elapsed * 1000:.1f} ms; at two per test that is "
            f"{elapsed * 2 * 7356:.0f} s across the suite, which is where an opt-out gets added"
        )


class TestSnapshotOfTheRatchetSet:
    """The guard is pointed at something, and that something is the ratchet set."""

    def test_the_baselines_directory_exists_and_is_populated(self) -> None:
        """Pins what `TestSnapshot`'s hostile case only describes: if this path ever moves, the
        autouse fixture raises on every test rather than quietly guarding an empty set."""
        entries = snapshot(BASELINES)

        assert len(entries) >= 10, f"expected the gate ratchets, found {sorted(entries)}"
        assert "mutation_findings.json" in entries, "the file the original defect rewrote"
