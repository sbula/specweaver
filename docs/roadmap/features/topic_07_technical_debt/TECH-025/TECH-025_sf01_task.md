# Task List: TECH-025 SF-01 — Gate Integrity

- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf01_implementation_plan.md
- **FR**: FR-9 — stop the gate crediting fixture data
- **Commit boundaries**: 1 (CB-1 covers every task below)

## Adversarial test matrix

| Bucket | Tests |
|---|---|
| Happy path | T1 (marked file contributes nothing), T2 (unmarked control still contributes) |
| Boundary / edge | T3 (marker on last line of window), T4 (marker one line past window), T5 (predicate in isolation, incl. empty text), T8 (mixed tree — skip is per-file) |
| Graceful degradation | T6 (marked **and** undecodable file does not abort the sweep) |
| Hostile / wrong input | T7 (`# fr-coverage: fixture-database` must not count as marked) |
| Invariant | T9 (this test module contains exactly one literal `FR-<digit>` — its own `Proves:` tag) |

No bucket is vacuous for this sub-feature; all four are populated.

## Tasks

- [x] **T-0 — Red+Green: `scripts/` mirrors to `tests/unit/scripts/`.** Approved scope extension
      (plan §4). Without it this sub-feature cannot pass its own commit gate.
  - Test: `[MODIFY] tests/unit/scripts/test_tests_runner.py`
  - Source: `[MODIFY] scripts/tests.py` (`_src_relative`)
- [x] **T-A — Red: predicate tests.** T5, T3, T4, T7 against `is_fixture_data`.
  - Test: `[NEW] tests/unit/scripts/test_fr_coverage_fixture_exclusion.py` (class `TestIsFixtureData`)
  - Source: none yet — must fail on `AttributeError`
- [x] **T-B — Green: the predicate.** Marker constant, window constant, `is_fixture_data(text)`.
  - Source: `[MODIFY] scripts/check_fr_coverage.py`
- [x] **T-C — Red: sweep-integration tests.** T1, T2, T6, T8 against `cited_frs_in_tests`.
  - Test: same file (class `TestCitedFrsInTests` — names the function under test)
- [x] **T-D — Green: wire the skip.** Add the `continue` after the `story not in text` reject.
  - Source: `[MODIFY] scripts/check_fr_coverage.py`
- [x] **T-E — Red+Green: T9 self-invariant.** Assert this module holds exactly one literal `FR-<digit>`.
  - Test: same file
- [x] **T-F — Apply the marker + docstring.** Marker on line 3–4 of the checker's own test file
      (after the licence header); extend the script docstring with the marker's purpose, the
      "can only remove citations, never add one" argument (AD-8), and the rejected same-line rule (R2).
  - Source: `[MODIFY] tests/unit/scripts/test_check_fr_coverage.py`, `[MODIFY] scripts/check_fr_coverage.py`
- [x] **T-G — Probe.** Revert the `continue` and confirm exactly T1/T8 go red and no others; restore
      and verify zero residue. Mandatory per `test-quality.md`.
- [x] **T-H — Ledger verification.** `check_fr_coverage.py` for INT-US-21 (must stay 0), INT-US-24,
      TECH-006, TECH-019 (unmoved), TECH-025 (FR-9 now cited; FR-1/2/3 still absent — expected).

## Commit boundary CB-1

All tasks above. Gate: `python scripts/tests.py cb TECH-025 --kind tooling`, then the full
pre-commit skill, then HITL.

## Pre-commit progress

- [x] **Phase 1 — Architecture.** No violations. Zero `src/specweaver/` changes; `tach check` clean;
      `tests/unit/test_architecture.py` 4 passed; no import added.
- [x] **Phase 2 — Test gap.** Combined analysis in `TECH-025_sf01_precommit_review.md`.
      `quality.py cb --only useless_asserts,test_basenames` → 2 passed repo-wide. Probe performed
      and restored with zero residue.
- [x] **Phase 3 — Implement missing tests.** U1, U2, U3, I1 (user approved all). Column-0 rule
      adopted; `line.strip()` → `line.rstrip()`. 350 passed in `tests/unit/scripts/`; ruff clean.
- [x] **Phase 4 — Full test suite.** `tests.py cb TECH-025 --kind tooling` ok (DAL-C), widened with
      `--all`; full suite **6265 passed, 19 skipped** (4m19), re-run after the extraction.
- [x] **Phase 5 — Code quality.** 10 of 12 pass. `complexipy` and `cycles` fail pre-existing —
      proven by `git stash`; `file_sizes` passed without the change, so both REDs were mine and were
      fixed by extracting `_story_resolution.py` and splitting `test_refactor_diff_safety.py`.
- [x] **Phase 6 — Documentation.** `tests.py` docstring corrected (it claimed `tests/<tier>/` mirrors
      only `src/specweaver/`); plan updated with what actually shipped; walkthrough written. Roadmap
      deliberately **not** touched — TECH-025 is 1 of 7 sub-features done and stays 🔴.
- [x] **Phase 7 — Walkthrough.** `TECH-025_sf01_walkthrough.md`.
- [x] **Phase 7.5 — Red/Blue on the code.** Found two dead fixtures left by the split (`rds` in the
      runner file, `tr` in the new one) — both removed; duplicate `UsageError`; and a regex mangled
      to a literal backspace byte by a shell heredoc.
