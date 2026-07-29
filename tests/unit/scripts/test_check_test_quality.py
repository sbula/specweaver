# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the two test-quality guards (2026-07-27).

Both guards exist because a real defect got through: duplicate basenames let a truncated grep hide
a file and stop 5806 tests from collecting, and an `assert len(x) >= 0` kept a story unverified for
the life of its test.

A guard that cannot itself fail is the defect it is meant to catch, so each detector is exercised
against input known to be bad AND input known to be good.

`scripts/` is not an importable package, so the modules are loaded by path.
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
def basenames() -> ModuleType:
    return _load("check_test_basenames")


@pytest.fixture(scope="module")
def useless() -> ModuleType:
    return _load("check_useless_asserts")


def _write(root: Path, rel: str, body: str = "def test_x():\n    assert 1 == 2\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Unique basenames
# ---------------------------------------------------------------------------


class TestBasenameGuard:
    def test_unique_names_pass(self, basenames: ModuleType, tmp_path: Path) -> None:
        _write(tmp_path, "unit/test_alpha.py")
        _write(tmp_path, "integration/test_beta.py")

        assert basenames.main([str(tmp_path)]) == 0

    def test_duplicate_in_different_directories_blocks(
        self, basenames: ModuleType, tmp_path: Path
    ) -> None:
        """The exact shape that broke a refactor: same name, two directories."""
        _write(tmp_path, "unit/core/test_cli_pipelines.py")
        _write(tmp_path, "integration/cli/test_cli_pipelines.py")

        assert basenames.main([str(tmp_path)]) == 1

    def test_duplicates_report_every_path(self, basenames: ModuleType, tmp_path: Path) -> None:
        _write(tmp_path, "a/test_dup.py")
        _write(tmp_path, "b/test_dup.py")
        _write(tmp_path, "c/test_dup.py")

        dupes = basenames.duplicate_basenames(tmp_path)

        assert set(dupes) == {"test_dup.py"}
        assert len(dupes["test_dup.py"]) == 3

    def test_pycache_copies_are_not_duplicates(self, basenames: ModuleType, tmp_path: Path) -> None:
        _write(tmp_path, "unit/test_alpha.py")
        _write(tmp_path, "unit/__pycache__/test_alpha.py")

        assert basenames.main([str(tmp_path)]) == 0

    def test_empty_tree_blocks_rather_than_passing_vacuously(
        self, basenames: ModuleType, tmp_path: Path
    ) -> None:
        """Finding nothing to check is a wrong root, not a clean bill of health."""
        assert basenames.main([str(tmp_path)]) == 1

    def test_missing_root_blocks(self, basenames: ModuleType, tmp_path: Path) -> None:
        assert basenames.main([str(tmp_path / "nope")]) == 1

    def test_the_repo_itself_is_clean(self, basenames: ModuleType) -> None:
        assert basenames.main([str(REPO_ROOT / "tests")]) == 0


# ---------------------------------------------------------------------------
# Assertions that cannot fail
# ---------------------------------------------------------------------------

SYNTHETIC_BAD = """
from unittest.mock import MagicMock

def test_literal():
    assert True

def test_self_compare():
    x = compute()
    assert x == x

def test_len_bound():
    items = build()
    assert len(items) >= 0

def test_len_bound_gt():
    items = build()
    assert len(items) > -1

def test_vacuous_isinstance():
    thing = build()
    assert isinstance(thing, object)

def test_mock_truthiness():
    m = MagicMock()
    do_work(m)
    assert m.was_called
"""

SYNTHETIC_GOOD = """
from unittest.mock import MagicMock

def test_real_equality():
    assert compute() == 42

def test_real_length():
    assert len(build()) == 3

def test_real_isinstance():
    assert isinstance(build(), dict)

def test_mock_call_is_checked():
    m = MagicMock()
    do_work(m)
    m.assert_called_once_with(7)

def test_falsy_literal_is_a_real_failure_not_a_vacuous_pass():
    assert False, "intentionally failing placeholder"
"""


class TestUselessAssertGuard:
    def test_every_bad_pattern_is_caught(self, useless: ModuleType) -> None:
        kinds = {kind for _, kind, _ in useless.scan_source(SYNTHETIC_BAD)}

        assert kinds == {
            "literal",
            "self-comparison",
            "always-true-bound",
            "vacuous-isinstance",
            "mock-truthiness",
        }

    def test_legitimate_assertions_are_not_flagged(self, useless: ModuleType) -> None:
        assert useless.scan_source(SYNTHETIC_GOOD) == []

    def test_bad_tree_blocks(self, useless: ModuleType, tmp_path: Path) -> None:
        _write(tmp_path, "unit/test_bad.py", SYNTHETIC_BAD)

        assert useless.main([str(tmp_path)]) == 1

    def test_good_tree_passes(self, useless: ModuleType, tmp_path: Path) -> None:
        _write(tmp_path, "unit/test_good.py", SYNTHETIC_GOOD)

        assert useless.main([str(tmp_path)]) == 0

    def test_unparseable_file_does_not_abort_the_sweep(
        self, useless: ModuleType, tmp_path: Path
    ) -> None:
        _write(tmp_path, "unit/test_broken.py", "def test_x(:\n")
        _write(tmp_path, "unit/test_bad.py", SYNTHETIC_BAD)

        assert useless.main([str(tmp_path)]) == 1

    def test_the_historical_defect_is_caught(self, useless: ModuleType) -> None:
        """The exact line that hid Story 4's edge-deletion gap."""
        source = "def test_delta():\n    assert len(engine._nx_graph.edges) >= 0\n"

        hits = useless.scan_source(source)

        assert [kind for _, kind, _ in hits] == ["always-true-bound"]

    def test_missing_root_blocks(self, useless: ModuleType, tmp_path: Path) -> None:
        assert useless.main([str(tmp_path / "nope")]) == 1

    def test_the_repo_itself_is_clean(self, useless: ModuleType) -> None:
        assert useless.main([str(REPO_ROOT / "tests")]) == 0
