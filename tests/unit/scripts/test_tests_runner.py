# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the test-tier runner (`scripts/tests.py`).

The dangerous logic here is not the pytest invocation, it is the resolution: story ID -> profile,
DAL -> shift, scope -> paths. Every one of those failing silently produces a GREEN run that tested
less than it claimed, which is worse than a red one.

The DAL direction gets its own class. DAL-A is Mission-Critical and DAL-E is Prototyping, so "most
critical" is the alphabetically lowest letter — `max()` returns E and selects the weakest profile.
That is a one-character mistake with no visible symptom, so it is pinned from several angles.

`scripts/` is not an importable package, so the module is loaded by path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(filename: str, register_as: str) -> ModuleType:
    """Load a script by path under a DISTINCT module name.

    `scripts/tests.py` must not be registered in `sys.modules` as `tests` — that key belongs to
    the test package itself, and shadowing it would break collection in a way that looks like a
    failure in whatever ran next.
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
def tr() -> ModuleType:
    return _load("tests.py", "sw_test_tier_runner")


@pytest.fixture(scope="module")
def rds() -> ModuleType:
    """`_refactor_diff_safety.py` — split out of `tests.py` (2026-08-02) to stay under the
    file-size RED threshold. `_parse_hunks`/`_is_safe_hunk` live here now; `refactor_violations`
    is re-exported from `tests.py` and is still reachable via the `tr` fixture."""
    return _load("_refactor_diff_safety.py", "sw_refactor_diff_safety")


# ---------------------------------------------------------------------------
# DAL direction
# ---------------------------------------------------------------------------


class TestMostCriticalDal:
    def test_a_beats_c(self, tr: ModuleType) -> None:
        assert tr.most_critical(["C", "A"]) == "A"

    def test_b_beats_c(self, tr: ModuleType) -> None:
        """The case the user specified explicitly: DAL-B wins over DAL-C."""
        assert tr.most_critical(["C", "B"]) == "B"

    def test_the_naive_max_answer_is_never_returned(self, tr: ModuleType) -> None:
        """max() would return 'E' here — the weakest profile, silently."""
        assert tr.most_critical(["E", "B", "D"]) == "B"

    def test_a_single_letter_is_itself(self, tr: ModuleType) -> None:
        assert tr.most_critical(["D"]) == "D"

    def test_all_equal_letters_collapse(self, tr: ModuleType) -> None:
        assert tr.most_critical(["C", "C", "C"]) == "C"

    def test_empty_input_is_an_error_not_a_default(self, tr: ModuleType) -> None:
        with pytest.raises(tr.UsageError):
            tr.most_critical([])


# ---------------------------------------------------------------------------
# Story identity
# ---------------------------------------------------------------------------


class TestStoryResolution:
    def test_a_capability_id_takes_its_dal_from_the_prefix(self, tr: ModuleType) -> None:
        story = tr.resolve_story("C-FLOW-12", None, None)

        assert (story.kind, story.dal) == ("capability", "C")

    def test_a_high_assurance_capability_is_dal_b(self, tr: ModuleType) -> None:
        assert tr.resolve_story("B-VAL-06", None, None).dal == "B"

    def test_an_int_story_derives_its_dal_from_what_it_integrates(self, tr: ModuleType) -> None:
        """INT-US-09 integrates D-EXEC-02, E-EXEC-01 and C-EXEC-02 — most critical is C."""
        story = tr.resolve_story("INT-US-09", None, None)

        assert story.kind == "int"
        assert story.dal == "C"

    def test_the_int_dal_derivation_names_its_sources(self, tr: ModuleType) -> None:
        """A derived value nobody can audit is a value nobody will trust."""
        story = tr.resolve_story("INT-US-09", None, None)

        assert "C-EXEC-02" in story.dal_source

    def test_a_base_int_story_ignores_its_sub_story_add_ons(self, tr: ModuleType) -> None:
        """INT-US-09's add-ons are blocked on A-EXEC-01/03 — unbuilt work the base does not integrate.

        Scanning the whole document reads the base as DAL-A and escalates every gate for a story
        that integrates D, E and C capabilities.
        """
        assert tr.resolve_story("INT-US-09", None, None).dal == "C"

    def test_a_sub_story_takes_its_own_scope_not_the_bases(self, tr: ModuleType) -> None:
        assert tr.resolve_story("INT-US-09-SF01", None, None).dal == "B"

    def test_a_sub_story_can_be_more_critical_than_its_base(self, tr: ModuleType) -> None:
        assert tr.resolve_story("INT-US-09-SF03", None, None).dal == "A"

    def test_a_sub_story_can_be_less_critical_than_its_base(self, tr: ModuleType) -> None:
        assert tr.resolve_story("INT-US-09-SF02", None, None).dal == "E"

    def test_a_passing_mention_of_a_sub_story_id_is_not_its_definition(
        self, tr: ModuleType
    ) -> None:
        """The base Status bullet says "container add-on = `INT-US-09-SF01`" — not a definition."""
        story = tr.resolve_story("INT-US-09-SF01", None, None)

        assert "B-EXEC-01" in story.dal_source

    def test_a_tech_ticket_without_a_kind_is_rejected(self, tr: ModuleType) -> None:
        with pytest.raises(tr.UsageError, match="kind"):
            tr.resolve_story("TECH-020", None, None)

    def test_a_tech_ticket_with_a_kind_resolves(self, tr: ModuleType) -> None:
        story = tr.resolve_story("TECH-020", "refactor", None)

        assert (story.kind, story.tech_kind) == ("tech", "refactor")

    def test_an_unknown_kind_is_rejected(self, tr: ModuleType) -> None:
        with pytest.raises(tr.UsageError):
            tr.resolve_story("TECH-020", "rewrite", None)

    def test_an_unrecognised_id_is_rejected_rather_than_defaulted(self, tr: ModuleType) -> None:
        """Defaulting would silently pick a profile — possibly the weak one."""
        with pytest.raises(tr.UsageError):
            tr.resolve_story("BANANA-7", None, None)

    def test_an_explicit_dal_override_wins(self, tr: ModuleType) -> None:
        assert tr.resolve_story("C-FLOW-12", None, "A").dal == "A"


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


class TestProfiles:
    def test_an_int_story_runs_no_unit_tests_at_any_state(self, tr: ModuleType) -> None:
        """The whole point: needing a unit test here means the capability shipped incomplete."""
        story = tr.resolve_story("INT-US-09", None, None)

        for state in tr.STATES:
            assert "unit" not in {s.tier for s in tr.resolve_selections(story, state)}

    def test_an_int_story_runs_e2e_at_the_commit_boundary(self, tr: ModuleType) -> None:
        story = tr.resolve_story("INT-US-09", None, None)

        tiers = {s.tier: s.scope for s in tr.resolve_selections(story, "cb")}

        assert tiers["e2e"] == "domain"

    def test_a_capability_story_does_not_run_e2e_at_the_commit_boundary(
        self, tr: ModuleType
    ) -> None:
        story = tr.resolve_story("C-FLOW-12", None, None)

        assert "e2e" not in {s.tier for s in tr.resolve_selections(story, "cb")}

    def test_a_capability_story_runs_unit_scoped_at_the_commit_boundary(
        self, tr: ModuleType
    ) -> None:
        story = tr.resolve_story("C-FLOW-12", None, None)

        assert tr.resolve_selections(story, "cb") == [tr.Selection("unit", "module")]

    def test_an_audit_ticket_declares_no_tiers(self, tr: ModuleType) -> None:
        story = tr.resolve_story("TECH-017", "audit", None)

        assert tr.resolve_selections(story, "feature") == []

    def test_selections_come_back_in_tier_order(self, tr: ModuleType) -> None:
        story = tr.resolve_story("C-FLOW-12", None, None)

        tiers = [s.tier for s in tr.resolve_selections(story, "feature")]

        assert tiers == ["unit", "integration", "e2e"]


class TestDalModifier:
    def test_dal_b_pulls_tiers_one_state_earlier(self, tr: ModuleType) -> None:
        """Capability integration is `sf` at DAL-C; at DAL-B it must arrive at `cb`."""
        story = tr.resolve_story("B-VAL-06", None, None)

        assert "integration" in {s.tier for s in tr.resolve_selections(story, "cb")}

    def test_dal_c_is_the_unshifted_baseline(self, tr: ModuleType) -> None:
        story = tr.resolve_story("C-FLOW-12", None, None)

        assert "integration" not in {s.tier for s in tr.resolve_selections(story, "cb")}

    def test_dal_a_forces_full_scope_from_the_commit_boundary(self, tr: ModuleType) -> None:
        story = tr.resolve_story("A-VAL-03", None, None)

        assert {s.scope for s in tr.resolve_selections(story, "cb")} == {"all"}

    def test_dal_a_runs_every_declared_tier_at_the_commit_boundary(self, tr: ModuleType) -> None:
        story = tr.resolve_story("A-VAL-03", None, None)

        assert {s.tier for s in tr.resolve_selections(story, "cb")} == {
            "unit",
            "integration",
            "e2e",
        }

    def test_dal_d_pushes_tiers_one_state_later(self, tr: ModuleType) -> None:
        story = tr.resolve_story("D-SENS-04", None, None)

        assert "unit" not in {s.tier for s in tr.resolve_selections(story, "quick")}

    def test_dal_e_defers_further_still(self, tr: ModuleType) -> None:
        story = tr.resolve_story("E-VAL-05", None, None)

        assert tr.resolve_selections(story, "quick") == []

    def test_a_tier_once_started_never_stops(self, tr: ModuleType) -> None:
        """Shifting must not leave a hole at `feature` — coverage may only accumulate."""
        for story_id in ("B-VAL-06", "C-FLOW-12", "D-SENS-04", "E-VAL-05"):
            story = tr.resolve_story(story_id, None, None)
            sf = {s.tier for s in tr.resolve_selections(story, "sf")}
            feature = {s.tier for s in tr.resolve_selections(story, "feature")}
            assert sf <= feature, f"{story_id}: feature dropped tiers present at sf"


class TestWideningOnly:
    def test_also_adds_a_tier_that_the_profile_omits(self, tr: ModuleType) -> None:
        story = tr.resolve_story("C-FLOW-12", None, None)

        tiers = {s.tier for s in tr.resolve_selections(story, "cb", also=["e2e"])}

        assert "e2e" in tiers

    def test_also_never_narrows_an_existing_selection(self, tr: ModuleType) -> None:
        story = tr.resolve_story("C-FLOW-12", None, None)

        before = {s.tier for s in tr.resolve_selections(story, "feature")}
        after = {s.tier for s in tr.resolve_selections(story, "feature", also=["unit"])}

        assert before <= after

    def test_an_unknown_tier_is_rejected(self, tr: ModuleType) -> None:
        story = tr.resolve_story("C-FLOW-12", None, None)

        with pytest.raises(tr.UsageError):
            tr.resolve_selections(story, "cb", also=["api"])

    def test_an_unknown_state_is_rejected(self, tr: ModuleType) -> None:
        story = tr.resolve_story("C-FLOW-12", None, None)

        with pytest.raises(tr.UsageError):
            tr.resolve_selections(story, "midway")


# ---------------------------------------------------------------------------
# Scope resolution
# ---------------------------------------------------------------------------


class TestScopeResolution:
    CHANGED: ClassVar[list[Path]] = [Path("src/specweaver/core/flow/runner.py")]

    def test_all_scope_is_the_whole_tier(self, tr: ModuleType) -> None:
        assert tr.paths_for("unit", "all", []) == [Path("tests/unit")]

    def test_module_scope_mirrors_the_owning_package(self, tr: ModuleType) -> None:
        assert tr.paths_for("unit", "module", self.CHANGED) == [Path("tests/unit/core/flow")]

    def test_domain_scope_maps_to_the_e2e_domain_directory(self, tr: ModuleType) -> None:
        paths = tr.paths_for("e2e", "domain", self.CHANGED)

        assert Path("tests/e2e/core") in paths

    def test_non_source_changes_select_nothing(self, tr: ModuleType) -> None:
        assert tr.paths_for("unit", "module", [Path("README.md")]) == []

    def test_test_file_changes_do_not_drive_source_scoping(self, tr: ModuleType) -> None:
        """Editing a test must not be what decides which tests run."""
        assert tr.paths_for("unit", "module", [Path("tests/unit/core/test_x.py")]) == []

    def test_a_package_with_no_mirror_selects_nothing(self, tr: ModuleType) -> None:
        assert (
            tr.paths_for("integration", "module", [Path("src/specweaver/nonexistent/a.py")]) == []
        )

    def test_touched_scope_finds_the_mirroring_test_file(self, tr: ModuleType) -> None:
        changed = [Path("src/specweaver/assurance/graph/hasher.py")]

        paths = tr.paths_for("unit", "touched", changed)

        assert all(p.name.startswith("test_hasher") for p in paths)


# ---------------------------------------------------------------------------
# The refactor rule
# ---------------------------------------------------------------------------


class TestRefactorRule:
    """`refactor_violations`'s original coarse behaviour: a nonexistent/no-diff path has nothing
    to prove it safe, so it stays a violation — same outcome as before this class's `_is_path_only`
    refinement below, just for a different reason (no diff to examine, not "diff examined and
    found unsafe")."""

    def test_a_refactor_touching_tests_is_reported(self, tr: ModuleType) -> None:
        changed = [Path("src/specweaver/a.py"), Path("tests/unit/test_a.py")]

        assert tr.refactor_violations(changed) == [Path("tests/unit/test_a.py")]

    def test_a_refactor_touching_only_source_is_clean(self, tr: ModuleType) -> None:
        assert tr.refactor_violations([Path("src/specweaver/a.py")]) == []

    def test_non_python_test_assets_are_not_violations(self, tr: ModuleType) -> None:
        assert tr.refactor_violations([Path("tests/fixtures/sample.yaml")]) == []


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


class TestRefactorViolationsRealDiff:
    """End-to-end: `refactor_violations` against a REAL git repo and REAL `git diff` output —
    the pure-function tests above prove the logic, this proves the wiring."""

    def test_import_path_only_change_in_a_real_repo_is_not_a_violation(
        self, tr: ModuleType, tmp_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess_run = tr.subprocess.run
        subprocess_run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess_run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
        subprocess_run(["git", "config", "user.name", "t"], cwd=repo, check=True)

        test_file = repo / "tests" / "unit" / "test_x.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("from a.b import c\n")
        subprocess_run(["git", "add", "."], cwd=repo, check=True)
        subprocess_run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

        test_file.write_text("from a.b.d import c\n")

        violations = tr.refactor_violations([Path("tests/unit/test_x.py")], repo_root=repo)

        assert violations == []

    def test_assertion_change_in_a_real_repo_is_a_violation(
        self, tr: ModuleType, tmp_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess_run = tr.subprocess.run
        subprocess_run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess_run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
        subprocess_run(["git", "config", "user.name", "t"], cwd=repo, check=True)

        test_file = repo / "tests" / "unit" / "test_x.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("assert result == 5\n")
        subprocess_run(["git", "add", "."], cwd=repo, check=True)
        subprocess_run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

        test_file.write_text("assert result == 3\n")

        violations = tr.refactor_violations([Path("tests/unit/test_x.py")], repo_root=repo)

        assert violations == [Path("tests/unit/test_x.py")]

    def test_untracked_new_test_file_with_no_diff_is_still_a_violation(
        self, tr: ModuleType, tmp_path: Path
    ) -> None:
        """Graceful degradation: no committed baseline to diff against -> nothing proves it
        safe -> conservative default wins, same as the pre-fix behaviour."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess_run = tr.subprocess.run
        subprocess_run(["git", "init", "-q"], cwd=repo, check=True)

        test_file = repo / "tests" / "unit" / "test_new.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("def test_it(): pass\n")

        violations = tr.refactor_violations([Path("tests/unit/test_new.py")], repo_root=repo)

        assert violations == [Path("tests/unit/test_new.py")]


class TestCliSurface:
    def test_matrix_prints_without_a_story(self, tr: ModuleType) -> None:
        assert tr.main(["matrix"]) == 0

    def test_a_missing_story_id_is_rejected(self, tr: ModuleType) -> None:
        assert tr.main(["cb"]) == 2

    def test_an_unknown_state_is_rejected_by_argparse(self, tr: ModuleType) -> None:
        with pytest.raises(SystemExit):
            tr.main(["midway", "C-FLOW-12"])

    def test_a_tech_ticket_without_kind_exits_two(self, tr: ModuleType) -> None:
        assert tr.main(["cb", "TECH-020"]) == 2

    def test_an_audit_ticket_runs_nothing_and_succeeds(self, tr: ModuleType) -> None:
        assert tr.main(["feature", "TECH-017", "--kind", "audit"]) == 0
