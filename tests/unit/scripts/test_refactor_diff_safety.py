# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the refactor diff-safety rule (`scripts/_refactor_diff_safety.py`).

The rule decides whether a diff that touches a test file is a legitimate refactor (an import path
moved, an identifier was renamed) or a behaviour change wearing a refactor's label. Getting it
wrong in the permissive direction lets a bent test through under the one label whose entire claim
is that behaviour did not move.

Split out of `test_tests_runner.py` (2026-08-08) so each file mirrors one script, and so neither
sits on the file-size ceiling.

`scripts/` is not an importable package, so the module is loaded by path.
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


def _load(filename: str, register_as: str) -> ModuleType:
    """Load a script by path under a DISTINCT module name.

    A script must not be registered in `sys.modules` under a key that belongs to the test package
    itself; shadowing it breaks collection in a way that looks like a failure in whatever ran next.
    """
    path = REPO_ROOT / "scripts" / filename
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(register_as, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[register_as] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rds() -> ModuleType:
    return _load("_refactor_diff_safety.py", "sw_refactor_diff_safety")


class TestLogicalLineGroups:
    """`_logical_line_groups`: bracket-depth splitting of a hunk-side into matchable units —
    coarse enough to keep a formatter's multi-line reflow together, fine enough to keep an
    import-sorter's bundled-but-independent relocations apart."""

    def test_balanced_lines_are_each_their_own_group(self, rds: ModuleType) -> None:
        lines = ["import a", "import b"]

        assert rds._logical_line_groups(lines) == [["import a"], ["import b"]]

    def test_an_open_bracket_merges_with_the_lines_that_close_it(self, rds: ModuleType) -> None:
        lines = ["foo(", "    bar,", ")"]

        assert rds._logical_line_groups(lines) == [["foo(", "    bar,", ")"]]

    def test_the_real_bug_this_pins_bundled_independent_relocations_stay_separate(
        self, rds: ModuleType
    ) -> None:
        """The exact shape ruff's import sorter produced in tests/unit/interfaces/api/test_ui.py:
        one hunk's added side held TWO unrelated import lines (one relocation, one reordering) —
        each balanced on its own, so each must be its own group, not one joined blob."""
        lines = [
            "    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database",
            "    from specweaver.core.config.database import Database",
        ]

        groups = rds._logical_line_groups(lines)

        assert len(groups) == 2

    def test_a_line_with_balanced_brackets_on_its_own_does_not_merge_with_its_neighbor(
        self, rds: ModuleType
    ) -> None:
        """A single physical line that opens AND closes its own brackets (e.g. a function call
        with no line-wrap) must not accidentally swallow the next unrelated line."""
        lines = ["extra_new_line()", "import a"]

        assert rds._logical_line_groups(lines) == [["extra_new_line()"], ["import a"]]

    def test_empty_input_yields_no_groups(self, rds: ModuleType) -> None:
        assert rds._logical_line_groups([]) == []

    def test_boundary_unbalanced_trailing_close_never_goes_negative_forever(
        self, rds: ModuleType
    ) -> None:
        """A stray closing bracket (depth would go negative) still closes and resets — it must
        not poison the running depth count for every subsequent line in the hunk."""
        lines = [")", "import a"]

        assert rds._logical_line_groups(lines) == [[")"], ["import a"]]


class TestParseHunks:
    """`_parse_hunks` turns `git diff -U0` text into (removed, added) line-list pairs per hunk."""

    def test_single_line_substitution(self, rds: ModuleType) -> None:
        diff_text = (
            "diff --git a/x.py b/x.py\n"
            "--- a/x.py\n"
            "+++ b/x.py\n"
            "@@ -17 +17 @@ def f():\n"
            "-    from a.b import c\n"
            "+    from a.b.d import c\n"
        )

        hunks = rds._parse_hunks(diff_text)

        assert hunks == [(["    from a.b import c"], ["    from a.b.d import c"])]

    def test_multiple_hunks_stay_separate(self, rds: ModuleType) -> None:
        diff_text = "@@ -1 +1 @@\n-old1\n+new1\n@@ -5 +5 @@\n-old2\n+new2\n"

        assert rds._parse_hunks(diff_text) == [(["old1"], ["new1"]), (["old2"], ["new2"])]

    def test_empty_diff_yields_no_hunks(self, rds: ModuleType) -> None:
        assert rds._parse_hunks("") == []

    def test_file_header_lines_are_not_mistaken_for_content(self, rds: ModuleType) -> None:
        """`---`/`+++` are the file-identity header, not a removed/added blank line."""
        diff_text = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new\n"

        assert rds._parse_hunks(diff_text) == [(["old"], ["new"])]


class TestIsSafeHunk:
    """`_is_safe_hunk`: True if the hunk is either (a) a 1:1 line-for-line pairing that differs
    solely by dotted-path-shaped tokens, or (b) a pure addition (nothing removed). Both are
    provably incapable of "bending an existing assertion to hide a bug" — (a) never changes
    anything but where a module lives, (b) never touches an existing line at all, only adds new
    ones. Extending an existing test file with new coverage is the complement of weakening it, not
    a variant of the same risk."""

    def test_pure_import_path_relocation_is_path_only(self, rds: ModuleType) -> None:
        removed = ["    from specweaver.core.config.db_bootstrap import get_db"]
        added = ["    from specweaver.core.config.bootstrap.db_bootstrap import get_db"]

        assert rds._is_safe_hunk(removed, added) is True

    def test_monkeypatch_string_target_is_path_only(self, rds: ModuleType) -> None:
        removed = ['monkeypatch.setattr("specweaver.core.config.db_bootstrap.get_db", f)']
        added = ['monkeypatch.setattr("specweaver.core.config.bootstrap.db_bootstrap.get_db", f)']

        assert rds._is_safe_hunk(removed, added) is True

    def test_boundary_an_assertion_change_alongside_a_path_change_is_not_path_only(
        self, rds: ModuleType
    ) -> None:
        """The exact case this check must still catch: a real behaviour change riding along
        with a legitimate-looking import fix."""
        removed = ["    from a.b import c", "    assert result == 5"]
        added = ["    from a.b.d import c", "    assert result == 3"]

        assert rds._is_safe_hunk(removed, added) is False

    def test_a_path_substitution_plus_an_unrelated_new_line_is_safe(self, rds: ModuleType) -> None:
        """Design decision, made explicit: under logical-group matching (not whole-hunk-blob
        matching), `extra_new_line()` is its OWN group — a balanced, bracket-complete statement,
        not a continuation of the import line. It has no removed counterpart, so it's just a pure
        addition (safe by the same logic as `test_a_pure_addition_is_safe`), sitting next to an
        independently-safe path substitution. Mismatched line COUNT alone no longer means unsafe —
        only an unmatched REMOVED group does (see the assertion-change test above, which still
        blocks because "5" has no home in the added side, not because of a raw count mismatch)."""
        removed = ["    from a.b import c"]
        added = ["    from a.b.d import c", "    extra_new_line()"]

        assert rds._is_safe_hunk(removed, added) is True

    def test_a_line_wrapped_by_ruff_format_after_a_path_substitution_is_still_safe(
        self, rds: ModuleType
    ) -> None:
        """The real bug this test pins: `ruff format` reflows a long `monkeypatch.setattr(...)`
        call from 1 line into 3 once the substituted path makes it exceed the line-length limit.
        Mismatched line COUNT (1 removed vs 3 added) must not be confused with mismatched
        CONTENT — only the whitespace changed, so this must still be safe."""
        removed = [
            '    monkeypatch.setattr("specweaver.core.config.db_bootstrap.config_db_path", lambda: test_db_path)'
        ]
        added = [
            "    monkeypatch.setattr(",
            '        "specweaver.core.config.bootstrap.db_bootstrap.config_db_path", lambda: test_db_path',
            "    )",
        ]

        assert rds._is_safe_hunk(removed, added) is True

    def test_a_reflow_that_adds_black_style_trailing_comma_is_still_safe(
        self, rds: ModuleType
    ) -> None:
        """The real bug this test pins, from tests/unit/core/flow/interfaces/test_flow_cli_pipelines.py:
        `ruff format` reflowing a `patch(...)` call onto multiple lines also adds a Black-style
        trailing comma before the closing paren that the single-line version never had
        (`sentinel)` -> `sentinel,\\n)`). That comma is syntactically insignificant — it must not
        make an otherwise-identical reflow register as a content change."""
        removed = [
            '            patch("specweaver.core.config.settings_loader.load_settings", return_value=sentinel),'
        ]
        added = [
            "            patch(",
            '                "specweaver.core.config.bootstrap.settings_loader.load_settings",',
            "                return_value=sentinel,",
            "            ),",
        ]

        assert rds._is_safe_hunk(removed, added) is True

    def test_a_multi_import_reflow_gaining_required_wrapping_parens_is_still_safe(
        self, rds: ModuleType
    ) -> None:
        """The real bug this test pins, from tests/unit/core/config/test_settings_db.py: Python
        allows `from x import a, b` unwrapped on one line, but a multi-line reflow of the SAME
        import REQUIRES wrapping parens (`from x import (\\n    a,\\n    b,\\n)`) that the
        single-line form never had and never needs. The parens exist only because of the line
        wrap, not because the imported names changed."""
        removed = [
            "        from specweaver.core.config.settings_loader import load_settings, migrate_legacy_config"
        ]
        added = [
            "        from specweaver.core.config.bootstrap.settings_loader import (",
            "            load_settings,",
            "            migrate_legacy_config,",
            "        )",
        ]

        assert rds._is_safe_hunk(removed, added) is True

    def test_boundary_empty_hunk_is_trivially_path_only(self, rds: ModuleType) -> None:
        assert rds._is_safe_hunk([], []) is True

    def test_a_pure_addition_is_safe(self, rds: ModuleType) -> None:
        """Extending an existing test file with a brand-new test function: nothing removed,
        so nothing existing could have been weakened — this is the case the user explicitly
        flagged as wrongly blocked by the original any-diff check."""
        removed: list[str] = []
        added = ["def test_new_case() -> None:", "    assert something_new() is True"]

        assert rds._is_safe_hunk(removed, added) is True

    def test_boundary_a_pure_deletion_is_not_automatically_safe(self, rds: ModuleType) -> None:
        """The mirror image of a pure addition is NOT automatically safe — deleting an existing
        assertion (removed non-empty, added empty) is exactly "bending a test to hide a bug"."""
        removed = ["    assert result == 5"]
        added: list[str] = []

        assert rds._is_safe_hunk(removed, added) is False

    def test_hostile_no_code_execution_on_diff_content(self, rds: ModuleType) -> None:
        """Diff lines are only ever text-compared, never eval'd/exec'd — a line containing
        exploit-shaped text is just a string that fails to match, not a code-execution vector.
        Justifies the 'hostile input' test-matrix bucket: there is no interpreter in this path."""
        removed = ["    x = 1"]
        added = ["    x = __import__('os').system('rm -rf /')"]

        assert rds._is_safe_hunk(removed, added) is False


class TestIsSafeFileDiff:
    """`_is_safe_file_diff`: judges a WHOLE file's diff (all hunks together), not one hunk in
    isolation — needed because a formatter/import-sorter can split a single line-move into a
    separate addition hunk and deletion hunk elsewhere in the same file."""

    def test_a_relocated_import_split_across_two_hunks_is_still_safe(self, rds: ModuleType) -> None:
        """The real bug this test pins: ruff's import sorter deleted an import at its old
        alphabetical position and re-added it, differently-pathed, at a NEW position — two
        separate hunks, neither of which is individually a 1:1 substitution or a self-contained
        pure addition/deletion. Judged in isolation, the deletion hunk looks like an unmatched
        loss and wrongly blocks; judged as a whole file, the addition elsewhere covers it."""
        hunks = [
            (
                [],
                [
                    "    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database"
                ],
            ),
            (["    from specweaver.core.config.db_bootstrap import bootstrap_database"], []),
        ]

        assert rds._is_safe_file_diff(hunks) is True

    def test_boundary_an_unmatched_deletion_elsewhere_in_the_file_is_not_safe(
        self, rds: ModuleType
    ) -> None:
        """The case relocation-matching must NOT paper over: a real assertion deleted from one
        hunk, with an unrelated addition elsewhere that happens to not match it."""
        hunks = [
            ([], ["    def test_new_case(): pass"]),
            (["    assert result == 5"], []),
        ]

        assert rds._is_safe_file_diff(hunks) is False

    def test_a_normal_single_safe_hunk_still_passes_at_file_level(self, rds: ModuleType) -> None:
        hunks = [(["    from a.b import c"], ["    from a.b.d import c"])]

        assert rds._is_safe_file_diff(hunks) is True

    def test_no_hunks_is_trivially_safe(self, rds: ModuleType) -> None:
        assert rds._is_safe_file_diff([]) is True

    def test_duplicate_signatures_must_each_be_matched_once(self, rds: ModuleType) -> None:
        """Two identical removed lines need TWO matching added lines, not one covering both —
        this is exactly what a multiset (not a plain set) comparison guarantees."""
        hunks = [
            (["    assert x == 1"], []),
            (["    assert x == 1"], []),
            ([], ["    assert x == 1"]),
        ]

        assert rds._is_safe_file_diff(hunks) is False


class TestSingleTokenRenameClosure:
    """A further safe pattern beyond exact-match and path-relocation: a single, file-wide-
    consistent literal-token substitution (e.g. a SQL table rename `nodes` -> `graph_nodes`
    embedded in string literals, which the dotted-path stripper does not touch since it isn't a
    dotted module path). Discovered as a real, non-hypothetical blocker while planning TECH-005
    SF-3: every mechanical test-file update for that ticket's table renames is exactly this shape,
    and `--kind refactor` would otherwise hard-block a legitimate, Red/Blue-reviewed rename.

    The load-bearing guarantee is CLOSURE: the inferred (old, new) pair must explain every
    remaining unmatched line with nothing left over, and inference itself must find exactly ONE
    consistent pair or refuse — this is what stops a genuine bug-hiding edit (which essentially
    never reduces to one clean global word swap) from being laundered as a rename.
    """

    def test_a_consistent_table_rename_across_multiple_lines_is_safe(self, rds: ModuleType) -> None:
        hunks = [
            (
                ["            SELECT id FROM nodes WHERE is_active = 1"],
                ["            SELECT id FROM graph_nodes WHERE is_active = 1"],
            ),
            (
                ['cursor.execute("INSERT INTO nodes (id) VALUES (?)", (1,))'],
                ['cursor.execute("INSERT INTO graph_nodes (id) VALUES (?)", (1,))'],
            ),
            (
                ['assert "nodes" in tables'],
                ['assert "graph_nodes" in tables'],
            ),
        ]

        assert rds._is_safe_file_diff(hunks) is True

    def test_boundary_a_rename_alongside_an_unrelated_pure_addition_is_still_safe(
        self, rds: ModuleType
    ) -> None:
        hunks = [
            (["FROM nodes"], ["FROM graph_nodes"]),
            ([], ["def test_new_case(): pass"]),
        ]

        assert rds._is_safe_file_diff(hunks) is True

    def test_graceful_degradation_a_rename_that_only_closes_part_of_the_gap_is_not_safe(
        self, rds: ModuleType
    ) -> None:
        """One line matches the inferred nodes->graph_nodes pair; a second, unrelated removed
        line (`assert count == 5`) has no home under that same substitution and must still block."""
        hunks = [
            (["FROM nodes"], ["FROM graph_nodes"]),
            (["assert count == 5"], []),
        ]

        assert rds._is_safe_file_diff(hunks) is False

    def test_hostile_two_different_substitutions_required_is_not_safe(
        self, rds: ModuleType
    ) -> None:
        """The case that must keep being caught: two independent single-word changes, each
        individually shaped like a clean rename, but NOT explainable by one consistent pair —
        exactly what a bug hidden behind a fake "rename" would look like."""
        hunks = [
            (["FROM nodes"], ["FROM graph_nodes"]),
            (["assert x == 1"], ["assert x == 2"]),
        ]

        assert rds._is_safe_file_diff(hunks) is False

    def test_hostile_ambiguous_inference_with_no_clear_pair_is_not_safe(
        self, rds: ModuleType
    ) -> None:
        """Different token counts on every candidate pairing -- no single-token substitution can
        even be inferred, so this must fall through to the existing (safe default: unsafe) verdict."""
        hunks = [(["assert result == 5 and flag is True"], ["totally different shape entirely"])]

        assert rds._is_safe_file_diff(hunks) is False

    def test_two_simultaneous_consistent_renames_in_the_same_file_are_both_safe(
        self, rds: ModuleType
    ) -> None:
        """The real bug this pins, found running the actual TECH-005 SF-3 gate: a single file
        legitimately needing TWO independent, each-internally-consistent renames at once (`nodes`
        -> `graph_nodes` on most lines, `edges` -> `graph_edges` on one line) was rejected as
        "ambiguous" by an inference that only ever accepted a single global (old, new) pair. A file
        needing several simultaneous identifier renames is exactly TECH-005 SF-3's own shape and
        must be recognized, not just the single-identifier case the earlier, narrower tests here
        happened to use."""
        hunks = [
            (["SELECT id FROM nodes"], ["SELECT id FROM graph_nodes"]),
            (["UPDATE nodes SET x = 1"], ["UPDATE graph_nodes SET x = 1"]),
            (["INSERT INTO edges VALUES (1)"], ["INSERT INTO graph_edges VALUES (1)"]),
        ]

        assert rds._is_safe_file_diff(hunks) is True

    def test_duplicate_lines_needing_the_same_rename_are_still_safe(self, rds: ModuleType) -> None:
        """The real bug this pins, found running the actual TECH-005 SF-3 gate:
        `tests/unit/graph/core/store/test_repository_load.py` has THREE identical
        `INSERT INTO nodes (...)` lines (repeated fixture setup) all renamed to the identical
        `INSERT INTO graph_nodes (...)`. Discovery matched the first removed line against all
        three not-yet-used added candidates, found 3 (not 1) matches, and rejected as "ambiguous"
        even though every match implied the exact same (nodes, graph_nodes) substitution."""
        hunks = [
            (
                ["INSERT INTO nodes (a, b)"],
                ["INSERT INTO graph_nodes (a, b)"],
            ),
            (
                ["INSERT INTO nodes (a, b)"],
                ["INSERT INTO graph_nodes (a, b)"],
            ),
            (
                ["INSERT INTO nodes (a, b)"],
                ["INSERT INTO graph_nodes (a, b)"],
            ),
        ]

        assert rds._is_safe_file_diff(hunks) is True

    def test_a_spurious_cross_rename_candidate_is_resolved_by_already_established_pairs(
        self, rds: ModuleType
    ) -> None:
        """The real bug this pins, found running the actual TECH-005 SF-3 gate against
        `test_repository_flush.py`: with TWO simultaneous renames active (`nodes` ->
        `graph_nodes`, `edges` -> `graph_edges`), the line `SELECT COUNT(*) FROM nodes;` is the
        SAME TOKEN LENGTH as, and differs in exactly one position from, BOTH its true counterpart
        (`FROM graph_nodes;`) AND an unrelated added line from the OTHER rename
        (`FROM graph_edges;` — same sentence shape, different renamed table). A naive per-line
        match sees two equally-plausible candidates implying two DIFFERENT substitutions for
        `nodes` and rejects as ambiguous, even though the correct pairing is unambiguous once the
        two renames from other, less coincidentally-shaped lines are already known."""
        hunks = [
            (["FROM nodes ORDER BY x"], ["FROM graph_nodes ORDER BY x"]),  # resolves nodes first
            (["FROM edges e"], ["FROM graph_edges e"]),  # resolves edges next
            (
                ['cursor.execute("SELECT COUNT(*) FROM nodes;")'],
                ['cursor.execute("SELECT COUNT(*) FROM graph_nodes;")'],
            ),
            (
                ['cursor.execute("SELECT COUNT(*) FROM edges;")'],
                ['cursor.execute("SELECT COUNT(*) FROM graph_edges;")'],
            ),
        ]

        assert rds._is_safe_file_diff(hunks) is True

    def test_hostile_permanently_ambiguous_pair_reaches_the_fixpoint_exhausted_exit(
        self, rds: ModuleType
    ) -> None:
        """Every other hostile test here resolves via the IMMEDIATE `not candidates: return None`
        exit (some removed line runs out of viable candidates outright). This one instead reaches
        the OTHER unsafe exit: the fixpoint loop runs to a stable state where two removed lines
        (`target p`/`target q`) each keep exactly 2 distinct candidate pairs forever (matched
        against `target zz`/`target ww` either way — nothing about them narrows the ambiguity),
        while an unrelated third pair (`nodes`->`graph_nodes`) resolves cleanly first. Only the
        trailing `len(resolved_removed_indices) != len(removed_texts)` check catches this."""
        hunks = [
            (["FROM nodes"], ["FROM graph_nodes"]),
            (["target p"], ["target zz"]),
            (["target q"], ["target ww"]),
        ]

        assert rds._is_safe_file_diff(hunks) is False

    def test_hostile_a_numeric_assertion_change_beside_a_real_rename_is_not_safe(
        self, rds: ModuleType
    ) -> None:
        """The real regression this pins: with digit tokens treated as candidates, `5` -> `3` was
        inferred as "the" rename (the only single-token diff actually compared) and the closure
        check rewrote the weakened assertion to match — laundering exactly the bug this whole gate
        exists to catch. Numeric literals must never be rename candidates, only identifiers."""
        hunks = [
            (["FROM nodes"], ["FROM graph_nodes"]),
            (["    assert result == 5"], ["    assert result == 3"]),
        ]

        assert rds._is_safe_file_diff(hunks) is False
