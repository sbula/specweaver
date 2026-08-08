# Implementation Plan: Registry IDs Leaking Into Proofs [SF-02: Test Naming Closure]

- **Feature ID**: TECH-025
- **Sub-Feature**: SF-02 — Test Naming Closure
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf02_implementation_plan.md
- **Status**: APPROVED (2026-08-08) — two commit boundaries confirmed; CB-1's red gate is intended

## Overview

Nine test files and three test functions are named after the story that paid for them rather than
the behaviour they protect. `check_conventions.py` R5 already forbids this and already grandfathers
six of them, with a note that reads as this sub-feature's charter: *"These are NOT grandfathered on
merit — every one of them should be renamed for its subject… each is cited by name in the
walkthroughs and integration docs of a DELIVERED story… That needs a ticket that decides both
halves together, not a drive-by rename."*

SF-02 renames them, moves every reference in the same change, and widens R5 so the rule holds in
every tier instead of only `tests/e2e/`.

**FRs**: FR-6 (rename + reference updates), FR-7 (widen R5, empty the allowlist).

## Research Notes

**R1 — Why three offenders were never candidates.** R5 inspects only paths under `tests/e2e/`
(`check_conventions.py:175`) and its regex has no `_sf<N>` alternative
(`_STORY_ID_IN_FILENAME`, line 62). So `test_dispatcher_sf2_integration.py` (integration),
`test_dispatcher_sf3_integration.py` (integration) and
`test_af60fd3509a2_tech_005_rename_tables.py` (unit) were invisible to it. The six in
`LEGACY_E2E_NAMES` were visible and explicitly excused.

**R2 — Validation rule IDs are already safe, and must stay that way.** Ten test files are named for
validation rules: `test_c01_c02_c03.py`, `test_c03_context.py`, `test_c04_context.py`,
`test_c05_architecture_integration.py`, `test_c09_traceability.py`,
`test_c12_archetype_code_bounds.py`, `test_c13_contract_drift.py`, `test_s07_test_first.py`,
`test_s12_integration.py`, `test_s12_archetype_spec_bounds.py`. These are **domain vocabulary** —
`c05` is a rule, not a ticket. The current regex misses them because its capability alternative
requires a topic word (`_(ui|sens|flow|intl|val|exec)_\d{2}_`). The danger is widening carelessly:
a `[a-z]\d{2}` style pattern would flag all ten, and the likely reaction is a fresh allowlist that
reopens the hole this ticket closes. FR-7 names the exclusion; a test pins all ten as passing.

**R3 — The checker's own docstring is one of the references.** `check_e2e_naming`'s docstring uses
`test_int_us_21_decomposition_e2e.py` as its worked example (line 167). The rule's documentation is
a reference that must move with the file.

**R4 — Dispatch is a flat per-file loop** (`check_conventions.py:356-359`): `check_grab_bag_name`,
`check_header`, `check_e2e_naming`. Adding class/function inspection means parsing AST inside the
naming check; `_family_class` (line 230) is the existing pattern for `ast.parse` with a
`SyntaxError` fallback, and it returns `None` rather than raising.

**R5 — Reference inventory** (files containing each old basename, across `docs/`, `scripts/`,
`tests/`, `.claude/`, `.agents/`):

| Old basename | Files referencing |
|---|---|
| `test_int_us_24_scenario_e2e` | 16 |
| `test_int_us_02_drafter_e2e` | 13 |
| `test_int_us_09_isolation_e2e` | 13 |
| `test_int_us_21_decomposition_e2e` | 12 |
| `test_c_exec_06_session_isolation_e2e` | 12 |
| `test_int_us_03_isolation_e2e` | 10 |
| `test_dispatcher_sf3_integration` | 5 |
| `test_af60fd3509a2_tech_005_rename_tables` | 4 |
| `test_dispatcher_sf2_integration` | 4 |

Most live in delivered stories' walkthroughs, task files and `topic_08_integration/` docs — which
design AD-4 explicitly authorises this ticket to edit.

**R6 — One offender the widened rule will still not catch.**
`test_story_block_unaffected_for_int_us_ticket` (`test_check_story_preconditions.py:83`) contains
`int_us_` with **no digit**, so `int_us_\d+` misses it. It names an ID *family*, not a story, which
is a weaker offence — but the design's inventory lists it, so it is renamed by hand here. See Q2.

**R7 — Subjects, read from each file rather than guessed.** Needed because three of the six e2e
files are all "worktree isolation" and must be told apart by what they isolate:

