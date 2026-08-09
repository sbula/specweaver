# Walkthrough: TECH-025 SF-04 CB-1 — a changed test contributes its module

- **Feature ID**: TECH-025 / SF-04 (TECH-001 FR Ledger)
- **Commit boundary**: CB-1 of 3
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf04_implementation_plan.md §Commit Boundaries
- **Date**: 2026-08-09

## What changed and why

SF-04's work is tests and documents — NFR-1 forbids touching `src/`. The commit gate refused it:

```
BLOCKED: unit at scope 'module' selected NO tests.
You changed source that nothing mirrors — that is missing coverage, not a clean run.
```

That message was **false**. No source had changed, so no source could be missing a mirror.
`_src_relative` maps only `src/specweaver/` and `scripts/`, so a tests-only diff produced zero
relatives and the tier selected nothing. SF-05 and SF-06 are tests-and-docs by design and hit the
same wall.

**The model, chosen by the user: a test belongs to the module it covers**, so it contributes that
module exactly as a source file does.

| File | Change |
|---|---|
| `scripts/tests.py` | `tier_relative()` maps a changed test to its module **for that tier only**. `_scoped_paths()` extracted so source- and test-derived relatives run the same scope machinery, and its `domain` branch now handles tier-root and container-nested tests. 594 → **566** lines. |
| `scripts/_changed_file_mapping.py` | **New.** `src_relative`, `tier_relative`, `domain_parts`, `blocked_reason` — the pure path→module mapping, re-exported by `tests.py`. |
| `tests/unit/scripts/test_tests_runner.py` | 14 new tests; one existing test inverted and renamed. |
| `docs/dev_guides/special_patterns_and_adaptations.md` | New pattern 26 — union-only contribution in change-driven selection. |
| `docs/dev_guides/testing_guide.md` | New section documenting the commit gate, which the guide had never mentioned. |

Two properties carry the design:

- **Union-only.** A changed test can *add* a module, never redirect or remove one. That preserves
  the intent of the guard it replaced — *"editing a test must not be what decides which tests run"* —
  because under a union a test **contributes**, it does not **decide**.
- **Tier-specific.** A test's tier is baked into its own path; a source file serves every tier.
  Without that, editing an e2e test would pull in unit paths.

The directory mapping is an admitted proxy: an integration test spanning three modules maps to
whichever directory it sits in. Same proxy the source side already uses; the code says so.

## The inverted test

`test_test_file_changes_do_not_drive_source_scoping` asserted `paths_for(...) == []`. It is now
`test_a_changed_test_contributes_its_own_module` and asserts the opposite. Recorded rather than
silently flipped: its rationale still holds and is *why* the model is a union. The docstring says
"Inverted deliberately, not by accident."

## Test results

| Tier | Scope | Paths | Result |
|---|---|---|---|
| unit | module | `tests/unit/scripts` | **413 passed** |

Gate: `python scripts/tests.py cb TECH-025 --kind tooling`, DAL-C (TECH baseline). 399 before the
14 new tests. Integration and e2e are not selected for `--kind tooling` at `cb` — the deliverable is
a guardrail script and its own unit tests are the proof.

## Quality results

| Gate | Result |
|---|---|
| `quality.py cb` | 9 ok, 1 skip, **2 FAIL** — `complexipy`, `cycles` |
| `quality.py doc` | 3/3 ok (`roadmap_sync`, `skill_references`, `skill_sync`) |
| `ruff` / `format` / `mypy` / `tach` / `conventions` / `file_sizes` / `suppressions` / `test_basenames` / `useless_asserts` | all ok |
| `scripts/tests.py` size | 594/600 |

**The two failures are chronic and provably not this boundary's.** `complexipy` reports 97
offenders and `cycles` reports 4 — identical to the figures the roadmap records for `TECH-023`
("fell 98 → 97 from TECH-006 alone") and `TECH-024`. Both checks scan `src` **only**, and
`git status --porcelain -- src/` returns zero lines, so neither is attributable here and neither is
fixable without breaking NFR-1. The roadmap additionally sequences `TECH-023` **last** and forbids
it sharing a working tree with `TECH-024`; doing either here would destroy the attribution those
tickets depend on. `class_health` skipped for the same reason — "nothing in scope" is correct.

## HITL gate decisions

| Gate | What was presented | Decision |
|---|---|---|
| **Phase 2** (architecture + test gap) | `TECH-025_sf04_precommit_review.md`: no architecture violations; Finding A1 (`tests.py` at 585/600 and this ticket keeps feeding it); Finding A2 (the tier-root case is unpinned and CB-2 lands on it); four gaps U1–U4; and the admission that the probe had **not** been run, since the pre-reboot session's results cannot be relied on | User: *"implement U1-U4 and run the probe"* — all four approved, no descoping |
| **Phase 3** | Implemented; yielded with the list of edge cases and the probe results | User: *"yes, proceed"* |

