# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`scripts/readme_counts.py`: the README's test and mutant numbers, measured.

| Bucket | Case |
|---|---|
| Happy | pytest's collect line gives the count; corpora and live mutants are counted |
| Boundary | a marker-filtered line gives the selected count; "no tests collected" is 0 |
| Degradation | a collect line with errors is refused rather than read as a count |
| Hostile | output with no collect line is refused; a retired campaign's mutants are not counted |
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def rc() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "readme_counts", REPO_ROOT / "scripts" / "readme_counts.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["readme_counts"] = module
    spec.loader.exec_module(module)
    return module


class TestCollected:
    @pytest.mark.parametrize(
        ("output", "count"),
        [
            ("tests/x.py::t\n\n11170 tests collected in 5.12s\n", 11170),
            ("1 test collected in 0.1s", 1),
            ("38/11170 tests collected (11132 deselected) in 4.0s", 38),
            ("no tests collected in 0.5s", 0),
            ("no tests collected (5 deselected) in 0.5s", 0),
            ("==== 11170 tests collected in 5.12s ====", 11170),
        ],
    )
    def test_the_collect_line_gives_the_selected_count(
        self, rc: ModuleType, output: str, count: int
    ) -> None:
        assert rc.collected(output) == count

    def test_a_collect_line_with_errors_is_refused(self, rc: ModuleType) -> None:
        with pytest.raises(ValueError, match="error"):
            rc.collected("11170 tests collected, 2 errors in 4s")

    def test_output_without_a_collect_line_is_refused(self, rc: ModuleType) -> None:
        with pytest.raises(ValueError, match="no collect line"):
            rc.collected("ImportError: something broke\n")


class TestMutants:
    def _corpus(self, tmp_path: Path, name: str, campaigns: list[dict[str, object]]) -> Path:
        path = tmp_path / f"{name}_mutants.json"
        path.write_text(json.dumps({"campaigns": campaigns}), encoding="utf-8")
        return path

    def test_live_mutants_are_counted_and_retired_ones_are_not(
        self, rc: ModuleType, tmp_path: Path
    ) -> None:
        a = self._corpus(
            tmp_path,
            "A",
            [{"mutants": [1, 2]}, {"mutants": [3], "retired": {"reason": "descoped"}}],
        )
        b = self._corpus(tmp_path, "B", [{"mutants": [4]}])
        assert rc.mutant_counts([a, b]) == (2, 3)

    def test_no_corpora_is_zero(self, rc: ModuleType) -> None:
        assert rc.mutant_counts([]) == (0, 0)


class TestReport:
    def test_each_tier_is_collected_with_its_marker(self, rc: ModuleType) -> None:
        calls: list[list[str]] = []

        def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "7 tests collected in 1s", "")

        tiers = rc.test_counts(run)
        assert tiers == dict.fromkeys(rc.TIERS, 7)

        def marker(cmd: list[str]) -> str | None:
            flags = [i for i, part in enumerate(cmd) if part == "-m"][1:]
            return cmd[flags[0] + 1] if flags else None

        by_tier = dict(zip(rc.TIERS, calls, strict=True))
        assert marker(by_tier["live"]) == "live"
        assert marker(by_tier["unit"]) == ""
        assert marker(by_tier["default"]) is None
        assert by_tier["default"].count("-m") == 1, "only python -m pytest"


class TestMain:
    def test_main_prints_tiers_and_mutants(
        self, rc: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(rc, "test_counts", lambda run: {"unit": 3, "all": 5})
        monkeypatch.setattr(rc, "mutant_counts", lambda paths: (2, 9))
        assert rc.main() == 0
        assert capsys.readouterr().out == "unit=3 all=5\ncorpora=2 mutants=9\n"

    def test_a_broken_collection_prints_no_number(
        self, rc: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def broken(run: object) -> dict[str, int]:
            raise ValueError("collection had errors: x")

        monkeypatch.setattr(rc, "test_counts", broken)
        assert rc.main() == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "could not count" in captured.err