| File | What it actually proves |
|---|---|
| `test_int_us_09_isolation_e2e` | ONE `action: bash` step bounded to an ephemeral worktree; `pwd` inside `.worktrees/` |
| `test_c_exec_06_session_isolation_e2e` | MULTI-step run sharing ONE session worktree; step 2 sees step 1's output; one authorised reconcile |
| `test_int_us_03_isolation_e2e` | The autonomous implement loop running QA on freshly generated code, engaged by DAL auto-escalation |
| `test_int_us_02_drafter_e2e` | The interactive Drafter loop: real Drafter, real S-battery, scripted LLM + keystrokes |
| `test_int_us_21_decomposition_e2e` | Feature decomposition driven through a real HITL gate |
| `test_int_us_24_scenario_e2e` | Behavioural scenario verification: contract extraction → dual-pipeline → generated tests → arbiter |
| `test_dispatcher_sf2_integration` | Domain facades conform to `BaseTool`; `NO_ROLE` sentinel; topology pass-through |
| `test_dispatcher_sf3_integration` | `create_standard_set` delegates to `ToolRegistry` |
| `test_af60fd3509a2_tech_005_rename_tables` | The bounded-context table-prefix migration, up and down, mocked and against live SQLite |

## Proposed Changes

### 1. Renames (FR-6)

Names — **approved 2026-08-08** at the Phase 4 gate. This table is authoritative; the design's
Sub-Feature Breakdown carries only the 8-line stub, by design (see TECH-026's design/plan altitude
contract). The three isolation e2e files are distinguished by *what* they isolate, which is the
only thing that tells them apart:

| Current | Proposed |
|---|---|
| `tests/unit/alembic/test_af60fd3509a2_tech_005_rename_tables.py` | `test_table_prefix_migration.py` |
| `tests/integration/sandbox/test_dispatcher_sf2_integration.py` | `test_dispatcher_domain_conformance.py` |
| `tests/integration/sandbox/test_dispatcher_sf3_integration.py` | `test_dispatcher_registry_delegation.py` |
| `tests/e2e/capabilities/workflows/test_int_us_02_drafter_e2e.py` | `test_drafter_loop_e2e.py` |
| `tests/e2e/capabilities/workflows/test_int_us_21_decomposition_e2e.py` | `test_feature_decomposition_e2e.py` |
| `tests/e2e/capabilities/workflows/test_int_us_24_scenario_e2e.py` | `test_scenario_verification_e2e.py` |
| `tests/e2e/sandbox/test_int_us_09_isolation_e2e.py` | `test_step_worktree_isolation_e2e.py` |
| `tests/e2e/sandbox/test_c_exec_06_session_isolation_e2e.py` | `test_session_worktree_isolation_e2e.py` |
| `tests/e2e/sandbox/test_int_us_03_isolation_e2e.py` | `test_implement_loop_worktree_isolation_e2e.py` |

Functions:

| Current | Proposed |
|---|---|
| `test_exclusions.py::test_integration_orchestrator_initializes_ignores_sf4` | `test_scaffolded_ignore_file_contains_analyzer_default_dirs` |
| `test_exclusions.py::test_e2e_topological_spec_bypass_hidden_binary_sf4` | `test_compiled_spec_matches_analyzer_binary_patterns` |
| `test_check_story_preconditions.py::test_story_block_unaffected_for_int_us_ticket` | `test_story_block_unaffected_for_a_multi_segment_id` |

> [!NOTE]
> The two `_sf4` functions also claim `integration_` and `e2e_` while living in `tests/unit/`. The
> rename fixes both defects at once — the new names describe the assertion, which is what makes the
> tier lie visible in the first place.

Use `git mv` so history follows the file; a delete-plus-create loses the blame trail that told us
`LEGACY_E2E_NAMES` was deliberate rather than accidental.

### 2. Reference updates (FR-6)

Every occurrence of each old basename across `docs/`, `scripts/`, `tests/` and `.agents/`/`.claude/`
moves in the same commit. NFR-6's check is a repo-wide search returning zero hits for all nine old
names (`check_skill_references.py` does **not** cover this — it scans `.agents/` and `CLAUDE.md`
only, while these references live under `docs/roadmap/`).

> [!CAUTION]
> `.claude/` is a junction and `grep -r` returns zero hits inside it even when matches exist.
> Enumerate it explicitly and include a positive control (search for a string known to be present)
> before believing a clean result.

### 3. R5 widened (FR-7)

- Drop the `tests/e2e/` path restriction so the rule applies to every tier.
- Add an `_sf<N>` alternative to `_STORY_ID_IN_FILENAME`.
- Extend the check to test **class and function names**, not just filenames, parsing with `ast` and
  degrading like `_family_class` does on `SyntaxError`.
- Delete `LEGACY_E2E_NAMES` entirely rather than leaving it empty — an empty allowlist is an
  invitation (see Q5).
- Rename the check itself; `check_e2e_naming` is wrong once it spans tiers.
- Update its docstring, which currently cites a file this sub-feature renames (R3).

Pseudocode for the widened check — order matters because each step is more expensive:

```
skip if the path is not under tests/
flag the FILENAME if the story-id pattern matches
parse the file with ast; give up quietly if it will not parse
for each ClassDef / FunctionDef whose name starts with Test/test:
    flag the NAME if the story-id pattern matches
```

