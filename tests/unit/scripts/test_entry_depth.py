# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""R-DEPTH: a registry line that runs long is content sitting at the wrong depth. `TECH-017`.

`R-LENGTH` capped `master_story_roadmap.md` entries at 200 characters and worked — 1.6% of that
file exceeds it, max 363. Its rationale was *"detail lives in the topic doc and the design"*, and
nothing then checked the topic doc. Measured 2026-08-13: **33.5% of topic-doc lines exceed 200,
the longest is 5624 characters**, and all ten worst lines in the whole roadmap tree are `TECH`
entries.

The remedy is **redistribution, never deletion**. A 5624-character topic entry holds design-doc
content — measurements, approach tables, out-of-scope lists — which belongs in
`<ID>_design.md`; the topic entry keeps the summary. Where content is already at the right depth,
the remedy is simply wrapping, which markdown renders identically.

Ratcheted per file rather than per line, because line numbers shift under every edit and a
baseline keyed on them would be re-frozen until nobody read it.
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


def _prose(length: int) -> str:
    """Realistic wrappable text of exactly `length` characters.

    Not `"x" * length`: a single unbroken run is what the unbreakable-token guard is FOR, so a
    synthetic line built that way is excluded by the rule and tests nothing. Caught by the guard
    firing on the fixtures themselves.
    """
    return (("word " * (length // 5 + 2))[:length]).strip().ljust(length, "!")


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "_entry_depth.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("_entry_depth", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_entry_depth"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ed() -> ModuleType:
    return _load()


class TestCensus:
    def test_a_short_file_has_no_violations(self, ed: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("# Title\n\nA short line.\n", encoding="utf-8")

        assert ed.census(tmp_path) == {}

    def test_a_long_line_is_counted(self, ed: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text(_prose(250) + "\n", encoding="utf-8")

        assert ed.census(tmp_path) == {"a.md": 1}

    def test_the_limit_is_inclusive(self, ed: ModuleType, tmp_path: Path) -> None:
        """Exactly at the limit passes; one over does not — pinned so the boundary cannot drift."""
        (tmp_path / "a.md").write_text(_prose(ed.MAX_LINE) + "\n", encoding="utf-8")
        (tmp_path / "b.md").write_text(_prose(ed.MAX_LINE + 1) + "\n", encoding="utf-8")

        assert ed.census(tmp_path) == {"b.md": 1}

    def test_a_long_url_is_not_counted(self, ed: ModuleType, tmp_path: Path) -> None:
        """An unbreakable token cannot be wrapped or redistributed, so flagging it teaches nothing."""
        (tmp_path / "a.md").write_text(f"See <https://example.com/{'q' * 260}>\n", encoding="utf-8")

        assert ed.census(tmp_path) == {}

    def test_a_markdown_table_row_is_not_counted(self, ed: ModuleType, tmp_path: Path) -> None:
        """A table row has no legal wrap point — a newline ends the row.

        Found by the rule firing on five rows moved into `TECH-035`'s build record during the very
        first redistribution it was written to enable. Flagging them left only bad options: destroy
        the table, or split a cell across rows that no longer align.
        """
        row = "| " + _prose(240) + " |"
        (tmp_path / "a.md").write_text(row + "\n", encoding="utf-8")

        assert ed.census(tmp_path) == {}

    def test_prose_that_merely_mentions_a_pipe_is_still_counted(
        self, ed: ModuleType, tmp_path: Path
    ) -> None:
        """The exemption is for rows, not for any line containing a pipe — otherwise it is a hole."""
        (tmp_path / "a.md").write_text(f"{_prose(240)} | and more\n", encoding="utf-8")

        assert ed.census(tmp_path) == {"a.md": 1}

    def test_counts_are_per_file_not_per_line(self, ed: ModuleType, tmp_path: Path) -> None:
        """Line numbers shift under every edit; a baseline keyed on them would never hold."""
        (tmp_path / "a.md").write_text((_prose(250) + "\n") * 3, encoding="utf-8")

        assert ed.census(tmp_path) == {"a.md": 3}


class TestRegressions:
    def test_a_new_offender_is_a_regression(self, ed: ModuleType) -> None:
        assert ed.regressions({"a.md": 1}, {}) == [("a.md", 0, 1)]

    def test_a_growing_file_is_a_regression(self, ed: ModuleType) -> None:
        assert ed.regressions({"a.md": 4}, {"a.md": 2}) == [("a.md", 2, 4)]

    def test_a_shrinking_file_is_never_a_regression(self, ed: ModuleType) -> None:
        """The count may fall freely — that is the direction the ratchet exists to allow."""
        assert ed.regressions({"a.md": 1}, {"a.md": 9}) == []

    def test_a_cleared_file_is_never_a_regression(self, ed: ModuleType) -> None:
        assert ed.regressions({}, {"a.md": 9}) == []


class TestMain:
    def test_the_repo_is_at_its_frozen_baseline(self, ed: ModuleType) -> None:
        assert ed.main([]) == 0

    def test_the_baseline_has_no_stale_entries(self, ed: ModuleType) -> None:
        """A file that is gone, or already clean, must not sit in the baseline claiming debt."""
        live = ed.census(REPO_ROOT / ed.TREE)
        stale = sorted(set(ed.load_baseline()) - set(live))

        assert stale == [], f"baseline names files with no violations: {stale}"


class TestTheOrphanCheckerIsDeletedWhenDone:
    """`check_entry_orphans.py` is scaffolding for `TECH-044` and must not outlive it.

    It exists to make the redistribution safe: before a topic entry is shortened, it names the
    facts that appear nowhere deeper, so they are moved rather than dropped. When the R-DEPTH
    backlog reaches zero there is nothing left to redistribute and the tool has no job.

    A promise in a docstring would not survive the session that made it — this repo has watched a
    `pytest.skip` guard survive its own written-down lesson by eighteen days. So the deletion is a
    failing test instead: the moment the baseline empties, the suite demands the file go.
    """

    CHECKER = REPO_ROOT / "scripts" / "check_entry_orphans.py"

    def test_the_checker_exists_exactly_while_the_backlog_does(self, ed: ModuleType) -> None:
        """One assertion, failing in BOTH directions — deleted too early, or kept too long.

        First written as two `pytest.skip`-guarded tests, which `R8` rejected on sight: a skip
        conditioned on repo state turns a defect into a green run, and this file's own rule says so.
        The equality is simpler than the pair it replaced and cannot be half-satisfied.
        """
        backlog = bool(ed.load_baseline())

        assert self.CHECKER.is_file() == backlog, (
            "check_entry_orphans.py is gone while the R-DEPTH backlog is not empty — "
            "redistribution still needs its safety net; restore it or finish TECH-044."
            if backlog
            else "The R-DEPTH backlog is empty, so TECH-044 is finished and "
            "scripts/check_entry_orphans.py has no remaining job. Delete it, drop it from "
            "UNGATED_CHECKERS in test_quality_runner.py, and delete this test class."
        )
