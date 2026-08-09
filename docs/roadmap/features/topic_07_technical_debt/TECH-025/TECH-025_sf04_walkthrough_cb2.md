# Walkthrough: TECH-025 SF-04 CB-2 — five structural invariants for TECH-001

- **Feature ID**: TECH-025 / SF-04 (TECH-001 FR Ledger)
- **Commit boundary**: CB-2 of 3
- **Implementation Plan**: `TECH-025_sf04_implementation_plan.md` §3, §Commit Boundaries
- **Date**: 2026-08-09

## What changed and why

CB-2 answers *is TECH-001's claim true?* — CB-3 answers *is it linked?* Split so a real proof is
distinguishable from a tag. **The ledger stays RED after this boundary, on purpose.**

Five of TECH-001's eight requirements had no test at all (FR-5, FR-6, FR-7), one was covered for a
single domain out of nine (FR-4), and one exercised the DI signature without asserting the coupling
it removed (FR-8). Per NFR-3 that is a finding, not an inconvenience: tagging a bystander would make
the gate green while traceability stayed fictional.

| Claim | Assertion |
|---|---|
| FR-4 | ≥ 9 domains own their CLI, enumerated from the tree — never a hard-coded list |
| FR-5 | every domain CLI found on disk is mounted in `interfaces/cli/main.py` |
| FR-6 | flat `atoms/`/`tools/`/`commons/` absent, and every sandbox feature carries ≥ 1 layer dir |
| FR-7 | `core/config/`'s own modules hold no domain imports **and** do no import-time DB work |
| FR-8 | `llm/factory.py` and `router.py` reference no `Database`, and the settings seam is intact |

Every helper takes a `root`, so each invariant can be driven against a synthetic tree — mutating
the real tree to probe it breaks collection rather than failing an assertion.

## Phase 2 finding B1 — four of five tests passed against a tree that did not exist

Measured by calling every helper with `Path("C:/nonexistent/tree")`:

| Helper | Real | Bogus | Vacuous? |
|---|---|---|---|
| `domain_cli_modules` | 9 | 0 | no — the count assertion catches it |
| `unmounted_domain_clis` | `[]` | `[]` | **YES** |
| `sandbox_layer_violations` | `([], [])` | `([], [])` | **YES** |
| `config_orchestration_offenders` | `[]` | `[]` | **YES** |
| `llm_database_coupling` | `[]` | `[]` | partly — its test's second assertion reads `factory.py` and raises |

The plan anticipated this class and answered it with synthetic probes. Those probes work — but they
prove the **logic**, and not one of them touches `SRC_ROOT`. Nothing proved the live invocation was
pointed at anything. Since CB-3 is about to attach `Proves: TECH-001 FR-N` to these tests, shipping
as-is would have closed a ledger against tests that cannot fail — the exact fiction TECH-025 exists
to remove.

**V1** adds one guard test asserting the inputs are real. It does not *make* the three silent tests
fail; it fails **alongside** them, which is what surfaces a broken tree. One guard, not four
restatements.

## The other three repairs

- **V2** — the FR-4 floor was `>= 5` against a reality of 9, so four domains could re-centralise in
  silence. Raised to `DOMAIN_CLI_COUNT = 9`, documented as a floor (adding a domain is progress and
  must not go red).
- **V3** — `config_orchestration_offenders` checked imports only while its docstring claimed "no
  orchestration". Added `config_bootstrapping_offenders`: import-time DB work, plus reaching for the
  `bootstrap/` package where that work legitimately lives.
- **V4** — `"Database" in source` also fires on `DatabaseError` and on the word in a comment.
  Resolved through the AST instead.

> [!CAUTION]
> **A blanket "no module-level calls" rule for V3 would have been false against correct code.**
> Measured first: `logging.getLogger`, `re.compile` and `frozenset` all run at module scope in the
> six real config modules. The rule matches callee names against explicit hints instead. This is
> the same trap plan R3a caught for FR-6.

## Two bugs my own control tests caught

1. **`ast.walk` descended into function bodies**, so "import time" included every method —
   `database.py` reported six false offenders. Caught by
   `test_database_work_inside_a_function_is_not_import_time`, written as a control *before* the
   rule. Fixed with `_import_time_statements()`, which skips function and method bodies but keeps
   class bodies, since a class attribute really does execute on import.
2. Confirmed in CB-1 too — the pattern is that the negative control, not the positive test, is what
   finds the bug.

## Test results

| Tier | Scope | Paths | Result |
|---|---|---|---|
| unit | module | `tests/unit` | **5568 passed, 16 skipped** (1m42) |

The whole unit tier, because `tests/unit/test_architecture.py` sits at the tier root — the exact
behaviour CB-1's U4 pinned. First live demonstration of CB-1 working.

`tests/unit/test_architecture.py`: 16 → **22 tests**.

## Quality results

| Gate | Result |
|---|---|
| `quality.py cb` | 10 ok, 1 skip, 2 FAIL — `complexipy` 97, `cycles` 4 |
| `quality.py doc` | 3/3 ok |

Same two chronic failures as CB-1, at the same recorded baselines, and for the same reason: both
scan `src` only and this boundary changes zero `src` files.

## Probes

| Probe | Defect reintroduced | Red |
|---|---|---|
| Q1 | `SRC_ROOT` pointed at a nonexistent directory | **3** — V1's guard, the CLI count, the LLM settings assertion |
| Q4 | LLM coupling back to a substring match | 1 |
| Q2 | `DOMAIN_CLI_COUNT` floor back to 5 | **0** |
| Q3 | the bootstrapping assertion removed | **0** |

**Q2 and Q3 finding nothing is itself the honest result, and worth stating.** Weakening a live-tree
*absence* assertion cannot be detected while the tree is healthy — there is no violation present for
the weaker rule to miss. What is provable is the helper logic, and that is: the counting helper is
pinned by `test_the_root_cli_package_is_not_counted_as_a_domain`, and the bootstrapping helper by
four synthetic tests including two negative controls. Recorded rather than papered over, because
"the probe passed" and "the probe could not apply" are different facts.

## HITL gate decisions

| Gate | Presented | Decision |
|---|---|---|
| **Phase 2** | `TECH-025_sf04_precommit_review_cb2.md`: no architecture violations; B1 (critical, measured), B2, B3; stories V1–V4 | User: *"V1-V4, and run the probe"* — all four, no descoping |

No gate bypassed. One addition beyond the stories, flagged for review: **pattern 8 was added to
`test-quality.md`** (below).

## Documentation

- **New vacuous-proof pattern 8, "Subject never located"**, in
  `specweaver-pre-commit/references/test-quality.md`, with the two references to "seven patterns"
  updated in `phase-2-test-gap.md` and `specweaver-dev/SKILL.md`. B1 is a general failure mode the
  catalogue did not have: pattern 3 covers a test that never *runs*, this one runs and reports clean
  because its subject resolved to nothing.
- `.claude/` and `.agents/` are **the same tree** via a junction, so the three files were edited
  once, not twice. `grep -r` over `.claude/` is blind to it; the copies were checked by explicit
  path with a positive control. `skill_sync` green.

## Next

CB-3 — plan-side and test-side citations plus the orphan adoption of TECH-001 FR-7/FR-8. That is the
boundary that turns the ledger green, and the one AD-4's delivered-story waiver applies to.
