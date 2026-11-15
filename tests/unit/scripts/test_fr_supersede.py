# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.
# fr-coverage: fixture-data

"""A later design supersedes a closed story's FR, and the FR gates see it. `A-SENS-02` FR-3.

A closed story's FR row stays as written. The later design marks it on one line:
``supersedes `<STORY>` FR-<n> with FR-<m>``, the user's ``[agreed <date>]`` right after it. The gates then show
the old FR as "superseded by …" instead of uncited, and only while the marker holds up: approval
tag, an FR that exists, no self-supersede, a superseding FR a test cites, one marker per FR.

| Bucket | Case |
|---|---|
| Happy | a valid marker: the ledger prints "superseded by …" and passes; the sweep does not count it |
| Boundary | a superseded FR still cited is fine; two markers for one FR fail |
| Degradation | the superseded story has no design, or does not declare the FR → fail |
| Hostile | no tag, a placeholder tag, a tag elsewhere on the row only, self-supersede, an uncited or undeclared superseding FR → fail |
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
_TAG = "`[agreed 2026-11-13]`"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cov() -> ModuleType:
    return _load("check_fr_coverage")


@pytest.fixture(scope="module")
def sweep() -> ModuleType:
    return _load("check_fr_sweep")


def _design(root: Path, story: str, rows: list[str]) -> None:
    folder = root / "docs" / "roadmap" / "features" / "topic_x" / story
    folder.mkdir(parents=True, exist_ok=True)
    table = "\n".join(rows)
    (folder / f"{story}_design.md").write_text(
        f"# Design: {story}\n\n| FR | Text |\n|---|---|\n{table}\n", encoding="utf-8"
    )
    (folder / f"{story}_implementation_plan.md").write_text(
        " ".join(r.split("|")[1] for r in rows), encoding="utf-8"
    )


def _test_file(root: Path, name: str, text: str) -> None:
    path = root / "tests" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _world(root: Path, marker: str, *, cite_new: bool = True, old_rows: int = 2) -> None:
    """`OLD-1` (closed) declares FR-1..FR-n; `NEW-1` supersedes OLD-1 FR-2 with its FR-1."""
    _design(root, "OLD-1", [f"| FR-{i} | old rule {i} |" for i in range(1, old_rows + 1)])
    _design(root, "NEW-1", [f"| FR-1 | the new rule; {marker} |", "| FR-2 | other |"])
    _test_file(root, "test_old.py", '"""OLD-1 FR-1."""\n')
    if cite_new:
        _test_file(root, "test_new.py", '"""NEW-1 FR-1, FR-2."""\n')


def _judge(cov: ModuleType, root: Path) -> tuple[dict[tuple[str, str], object], list[str]]:
    result: tuple[dict[tuple[str, str], object], list[str]] = cov.judge_supersedes(
        root / "docs" / "roadmap" / "features", root / "tests"
    )
    return result


_VALID = f"supersedes `OLD-1` FR-2 with FR-1 {_TAG}"


class TestJudge:
    def test_a_valid_marker_supersedes_the_fr(self, cov: ModuleType, tmp_path: Path) -> None:
        _world(tmp_path, _VALID)
        valid, errors = _judge(cov, tmp_path)
        assert errors == []
        (marker,) = valid.values()
        assert list(valid) == [("OLD-1", "FR-2")]
        assert (marker.by_story, marker.by_fr, marker.agreed) == ("NEW-1", "FR-1", "2026-11-13")

    def test_a_superseded_fr_that_is_still_cited_is_fine(
        self, cov: ModuleType, tmp_path: Path
    ) -> None:
        _world(tmp_path, _VALID)
        _test_file(tmp_path, "test_old2.py", '"""OLD-1 FR-2."""\n')
        valid, errors = _judge(cov, tmp_path)
        assert errors == [] and ("OLD-1", "FR-2") in valid

    @pytest.mark.parametrize(
        ("marker", "cite_new", "reason"),
        [
            ("supersedes `OLD-1` FR-2 with FR-1", True, "approval tag"),
            ("supersedes `OLD-1` FR-2 with FR-1 `[agreed <date>]`", True, "approval tag"),
            (f"an earlier rule {_TAG}; supersedes `OLD-1` FR-2 with FR-1", True, "approval tag"),
            (f"supersedes `OLD-1` FR-2 with FR-1 (a reason) {_TAG}", True, "approval tag"),
            (f"supersedes `OLD-1` FR-7 with FR-1 {_TAG}", True, "does not exist"),
            (f"supersedes `NOPE-1` FR-2 with FR-1 {_TAG}", True, "does not exist"),
            (f"supersedes `NEW-1` FR-2 with FR-1 {_TAG}", True, "itself"),
            (f"supersedes `OLD-1` FR-2 with FR-9 {_TAG}", True, "not declared"),
            (_VALID, False, "no test"),
        ],
    )
    def test_a_marker_that_does_not_hold_up_is_an_error_and_supersedes_nothing(
        self, cov: ModuleType, tmp_path: Path, marker: str, cite_new: bool, reason: str
    ) -> None:
        _world(tmp_path, marker, cite_new=cite_new)
        valid, errors = _judge(cov, tmp_path)
        assert valid == {}
        (error,) = errors
        assert reason in error
        assert "NEW-1" in error

    def test_only_the_tag_beside_the_marker_dates_it(self, cov: ModuleType, tmp_path: Path) -> None:
        _world(tmp_path, f"an earlier rule `[agreed 2026-11-01]`; {_VALID}")
        valid, errors = _judge(cov, tmp_path)
        assert errors == []
        assert valid[("OLD-1", "FR-2")].agreed == "2026-11-13"

    def test_two_markers_for_one_fr_are_an_error(self, cov: ModuleType, tmp_path: Path) -> None:
        _world(tmp_path, _VALID)
        folder = tmp_path / "docs/roadmap/features/topic_x/NEW-1"
        design = folder / "NEW-1_design.md"
        design.write_text(
            design.read_text().replace("| FR-2 | other |", f"| FR-2 | other; {_VALID} |")
        )
        valid, errors = _judge(cov, tmp_path)
        assert valid == {}
        assert any("superseded twice" in e for e in errors)


class TestLedger:
    def test_the_superseded_fr_stays_visible_and_the_story_passes(
        self, cov: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _world(tmp_path, _VALID)
        code = cov.main(
            [
                "OLD-1",
                "--features-root",
                str(tmp_path / "docs/roadmap/features"),
                "--tests-root",
                str(tmp_path / "tests"),
            ]
        )
        out = capsys.readouterr().out
        assert "superseded by NEW-1 FR-1 [agreed 2026-11-13]" in out
        assert "NO TEST" not in out
        assert code == 0

    def test_without_the_tag_the_story_blocks(
        self, cov: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _world(tmp_path, "supersedes `OLD-1` FR-2 with FR-1")
        code = cov.main(
            [
                "OLD-1",
                "--features-root",
                str(tmp_path / "docs/roadmap/features"),
                "--tests-root",
                str(tmp_path / "tests"),
            ]
        )
        out = capsys.readouterr().out
        assert code == 1
        assert "approval tag" in out
        assert "superseded by" not in out


@pytest.fixture
def swept(sweep: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(sweep, "FEATURES", tmp_path / "docs" / "roadmap" / "features")
    monkeypatch.setattr(sweep, "REPO_ROOT", tmp_path)
    roadmap = tmp_path / "roadmap.md"
    roadmap.write_text("`✅` **OLD-1: the old story**\n", encoding="utf-8")
    monkeypatch.setattr(sweep, "ROADMAP", roadmap)
    monkeypatch.setattr(sweep, "BASELINE", tmp_path / "baseline.json")
    (tmp_path / "baseline.json").write_text('{"uncited_frs": 0}\n', encoding="utf-8")
    return tmp_path


class TestSweep:
    def test_a_superseded_fr_is_not_counted_and_is_listed(
        self, sweep: ModuleType, swept: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _world(swept, _VALID)
        assert sweep.main([]) == 0
        assert "1 superseded" in capsys.readouterr().out
        assert sweep.main(["--list"]) == 0
        assert "OLD-1 FR-2 superseded by NEW-1 FR-1" in capsys.readouterr().out

    def test_without_the_marker_the_fr_is_uncited(
        self, sweep: ModuleType, swept: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _world(swept, "no marker here")
        assert sweep.main([]) == 1

    def test_a_marker_without_its_tag_fails_the_sweep(
        self, sweep: ModuleType, swept: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _world(swept, "supersedes `OLD-1` FR-2 with FR-1")
        assert sweep.main([]) == 1
        assert "approval tag" in capsys.readouterr().out
