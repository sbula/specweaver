# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the consolidated quality-gate runner (`scripts/quality.py`).

The runner's whole contract is *which checks run, over how much code, at which gate*. That
contract is data (`MATRIX`), so it is asserted directly rather than inferred from a live run: a
gate that silently drops a check would otherwise look identical to a gate that passes.

Each gate is pinned to an EXACT set — not a superset — because "only the required checks run" is
half the requirement. A test asserting mere membership would stay green if `quick` started
dragging in mypy and cost 25s.

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

#: Checkers deliberately outside the battery, each with the reason it cannot be a gate. Kept as an
#: explicit allowlist rather than a pattern so adding one is a decision somebody makes, and
#: `test_the_ungated_allowlist_is_not_stale` stops a deleted name masking a real gap.
#:
#: Both take a STORY ID rather than a tree, so they answer "is this story closable" rather than "is
#: the repo healthy". (A third lived here until 2026-08-13: `check_entry_orphans.py`, advisory
#: scaffolding for `TECH-044`'s redistribution, deleted by the test that demanded it once the
#: R-ENTRY backlog reached zero.)
UNGATED_CHECKERS = {
    "check_fr_coverage.py",  # `check_fr_coverage.py <STORY>` — FR ledger closure (TECH-025)
    "check_story_preconditions.py",  # `<STORY>` — prerequisites green in code, not documents
}


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
def q() -> ModuleType:
    return _load("quality")


# ---------------------------------------------------------------------------
# The matrix, gate by gate
# ---------------------------------------------------------------------------

#: check -> scope, exactly as agreed. Kept literal (not derived from the module under test) so a
#: wrong edit to MATRIX fails here instead of being mirrored into the expectation.
EXPECTED: dict[str, dict[str, str]] = {
    "quick": {
        "ruff": "all",
        "format": "all",
        "file_sizes": "changed",
        "complexipy": "changed",
        # Duplicate-basename detection compares every test file against every other, so a
        # diff-scoped run cannot see the collision it exists to catch. Cheap (names only, no
        # reads), so it runs `all` even in the inner loop.
        "test_basenames": "all",
        "useless_asserts": "changed",
        "conventions": "changed",
    },
    "cb": {
        "ruff": "all",
        "format": "all",
        "file_sizes": "all",
        "complexipy": "all",
        "test_basenames": "all",
        "useless_asserts": "all",
        "conventions": "all",
        "mypy": "all",
        "tach": "all",
        "suppressions": "all",
        "class_health": "changed",
        "cycles": "all",
        # `TECH-037`. Cross-file by definition -- a clone's twin may be in a file the commit never
        # touched -- so there is no meaningful `changed` scope and it never narrows. Absent from
        # `quick` on purpose: it shells out to npx and the inner loop should stay fast.
        "duplication": "all",
    },
    "sf": {
        "ruff": "all",
        "format": "all",
        "file_sizes": "all",
        "complexipy": "all",
        "test_basenames": "all",
        "useless_asserts": "all",
        "conventions": "all",
        "mypy": "all",
        "tach": "all",
        "suppressions": "all",
        "class_health": "module",
        "cycles": "all",
        "duplication": "all",
        "coupling": "module",
    },
    "feature": {
        "ruff": "all",
        "format": "all",
        "file_sizes": "all",
        "complexipy": "all",
        "test_basenames": "all",
        "useless_asserts": "all",
        "conventions": "all",
        "mypy": "all",
        "tach": "all",
        "suppressions": "all",
        "class_health": "all",
        "cycles": "all",
        "duplication": "all",
        "coupling": "all",
    },
    # A separate track, not a rung on the ladder above: registries, not code.
    "doc": {
        "roadmap_sync": "all",
        "roadmap_placement": "all",
        # `ADR-003`'s 2026-08-16 addendum: a retirement note may only move scope to an UNBUILT
        # capability. A delivered one cannot accept the FR, so the scope lands nowhere and no
        # other gate can see it -- `check_fr_coverage.py` judges only FRs somebody wrote.
        "retirement_targets": "all",
        "skill_sync": "all",
        "skill_references": "all",
        # `TECH-017`: every delivered integration contract's proof, judged in one sweep. Takes no
        # story ID on purpose -- a story-scoped check only fires when someone remembers to pass the
        # story, which is exactly how INT-US-25 stayed wrong.
        "proof_tier": "all",
        # `TECH-017`: the audit matrix itself, ratcheted. The audit's FRs name "Auditor" as the
        # Actor -- they emit a document, so no test in `src/` could own them and `check_fr_coverage`
        # blocked the ticket. This is where FR-1/2/3/4/6 live; FR-5 was descoped to AD-2.
        "audit_matrix": "all",
        # R-DEPTH: `R-LENGTH` capped the roadmap, its rationale pushed detail into the topic doc,
        # and nothing checked that level -- 33.5% of topic lines over 200, longest 5624.
        "entry_depth": "all",
        # `TECH-047`: uncited-FR ratchet, swept rather than story-scoped.
        "fr_sweep": "all",
        # `TECH-017`: the same for NFRs, which no script in this repo looked at until 2026-08-13.
        # Behavioural rows only -- a row proved by `tach` or `file_sizes`, or unfalsifiable as
        # written, is excused by an explicit `[proof: ...]` marker in the design.
        "nfr_sweep": "all",
    },
}


