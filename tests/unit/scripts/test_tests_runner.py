# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the test-tier runner (`scripts/tests.py`).

Proves: TECH-060 FR-1

The dangerous logic here is not the pytest invocation, it is the resolution: story ID -> profile,
DAL -> shift, scope -> paths. Every one of those failing silently produces a GREEN run that tested
less than it claimed, which is worse than a red one.

The DAL direction gets its own class. DAL-A is Mission-Critical and DAL-E is Prototyping, so "most
critical" is the alphabetically lowest letter — `max()` returns E and selects the weakest profile.
That is a one-character mistake with no visible symptom, so it is pinned from several angles.

`scripts/` is not an importable package, so the module is loaded by path.

The diff-safety rule this file used to cover lives in `test_refactor_diff_safety.py`, mirroring
`scripts/_refactor_diff_safety.py` — one test file per script.

`scripts/_changed_file_mapping.py` is the exception, and deliberately so: `tests.py` re-exports its
whole surface under the names used here, and the mapping is only ever meaningful as an input to
scope resolution. Testing it through its caller is what makes the union model assertable at all.
Same arrangement as `_test_class_naming.py`, covered via `test_check_conventions.py`.
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

    def test_a_migration_id_resolves_as_an_integration_story(self, tr: ModuleType) -> None:
        """`INT-US-NN-MIG` is a first-class registry id (`ADR-004`, `TECH-060` FR-1).

        Without the suffix in `INT_ID`, `resolve_story` falls through every branch and the migration
        entry cannot be named on the command line at all.
        """
        story = tr.resolve_story("INT-US-09-MIG", None, "C")
        assert story.kind == "int"
        assert story.dal == "C"

    def test_a_sub_story_migration_id_resolves_too(self, tr: ModuleType) -> None:
        story = tr.resolve_story("INT-US-09-SF01-MIG", None, "B")
        assert story.kind == "int"
        assert story.dal == "B"

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

        assert Path("tests/e2e/capabilities/core") in paths

    def test_non_source_changes_select_nothing(self, tr: ModuleType) -> None:
        assert tr.paths_for("unit", "module", [Path("README.md")]) == []

    def test_a_changed_test_contributes_its_own_module(self, tr: ModuleType) -> None:
        """A test belongs to the module it covers, so it contributes that module like a source file.

        This assertion is the REVERSE of the one it replaces
        (`test_test_file_changes_do_not_drive_source_scoping`, which required `[]`). That guard's
        reasoning — "editing a test must not be what decides which tests run" — still holds and is
        why the model is a UNION: a changed test can ADD a module, never redirect or remove one, so
        it decides nothing. Inverted deliberately, not by accident.

        Without this, a tests-only change resolves to zero paths and the gate refuses it as "source
        that nothing mirrors" — which is false when no source changed at all, and blocks every
        commit whose work is tests and documents.
        """
        assert tr.paths_for("unit", "module", [Path("tests/unit/core/test_x.py")]) == [
            Path("tests/unit/core")
        ]

    def test_a_changed_test_does_not_leak_into_another_tier(self, tr: ModuleType) -> None:
        """A test's tier is embedded in its own path, unlike a source file which serves every tier."""
        changed = [Path("tests/e2e/sandbox/test_x.py")]

        assert tr.paths_for("unit", "module", changed) == []

    def test_source_and_test_changes_union_their_modules(self, tr: ModuleType) -> None:
        changed = [
            Path("src/specweaver/core/flow/runner.py"),
            Path("tests/unit/graph/test_builder.py"),
        ]

        assert tr.paths_for("unit", "module", changed) == [
            Path("tests/unit/core/flow"),
            Path("tests/unit/graph"),
        ]

    def test_a_changed_e2e_test_maps_to_its_domain(self, tr: ModuleType) -> None:
        """The domain is found whether or not the changed path spells `capabilities/` itself.

        `tests/e2e/sandbox/` no longer exists — `C-EXEC-03` FR-8 moved it under `capabilities/` — and
        the resolver still lands on the right directory, because it tries both spellings and keeps
        only what is on disk.
        """
        changed = [Path("tests/e2e/sandbox/test_x.py")]

        assert tr.paths_for("e2e", "domain", changed) == [Path("tests/e2e/capabilities/sandbox")]

    def test_touched_scope_runs_the_changed_test_itself(self, tr: ModuleType) -> None:
        """The `test_{stem}*.py` glob cannot serve a test file — it would seek `test_test_x*.py`."""
        changed = [Path("tests/unit/scripts/test_tests_runner.py")]

        assert tr.paths_for("unit", "touched", changed) == [
            Path("tests/unit/scripts/test_tests_runner.py")
        ]

    def test_a_changed_test_in_a_nonexistent_package_selects_nothing(self, tr: ModuleType) -> None:
        assert tr.paths_for("unit", "module", [Path("tests/unit/nope/test_x.py")]) == []

    def test_a_deleted_test_is_not_handed_to_pytest(self, tr: ModuleType) -> None:
        """A deletion shows up in the diff too; passing the missing path on would abort the run."""
        changed = [Path("tests/unit/scripts/test_deleted_yesterday.py")]

        assert tr.paths_for("unit", "touched", changed) == []

    def test_a_package_with_no_mirror_selects_nothing(self, tr: ModuleType) -> None:
        assert (
            tr.paths_for("integration", "module", [Path("src/specweaver/nonexistent/a.py")]) == []
        )

    def test_touched_scope_finds_the_mirroring_test_file(self, tr: ModuleType) -> None:
        changed = [Path("src/specweaver/assurance/graph/hasher.py")]

        paths = tr.paths_for("unit", "touched", changed)

        assert all(p.name.startswith("test_hasher") for p in paths)

    def test_a_non_python_file_under_the_tier_root_selects_nothing(self, tr: ModuleType) -> None:
        """The suffix guard, which `README.md` never reaches — that one exits at the prefix check.

        `tests/unit/scripts/` is a real mirror directory on purpose: drop the `.py` check and this
        resolves to it, so the assertion moves. Point it at a non-existent package and the test
        would pass for the wrong reason.
        """
        assert tr.paths_for("unit", "module", [Path("tests/unit/scripts/fixture.yaml")]) == []

    def test_a_test_at_the_tier_root_resolves_to_the_whole_tier(self, tr: ModuleType) -> None:
        """`rel.parent` is `.`, so the mirror IS the tier root.

        Defensible — a repo-root architecture test really does cover the tier — but it is a
        6000-test consequence of a `Path(".")`, so it is pinned rather than left to be discovered.
        """
        changed = [Path("tests/unit/test_architecture.py")]

        assert tr.paths_for("unit", "module", changed) == [Path("tests/unit")]

    def test_an_unknown_scope_is_rejected(self, tr: ModuleType) -> None:
        """Reached only with a changed file: an empty diff never enters the scope branch at all."""
        with pytest.raises(tr.UsageError, match="sideways"):
            tr.paths_for("unit", "sideways", self.CHANGED)


