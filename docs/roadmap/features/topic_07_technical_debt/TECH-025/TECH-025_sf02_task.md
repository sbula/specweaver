# Task List: TECH-025 SF-02 — Test Naming Closure

- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf02_implementation_plan.md
- **FRs**: FR-6 (renames + references), FR-7 (widen R5, delete the allowlist)
- **Commit boundaries**: 2

## Adversarial test matrix (CB-1)

| Bucket | Tests |
|---|---|
| Happy path | T1 story-named file under `tests/integration/` flagged · T2 under `tests/unit/` flagged · T3 `_sf<N>` filename flagged · T4 story-named test **class** flagged · T5 story-named test **function** flagged |
| Boundary / edge | T6 all ten real rule-ID files pass (`c01`…`c13`, `s07`, `s12`) · T7 a subject-named file passes in every tier |
| Graceful degradation | T8 an unparseable file yields no naming violation |
| Hostile / wrong input | T9 a registry ID in a docstring or comment is **not** flagged |
| Regression | T10 the real `tests/` tree is clean after CB-2 |

## CB-1 — widen R5, delete the allowlist

- [x] **T-A — Red: invert the two existing assertions.**
      **Three, not two.** `test_the_rule_does_not_reach_outside_e2e` and
      `test_a_legacy_name_is_not_flagged` inverted to assert *flagged*;
      `test_the_legacy_list_covers_exactly_todays_offenders` is obsolete (nothing left to keep
      in step with) and its replacement -- the whole tree as the assertion -- lands in CB-2,
      because it cannot pass until the renames do.
  - Test: `[MODIFY] tests/unit/scripts/test_check_conventions.py` (`TestE2ENaming`)
- [x] **T-B — Red: the new cases.** T1–T9 above.
  - Test: same file; class renamed for the widened rule
- [x] **T-C — Green: widen the rule.** Drop the `tests/e2e/` restriction; add `_sf<N>` to
      `_STORY_ID_IN_FILENAME`; extend to test class and function names via `ast`, degrading quietly
      on `SyntaxError` like `_family_class` does; delete `LEGACY_E2E_NAMES`; rename
      `check_e2e_naming` (wrong once it spans tiers) and update its docstring, which cites a file
      CB-2 renames.
  - Source: `[MODIFY] scripts/check_conventions.py`
- [x] **T-D — Verify the gate's reach.** `quality.py cb --only conventions` must report **exactly**
      9 files + 2 function names — measured before writing this plan — and none of the 10 rule-ID
      files. This red is the deliverable of CB-1.

## CB-2 — renames and references

- [x] **T-E — `git mv` the 9 files** to the approved names (plan §1).
- [x] **T-F — Rename the 3 functions**, including the one the rule cannot catch (Q2).
- [x] **T-G — Move every reference** across `docs/`, `scripts/`, `tests/`, `.agents/`, `.claude/`.
      `.claude/` is a junction and `grep -r` returns zero inside it — enumerate explicitly and use a
      positive control before believing a clean result.
- [x] **T-H — Verify.** Zero hits for all 9 old basenames; conventions gate green; identical test
      count before and after (renames change no assertion).

## Known deviation, needs a decision at the Phase 2 gate

**CB-1 cannot pass its own pre-commit gate.** `quality.py cb` runs `conventions`, which CB-1
deliberately turns red. The pre-commit skill requires every check green before a commit. The user
approved the two-boundary split knowing CB-1 lands red; this records that the conflict is with the
*gate*, not just with taste, and that CB-1's pre-commit will report one expected failure.

## Contradicted precedent (record, do not silently flip)

`test_the_rule_does_not_reach_outside_e2e` carries the justification *"The alembic migration test
names a revision, which IS its subject."* The repo previously held a revision hash to be a
legitimate name. **Q6 overrules that**: a revision hash is as meaningless to a future reader as a
ticket id, the migration is still loaded by that id inside the test, and it is the only file in
`tests/unit/alembic/`.

## Pre-commit progress

### CB-1
- [x] **Phase 1 - Architecture.** No violations. 2 files changed, both `scripts/`+`tests/`; zero
      `src/`; `tach check` validated; `test_architecture.py` 4 passed.
- [x] **Phase 2 - Test gap.** `useless_asserts` + `test_basenames` pass repo-wide. Coverage matrix
      clean except `_snake()`, filled by U1.
- [x] **Phase 3 - Implement missing tests.** U1 added (user-approved): `_snake()` parametrized over
      all three transitions plus idempotence and empty, and a class-level rule-ID guard.
- [x] **Phase 4 - Test suite.** `tests.py cb TECH-025 --kind tooling` ok; full suite
      **6283 passed, 19 skipped**.
- [x] **Phase 5 - Quality.** 9 of 12 pass. `conventions` red **by design** (11 violations = the
      9 files + 2 function names). `complexipy` and `cycles` chronic - offender lists contain no
      file this boundary touched.
- [x] **Phase 6 - Documentation.** Module docstring said "Four rules" and documented R1-R4 only;
      R5 has existed all along and was undocumented. Now "Five rules" with R5 written up. Rule
      label corrected from "e2e named for a registry ID" to "test named for a registry ID".
- [x] **Phase 7 - Walkthrough.** `TECH-025_sf02_walkthrough.md` (CB-1 section).
- [x] **Phase 7.5 - Red/Blue.** Three probes run and restored; findings below.

### CB-2
- [x] **Phase 1 - Architecture.** No violations. Renames only; zero `src/`; `tach check` validated.
- [x] **Phase 2 - Test gap.** `useless_asserts` + `test_basenames` pass repo-wide.
- [x] **Phase 3 - Implement missing tests.** T10 landed: "no test anywhere in the tree carries a
      registry ID" -- the tree itself as the assertion, replacing the retired allowlist-parity test.
      It could not exist before the renames.
- [x] **Phase 4 - Test suite.** `tests.py cb TECH-025 --kind tooling --all` ok across all three
      tiers; full suite **6284 passed, 19 skipped** (6283 + T10; renames changed no behaviour).
- [x] **Phase 5 - Quality.** 10 of 12 pass. **`conventions` is GREEN** -- CB-1's deliberate red is
      cleared. `complexipy` and `cycles` remain chronic (TECH-023 / TECH-024).
- [x] **Phase 6 - Documentation.** 92 references moved across 36 files. TECH-025's own plan and
      design restored after the sweep over-reached into them (see below).
- [x] **Phase 7 - Walkthrough.** CB-2 section added.
- [x] **Phase 7.5 - Red/Blue.** The sweep's over-reach was the finding; see below.

## The sweep over-reached, and the guard was the diff

A blind basename replace across `docs/`, `scripts/`, `tests/`, `.agents/` and `.claude/` also
rewrote **TECH-025's own rename record** -- the plan's `Current | Proposed` table came out with
both columns identical, and Research Notes R1/R3/R5, which describe why the OLD names were
invisible to the OLD rule, were rewritten into nonsense.

Caught by reading the diff, not by any gate: every test still passed and every reference still
resolved. Both files were restored from `c34fefaa` and only the two genuinely *live* pointers in
the design (where a proof actually lives) were re-applied by hand.

**The distinction a future sweep must make:** a reference that must *resolve* moves with the file;
a reference that *describes the state before the rename* must not. TECH-025's own documents are
almost entirely the second kind -- 33 old-name occurrences remain there deliberately, and a repo
wide search confirms **zero** stray occurrences anywhere else.

**`.claude/` was walked with a positive control**, since `grep -r` returns zero inside the junction
even when matches exist: searching for a string known to be present matched 6 files, proving the
walk reached it before any clean result was believed.
