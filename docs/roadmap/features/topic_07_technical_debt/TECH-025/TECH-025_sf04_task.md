# Task List: TECH-025 SF-04 — TECH-001 FR Ledger

- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf04_implementation_plan.md
- **FRs**: FR-1 (close TECH-001's ledger) · FR-4 (adopt its two orphaned requirements)
- **Commit boundaries**: 3

> Bare `FR-N` is **TECH-025's**. TECH-001's are written qualified — `TECH-001 FR-7`.

## Adversarial test matrix

Two matrices, because CB-1 and CB-2 test different things.

**CB-1 — the selector change (`scripts/tests.py`)**

| Bucket | Tests |
|---|---|
| Happy path | T-a1 a changed test contributes its own module · T-a2 source and test changes union |
| Boundary / edge | T-a3 `touched` scope resolves a test to itself · T-a4 an e2e test maps to its domain |
| Graceful degradation | T-a5 a deleted test is not handed to pytest · T-a6 a test in a package with no mirror selects nothing |
| Hostile / wrong input | T-a7 a changed e2e test must not leak into the unit tier |

**CB-2 — the five structural invariants (`tests/unit/test_architecture.py`)**

| Bucket | Tests |
|---|---|
| Happy path | T1 domain CLIs exist (TECH-001 FR-4) · T2 all are mounted (FR-5) · T3 sandbox grouped by feature (FR-6) · plus FR-7 and FR-8 absence proofs |
| Boundary / edge | T4 the enumeration is derived from the tree — the root `interfaces/cli/` package is not counted as a domain |
| Graceful degradation | covered by T5 below; a synthetic tree with no `sandbox/` returns empty rather than raising |
| Hostile / wrong input | T6 a domain import planted in a `core/config/` module is detected · T7 a `Database` reference planted in `llm/factory.py` is detected · plus an unmounted CLI and a layerless sandbox feature |
| Regression | T8 `check_fr_coverage.py TECH-001` exits 0 (lands at CB-3, not CB-2 — see below) |

The synthetic-tree half is the point, not decoration: every one of the five invariants is an
absence proof, and an absence proof nobody has watched fail is indistinguishable from one that
*cannot* fail. Each helper takes a root so it can be driven against a `tmp_path` tree — mutating
the real tree to probe it breaks collection instead of failing an assertion.

## Tasks

- [x] **T-A — Red: the selector.** T-a1..T-a7 against `paths_for`. `test_test_file_changes_do_not_drive_source_scoping` inverted and renamed (its rationale still holds — see plan §CB-1).
  - Test: `[MODIFY] tests/unit/scripts/test_tests_runner.py`
- [x] **T-B — Green: the selector.** `_tier_relative()` maps a changed test to its module for THIS
      tier only; `_scoped_paths()` extracted so source- and test-derived relatives run the same
      machinery; the two sets are UNIONED so a test can add a module, never redirect one.
  - Source: `[MODIFY] scripts/tests.py`
- [x] **T-C — Red: the five invariants.** Written against the live tree and the synthetic probes.
  - Test: `[MODIFY] tests/unit/test_architecture.py`
- [x] **T-D — Green: the invariant helpers.** `domain_cli_modules`, `unmounted_domain_clis`,
      `sandbox_layer_violations`, `config_orchestration_offenders`, `llm_database_coupling` — each
      root-parameterised.
  - Source: none. NFR-1 forbids touching `src/`; the "implementation" here is the assertion logic.
- [ ] **T-E — Plan-side citations.** `TECH-001_sf01` gains FR-1/2/3/7/8; `TECH-001_sf02` gains FR-4/5.
  - Docs: `[MODIFY]` TECH-001's SF-01 and SF-02 implementation plans
- [ ] **T-F — Test-side citations.** `Proves: TECH-001 FR-N.` in `test_llm_store.py` (FR-1),
      `test_flow_store.py` (FR-2), `test_workspace_store.py` (FR-3).
- [ ] **T-G — Adopt the orphans (FR-4).** TECH-001's design: SF-01 `[FR-1, FR-2, FR-3]` →
      `[FR-1, FR-2, FR-3, FR-7, FR-8]`, with a dated note naming TECH-025 as the author (AD-4).
- [ ] **T-H — Verify.** `check_fr_coverage.py TECH-001` exits 0; TECH-002 and TECH-005 stay
      blocked (plan Q6 — a citation in a shared file closing someone else's ledger is the
      false-credit defect SF-01 existed to fix); `quality.py cb`; full suite.

## Commit boundaries

**CB-1 — T-A, T-B.** The selector fix, alone, so a reviewer sees the gate change without the
FR-citation work layered on it. Rider: the boundary gate refused SF-04's first attempt with
`unit scope=module (0 path(s))` because a tests-only change resolved to nothing.

**CB-2 — T-C, T-D.** The five invariants. Ledger still RED on purpose: this boundary answers
*is the claim true?*

**CB-3 — T-E, T-F, T-G.** The citations and the orphan adoption. Answers *is it linked?* and turns
the ledger green. Split from CB-2 so a real proof is distinguishable from a tag.

## Pre-commit progress

### CB-1

- [x] **Phase 1 - Architecture.** No violations. `tach check` green; zero `src/`; `scripts/` has no
      `context.yaml`. Finding A1: `tests.py` at 585/600 — trajectory noted, extraction left to the
      closure-time ticket.
- [x] **Phase 2 - Test gap.** `useless_asserts` + `test_basenames` green repo-wide. Four gaps
      (U1–U4) + Finding A2. Written to `TECH-025_sf04_precommit_review.md`.
- [x] **Phase 3 - Implement missing tests.** U1–U4 implemented (9 new tests, 74 in the file).
      U3 became a source change too: `_blocked_reason()` now computes WHICH cause applies instead
      of asserting the source one unconditionally. Four probes run, all bite — see below.
      `quality.py quick --only ruff` green. `tests.py` 594/600 (trimmed back from 597).
- [x] **Phase 4 - Test suite.** `tests.py cb TECH-025 --kind tooling` → unit @ module,
      `tests/unit/scripts`, **408 passed** (399 before the 9 new). DAL-C, TECH baseline.
- [x] **Phase 5 - Quality.** `cb`: 9 ok, 1 skip, **2 FAIL — both chronic and both provably not
      mine** (below). `doc`: 3/3 ok.
- [x] **Phase 6 - Documentation.** New pattern 26 in `special_patterns_and_adaptations.md`
      (union-only contribution in change-driven selection). New commit-gate section in
      `testing_guide.md`, which had never mentioned `scripts/tests.py`; its wider staleness flagged
      in a note, not fixed. No architecture doc change (zero `src/`), no roadmap change (SF-04 is
      not complete at CB-1).
- [x] **Phase 7 - Walkthrough.** `TECH-025_sf04_walkthrough.md`.
- [x] **Phase 7.5 - Red/Blue. Two findings, both FIXED (user chose option A).** R13 (critical): a
      changed test directly under `tests/e2e/` contributed nothing at `domain` scope — the same
      defect class this boundary targets, one tier over, affecting four files. R12 (minor):
      capabilities tests resolved to the container rather than the domain. Seven other attacks
      found nothing. Fix + extraction to `scripts/_changed_file_mapping.py`; `tests.py` 594 → 566.
      Probes P5–P7 added. Re-ran every gate after the change: **413 passed**, `conventions` green
      after an R6-mandated class rename, `doc` 3/3, the same two chronic failures and no others.
      Commented in the implementation plan (§CB-1 amendment + §Finding).

#### The two Phase 5 failures

`complexipy` **97 offenders** and `cycles` **4** — identical to the figures the roadmap records for
`TECH-023` ("fell 98 → 97 from TECH-006 alone") and `TECH-024` (validation registry, llm
rate-limit/factory, API layer, and the 6-module `core.flow` one). Not deferred on the usual "it was
already broken" excuse, which this repo rejects; deferred because **both checks scan `src` only and
this boundary changes zero `src` files** (`git status --porcelain -- src/` → 0 lines), so neither
can be attributable to it and neither is fixable from inside it without breaking NFR-1. The roadmap
also sequences `TECH-023` **last** and forbids it sharing a working tree with `TECH-024`, so doing
either here would destroy the attribution those tickets depend on.

`class_health` skipped for the same reason — "nothing in scope" is correct, not a miss.

> Tooling note: `complexipy` crashes with a Unicode traceback when its stdout is redirected to a
> file on Windows (it cannot encode `❌`). Counted through `quality.py`, which captures it safely.

### CB-2

- [ ] Phases 1-7.5

### CB-3

- [ ] Phases 1-7.5

## What the CB-1 probes caught

Four probes, each reintroducing one specific defect. All four bite, and the blast radius is the
predicted one every time.

| Probe | Defect reintroduced | Red |
|---|---|---|
| P1 | `_tier_relative` returns `None` for everything | **6** — every test-derived assertion, and *only* those. All source-derived ones stayed green, which is the union model's whole claim |
| P2 | suffix guard removed (`tests/unit/scripts/fixture.yaml` accepted) | 1 — U1, alone |
| P3 | unknown scope returns `set()` instead of raising | 1 — U2, alone |
| P4 | the OLD unconditional "you changed source that nothing mirrors" message | **4** — including the one named for the defect |

**P1 also confirmed the Phase 2 pattern-6 finding.** Three tests stayed GREEN under P1 that assert
`== []`: `test_a_changed_test_does_not_leak_into_another_tier`,
`test_a_changed_test_in_a_nonexistent_package_selects_nothing` and
`test_a_deleted_test_is_not_handed_to_pytest`. All three pass equally well when `_tier_relative`
returns `None` for *every* input — they are fail-open on their own. Each has a non-empty-asserting
sibling that went red, so the suite is sound as a suite; recorded because a future edit that
deletes a sibling would silently remove the only thing making its partner meaningful.

Residue check after restore: `grep PROBE` over both files returns nothing; `git diff --stat` shows
the intended 79/23 only.

## Session note (2026-08-08)

Recovered after an unacknowledged Windows reboot. T-A..T-D were already written and green in the
working tree but uncommitted, and this task list did not exist — Phase 2 was never recorded. Both
were reconstructed from the approved plan and the working-tree diff before resuming at CB-1's gate.
