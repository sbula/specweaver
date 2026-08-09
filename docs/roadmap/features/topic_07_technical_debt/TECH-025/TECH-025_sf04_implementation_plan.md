# Implementation Plan: Registry IDs Leaking Into Proofs [SF-04: TECH-001 FR Ledger]

- **Feature ID**: TECH-025
- **Sub-Feature**: SF-04 — TECH-001 FR Ledger
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf04_implementation_plan.md
- **Status**: APPROVED (2026-08-08)

> Bare `FR-N` below means **TECH-025's** requirement. TECH-001's are always written qualified —
> `TECH-001 FR-7`. This plan is about FR numbering, so the qualification is not optional.

## Overview

`check_fr_coverage.py TECH-001` reports eight requirements with no plan that owns them and no test
that proves them. The substance is not in doubt — TECH-001's declared `Verifiable Proof` passes and
its circular-dependency claim is independently verified — but the design→proof link was never made.

SF-04 makes it, and fixes an orphan found during TECH-025's design: **TECH-001 FR-7 and FR-8 belong
to no sub-feature at all.**

**FRs**: FR-1 (close TECH-001's ledger), FR-4 (adopt its orphaned requirements).

## Research Notes

**R1 — The plan side is emptier than a naive grep suggests, and the difference matters.**
`grep -o 'FR-[0-9]*'` reports `FR-1`/`FR-2` in three of TECH-001's four plans. Every one of those is
a substring of **`NFR-1`**, **`NFR-2`** or **`NFR-6`**. The gate's regex carries a `(?<![\w-])`
lookbehind precisely to exclude them, so the truth is:

| Plan | Genuinely cites |
|---|---|
| `TECH-001_sf01_implementation_plan.md` | *nothing* |
| `TECH-001_sf02_implementation_plan.md` | *nothing* |
| `TECH-001_sf03_implementation_plan.md` | `FR-6` |
| `TECH-001_sf04_implementation_plan.md` | `FR-9` |

Anyone auditing this with `grep` will reach the wrong conclusion. Use the gate.

**R2 — Test-side reality: three of eight already have a genuine proof, five do not.**

| TECH-001 FR | Claim | Existing proof | Verdict |
|---|---|---|---|
| FR-1 | standalone LLM telemetry store | `tests/unit/infrastructure/llm/test_llm_store.py` | **Genuine** — drives the store's models and constraints directly |
| FR-2 | standalone flow-state store | `tests/unit/core/flow/test_flow_store.py` | **Genuine** |
| FR-3 | standalone profile store | `tests/unit/workspace/test_workspace_store.py` | **Genuine** |
| FR-4 | domain-local `cli.py` modules | `tests/unit/graph/interfaces/test_cli_graph.py` proves *graph's* CLI works | **Insufficient** — one domain working is not decentralisation |
| FR-5 | every command discovered and mounted | — | **None** |
| FR-6 | sandbox grouped into feature directories | — | **None** (the plan cites it; no test does) |
| FR-7 | config carries zero orchestration | — | **None**. `test_core_config_has_no_cross_domain_runtime_imports` is adjacent but is FR-9's proof and asserts *imports*, not control flow |
| FR-8 | LLM factory/router take settings by DI | `tests/unit/infrastructure/llm/test_llm_factory.py` calls `create_llm_adapter(base_settings, …)` | **Partial** — exercises the DI signature, asserts nothing about the `Database` coupling that FR-8 removed |

**Five FRs need a test written.** Per NFR-3 that is the finding, not an inconvenience: tagging a
bystander would make the gate green while the traceability stayed fictional.

**R3 — The substance is verified in code**, so these are proofs of a true claim, not repairs:
`infrastructure/llm/store.py`, `core/flow/store.py`, `workspace/store.py` all exist; nine domain
`interfaces/cli.py` modules exist and `interfaces/cli/main.py` mounts every one; `sandbox/` is
grouped into feature directories; `core/config/database.py` imports only stdlib and SQLAlchemy;
`llm/factory.py` takes `SpecWeaverSettings` and `llm/router.py` a settings-provider callable, with
no `Database` reference in either.

**R3a — All five claims verified true against the live tree before planning to assert them**
(2026-08-08). A test written against a false claim is worse than no test:

- **FR-4**: nine domain `interfaces/cli.py` modules — `assurance.standards`, `assurance.validation`,
  `core.config`, `core.flow`, `graph`, `infrastructure.llm`, `workflows.implementation`,
  `workflows.review`, `workspace.project`.
- **FR-5**: `interfaces/cli/main.py` mounts **all nine**.
- **FR-6**: `sandbox/atoms/`, `sandbox/tools/`, `sandbox/commons/` are all gone.
- **FR-7**: none of `core/config/`'s six own modules imports any domain package.
- **FR-8**: neither `llm/factory.py` nor `llm/router.py` mentions `Database`.

> [!CAUTION]
> **FR-6's obvious assertion is false.** "Every feature directory carries its own layer files"
> sounds right and fails for three of nine: `execution/` and `language/` have only `core/`, `web/`
> only `interfaces/`. The claim FR-6 actually made was about *grouping* — the flat
> `atoms/`/`tools/`/`commons/` split becoming feature directories — so the test asserts that
> absence plus **at least one** layer directory per feature. Caught by measuring before writing.

**R4 — TECH-006 is the precedent for the shape of an absence proof.**
`tests/unit/interfaces/cli/test_interface_layer_boundaries.py` shows what to do when a requirement
is "delete this thing": assert the absence directly rather than hunting for a behaviour to observe.
FR-7 and FR-8 are exactly that shape.

**R5 — `tests/unit/test_architecture.py` is the natural home** for the five new tests. It already
holds this repo's structural invariants and already carries TECH-001 FR-9's citation, so all of
TECH-001's architectural claims end up provable from one file. 174 lines today; module-level
functions only, so SF-03's R6 class-naming ratchet does not apply.

**R6 — Every new test name must satisfy R5 and R6 from SF-02/SF-03.** No registry ID in any file,
class or function name; the `Proves:` docstring tag is the only place `TECH-001` may appear.

## Proposed Changes

### 1. Plan-side citations (7 requirements)

Add a citation to the plan that already owns the work. No plan gains new scope — each simply names
the requirement it delivered.

| Plan | Add |
|---|---|
| `TECH-001_sf01_implementation_plan.md` | `FR-1`, `FR-2`, `FR-3`, plus `FR-7`, `FR-8` (its §4b "Dependency Inversion" already describes exactly that work) |
| `TECH-001_sf02_implementation_plan.md` | `FR-4`, `FR-5` |

### 2. Test-side citations (3 existing proofs)

A single trailing `Proves: TECH-001 FR-N.` line in each module docstring:
`test_llm_store.py` → FR-1, `test_flow_store.py` → FR-2, `test_workspace_store.py` → FR-3.

### 3. `[MODIFY] tests/unit/test_architecture.py` — five new invariants

Written test-first; each must fail if the thing it guards is broken.

| For | Asserts |
|---|---|
| FR-4 | Every domain that owns CLI commands has an `interfaces/cli.py`, enumerated from the tree rather than hard-coded — a hard-coded list would pass after someone deleted the module *and* the list entry |
| FR-5 | `interfaces/cli/main.py` mounts every one of those modules. Derived from the filesystem and compared against what `main.py` registers, so a new domain CLI that nobody wired is a failure |
| FR-6 | The old flat `sandbox/atoms/`, `sandbox/tools/`, `sandbox/commons/` are **absent**, and every sandbox feature directory carries **at least one** recognised layer directory (`core/` or `interfaces/`) |
| FR-7 | `core/config/`'s own modules (excluding `bootstrap/` and `interfaces/`, separately-scoped boundaries) contain no orchestration — no domain imports, no DB bootstrapping. An **absence** proof, per R4 |
| FR-8 | `llm/factory.py` and `llm/router.py` name no `Database`, and their entry points accept settings. Also an absence proof |

> [!CAUTION]
> **Do not assert FR-7 by re-using FR-9's test.** They are adjacent and different: FR-9 is about
> *circular imports*, FR-7 about *orchestration living in a config module*. One test cited for both
> would mean deleting one claim's only proof the day the other is refactored — and would be exactly
> the bystander-tagging NFR-3 forbids.

### 4. `[MODIFY] TECH-001_design.md` — adopt the orphans (TECH-025 FR-4)

SF-01's `**FRs**: [FR-1, FR-2, FR-3]` becomes `[FR-1, FR-2, FR-3, FR-7, FR-8]`, with a dated note
recording that the assignment was made by TECH-025 and why SF-01 is the right owner (its plan §4b
delivered both). This is a delivered story's design; AD-4 authorises it and the note makes the edit
visible rather than silent.

## Test Plan

Unit tier. All five new tests are structural invariants over the source tree.

| # | Bucket | Story |
|---|---|---|
| T1 | Happy | Every domain with CLI commands has `interfaces/cli.py` (FR-4) |
| T2 | Happy | `main.py` mounts every domain CLI found on disk (FR-5) |
| T3 | Happy | Sandbox feature directories carry their own layer files (FR-6) |
| T4 | Boundary | The FR-4/FR-5 enumeration is derived from the tree, not hard-coded — a fixture with an unmounted module fails |
| T5 | Degradation | A module that will not parse is reported, not silently skipped — silence here means the invariant stops holding without anyone noticing |
| T6 | Hostile | FR-7: a domain import planted in a `core/config/` module is detected |
| T7 | Hostile | FR-8: a `Database` reference planted in `llm/factory.py` is detected |
| T8 | Regression | `check_fr_coverage.py TECH-001` exits 0 |

T6 and T7 are the probes for the two absence proofs — an absence assertion that cannot fail is the
easiest vacuous test to write and the hardest to spot.

## Verification

```bash
PY=.venv/Scripts/python.exe
$PY -m pytest tests/unit/test_architecture.py -v --tb=short
$PY scripts/check_fr_coverage.py TECH-001          # MUST exit 0 — the sub-feature's whole point
$PY scripts/check_fr_coverage.py TECH-002          # unchanged: still blocked, SF-05 owns it
$PY scripts/check_fr_coverage.py TECH-005          # unchanged: still blocked, SF-06 owns it
$PY scripts/quality.py cb
$PY -m pytest -n auto --tb=short -q
```

The TECH-002/TECH-005 lines are not decoration: a citation added to a shared test file could close
someone else's ledger by accident, and that would be the same false-credit defect SF-01 fixed.

## Commit Boundaries

Three, amended 2026-08-08 after the boundary gate refused SF-04's first attempt.

**CB-1 — `scripts/tests.py`: a changed test contributes its module to the scope.**

The gate blocked SF-04 with `unit scope=module (0 path(s))` — *"you changed source that nothing
mirrors"* — which was false: SF-04 changes **no** source, only tests and docs, because NFR-1 forbids
touching `src/`. `_src_relative` maps only `src/specweaver/` and `scripts/`, so a tests-only change
yields zero relatives and the tier selects nothing. **SF-05 and SF-06 are tests-and-docs by design
and hit the same wall.**

The model, chosen by the user: **a test file belongs to the module it covers**, so it contributes
that module exactly as a source file does. Union the modules from every changed file; run all tests
covering each.

| Changed | Contributes | Runs |
|---|---|---|
| `src/specweaver/core/flow/runner.py` | `core/flow` | all of `tests/unit/core/flow/` |
| `tests/unit/core/flow/test_x.py` | `core/flow` | all of `tests/unit/core/flow/` |
| both, different modules | union | both |

Union-only, so a changed test can **add** a module but never redirect or remove one — which is
precisely the danger the existing guard was written against.

> [!CAUTION]
> **`test_test_file_changes_do_not_drive_source_scoping` must invert**, and the reversal needs its
> reasoning recorded rather than a silently flipped assertion. Its rationale — *"editing a test must
> not be what decides which tests run"* — still holds: under the union model a test decides nothing,
> it contributes. Rename it for what it now proves.

Also: a changed `tests/e2e/` file must **not** leak into the unit tier (the tier is embedded in the
test's own path, unlike a source file which serves every tier), and `tests/e2e/` is organised by
top-level *domain* rather than package path. At `touched` scope a changed test resolves to itself —
the `test_{stem}*.py` glob would look for `test_test_x*.py`.

> **Approximation, stated honestly:** "a test belongs to the module it covers" is true by
> *directory*. An integration test genuinely spanning three modules maps to whichever directory it
> sits in. That is the same proxy the source side already uses, so it is consistent — but it is a
> proxy, and the code should say so.

#### CB-1 amended at its Phase 7.5 gate (2026-08-09) — `domain` scope, and the extraction

The adversarial review found the fix **incomplete in the one scope none of the Phase 2 gap stories
touched**. U1–U4 all exercise `module` or `touched`; `domain` went unexamined while the boundary
claimed to have fixed test-derived scoping generally.

| # | Defect | Resolution |
|---|---|---|
| R13 | A test directly under `tests/e2e/` has `parts[0] == <filename>`, so it matched no domain directory and contributed **nothing**. Verified live: `INT-US-21` at `cb` with only `test_cli_bootstrap_e2e.py` changed → e2e selects `[]` and the tier is marked failed. Four files affected. **The same defect class this boundary exists to remove, one tier over.** | A tier-root relative resolves to **itself**, the answer `touched` already gives |
| R12 | `tests/e2e/capabilities/core/test_x.py` resolved to `tests/e2e/capabilities` — *every* capability — while the source route resolved the same domain precisely. Safe under union-only, but the two routes disagreed about what `domain` means | `DOMAIN_CONTAINERS` stripped before taking `parts[0]`; a test asserts the two routes now agree |

**User chose option A (2026-08-09): fix both here, extract to make room.** The ~8 lines took
`tests.py` past the 600 ceiling that Finding A1 had already flagged at 594.

**The extraction: `scripts/_changed_file_mapping.py`.** `src_relative`, `tier_relative`,
`domain_parts` and `blocked_reason` moved out; `tests.py` re-exports them under the underscore names
its callers already use. The seam is *"what module does a changed file belong to"* (a pure mapping
over paths) versus *"what do I run for it"* — not a convenience split to satisfy a line count.
`tests.py` 594 → **566**.

`UsageError` deliberately did **not** move. It lives in `_story_resolution.py`, and a second module
loading that by path would create a second class of the same name that no caller's `except` would
catch — the hazard `_story_resolution`'s own docstring warns about. Scope *validation* therefore
stays with scope *resolution*.

> [!CAUTION]
> **The R13 fix needs its `test_` guard, and a guard test caught that the hard way.** A bare
> **source** relative also reaches the tier-root branch, so `src/specweaver/conftest.py` selected
> the entirely unrelated `tests/e2e/conftest.py` purely because that file exists. Written as a
> negative-control story before the fix, it went red on the first green run. An "it resolves to
> itself" branch must confirm the *itself* is a test.

Three further probes (P5 tier-root branch removed, P6 container strip removed, P7 `test_` guard
removed) each turn exactly their own assertions red. **R6 also fired**, correctly: the new class was
first named `TestDomainScopeForChangedTests`, which names a behaviour grouping rather than a
subject, and SF-03's ratchet blocked it at `scripts: 26 -> 27`. Renamed `TestPathsForAtDomainScope`.

**CB-2 — the five new invariants.** Written test-first against the live tree.

**CB-3 — citations and the orphan adoption.** Plan-side and test-side tags, TECH-001's design
updated. Turns the ledger green.

> CB-2 answers *is the claim true?* and CB-3 answers *is it linked?* Doing both at once makes a real
> proof indistinguishable from a tag. CB-1 is separate so a reviewer can see the gate change without
> the FR-citation work layered on top.

### Finding: the selection model assumes every change is source-shaped

This is the **second** time `tests.py` has blocked TECH-025 — SF-01 found that `scripts/` had no
mirror at all, and now that a tests-only change selects nothing. Both were fixed as riders because
each blocked the work in front of us, but the pattern is the conclusion: `paths_for` was built
assuming a change is a `src/` change, and TECH-025 keeps discovering that only because it is the
first ticket whose work isn't. **Recorded here for its own ticket at TECH-025's closure** — not
fixed further inline.

> **Amended 2026-08-09.** Make that the **third and fourth** time: CB-1's Phase 7.5 review found the
> same root cause twice more, in `domain` scope (R13, R12 above). Four instances of one assumption
> is no longer a pattern to record — it is the finding. The immediate defects are fixed here and the
> mapping now has its own module, but **the closure ticket still has real work**: nothing enumerates
> the (tier × scope × change-shape) space, so the next unexamined cell will be found the same way
> these four were — by something breaking. A table-driven case matrix over that space is what would
> have caught all four at once, and it is the ticket's job.
>
> The option-A decision is recorded rather than the extraction being silently absorbed: Finding A1
> had recommended deferring it, and the user overrode that to keep CB-1 complete. Anyone reading the
> diff should see a deliberate reversal, not a plan that quietly disagrees with what shipped.

## Decisions (Phase 4 gate, 2026-08-08)

| # | Decision |
|---|---|
| Q1 | **Five structural tests get written**, not five citations found. Only FR-1/FR-2/FR-3 have a genuine proof today; FR-4 is covered for one domain out of nine, FR-8 exercises the DI signature without asserting the coupling it removed, and FR-5/FR-6/FR-7 have nothing. Home: `tests/unit/test_architecture.py`. |
| Q2 | **FR-7 does not reuse FR-9's test.** Circular imports and config-held orchestration are different claims; one test cited for both loses a proof the day either is refactored. |
| Q3 | **Enumerate from the tree, never hard-code.** A fixed list passes once someone deletes the module *and* its entry. Pinned by T4. |
| Q4 | **Two boundaries.** CB-1 proves the claims (ledger still red); CB-2 links them (ledger green). Together, a real proof is indistinguishable from a tag. |
| Q5 | **TECH-001's design is edited** to give SF-01 `[FR-1, FR-2, FR-3, FR-7, FR-8]`, with a dated note naming TECH-025 as the author of the assignment. AD-4 authorises it; the note makes it visible. |
| Q6 | **All three ledgers are checked at closure.** TECH-002 and TECH-005 must stay blocked — a citation in a shared test file closing someone else's ledger is the false-credit defect SF-01 existed to fix. |