class TestGateResolution:
    @pytest.mark.parametrize("gate", ["quick", "cb", "sf", "feature", "doc"])
    def test_gate_resolves_to_exactly_the_agreed_checks(self, q: ModuleType, gate: str) -> None:
        plans = q.resolve_plans(gate)

        assert {p.check: p.scope for p in plans} == EXPECTED[gate]

    def test_declared_gates_match_the_expectation_table(self, q: ModuleType) -> None:
        """Guards against a fifth gate appearing with no test coverage."""
        assert set(q.GATES) == set(EXPECTED)

    def test_mypy_is_absent_from_quick(self, q: ModuleType) -> None:
        """Measured at 25s warm / 91s cold — it would destroy the inner loop."""
        assert "mypy" not in {p.check for p in q.resolve_plans("quick")}

    def test_plans_are_ordered_deterministically(self, q: ModuleType) -> None:
        """Parallel execution must still report in a stable order."""
        assert [p.check for p in q.resolve_plans("cb")] == sorted(
            p.check for p in q.resolve_plans("cb")
        )


class TestDocTrackIsSeparate:
    """`doc` answers a different question and must not leak into the code ladder.

    A stale roadmap checkbox failing a commit-boundary code gate would train everyone to run the
    gate with the doc checks disabled, which is how the doc checks stop running at all.
    """

    @pytest.mark.parametrize("gate", ["quick", "cb", "sf", "feature"])
    def test_no_code_gate_runs_a_registry_check(self, q: ModuleType, gate: str) -> None:
        assert not {p.check for p in q.resolve_plans(gate)} & {"roadmap_sync", "skill_sync"}

    def test_the_reference_check_runs_in_the_standard_gate(self, q: ModuleType) -> None:
        """Proves TECH-019 FR-6.

        A guardrail nothing invokes is a script, not a gate. This is the wiring that makes a doc
        refactor breaking an instruction reference fail at the commit that breaks it, rather than
        a fortnight later when an agent silently loads nothing.
        """
        assert "skill_references" in q.CHECKS
        assert q.MATRIX["skill_references"] == {"doc": "all"}
        assert {p.check for p in q.resolve_plans("doc")} >= {"skill_references"}

    def test_the_doc_gate_runs_no_code_checks(self, q: ModuleType) -> None:
        assert {p.check for p in q.resolve_plans("doc")} == {
            "roadmap_sync",
            "roadmap_placement",
            "retirement_targets",
            "skill_sync",
            "skill_references",
            "proof_tier",
            "audit_matrix",
            "entry_depth",
            "fr_sweep",
            "nfr_sweep",
        }

    def test_doc_is_not_in_the_code_ladder(self, q: ModuleType) -> None:
        assert "doc" not in q.CODE_GATES
        assert "doc" in q.GATES

    def test_registry_checks_take_no_paths(self, q: ModuleType) -> None:
        """Both are repo-wide by nature — a diff-scoped registry check proves nothing."""
        for name in ("roadmap_sync", "skill_sync"):
            assert q.CHECKS[name].ignores_paths


