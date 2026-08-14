# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.
# fr-coverage: fixture-data

"""Change the code so a claim's behaviour no longer holds, then see whether anything objects.

`TECH-017` ran six of these by hand and four caught vacuous assertions in the audit's own work — a
guard that passed with a bypass planted, a credential check that passed un-isolated, a `parents[4]`
root that globbed a directory which does not exist. Doing it by hand does not scale and does not
leave a citable record, so this wires it.

The measurement it produces is the one a citation cannot: **`sw check --lineage` orphan detection,
neutralised, is caught by exactly one test out of 6829** — and that test failed at `COLUMNS=80`
until 2026-08-14, so the feature was unprotected on any 80-column CI.

> [!IMPORTANT]
> **The isolation self-check is the point, not a nicety.** A mutation runner that silently tests the
> *unmutated* tree reports every mutant as killed and is worse than nothing. `_verify_isolated`
> makes the runner prove which tree it imported before any verdict is believed — `TECH-032`: a check
> that cannot find its subject must say so, not pass.
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


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "_mutate.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("_mutate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_mutate"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mut() -> ModuleType:
    return _load()


class TestApplyMutation:
    """`apply_mutation` — an exact, unambiguous edit or a loud refusal."""

    def test_a_unique_anchor_is_replaced(self, mut: ModuleType, tmp_path: Path) -> None:
        target = tmp_path / "m.py"
        target.write_text("a = 1\nb = 2\n", encoding="utf-8")
        mut.apply_mutation(target, "b = 2", "b = 99")
        assert target.read_text(encoding="utf-8") == "a = 1\nb = 99\n"

    def test_a_missing_anchor_raises(self, mut: ModuleType, tmp_path: Path) -> None:
        target = tmp_path / "m.py"
        target.write_text("a = 1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="not found"):
            mut.apply_mutation(target, "b = 2", "b = 99")

    def test_an_ambiguous_anchor_raises(self, mut: ModuleType, tmp_path: Path) -> None:
        """Two matches means the runner cannot say which line it mutated — refuse, do not guess."""
        target = tmp_path / "m.py"
        target.write_text("x = 0\nx = 0\n", encoding="utf-8")
        with pytest.raises(ValueError, match="2 times"):
            mut.apply_mutation(target, "x = 0", "x = 1")

    def test_a_no_op_edit_raises(self, mut: ModuleType, tmp_path: Path) -> None:
        """Replacing a string with itself mutates nothing and would report a false SURVIVED."""
        target = tmp_path / "m.py"
        target.write_text("a = 1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="identical"):
            mut.apply_mutation(target, "a = 1", "a = 1")


class TestKillers:
    """`killers` — which tests objected to the change."""

    def test_it_collects_failed_test_ids(self, mut: ModuleType) -> None:
        out = (
            "FAILED tests/unit/a.py::test_one - AssertionError\n"
            "FAILED tests/e2e/b.py::TestX::test_two\n"
            "1 failed, 3 passed\n"
        )
        assert mut.killers(out) == ["tests/e2e/b.py::TestX::test_two", "tests/unit/a.py::test_one"]

    def test_a_green_run_has_no_killers(self, mut: ModuleType) -> None:
        assert mut.killers("6829 passed, 11 skipped\n") == []

    def test_a_collection_error_is_not_a_kill(self, mut: ModuleType) -> None:
        """A syntactically broken mutant makes every test error — that is a bad mutant, not proof.

        Reporting it as `killed` would let a nonsense edit masquerade as coverage.
        """
        out = "ERROR tests/unit/a.py - SyntaxError: invalid syntax\n1 error\n"
        assert mut.killers(out) == []
        assert mut.is_broken(out) is True


class TestVerdict:
    """`verdict` — the one word the audit cites."""

    def test_no_killers_means_survived(self, mut: ModuleType) -> None:
        assert mut.verdict([]) == "SURVIVED"

    def test_any_killer_means_killed(self, mut: ModuleType) -> None:
        assert mut.verdict(["tests/unit/a.py::test_one"]) == "KILLED"


class TestVerifyIsolated:
    """`_verify_isolated` — the runner must prove which tree it imported."""

    def test_a_path_inside_the_sandbox_passes(self, mut: ModuleType, tmp_path: Path) -> None:
        mut._verify_isolated(str(tmp_path / "src" / "specweaver" / "__init__.py"), tmp_path)

    def test_a_path_in_the_real_repo_raises(self, mut: ModuleType, tmp_path: Path) -> None:
        """The failure this exists for: the sandbox is built, and the REAL tree is what runs."""
        with pytest.raises(RuntimeError, match="not isolated"):
            mut._verify_isolated(str(REPO_ROOT / "src" / "specweaver" / "__init__.py"), tmp_path)