class TestPathsForAtDomainScope:
    """`domain` is the one scope where a test's path is not shaped like a source path.

    Both cases here were found by CB-1's adversarial review, after U1-U4 were already green: every
    one of those exercises `module` or `touched`, so the domain branch went unexamined while the
    boundary claimed to have fixed test-derived scoping generally.
    """

    def test_a_test_in_the_tier_root_selects_nothing(self, tr: ModuleType) -> None:
        """`rel.parts[0]` is a FILENAME here, not a domain, so there is no directory to name.

        This case used to return the file itself, because four e2e tests sat directly in `tests/e2e/`
        and would otherwise have contributed nothing to their own gate. `C-EXEC-03` FR-8 moved all
        four into capability folders, and `tests/unit/test_macro_domain_layout.py` now *fails* a loose
        file at the tier root — so the compensation was deleted with the condition that caused it.

        Asserted rather than dropped: this pins that a tier-root file selects nothing, which is the
        behaviour a second guard is relied on to make unreachable.
        """
        changed = [Path("tests/e2e/test_cli_bootstrap_e2e.py")]

        assert tr.paths_for("e2e", "domain", changed) == []

    def test_a_capabilities_test_resolves_to_its_domain_not_the_container(
        self, tr: ModuleType
    ) -> None:
        """`capabilities/` is a container, so the domain is what follows it.

        Taking `parts[0]` verbatim selects EVERY capability. Union-only makes that safe rather
        than wrong, but the source route resolves the same domain precisely, and two routes
        disagreeing about what `domain` means reads as a bug to whoever meets it next.
        """
        changed = [Path("tests/e2e/capabilities/core/test_lineage_e2e.py")]

        assert tr.paths_for("e2e", "domain", changed) == [Path("tests/e2e/capabilities/core")]

    def test_the_test_route_and_the_source_route_agree_on_a_domain(self, tr: ModuleType) -> None:
        """The asymmetry itself, asserted — so closing one route and not the other goes red."""
        from_test = tr.paths_for("e2e", "domain", [Path("tests/e2e/capabilities/core/test_x.py")])
        from_source = tr.paths_for("e2e", "domain", [Path("src/specweaver/core/flow/runner.py")])

        assert from_test == from_source

    def test_a_tier_root_test_that_does_not_exist_selects_nothing(self, tr: ModuleType) -> None:
        """A deletion reaches the selector too; handing pytest a missing path aborts the run."""
        changed = [Path("tests/e2e/test_deleted_yesterday.py")]

        assert tr.paths_for("e2e", "domain", changed) == []

    def test_a_bare_source_module_still_selects_nothing_at_domain_scope(
        self, tr: ModuleType
    ) -> None:
        """The new tier-root branch must not start inventing e2e paths for source files."""
        assert tr.paths_for("e2e", "domain", [Path("src/specweaver/conftest.py")]) == []


