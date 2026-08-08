# Task List: TECH-025 SF-03 — Unit Test Class Naming Ratchet

- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf03_implementation_plan.md
- **FR**: FR-8 — a unit test class names the class or function under test, ratcheted
- **Commit boundaries**: 1

## Adversarial test matrix

| Bucket | Tests |
|---|---|
| Happy path | T1 names a real class · T2 names a real function · T3 the prefix case (stem inside symbol) |
| Boundary / edge | T4 behaviour-grouping name counted · T5 non-`Test` classes ignored · T6 `compare()` silent when a count falls · T7 `compare()` reports a rise · T12 5-char stem passes, 4-char does not |
| Graceful degradation | T8 unparseable file does not abort the census · T9 missing baseline reported, not crashed on |
| Hostile / wrong input | T10 empty stem (`class Test`) counted, not passed · T11 short accidental stem (`TestGet`, matched by 99 symbols) counted |
| Regression | T13 the live tree matches the committed baseline exactly |

T10 and T11 both **fail open** without their guard: the rule would accept the worst names while
reporting a healthy count.

## Tasks

- [x] **T-A — Red: the predicate.** T1–T5, T10, T11, T12 against the naming predicate.
  - Test: `[MODIFY] tests/unit/scripts/test_check_conventions.py`
- [x] **T-B — Green: predicate + census.** Symbol table from `src/` + `scripts/`; bidirectional
      containment with stem length ≥ 5 on the reverse direction and empty stem rejected; census
      counted per top-level `tests/unit/` directory. Reuses `_snake()` from SF-02.
  - Source: `[MODIFY] scripts/check_conventions.py`
- [x] **T-C — Red: the ratchet.** T6, T7, T9 against `load_baseline` / `compare`.
  - Test: same file
- [x] **T-D — Green: baseline helpers.** Copy the shape from `check_suppressions.py`:
      `{_comment, counts, total}`, `--update-baseline`, `compare()` returning only categories that
      grew.
  - Source: `[MODIFY] scripts/check_conventions.py`, `[NEW] scripts/baselines/test_class_naming.json`
- [x] **T-E — Register the gate.** Mirror `suppressions` exactly: scope row
      `{"cb": "all", "sf": "all", "feature": "all"}`, a `_test_class_naming` argv builder, and a
      `Check(...)` entry. T13 pins the live tree against the committed baseline.
  - Source: `[MODIFY] scripts/quality.py`
- [x] **T-F — Probe.** Break the minimum-length guard and confirm T11/T12 go red; break the
      empty-stem rejection and confirm T10 goes red. Restore, verify zero residue.
- [x] **T-G — Verify.** `quality.py cb --only test_class_naming` green on arrival; full suite.

## Commit boundary CB-1

All tasks. The baseline is generated from the tree as it stands, so unlike SF-02 there is nothing
to be red about — this sub-feature deliberately fixes nothing (plan §Decisions Q4 note).

## Pre-commit progress

- [x] **Phase 1 - Architecture.** No violations. `scripts/` + `tests/` + one baseline file; zero
      `src/`; `tach check` validated.
- [x] **Phase 2 - Test gap.** `useless_asserts` + `test_basenames` pass repo-wide.
- [x] **Phase 3 - Implement missing tests.** `TestWholeTestTreeInScope` added after the probe (below).
- [x] **Phase 4 - Test suite.** Full suite **6308 passed, 19 skipped** (6284 + 24).
- [x] **Phase 5 - Quality.** 10 of 12. `complexipy` and `cycles` chronic; `file_sizes` green after
      the extraction.
- [x] **Phase 6 - Documentation.** R6 documented in `check_conventions.py`'s docstring ("Five
      rules" -> "Six"); rationale lives in the sibling module.
- [x] **Phase 7 - Walkthrough.** `TECH-025_sf03_walkthrough.md`.
- [x] **Phase 7.5 - Red/Blue.** Three findings, below.

## What the probes caught

**1. R6 was not running in the gate at all — every gate reported green.** The first wiring keyed on
"no paths were given" as the signal for a repo-wide run. That looked right and was wrong:
`quality.py` ALWAYS passes paths — the tree roots at `cb`, individual changed files at `quick` — so
the census never executed. Lowering a baseline count by one produced *no* failure. Fixed to key on
the `tests/` tree root being in scope, and re-probed: red at `cb`, silent at `quick`. Pinned by
`TestWholeTestTreeInScope`, whose docstring records that no test would have caught this — only the
probe did.

**2. Both fail-open guards bite.** Removing the empty-stem rejection and the minimum-length guard
turned exactly the three guard tests red, and nothing else.

**3. The census keyed on filenames.** Files directly under `tests/unit/` produced keys like
`test_logging_rollout.py` in a table of directories — and gave each such file its own
independently-ratcheting category. Caught by reading the generated baseline. Now grouped under `.`.

## Deviations from the approved plan

- **Plan §3 said register a `test_class_naming` gate in `quality.py`. It does not.** Adding it took
  `quality.py` from 595 to 607 lines, over the 600 ceiling. Since the existing `conventions` check
  is already diff-scoped at `quick` and repo-wide at `cb`/`sf`/`feature`, R6 folds into it and needs
  no new gate entry, no `quality.py` change, and no update to its pinned expectation table. Better
  wiring, found by the size gate.
- **R6's implementation lives in `scripts/_test_class_naming.py`**, not in `check_conventions.py`.
  That file went to 614 lines. `check_conventions.py` re-exports the whole surface, so Q3's intent
  holds — one place to look — while the repo-wide census sits behind its own seam, matching
  `_refactor_diff_safety.py` and `_story_resolution.py`.