class TestGateEscalation:
    """Each gate must cover everything the gate below it covers."""

    @pytest.mark.parametrize(
        ("lower", "higher"), [("quick", "cb"), ("cb", "sf"), ("sf", "feature")]
    )
    def test_checks_only_ever_accumulate(self, q: ModuleType, lower: str, higher: str) -> None:
        low = {p.check for p in q.resolve_plans(lower)}
        high = {p.check for p in q.resolve_plans(higher)}

        assert low <= high, f"{higher} dropped checks present in {lower}: {low - high}"

    @pytest.mark.parametrize(
        ("lower", "higher"), [("quick", "cb"), ("cb", "sf"), ("sf", "feature")]
    )
    def test_scope_never_narrows_as_the_gate_rises(
        self, q: ModuleType, lower: str, higher: str
    ) -> None:
        rank = {"changed": 0, "module": 1, "all": 2}
        low = {p.check: p.scope for p in q.resolve_plans(lower)}

        for plan in q.resolve_plans(higher):
            if plan.check in low:
                assert rank[plan.scope] >= rank[low[plan.check]], (
                    f"{plan.check} narrowed from {low[plan.check]} at {lower} "
                    f"to {plan.scope} at {higher}"
                )

    def test_the_users_floor_every_commit_gate_checks_all_source(self, q: ModuleType) -> None:
        """The stated rule: from the first commit point up, core checks cover ALL code.

        `class_health` is the sole documented exception at `cb` — it is diff-scoped there because
        a class is legitimately half-built mid-commit-boundary, not because it is expensive.
        """
        for gate in ("cb", "sf", "feature"):
            narrow = {p.check for p in q.resolve_plans(gate) if p.scope != "all"}
            assert narrow <= {"class_health", "coupling"}, f"{gate} runs {narrow} below 'all' scope"


class TestGateValidation:
    def test_unknown_gate_is_rejected(self, q: ModuleType) -> None:
        with pytest.raises(SystemExit):
            q.main(["bogus-gate"])

    def test_missing_gate_is_rejected(self, q: ModuleType) -> None:
        with pytest.raises(SystemExit):
            q.main([])

    def test_every_matrix_check_has_a_registered_command(self, q: ModuleType) -> None:
        """A check in the matrix with no runner is a gate that silently does nothing."""
        for gate in q.GATES:
            for plan in q.resolve_plans(gate):
                assert plan.check in q.CHECKS, f"{plan.check} has no entry in CHECKS"

    def test_every_registered_check_is_reachable_from_some_gate(self, q: ModuleType) -> None:
        """Dead checks rot; if it is not in the matrix it is not being run."""
        reachable = {p.check for gate in q.GATES for p in q.resolve_plans(gate)}

        assert set(q.CHECKS) == reachable

    def test_every_checker_on_disk_is_wired_into_a_gate(self, q: ModuleType) -> None:
        """The direction the two tests above do NOT cover: a checker nobody registered.

        They both start from the registry, so a `scripts/check_*.py` that was written and never
        added to `CHECKS` is invisible to them — the battery lints the file and never runs it.
        Probed: planting `check_probe_unwired.py` left all 71 tests in this file and
        `test_architecture.py` green.

        That is this repo's most repeated failure shape — `R-OWNER` shipped inert, `-p no:randomly`
        was a no-op for an uninstalled plugin, `check_class_health` reported `nothing in scope` for
        a session. **A check that silently does not run is indistinguishable from one that passes.**
        """
        on_disk = {p.name for p in (REPO_ROOT / "scripts").glob("check_*.py")}
        wired = {c.script for c in q.CHECKS.values() if c.script}

        unwired = on_disk - wired - UNGATED_CHECKERS

        assert not unwired, (
            "checker(s) on disk that no gate runs: " + ", ".join(sorted(unwired)) + ". "
            "Register it in quality.py's CHECKS and MATRIX, or add it to "
            "UNGATED_CHECKERS in this test with the reason."
        )

    def test_the_ungated_allowlist_is_not_stale(self, q: ModuleType) -> None:
        """An allowlisted checker that no longer exists would hide a real gap behind a stale name."""
        del q
        on_disk = {p.name for p in (REPO_ROOT / "scripts").glob("check_*.py")}

        assert on_disk >= UNGATED_CHECKERS, (
            f"allowlisted but absent: {sorted(UNGATED_CHECKERS - on_disk)}"
        )


