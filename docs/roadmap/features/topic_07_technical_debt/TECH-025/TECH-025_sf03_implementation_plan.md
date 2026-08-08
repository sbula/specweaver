# Implementation Plan: Registry IDs Leaking Into Proofs [SF-03: Unit Test Class Naming Ratchet]

- **Feature ID**: TECH-025
- **Sub-Feature**: SF-03 — Unit Test Class Naming Ratchet
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf03_implementation_plan.md
- **Status**: APPROVED (2026-08-08)

## Overview

SF-02 stopped registry IDs appearing in test names. SF-03 addresses the other half of the same
question — *does the name say what is under test?* — for unit test classes specifically, where the
convention is that the class names the class or function it exercises.

Sweeping every existing offender is out of scope (design AD-6): the count is in the hundreds, and
many are judgement calls. This sub-feature makes the rule real for **new** classes by freezing the
current count as a ratchet that may fall but never rise, and mints a follow-up ticket for the sweep.

**FR**: FR-8.

## Research Notes

**R1 — "names the class or function under test" has no obvious mechanical definition, and three of
the four candidates are unusable.** Measured across all **958** unit test classes:

| Definition | Flagged | Verdict |
|---|---|---|
| (a) one-way: some `src`/`scripts` symbol is a substring of the class stem | 305 | **False positives.** Flags `TestRegistryIdsInNames`, which correctly names `check_registry_ids_in_names` — the `check_` prefix defeats it. It would have blocked SF-02's own class |
| (b) the stem matches any identifier appearing anywhere in the test file | 15 | **Vacuous.** `TestDegradation`, `TestRatchet`, `TestLcom4`, `TestGateResolution`, `TestBatch1LoggingRollout` all pass — the exact behaviour-grouping names the rule exists to catch. They slip through because the word appears in a docstring or a local variable |
| (c) the stem matches a symbol in the mirrored source module | 107 | **Insufficient reach.** Only 253 of 958 classes have a mirrored module at all; **705 have none**, so the rule would be silent for 74% of the tree |
| **(a′) bidirectional: a symbol contains the stem, or the stem contains a symbol** | **275** | **Recommended.** Every spot-check lands correctly |

**R2 — (a′) verified against eight known cases**, four that must pass and four that must fail:

| Class | Result | Expected |
|---|---|---|
| `TestToolRegistry` | passes | ✅ names `ToolRegistry` |
| `TestIsFixtureData` | passes | ✅ names `is_fixture_data` |
| `TestRegistryIdsInNames` | passes | ✅ names `check_registry_ids_in_names` |
| `TestDegradation` | flagged | ✅ behaviour grouping |
| `TestRatchet` | flagged | ✅ behaviour grouping |
| `TestLcom4` | flagged | ✅ behaviour grouping |
| `TestGateResolution` | flagged | ✅ behaviour grouping |
| `TestBatch1LoggingRollout` | flagged | ✅ behaviour grouping |

Eight for eight. This is the evidence the definition is worth encoding; without it the rule is
either noise (a) or theatre (b).

**R3 — Current distribution of the 275**, by top-level test directory. Useful for deciding ratchet
granularity (see Q2) — a single total lets a fix in `graph` pay for a regression in `assurance`:

| Directory | Count (under definition (a), for shape) |
|---|---|
| `assurance` | 98 |
| `core` | 67 |
| `sandbox` | 59 |
| `scripts` | 29 |
| `infrastructure` | 13 |
| `interfaces` | 10 |
| `workspace` | 9 |
| `workflows` | 7 |
| `graph` | 1 |

**R4 — The ratchet mechanism already exists and should be copied, not reinvented.**
`scripts/check_suppressions.py` implements exactly this shape:

- `BASELINE_PATH = REPO_ROOT / "scripts" / "baselines" / "suppressions.json"`
- `load_baseline() -> dict[str, int] | None` — returns `None` when the file is absent
- `write_baseline(counts: Counter[str])` — writes `{_comment, counts (sorted), total}` with an
  explicit warning that the diff is meant to be reviewed
- `compare(current, baseline) -> list[tuple[str, int, int]]` — returns only categories that **grew**
- `--update-baseline` flag; positional paths are accepted and ignored, because "the ratchet is
  inherently repo-wide"

**R5 — Where the check belongs.** `check_conventions.py` owns naming rules (R1–R5) but has no
baseline concept; `check_suppressions.py` owns the ratchet but is about gate-bypasses, not naming.
See Q3.

**R6 — The count moved during this ticket.** 292 at design time, 293 after SF-02, 275 under the
recommended definition. Any number written into a document goes stale; the baseline file is the
only figure that should be treated as authoritative, and the design's "292" is already historical.

## Proposed Changes

### 1. `[MODIFY] scripts/check_conventions.py` — R6

- A predicate deciding whether a unit test class name references a `src`/`scripts` symbol, using
  bidirectional containment (R1 (a′)) after CamelCase normalisation — `_snake()` already exists
  from SF-02 and the symbol table is built the same way.

