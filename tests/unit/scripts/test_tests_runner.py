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
    def test_a_refactor_touching_tests_is_reported(self, tr: ModuleType) -> None:
        changed = [Path("src/specweaver/a.py"), Path("tests/unit/test_a.py")]

        assert tr.refactor_violations(changed) == [Path("tests/unit/test_a.py")]

    def test_a_refactor_touching_only_source_is_clean(self, tr: ModuleType) -> None:
        assert tr.refactor_violations([Path("src/specweaver/a.py")]) == []

    def test_non_python_test_assets_are_not_violations(self, tr: ModuleType) -> None:
        assert tr.refactor_violations([Path("tests/fixtures/sample.yaml")]) == []


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
