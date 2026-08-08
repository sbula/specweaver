# Walkthrough: TECH-025 SF-03 — Unit Test Class Naming Ratchet

- **FR**: FR-8 — a unit test class names the class or function under test, ratcheted
- **Commit boundary**: 1 of 1
- **Date**: 2026-08-08

## What changed and why

SF-02 stopped registry IDs appearing in test names. SF-03 answers the other half of the same
question — *does the name say what is under test?* — for unit test classes.

| File | |
|---|---|
| `scripts/_test_class_naming.py` | NEW — R6: symbol table, predicate, census, baseline I/O, ratchet |
| `scripts/check_conventions.py` | Loads and re-exports R6; `--update-naming-baseline`; runs the census when the whole `tests/` tree is in scope; R6 documented |
| `scripts/baselines/test_class_naming.json` | NEW — 278 classes across 10 directories, frozen |
| `tests/unit/scripts/test_check_conventions.py` | 24 tests added |

**The rule matches in both directions**, because both occur legitimately: `TestToolRegistry`
*contains* its symbol, while `TestRegistryIdsInNames` is *contained by*
`check_registry_ids_in_names` — the `check_` prefix is not part of the subject, and every gate
script here is named that way. One-way matching would have rejected the test class written for
SF-02's own rule.

## The definition was chosen by measurement, not preference

Four candidates, measured across all 958 unit test classes:

| Definition | Flagged | Why not |
|---|---|---|
| one-way containment | 305 | False positives — rejects `TestRegistryIdsInNames` |
| matches any identifier in the file | 15 | **Vacuous** — `TestDegradation`, `TestRatchet`, `TestLcom4` all pass |
| matches the mirrored source module | 107 | **74% blind** — 705 classes have no mirrored module |
| **bidirectional** | **278** | 8 of 8 spot-checks correct |

## Three defects caught, none by a test

**1. R6 was not running in the gate at all.** The first wiring used "no paths were given" as the
signal for a repo-wide run. It looked right and was wrong: `quality.py` **always** passes paths —
the tree roots at `cb`, individual changed files at `quick` — so the census never executed and every
gate reported green. Lowering a baseline count by one produced no failure whatsoever.

Fixed to key on the `tests/` tree root being in scope. Re-probed: red at `cb`, silent at `quick`.
`TestWholeTestTreeInScope` now pins it, and its docstring records that **no test would have caught
this — only the probe did.**

**2. Two fail-open guards.** An empty stem (`class Test:`) is contained by *every* symbol; a short
stem passes by accident — `Get` is contained by 99 real symbols, `Run` by 76, `Add` by 22. Both
would have let the census report a healthy number while accepting the least informative names in
the repo. Guards: reject empty stems, require length ≥ 5 for the reverse direction. Measured at
0/5/6/8; 5 is the least restrictive value with zero spot-check misses.

**3. The census keyed on filenames.** Files directly under `tests/unit/` produced keys like
`test_logging_rollout.py` inside a table of *directories*, and each got its own independently
ratcheting category. Caught by reading the generated baseline. Now grouped under `.`.

## Two deviations from the approved plan

- **No `test_class_naming` gate was added to `quality.py`.** Plan §3 said to add one; doing so took
  `quality.py` from 595 to 607 lines, past the 600 ceiling. The existing `conventions` check is
  already diff-scoped at `quick` and repo-wide at `cb`/`sf`/`feature` — exactly R6's requirement —
  so it folds in with no new gate entry, no `quality.py` change, and no edit to its pinned
  expectation table. The size gate found better wiring than the plan had.
- **R6 lives in `scripts/_test_class_naming.py`.** `check_conventions.py` hit 614 lines. It
  re-exports the whole surface, so Q3's intent holds — one place to look — while the repo-wide
  census sits behind its own seam, matching `_refactor_diff_safety.py` and `_story_resolution.py`.

## An SF-02 escape, found and fixed here

Two dangling references survived SF-02's CB-2 **in the committed tree**, and this sub-feature's
final audit caught them:

| File | Why it escaped |
|---|---|
| `docs/dev_guides/scenario_pipelines.md` | The sweep **did** update it, but CB-2 staged with `git add -A -- tests scripts docs/roadmap` — which excludes `docs/dev_guides/`. The fix was written and never committed |
| `task.md` (repo root) | Never swept at all: the sweep's roots were `docs/`, `scripts/`, `tests/`, `.agents/`, `.claude/`, and nobody thought of a file at the repository root |

**The lesson is about the verification, not the sweep.** SF-02's NFR-6 check reported "zero stray
references" and was correct — about the **working tree**. It never looked at what was actually
committed, so a staging mistake was invisible to it. The audit that found these runs over the whole
repo from the root and compares against `HEAD`, which is the only version that matters.

Both are fixed in this commit. A repo-wide re-audit now reports **zero** stray old-name references
anywhere outside TECH-025's own rename record.

## Results

| | |
|---|---|
| `tests/unit/scripts/` | 393 passed |
| Full suite | **6308 passed, 19 skipped** (6284 + 24) |
| Quality gate | 10 of 12; `conventions` green including R6 |
| Baseline | 278 across 10 directories |

`complexipy` and `cycles` remain chronic (TECH-023 / TECH-024); neither offender list contains a
file this sub-feature touched.

## What this sub-feature deliberately does not do

**It fixes nothing.** 278 classes keep names that do not say what they test; the ratchet only
guarantees the number never rises, per directory. That was design AD-6's choice, reaffirmed at the
Phase 4 gate, and the measurement supports it — but the honest reading is that if the follow-up
sweep never runs, this makes the situation *permanent-looking* rather than visible. The sweep ticket
is minted at TECH-025's closure so it can cite the final baseline.

## HITL gates

| Gate | Decision |
|---|---|
| Plan Phase 4 | All proposals: bidirectional definition, per-directory ratchet, R6 in `check_conventions`, sweep ticket at closure, unit tier only, baseline authoritative over the design's stale 292 |
| Plan Phase 5 | Approved after Red/Blue added the length guard and empty-stem rejection (275 → 279 expected; landed at 278) |
| Dev Phase 2 | Task list approved, no blocker |
