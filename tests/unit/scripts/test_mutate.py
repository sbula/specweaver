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

    def test_ansi_coloured_failures_are_still_killers(self, mut: ModuleType) -> None:
        """The defect that made every mutant read SURVIVED, measured 2026-08-15.

        `_run` inherits the environment, and `should_do_markup` honours `FORCE_COLOR` over the
        isatty test — so under any agent shell (Claude Code sets `FORCE_COLOR=3`) pytest wraps the
        verdict word: `\\x1b[31mFAILED\\x1b[0m tests/...`. `^FAILED` cannot match a line starting
        with an escape, every killer went invisible, and the runner reported SURVIVED for a mutant
        that genuinely killed two tests.

        It never fired for a human, because `capture_output=True` makes stdout a pipe and pytest
        drops colour on its own. Every fixture in this class was plain text, so 15 passing tests
        could not reach the failing path — the exact vacuity this tool exists to detect.
        """
        out = (
            "\x1b[31mFAILED\x1b[0m tests/unit/a.py::\x1b[1mtest_one\x1b[0m - assert 0 == 2\n"
            "\x1b[31m===== \x1b[31m\x1b[1m2 failed\x1b[0m, \x1b[32m16 passed\x1b[0m\x1b[31m =====\x1b[0m\n"
        )
        assert mut.is_broken(out) is False
        assert mut.killers(out) == ["tests/unit/a.py::test_one"]

    def test_colour_is_disabled_in_the_sandbox_environment(self, mut: ModuleType) -> None:
        """Belt and braces: strip the escapes AND stop pytest emitting them.

        `PY_COLORS` is the FIRST check in `should_do_markup`, so `"0"` beats an inherited
        `FORCE_COLOR`. Stripping alone would leave the next colour-forcing variable free to break
        it again; disabling alone would leave the parser fragile.
        """
        env = mut.sandbox_env(Path("/tmp/sandbox"))
        assert env["PY_COLORS"] == "0"

    def test_a_test_that_merely_prints_syntaxerror_is_not_broken(self, mut: ModuleType) -> None:
        """The false positive that cost a whole campaign.

        `is_broken` matched the bare word `SyntaxError` anywhere in the output, and some tests
        legitimately print it — a parser suite asserting on an error message, for one. Two real
        `KILLED` results were discarded as BROKEN because of it, which is worse than a miss: it
        turns a measurement into a non-result and looks like a bad anchor.
        """
        out = "tests/unit/parsers/test_x.py::test_reports_syntaxerror PASSED\n6853 passed\n"
        assert mut.is_broken(out) is False
        assert mut.killers(out) == []

    def test_a_captured_log_line_at_error_level_is_not_broken(self, mut: ModuleType) -> None:
        """Third iteration on this detector, and the one that mattered.

        Pytest captures application logs, so a full-suite run is full of lines like
        `ERROR    specweaver.core.flow.engine.runner:runner.py:123 message`. Matching an `ERROR <path>.py` pattern
        caught those and reported every mutant BROKEN — a real KILLED discarded as a bad anchor.
        Only the SUMMARY line can say whether pytest itself errored.
        """
        out = (
            "ERROR    specweaver.core.flow.engine.runner:runner.py:123 handover failed\n"
            "FAILED tests/unit/a.py::test_one\n"
            "===== 1 failed, 6852 passed, 11 skipped in 58.6s =====\n"
        )
        assert mut.is_broken(out) is False
        assert mut.killers(out) == ["tests/unit/a.py::test_one"]

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


class TestProbePath:
    """`_probe_path` — find the import path in probe output that may carry other noise."""

    def test_it_finds_the_path_among_warnings(self, mut: ModuleType, tmp_path: Path) -> None:
        """The bug that cost a campaign: the path is not always the LAST line.

        `prove_isolation` took `lines[-1]`, and a `RuntimeWarning` printed after the path made that
        the warning. The isolation check then raised and every mutant was recorded BROKEN — failing
        closed, which is the right direction, but reporting a bad anchor rather than a runner bug.
        """
        out = f"{tmp_path}\nRuntimeWarning: Enable tracemalloc to get the object allocation traceback\n"
        assert mut._probe_path(out, tmp_path) == str(tmp_path)

    def test_no_path_at_all_raises(self, mut: ModuleType, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="probe"):
            mut._probe_path("RuntimeWarning: something\n", tmp_path)


class TestVerifyIsolated:
    """`_verify_isolated` — the runner must prove which tree it imported."""

    def test_a_path_inside_the_sandbox_passes(self, mut: ModuleType, tmp_path: Path) -> None:
        mut._verify_isolated(str(tmp_path / "src" / "specweaver" / "__init__.py"), tmp_path)

    def test_a_path_in_the_real_repo_raises(self, mut: ModuleType, tmp_path: Path) -> None:
        """The failure this exists for: the sandbox is built, and the REAL tree is what runs."""
        with pytest.raises(RuntimeError, match="not isolated"):
            mut._verify_isolated(str(REPO_ROOT / "src" / "specweaver" / "__init__.py"), tmp_path)