**No gate was bypassed.** One scope expansion happened inside an approved item and is flagged for
retroactive review: **U3 grew from a test into a source change.** The story as approved read "the
BLOCKED message distinguishes the two causes"; on implementing it, the message still *asserted* its
cause unconditionally — I had only made the prose less wrong, not correct. `_blocked_reason()` now
computes it. Offered for revert at the Phase 3 yield; the user proceeded.

## What the probes caught

Four probes, each reintroducing one specific defect.

| Probe | Defect reintroduced | Red |
|---|---|---|
| P1 | `_tier_relative` returns `None` for everything | **6** — every test-derived assertion and *only* those; all source-derived ones stayed green, which is the union model's whole claim |
| P2 | suffix guard removed | 1 — U1 alone |
| P3 | unknown scope returns `set()` instead of raising | 1 — U2 alone |
| P4 | the original unconditional message restored | **4**, including the test named for the defect |
| P5 | tier-root branch removed (R13 regressed) | 1 |
| P6 | container strip removed (R12 regressed) | 2 |
| P7 | `test_` guard removed (source leaks into e2e) | 1 |

**P1 also confirmed and widened the Phase 2 pattern-6 finding.** Three tests stayed green under P1:
`test_a_changed_test_does_not_leak_into_another_tier`,
`test_a_changed_test_in_a_nonexistent_package_selects_nothing`, and
`test_a_deleted_test_is_not_handed_to_pytest`. All assert `== []`, so all pass equally well when
`_tier_relative` returns `None` for every input — each is fail-open alone. Each has a
non-empty-asserting sibling that went red, so the suite is sound *as a suite*, but only as a suite.
Recorded rather than restructured: a future edit deleting a sibling would silently gut its partner.

Residue check after restore: `grep PROBE` over both files returns nothing; `git diff --stat` shows
the intended change only.

## Phase 7.5 outcome — two defects found and fixed (option A)

The adversarial pass found the fix **incomplete in `domain` scope**, which none of U1–U4 touched:
**R13** (a test directly under `tests/e2e/` contributed nothing — the same defect class, one tier
over, affecting four files) and **R12** (a `capabilities/` test resolved to every capability while
the source route resolved precisely). User chose **option A**: fix both, extract to make room.

That extraction is `scripts/_changed_file_mapping.py`. `UsageError` deliberately stayed behind —
a second module loading `_story_resolution.py` by path would mint a second class of that name which
no caller's `except` would catch.

**A negative-control story caught a bug in the R13 fix itself.** A bare *source* relative also
reaches the tier-root branch, so `src/specweaver/conftest.py` selected the unrelated
`tests/e2e/conftest.py` purely because that file exists. Written before the fix, red on the first
green run, now guarded by a `test_` name check and probe P7.

**R6 fired too, and was right.** The new class was first called `TestDomainScopeForChangedTests` —
a behaviour grouping, not a subject — and SF-03's own ratchet blocked it at `scripts: 26 -> 27`.
Renamed `TestPathsForAtDomainScope`. A gate this ticket shipped three sub-features ago catching this
ticket is the cheapest possible evidence that it works.

## Deviations from the approved plan

- **U3 became a source change** (above).
- **`_blocked_reason`'s docstring was trimmed** after the first version took `tests.py` to 597/600.
  Finding A1 exists precisely to stop this file creeping to the ceiling; spending 12 of its
  remaining 15 lines and saying nothing would have been the failure the finding predicts.
- **`tests.py` was extracted after all, reversing Finding A1's recommendation.** A1 said defer it to
  the closure ticket; the R13/R12 fix pushed the file over 600 and the user chose option A. 566 now.
  Recorded as a deliberate reversal so the plan does not quietly disagree with what shipped.
- **`testing_guide.md` gained a commit-gate section.** Not in the plan. The guide documented bare
  `pytest` and never mentioned `scripts/tests.py` at all, so a developer reading it would not know
  the gate exists. The wider staleness (raw `ruff check`, a module path that no longer exists) is
  flagged in a note rather than fixed — that is a whole-guide refresh, not this boundary's work.

## Known follow-ups

- **The selector's root cause is still open — now at four instances, not two.** SF-01 found
  `scripts/` had no mirror; SF-04 found a tests-only change selects nothing; Phase 7.5 found R13 and
  R12 in `domain` scope. `paths_for` was built assuming every change is source-shaped, and each
  instance has been found by something breaking. **Nothing enumerates the (tier × scope ×
  change-shape) space**, so the next unexamined cell will be found the same way. A table-driven case
  matrix over that space would have caught all four at once; that is the closure ticket's job, and
  the plan's §Finding now says so.

## Next

CB-2 — the five structural invariants in `tests/unit/test_architecture.py`, currently stashed so
they could not flatter this boundary's gate. Ledger stays RED until CB-3.