class TestBlockedReason:
    """A tier that selects nothing must say WHY, and the reason must be true.

    The message this pins replaced one that asserted the source cause unconditionally. It was
    therefore false for a tests-only change, and cost a session hunting for a coverage hole that
    did not exist. Untested prose is how that survived.
    """

    def test_changed_source_with_no_mirror_names_the_coverage_cause(self, tr: ModuleType) -> None:
        reason = tr._blocked_reason("unit", [Path("src/specweaver/nonexistent/a.py")])

        assert "missing coverage" in reason

    def test_a_tests_only_change_is_not_blamed_on_missing_source_coverage(
        self, tr: ModuleType
    ) -> None:
        """The false claim, stated exactly: no source changed, so none of it can lack a mirror."""
        reason = tr._blocked_reason("unit", [Path("tests/unit/nope/test_x.py")])

        assert "missing coverage" not in reason
        assert "no mirror in this tier" in reason

    def test_a_change_touching_neither_says_so(self, tr: ModuleType) -> None:
        reason = tr._blocked_reason("unit", [Path("README.md")])

        assert reason == "nothing you changed resolves to this tier at all"

    def test_an_e2e_test_does_not_explain_a_blocked_unit_tier(self, tr: ModuleType) -> None:
        """Tier-specific: an e2e file is invisible to the unit tier, so it cannot be the cause."""
        reason = tr._blocked_reason("unit", [Path("tests/e2e/sandbox/test_x.py")])

        assert reason == "nothing you changed resolves to this tier at all"

    def test_source_wins_when_both_kinds_changed(self, tr: ModuleType) -> None:
        """Missing source coverage is the more serious of the two, so it is reported first."""
        changed = [Path("tests/unit/nope/test_x.py"), Path("src/specweaver/nonexistent/a.py")]

        assert "missing coverage" in tr._blocked_reason("unit", changed)

    def test_an_empty_selection_is_reported_and_counted_as_a_failure(
        self, tr: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No pytest subprocess runs here — `run_selections` returns before `run_tier`."""
        selection = tr.Selection("unit", "module")

        results = tr.run_selections([selection], [Path("README.md")], "1")
        out = capsys.readouterr().out

        assert results == [(selection, 1, 0)]
        assert "BLOCKED" in out
        assert "nothing you changed resolves to this tier at all" in out

    def test_a_gate_script_mirrors_to_the_scripts_test_package(self, tr: ModuleType) -> None:
        """`scripts/` is mirrored by `tests/unit/scripts/`, so changing a gate must select it.

        Without this, no change confined to `scripts/` can satisfy its own commit boundary: the
        runner reported "selected NO tests -- you changed source that nothing mirrors" for a
        directory that has mirrored the whole time.
        """
        changed = [Path("scripts/check_fr_coverage.py")]

        assert tr.paths_for("unit", "module", changed) == [Path("tests/unit/scripts")]

    def test_touched_scope_finds_the_mirroring_gate_test(self, tr: ModuleType) -> None:
        changed = [Path("scripts/check_fr_coverage.py")]

        paths = tr.paths_for("unit", "touched", changed)

        assert paths and all(p.name.startswith("test_check_fr_coverage") for p in paths)

    def test_non_python_files_under_scripts_select_nothing(self, tr: ModuleType) -> None:
        """`scripts/baselines/*.json` is data. Editing a baseline is not a source change."""
        assert tr.paths_for("unit", "module", [Path("scripts/baselines/suppressions.json")]) == []

    def test_a_nested_script_with_no_mirror_selects_nothing(self, tr: ModuleType) -> None:
        """`scripts/` is flat today. Should it gain a package, the mirror must exist before the
        gate will accept a change there -- the same rule already applied to `src/specweaver/`,
        rather than a silent pass.
        """
        assert tr.paths_for("unit", "module", [Path("scripts/nested/helper.py")]) == []


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