> [!CAUTION]
> **The reverse direction needs a minimum stem length, and an empty stem must be rejected outright.**
> Found by this plan's Red/Blue review, measured rather than reasoned:
>
> - An empty stem (a class named exactly `Test`) is contained by **every** symbol, so plain
>   bidirectional containment passes it vacuously.
> - Short stems pass trivially by accident: `TestGet` is contained by **99** symbols
>   (`GetCompiledSpec`, `GetActiveTasks`, …), `TestRun` by 76, `TestAdd` by 22. `TestGet`,
>   `TestAdd` and `TestTag` are exactly the uninformative names the rule should catch.
>
> Requiring **stem length ≥ 5** for the *stem-inside-symbol* direction fixes all three, at a cost of
> four extra flagged classes (275 → **279**). Tested at 0/5/6/8: length 5 is the least restrictive
> value with zero spot-check misses. The forward direction (*symbol inside stem*) needs no guard —
> symbols are already filtered to >3 characters.
- Applies to `tests/unit/` only (FR-8 says unit); integration and e2e group by scenario, not by
  unit under test, so the rule would be wrong there.
- Reports a **count**, not a per-class violation, because the ratchet is the enforcement.

### 2. `[NEW] scripts/baselines/test_class_naming.json`

Same shape as `suppressions.json`: `_comment`, `counts`, `total`. Written by `--update-baseline`.

### 3. `[MODIFY] scripts/quality.py`

Register the ratchet in the gate table alongside `suppressions`.

Pseudocode for the check, ordered cheapest-first:

```
build the symbol table once from src/ and scripts/   (classes + snake->Camel functions)
for each file under tests/unit/:
    parse; skip quietly if it will not parse
    for each ClassDef whose name starts with Test:
        stem = name without the Test prefix
        ok if any symbol contains stem, or stem contains a symbol
        else count it under its top-level directory
compare counts against the baseline; fail only on categories that GREW
```

## Test Plan

Unit tier. TECH ticket, so `TECH-017`'s integration rule does not apply.

| # | Bucket | Story |
|---|---|---|
| T1 | Happy | A class naming a real class passes (`TestToolRegistry`) |
| T2 | Happy | A class naming a real function passes (`TestIsFixtureData`) |
| T3 | Happy | The prefix case passes — stem inside the symbol (`TestRegistryIdsInNames` ↔ `check_registry_ids_in_names`) |
| T4 | Boundary | A behaviour-grouping name is counted (`TestDegradation`) |
| T5 | Boundary | Non-`Test` classes and bare functions are ignored |
| T6 | Boundary | `compare()` returns nothing when a count **falls** |
| T7 | Boundary | `compare()` returns the category when a count **rises** |
| T8 | Degradation | An unparseable file does not abort the census |
| T9 | Degradation | A missing baseline file is reported, not crashed on |
| T10 | Hostile | A class named exactly `Test` (empty stem) is counted, not passed |
| T11 | Hostile | A short accidental stem is counted — `TestGet`, though 99 symbols contain "Get" |
| T12 | Boundary | A 5-character stem passes on the reverse direction; a 4-character one does not |
| T13 | Regression | The live tree matches the committed baseline exactly |

T10 and T11 are the two that would otherwise ship broken, and neither was in the plan before the
Red/Blue pass measured them. Both fail **open** — the rule would silently accept the worst names
while reporting a healthy count.

## Verification

```bash
PY=.venv/Scripts/python.exe
$PY -m pytest tests/unit/scripts/test_check_conventions.py -v --tb=short
$PY scripts/quality.py cb --only test_class_naming     # green against the frozen baseline
$PY scripts/tests.py cb TECH-025 --kind tooling
$PY -m pytest -n auto --tb=short -q
```

## Commit Boundaries

**CB-1 (only)** — rule, baseline, gate registration, tests. The baseline is generated from the
tree as it stands, so the gate is green on arrival; unlike SF-02 there is nothing to be red about,
because this sub-feature deliberately fixes nothing.

## Decisions (Phase 4 gate, 2026-08-08)

| # | Decision |
|---|---|
| Q1 | **Bidirectional containment (a′).** Chosen on measurement, not taste: 8 of 8 spot-checks correct, where one-way containment produces false positives that would have blocked SF-02's own `TestRegistryIdsInNames`, the local-file rule is vacuous, and the mirror rule is blind to 74% of the tree. |
| Q2 | **Ratchet per top-level test directory**, same shape as `suppressions.json`. A single total would let a fix in `graph` (1 class) pay for a regression in `assurance` (98). |
| Q3 | **R6 in `check_conventions.py`**, copying the baseline helpers from `check_suppressions.py`. Naming rules belong together — someone asking "why was my test class name rejected" looks there. |
| Q4 | **Mint the sweep ticket at TECH-025's closure**, not now, so it cites the final baseline rather than a figure that has already moved three times (292 → 293 → 275). |
| Q5 | **`tests/unit/` only**, as FR-8 says. Integration and e2e classes group by scenario, not by unit under test; `TestE8ValidationFailureLoopsBack` is a correct e2e name and the rule would be wrong to touch it. |
| Q6 | **The baseline file is the only authoritative count.** The design's "292" stays as the historical measurement it was — an approved design is not rewritten to chase a number, and the drift itself is recorded in R6 above. |

> [!NOTE]
> **This sub-feature deliberately fixes nothing.** It freezes a count and defers the sweep — design
> AD-6's choice, supported by the measurement (275 classes, many of them judgement calls). The
> alternative — drop the ratchet and let one later ticket do rule-and-sweep together — was offered
> at the Phase 4 gate and declined. Recorded so a future reader does not mistake the empty
> before/after diff for an unfinished job.
