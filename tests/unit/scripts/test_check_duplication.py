# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the duplication guard (`scripts/check_duplication.py`).

`TECH-037`. The detector is `jscpd`; what this repo adds is a ratchet over its JSON. The design
question the tests pin is the KEY: jscpd reports line ranges, which move on every edit, so a
baseline keyed on them would report a false regression for any change above a clone. The key is
therefore the duplicated TEXT plus the file pair.

`scripts/` is not an importable package, so the module is loaded by path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]


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
def cd() -> ModuleType:
    return _load("check_duplication")


def _dup(first: str, second: str, fragment: str, *, lines: int = 6, start: int = 1) -> dict:
    return {
        "format": "python",
        "lines": lines,
        "tokens": 90,
        "fragment": fragment,
        "firstFile": {"name": first, "start": str(start), "end": str(start + lines)},
        "secondFile": {"name": second, "start": "40", "end": str(40 + lines)},
    }


FRAGMENT = "def f(self):\n    return self._x\n"


class TestCloneKey:
    def test_the_same_clone_keys_the_same(self, cd: ModuleType) -> None:
        a = _dup("a.py", "b.py", FRAGMENT, start=1)
        b = _dup("a.py", "b.py", FRAGMENT, start=1)

        assert cd.clone_key(a) == cd.clone_key(b)

    def test_moving_a_clone_down_its_file_does_not_change_the_key(self, cd: ModuleType) -> None:
        """The property a line-range key cannot have, and the reason for this design.

        Inserting anything above a clone shifts its reported line numbers. Keyed on lines, every
        such edit reports a false regression; the ratchet would be re-frozen until nobody read it.
        """
        before = _dup("a.py", "b.py", FRAGMENT, start=1)
        after = _dup("a.py", "b.py", FRAGMENT, start=97)

        assert cd.clone_key(before) == cd.clone_key(after)

    def test_reindenting_a_clone_does_not_change_the_key(self, cd: ModuleType) -> None:
        """Leading whitespace is stripped: moving code into a method must not read as new."""
        plain = _dup("a.py", "b.py", "def f():\n    return 1\n")
        indented = _dup("a.py", "b.py", "    def f():\n        return 1\n")

        assert cd.clone_key(plain) == cd.clone_key(indented)

    def test_the_file_pair_order_does_not_matter(self, cd: ModuleType) -> None:
        """jscpd may report either file first; the same clone must not key two ways."""
        one = _dup("a.py", "b.py", FRAGMENT)
        other = _dup("b.py", "a.py", FRAGMENT)

        assert cd.clone_key(one) == cd.clone_key(other)

    def test_different_text_keys_differently(self, cd: ModuleType) -> None:
        assert cd.clone_key(_dup("a.py", "b.py", FRAGMENT)) != cd.clone_key(
            _dup("a.py", "b.py", "def g():\n    return 2\n")
        )

    def test_the_same_text_in_a_different_file_pair_keys_differently(self, cd: ModuleType) -> None:
        """A third copy is a NEW clone, even though its text already appears in the baseline."""
        assert cd.clone_key(_dup("a.py", "b.py", FRAGMENT)) != cd.clone_key(
            _dup("a.py", "c.py", FRAGMENT)
        )


class TestNewClones:
    def test_an_unchanged_report_has_nothing_new(self, cd: ModuleType) -> None:
        current = cd.clones_from([_dup("a.py", "b.py", FRAGMENT)])

        assert cd.new_clones(current, dict(current)) == []

    def test_a_planted_clone_is_reported(self, cd: ModuleType) -> None:
        frozen = cd.clones_from([_dup("a.py", "b.py", FRAGMENT)])
        current = cd.clones_from([_dup("a.py", "b.py", FRAGMENT), _dup("a.py", "c.py", FRAGMENT)])

        assert len(cd.new_clones(current, frozen)) == 1

    def test_a_removed_clone_is_not_a_regression(self, cd: ModuleType) -> None:
        """Deleting duplication must never block a commit — only adding it does."""
        frozen = cd.clones_from([_dup("a.py", "b.py", FRAGMENT), _dup("a.py", "c.py", FRAGMENT)])
        current = cd.clones_from([_dup("a.py", "b.py", FRAGMENT)])

        assert cd.new_clones(current, frozen) == []


class TestMain:
    def test_an_unavailable_detector_is_an_error_not_a_pass(
        self, cd: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`TECH-037`'s whole premise: a check that cannot run must not look like one that passed.

        `quality.py` already grades a missing script as MISSING, which counts as failed. This
        matches that, rather than inventing a quieter third state.
        """
        baseline = tmp_path / "duplication.json"
        baseline.write_text("{}\n", encoding="utf-8")

        exit_code = cd.main(
            ["--baseline", str(baseline), "--jscpd", str(tmp_path / "does-not-exist")]
        )

        assert exit_code != 0
        assert "could not run" in capsys.readouterr().out.lower()

    def test_a_missing_baseline_is_an_error_not_a_pass(
        self, cd: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An absent baseline means nothing is frozen, so every clone would read as accepted."""
        report = tmp_path / "jscpd-report.json"
        report.write_text(
            json.dumps({"duplicates": [_dup("a.py", "b.py", FRAGMENT)]}), encoding="utf-8"
        )

        exit_code = cd.main(["--baseline", str(tmp_path / "nope.json"), "--report", str(report)])

        assert exit_code != 0
        assert "baseline" in capsys.readouterr().out.lower()

    def test_an_unreadable_report_is_an_error_not_a_pass(
        self, cd: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A report that cannot be parsed measured nothing, so it must not read as clean."""
        report = tmp_path / "jscpd-report.json"
        report.write_text("not json", encoding="utf-8")
        baseline = tmp_path / "duplication.json"
        baseline.write_text("{}\n", encoding="utf-8")

        exit_code = cd.main(["--baseline", str(baseline), "--report", str(report)])

        assert exit_code != 0
        assert "could not run" in capsys.readouterr().out.lower()


class TestLoadReport:
    def test_a_report_is_read_into_keyed_clones(self, cd: ModuleType, tmp_path: Path) -> None:
        report = tmp_path / "jscpd-report.json"
        report.write_text(
            json.dumps({"duplicates": [_dup("a.py", "b.py", FRAGMENT)], "statistics": {}}),
            encoding="utf-8",
        )

        clones = cd.load_report(report)

        assert len(clones) == 1
        assert next(iter(clones.values()))["lines"] == 6