class TestOnlyFilter:
    def test_only_narrows_to_the_named_check(self, q: ModuleType) -> None:
        plans = q.resolve_plans("cb", only=["mypy"])

        assert [p.check for p in plans] == ["mypy"]

    def test_only_accepts_several_checks(self, q: ModuleType) -> None:
        plans = q.resolve_plans("cb", only=["mypy", "ruff"])

        assert [p.check for p in plans] == ["mypy", "ruff"]

    def test_only_rejects_a_check_absent_from_that_gate(self, q: ModuleType) -> None:
        """Asking for mypy at `quick` is a mistake, not a silent no-op."""
        with pytest.raises(q.UsageError):
            q.resolve_plans("quick", only=["mypy"])

    def test_only_rejects_an_unknown_check_name(self, q: ModuleType) -> None:
        with pytest.raises(q.UsageError):
            q.resolve_plans("cb", only=["nonesuch"])


class TestScopeOverride:
    def test_scope_override_applies_to_every_plan(self, q: ModuleType) -> None:
        plans = q.resolve_plans("cb", scope="all")

        assert {p.scope for p in plans} == {"all"}

    def test_unknown_scope_is_rejected(self, q: ModuleType) -> None:
        with pytest.raises(q.UsageError):
            q.resolve_plans("cb", scope="sideways")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestModuleWidening:
    def test_changed_files_widen_to_their_owning_package(self, q: ModuleType) -> None:
        widened = q.widen_to_modules(
            [Path("src/specweaver/core/flow/runner.py"), Path("src/specweaver/graph/engine.py")]
        )

        assert set(widened) == {
            Path("src/specweaver/core/flow"),
            Path("src/specweaver/graph"),
        }

    def test_several_files_in_one_package_collapse_to_one_entry(self, q: ModuleType) -> None:
        widened = q.widen_to_modules(
            [Path("src/specweaver/core/flow/a.py"), Path("src/specweaver/core/flow/b.py")]
        )

        assert widened == [Path("src/specweaver/core/flow")]

    def test_empty_input_widens_to_nothing(self, q: ModuleType) -> None:
        assert q.widen_to_modules([]) == []


class TestTreeFiltering:
    """Checks declare which trees they read; `changed` scope must respect that.

    These use paths that really exist, because `paths_for` also drops files git reports as
    changed but which are gone from disk — synthetic names would be filtered for the wrong
    reason and the assertions would pass without proving anything about tree filtering.
    """

    SRC_FILE = Path("src/specweaver/assurance/graph/hasher.py")
    TEST_FILE = Path("tests/unit/scripts/test_quality_runner.py")

    def test_src_only_check_ignores_changed_test_files(self, q: ModuleType) -> None:
        paths = q.paths_for(
            q.CHECKS["complexipy"], scope="changed", changed=[self.SRC_FILE, self.TEST_FILE]
        )

        assert paths == [self.SRC_FILE]

    def test_tests_only_check_ignores_changed_src_files(self, q: ModuleType) -> None:
        paths = q.paths_for(
            q.CHECKS["useless_asserts"], scope="changed", changed=[self.SRC_FILE, self.TEST_FILE]
        )

        assert paths == [self.TEST_FILE]

    def test_non_python_changes_are_ignored(self, q: ModuleType) -> None:
        paths = q.paths_for(
            q.CHECKS["complexipy"], scope="changed", changed=[Path("README.md"), self.SRC_FILE]
        )

        assert paths == [self.SRC_FILE]

    def test_all_scope_ignores_the_changed_list_entirely(self, q: ModuleType) -> None:
        paths = q.paths_for(q.CHECKS["complexipy"], scope="all", changed=[])

        assert paths == [Path("src")]

    def test_deleted_files_are_not_passed_to_checks(self, q: ModuleType, tmp_path: Path) -> None:
        """git reports deletions as changed; handing a missing path to ruff is an error."""
        gone = Path("src/specweaver/deleted_module.py")

        paths = q.paths_for(q.CHECKS["complexipy"], scope="changed", changed=[gone])

        assert paths == []


class TestSkipSemantics:
    def test_nothing_changed_is_a_skip_not_a_pass(self, q: ModuleType) -> None:
        """A skipped check must be visibly skipped — a silent pass reads as verified."""
        result = q.run_plan(
            q.Plan(check="complexipy", scope="changed"), changed=[], repo_root=REPO_ROOT
        )

        assert result.status == "SKIPPED"

    def test_a_skip_does_not_count_as_a_failure(self, q: ModuleType) -> None:
        result = q.run_plan(
            q.Plan(check="complexipy", scope="changed"), changed=[], repo_root=REPO_ROOT
        )

        assert not result.failed
