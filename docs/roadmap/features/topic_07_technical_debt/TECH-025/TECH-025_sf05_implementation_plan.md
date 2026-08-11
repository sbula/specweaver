# Implementation Plan: Registry IDs Leaking Into Proofs [SF-05: TECH-002 FR Ledger]

- **Feature ID**: TECH-025
- **Sub-Feature**: SF-05 — TECH-002 FR Ledger
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-05
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf05_implementation_plan.md
- **Status**: DRAFT

> Bare `FR-N` below means **TECH-025's** requirement. TECH-002's are always written qualified —
> `TECH-002 FR-5`. This plan is about FR numbering, so the qualification is not optional.

## Overview

`check_fr_coverage.py TECH-002` reports **all six** requirements with no plan that owns them and no
test that cites them — a cleaner failure than TECH-001's, and a smaller one. The substance is not in
doubt: TECH-002 was re-verified in code on 2026-08-08 (explicit `ToolRegistry` in
`sandbox/registry.py`, zero `__init_subclass__` anywhere, validation layer free of sandbox imports)
and its amber status corrected back to 🟢 in `cea3548c`. This is traceability, not repair.

**FRs**: FR-2 (close TECH-002's ledger).

## Research Notes

**R1 — No orphans.** Unlike TECH-001, every row of TECH-002's FR table belongs to exactly one
sub-feature: SF-1 `[FR-1, FR-2]`, SF-2 `[FR-4]`, SF-3 `[FR-3]`, SF-4 `[FR-5, FR-6]`. There is no
TECH-025 FR-4 equivalent here and no design edit is needed.

> ~~Note the plan filenames are `TECH-002_sf1_…`, not `sf01`. The gate's glob
> (`*/TECH-002/TECH-002*implementation_plan.md`) matches either; a citation added to the wrong
> guess simply would not be found.~~
>
> **Superseded 2026-08-11 — the workaround is no longer needed.** `TECH-027`'s rename landed first,
> by user decision, so `TECH-002`'s four plans are now `TECH-002_sf01_…` through `_sf04_`. Cite the
> padded names. The gate's glob still matches either, so this is about writing the citation against
> a name that will still exist, not about whether the gate finds it.

**R2 — Test-side reality: four of six have a genuine proof, one is half-covered, one has nothing.**
Every file below was read, not name-matched.

| TECH-002 FR | Claim | Existing proof | Verdict |
|---|---|---|---|
| FR-1 | `BaseTool` ABC exposing `role` + `definitions` | `tests/unit/sandbox/test_sandbox_registry.py::TestBaseTool` — ABC instantiation raises, incomplete subclass raises, conforming subclass works, empty-value boundary | **Genuine** |
| FR-2 | `ToolRegistry` registers factories and instantiates dynamically | same file, `TestToolRegistry` — happy path, missing factory, factory exception, lazy resolution, duplicate overwrite | **Genuine** |
| FR-3 | Dispatcher delegates creation to the registry | `tests/integration/sandbox/test_dispatcher_registry_delegation.py` — asserts `create_standard_set` calls `ToolRegistry.create_tools` with the right tools/role/cwd, and that grant and archetype logic survive | **Genuine** |
| FR-4 | Each domain facade inherits `BaseTool` and registers its factory | same unit file, `TestBaseToolConformance` + `TestFacadeConformance` — **parametrized over every domain tool and facade**, so a new non-conforming domain fails without anyone editing the test | **Genuine** |
| FR-5 | Handlers pre-run QA atoms and inject into `Rule.context`; rules c03/c04/c05 stop importing sandbox | **Injection half covered**: `tests/unit/core/flow/test_validation_hydrator.py`, `test_c03_context.py`, `test_c04_context.py`, `tests/integration/assurance/validation/test_c05_architecture_integration.py`. **Absence half: nothing** | **Partial** |
| FR-6 | Interface modules do not import sandbox directly | — | **None** |

**R3 — Both absence claims verified true against the live tree** (2026-08-09), before planning to
assert them. A test written against a false claim is worse than no test:

- **FR-5 (absence half)**: `grep -rn "import.*sandbox" src/specweaver/assurance/validation/` → zero
  hits. The rules read pre-hydrated results instead — c03 `context["qa_tests_result"]`, c04
  `context["qa_coverage_result"]`, c05 `context["qa_architecture_result"]` — and
  `assurance/validation/executor.py:187` is what sets `rule.context`.
- **FR-6**: `grep -rn "import.*sandbox" src/specweaver/interfaces/` → zero hits.

**R4 — `tests/unit/test_architecture.py` is the home again**, for the same reason as SF-04 (plan R5)
and now for a stronger one: SF-04 CB-2 added `test_the_invariants_below_are_reading_the_real_tree`,
so a new absence proof placed there inherits the guard that its live inputs actually exist. Placing
it anywhere else would mean re-earning that guarantee.

**R5 — The existing import-scanning helper does not fit, and should not be bent to.**
`config_orchestration_offenders()` is hard-coded to `core/config/`'s own modules and to
`DOMAIN_PREFIXES`. FR-5 and FR-6 scan *different roots* for a *different* forbidden prefix
(`specweaver.sandbox`), and FR-5 must scan recursively while the config one deliberately does not.
Generalising it to take `(root, prefixes, recursive)` is the honest move; three call sites then
share one scanner.

> [!CAUTION]
> **FR-5's scan must be recursive and FR-7's must not.** `core/config/` uses a non-recursive
> `glob("*.py")` precisely to exclude `bootstrap/` and `interfaces/`, which are separately-scoped
> and *allowed* to reach domains. `assurance/validation/` has no such carve-out — its rules live in
> `rules/code/` and `rules/spec/`, so a non-recursive scan there would inspect almost nothing and
> pass vacuously. Getting this backwards produces a green test that checks an empty set.

**R6 — A live NFR-5 violation, and a latent false credit.**
`tests/integration/sandbox/test_dispatcher_domain_conformance.py` opens with
`"""Integration tests for TECH-002 SF-2 Sandbox Domain Alignment edge cases."""` — a registry ID in
prose rather than on a `Proves:` line. It carries no `FR-N` token today, so it credits nothing *yet*;
the moment anyone adds one it silently credits TECH-002. This is the same shape as the `TECH-022`
defect SF-04 CB-3 found, caught here **before** it can pay out rather than after.

`tests/unit/sandbox/test_sandbox_registry.py:162` also carries a stale `"TDD red-phase marker for
SF-2"`. Not a registry ID, so not an NFR-5 violation — but it describes a state that stopped being
true when SF-2 shipped, and the test now passes for real. Reword while adding the citation.

## Proposed Changes

### 1. Plan-side citations (6 requirements, 4 plans)

Each plan names the requirements it already delivered. No plan gains scope.

| Plan | Add |
|---|---|
| `TECH-002_sf01_implementation_plan.md` | `FR-1`, `FR-2` |
| `TECH-002_sf02_implementation_plan.md` | `FR-4` |
| `TECH-002_sf03_implementation_plan.md` | `FR-3` |
| `TECH-002_sf04_implementation_plan.md` | `FR-5`, `FR-6` |

### 2. Test-side citations (4 existing proofs)

A single trailing `Proves: TECH-002 FR-N.` line per docstring:
`test_sandbox_registry.py` → FR-1, FR-2, FR-4 · `test_dispatcher_registry_delegation.py` → FR-3 ·
`test_validation_hydrator.py` → FR-5 (injection half).

### 3. `[MODIFY] tests/unit/test_architecture.py` — two new invariants

Written test-first.

| For | Asserts |
|---|---|
| TECH-002 FR-5 | No module under `assurance/validation/` imports `specweaver.sandbox` — recursive |
| TECH-002 FR-6 | No module under `interfaces/` imports `specweaver.sandbox` — recursive |

Generalise the existing config scanner to take a root, a forbidden-prefix tuple and a recursion
flag; keep `config_orchestration_offenders` as a thin caller so FR-7's non-recursive, domain-prefix
behaviour is unchanged and its four synthetic probes still pass untouched.

### 4. `[MODIFY]` the two docstrings from R6

Remove the registry ID from `test_dispatcher_domain_conformance.py`'s prose; reword
`test_sandbox_registry.py`'s stale red-phase marker.

## Test Plan

Unit tier, plus the integration proofs already cited.

| # | Bucket | Story |
|---|---|---|
| T1 | Happy | The validation layer imports no sandbox module (FR-5 absence half) |
| T2 | Happy | The interfaces layer imports no sandbox module (FR-6) |
| T3 | Boundary | The generalised scanner is **recursive** here — a planted import in a nested `rules/code/` module is found, which a non-recursive scan would miss |
| T4 | Boundary | `config_orchestration_offenders` still behaves non-recursively — a domain import in `core/config/bootstrap/` stays out of scope |
| T5 | Hostile | A planted `specweaver.sandbox` import in a validation module is detected |
| T6 | Hostile | A planted `specweaver.sandbox` import in an interfaces module is detected |
| T7 | Degradation | An unparseable module raises rather than being silently skipped |
| T8 | Regression | `check_fr_coverage.py TECH-002` exits 0; TECH-001 stays 0; TECH-005 stays 1 |

T3 and T4 are one decision seen from both sides: the recursion flag must be *proven* to differ
between the two callers, or a later tidy-up will unify them and quietly empty FR-5's scan.

## Verification

```bash
PY=.venv/Scripts/python.exe
$PY -m pytest tests/unit/test_architecture.py -v --tb=short
$PY scripts/check_fr_coverage.py TECH-002          # MUST exit 0 — the sub-feature's whole point
$PY scripts/check_fr_coverage.py TECH-001          # MUST stay 0 — SF-04's ledger must not reopen
$PY scripts/check_fr_coverage.py TECH-005          # MUST stay 1 — SF-06 owns it
$PY scripts/check_fr_coverage.py TECH-022          # MUST stay 1 — no new accidental credit
$PY scripts/quality.py cb
$PY scripts/tests.py cb TECH-025 --kind tooling
```

The TECH-001/005/022 lines are not decoration. SF-04 CB-3 found a live false credit created by a
story ID sitting in prose; this sub-feature adds citations to shared files and must prove it created
no new one.

## Commit Boundaries

**CB-1 — the two absence invariants.** Scanner generalised, T1–T7. Ledger stays RED: this boundary
answers *is the claim true?*

**CB-2 — citations and the NFR-5 repairs.** Plan-side and test-side tags, both docstrings fixed.
Turns the ledger green, and answers *is it linked?*

> Same split as SF-04, for the same reason: doing both at once makes a real proof indistinguishable
> from a tag. Two boundaries rather than SF-04's three, because SF-05 needs no `tests.py` rider —
> CB-1 of SF-04 already removed the wall that blocks a tests-and-docs commit.

## Open Questions for the Phase 4 Gate

| # | Question |
|---|---|
| Q1 | **Generalise the scanner, or write a second one?** Plan says generalise (R5), keeping `config_orchestration_offenders` as a thin caller so FR-7's probes are untouched. The alternative — a separate `sandbox_import_offenders` — duplicates an AST walk to avoid touching a working function. |
| Q2 | **Is `test_validation_hydrator.py` the right home for FR-5's injection citation**, or should it go on the three `c0N_context` rule tests? The hydrator is where the injection happens; the rule tests prove consumption. FR-5 claims both halves. Recommend the hydrator plus the absence test, and not tagging the rule tests — three more citations that each prove only half. |
| Q3 | **`test_sandbox_registry.py` carries three citations (FR-1, FR-2, FR-4) on one module docstring.** Per-class tags would be more precise. `TECH-006` set the per-test precedent in `test_base.py`. Recommend per-class, matching that precedent. |