> [!CAUTION]
> The pattern must not match validation rule IDs (R2). It must also never inspect docstrings or
> comments — the `Proves: TECH-NNN FR-N` tag is the one sanctioned place a registry ID appears in a
> test, and `check_fr_coverage.py` depends on it. This check reads **names only**.

## Test Plan

Unit tier. TECH ticket, so `TECH-017`'s integration rule does not apply; `check_conventions.py`'s
tests live in `tests/unit/scripts/test_check_conventions.py` (class `TestE2ENaming` today).

| # | Bucket | Story | Target |
|---|---|---|---|
| T1 | Happy | A story-named file under `tests/integration/` is flagged | widened check |
| T2 | Happy | A story-named file under `tests/unit/` is flagged | widened check |
| T3 | Happy | `_sf<N>` in a filename is flagged | pattern |
| T4 | Happy | A story-named test **class** is flagged | AST branch |
| T5 | Happy | A story-named test **function** is flagged | AST branch |
| T6 | Boundary | All ten real rule-ID-named files pass (`c01`…`c13`, `s07`, `s12`) | R2 exclusion |
| T7 | Boundary | A subject-named file passes in every tier | control for T1/T2 |
| T8 | Degradation | A file that will not parse is not reported as a naming violation | AST fallback |
| T9 | Hostile | A registry ID inside a docstring or comment is **not** flagged | names-only guarantee |
| T10 | Regression | The real `tests/` tree is clean after the renames | whole-repo run |

T9 is the one that protects `check_fr_coverage.py`: flagging docstrings would make the two gates
contradict each other, with `Proves:` tags impossible to write.

## Verification

```bash
PY=.venv/Scripts/python.exe

$PY -m pytest tests/unit/scripts/test_check_conventions.py -v --tb=short
$PY scripts/quality.py cb --only conventions      # whole tests/ tree, empty allowlist

# Renames did not change behaviour: same test count, same names collected
$PY -m pytest tests/e2e tests/integration --collect-only -q | tail -3

# No dangling references (NFR-6)
# for each of the 9 old basenames -> zero hits
$PY scripts/tests.py cb TECH-025 --kind tooling
$PY -m pytest -n auto --tb=short -q
```

## Commit Boundaries

**CB-1 — R5 widened, allowlist deleted.** Lands the rule first, red against the known offenders,
proving the checker actually catches them.

Verification, **measured against the live tree before writing this** (widened pattern =
`int_us_\d+|_(ui|sens|flow|intl|val|exec)_\d{2}_|tech_\d{3}|_sf_?\d`):

- **exactly 9 files** flagged — the nine in the rename table, nothing else
- **exactly 2 function names** flagged — both `_sf4` cases in `test_exclusions.py`
- **zero** of the 10 rule-ID files (`c01`…`c13`, `s07`, `s12`) flagged
- **zero** of the 12 new names flagged, so CB-2 turns the gate green rather than trading one violation for another

> [!NOTE]
> Two functions, not three. `test_story_block_unaffected_for_int_us_ticket` is **not** caught — it
> has `int_us_` with no digit — and deliberately so (Q2). It is renamed by hand in CB-2 and the
> rule never sees it. An earlier draft of this plan claimed three; that was wrong and would have
> made CB-1's gate output look like a miss.

**CB-2 — the renames and every reference.** Turns CB-1's gate green.

> Splitting this way makes the checker's claim falsifiable. Renaming first and widening after would
> produce a rule that has never failed on anything, which is indistinguishable from a rule that
> cannot fail. The cost is one intermediate commit where `quality.py conventions` is red — recorded
> here so it reads as intent, not breakage.

## Decisions (Phase 4 gate, 2026-08-08)

| # | Decision |
|---|---|
| Q1 | **The nine names above are approved as written**, plus the three function names. This plan is now the single source — the duplicate inventory that lived in the design was deleted, having already drifted on three of the nine. |
| Q2 | `test_story_block_unaffected_for_int_us_ticket` is renamed **by hand**; the pattern is *not* widened to catch bare family prefixes. `int_us_` with no digit names an ID family, and matching it would flag tests that legitimately discuss ID shapes — `check_story_preconditions`'s own suite does exactly that. |
| Q3 | **`git mv`**, not delete-and-create. Blame is what revealed `LEGACY_E2E_NAMES` was a deliberate deferral rather than an oversight. |
| Q4 | **Delete `LEGACY_E2E_NAMES` outright.** An empty allowlist carrying a "nothing may be added" comment is an invitation with instructions. |
| Q5 | **Two commit boundaries, CB-1 deliberately red.** Recorded as intent, not breakage — see Commit Boundaries. |
| Q6 | The alembic file **drops its revision hash**. A revision id is as meaningless to a future reader as a ticket id, the migration is still loaded by that id inside the test, and it is the only file in `tests/unit/alembic/`. |
| Q7 | **R5 reads names only — never docstrings or comments.** Not a preference: scanning docstrings would flag every `Proves: TECH-NNN FR-N` tag, putting `check_conventions` and `check_fr_coverage` in direct contradiction and making the citation convention impossible to satisfy. Pinned by T9. |
