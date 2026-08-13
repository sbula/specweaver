# Design: Registry IDs Leaking Into Proofs — FR Traceability Gap and Story-Named Tests

- **Feature ID**: TECH-025
- **Epic**: Topic 07 (Technical Debt)
- **Status**: COMPLETE (2026-08-12)
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_design.md

> **Reading convention used throughout this document.** A bare `FR-N` always means *this ticket's*
> requirement. A requirement belonging to one of the three subject stories is always written
> qualified — `TECH-001 FR-7`. The two are otherwise indistinguishable and the whole ticket is
> about FR numbering, so the qualification is not optional.

## Feature Overview

TECH-025 closes the gap between what three delivered technical-debt stories promised and what
provably tests them, and removes registry IDs from the places they leak into and outlive. It
solves two halves of one root cause: 21 FRs across TECH-001, TECH-002 and TECH-005 are declared in
their designs but owned by no implementation plan and cited by no test, so `check_fr_coverage.py`
blocks all three; and nine test files plus three test functions are named after the story that paid
for them rather than the behaviour they protect, which `check_conventions.py` R5 already forbids
but had to grandfather. It touches those stories' implementation plans, the `tests/` tree,
`scripts/check_conventions.py`, and the delivered-story documents that cite the renamed files by
name — and it changes **nothing** under `src/`. Key constraints: the finished-stories-immutable
rule is waived for the affected stories under this ticket only; no citation may be attached to a
test that does not actually exercise the requirement.

## Research Findings

### Codebase Patterns

**The gate.** `scripts/check_fr_coverage.py` parses the FR *table* from a story's design, then
requires each row to appear in at least one of that story's implementation plans **and** in at
least one file under `tests/` that contains both the story ID and the literal `FR-N`. Plan scanning
is globbed per story (`*/TECH-001/TECH-001*implementation_plan.md`), so one story's plans cannot
credit another's. **Test scanning is repo-wide**, so any test file naming a story credits every
`FR-N` token in it — this is the single most important mechanic in this design (see AD-2, NFR-4).

**The citation convention** is a single trailing `Proves: TECH-NNN FR-N, FR-M.` line in a docstring.
`TECH-006` is the worked example on both halves: `tests/unit/core/flow/handlers/test_base.py`
carries per-test tags, and `tests/unit/interfaces/cli/test_interface_layer_boundaries.py` shows
what to do when a requirement is "delete this thing" — assert the absence directly.

**Coverage mostly already exists; only the citation is missing.** Verified by reading the tests:

| Subject FR | Already proven by | Missing |
|---|---|---|
| TECH-002 FR-1, FR-2, FR-4 | `tests/unit/sandbox/test_sandbox_registry.py` — `BaseTool` ABC contract, `ToolRegistry` register/create/failure paths, and parametrized conformance over every domain tool and facade | citation only |
| TECH-002 FR-3 | `tests/integration/sandbox/test_dispatcher_registry_delegation.py` — asserts `create_standard_set` delegates to `ToolRegistry.create_tools` | citation only |
| TECH-005 FR-1, FR-2, FR-3, FR-6, FR-7 | `tests/unit/alembic/test_table_prefix_migration.py` — mocked `op.rename_table`/index calls **and** a live in-memory SQLite up/down migration | citation only |
| TECH-005 FR-4 | `tests/e2e/test_cli_bootstrap_e2e.py` bootstraps from the models and asserts `workspace_projects` exists | citation only |
| TECH-005 FR-5 | `tests/e2e/capabilities/core/test_lineage_e2e.py` issues raw SQL against `flow_artifact_events` | citation only |
| TECH-001 FR-9 | `tests/unit/test_architecture.py::test_core_config_has_no_cross_domain_runtime_imports` | already cited — out of scope |

The remaining subject FRs (TECH-001 FR-1..FR-8) need a per-FR search for an existing proof during
planning; where none genuinely exists, NFR-3 requires writing one rather than tagging a bystander.

**The substance is sound.** Spot-checked in code, independent of citation: `infrastructure/llm/store.py`,
`core/flow/store.py` and `workspace/store.py` exist as standalone per-domain stores (TECH-001
FR-1/2/3); nine domain `interfaces/cli.py` modules exist and `interfaces/cli/main.py` mounts every
one (FR-4/FR-5); `sandbox/` is grouped into feature directories (FR-6); `core/config/database.py`
imports only stdlib and SQLAlchemy (FR-7); `llm/factory.py` takes `SpecWeaverSettings` and
`llm/router.py` takes a settings-provider callable, with no `Database` coupling (FR-8). This ticket
is traceability, not repair.

**A genuine orphan, not just a citation gap.** TECH-001's design assigns FRs to sub-features as
SF-01 `[FR-1, FR-2, FR-3]`, SF-02 `[FR-4, FR-5]`, SF-03 `[FR-6]`, SF-04 `[FR-9]`. **TECH-001 FR-7
and FR-8 belong to no sub-feature at all.** Both were in fact delivered by SF-01, whose plan §4b
("Dependency Inversion — The Monolith Fix") lists exactly their work: strip `settings.py` and
`database.py` of control flow, add `interfaces/cli/settings_loader.py` and `interfaces/cli/_db_utils.py`,
and modify `llm/router.py` & `factory.py`. FR-4 records the assignment so the FR table and the
sub-feature map stop disagreeing.

**R5 already exists and already says this should be fixed.** `scripts/check_conventions.py`
forbids registry IDs in test filenames, and its `LEGACY_E2E_NAMES` allowlist carries a note that is
effectively this ticket's charter: *"These are NOT grandfathered on merit — every one of them should
be renamed for its subject… each is cited by name in the walkthroughs and integration docs of a
DELIVERED story… That needs a ticket that decides both halves together, not a drive-by rename."*
R5 is wired into `quality.py`'s `conventions` gate over `src` and `tests`. Two limits explain the
survivors: it only inspects paths under `tests/e2e/`, and its regex has no `_sf<N>` alternative — so
`test_dispatcher_sf2_integration.py` (integration) and `test_af60fd3509a2_tech_005_rename_tables.py`
(unit) were never candidates.

**Scope was measured, not assumed.** Running the FR gate over every story with a design document:
**78 fail, 4 pass** (TECH-006, TECH-019, INT-US-21, INT-US-24). A repo-wide FR invariant is
therefore firmly out of scope; TECH-025 stays at its three stories. Likewise, 292 of 954 unit test
classes name neither a class nor a function under test — too large and too judgement-heavy to sweep
here (AD-6).

### External Tools

None. No new library, no version change. `pytest`, `ast` and `re` are already in use by the
scripts this ticket extends.

### Blueprint References

None. `TECH-019` is the in-repo precedent for the shape — repair every instance, then ship the
checker that keeps them repaired — and `TECH-006` is the precedent for the citation convention.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Close TECH-001's FR ledger | System | Cite TECH-001 FR-1..FR-8 in the implementation plan that owns each and in a test file that exercises it | `python scripts/check_fr_coverage.py TECH-001` exits 0. |
| FR-2 | Close TECH-002's FR ledger | System | Cite TECH-002 FR-1..FR-6 likewise | `python scripts/check_fr_coverage.py TECH-002` exits 0. |
| FR-3 | Close TECH-005's FR ledger | System | Cite TECH-005 FR-1..FR-7 likewise | `python scripts/check_fr_coverage.py TECH-005` exits 0. |
| FR-4 | Adopt TECH-001's orphaned FRs | System | Assign TECH-001 FR-7 and FR-8 to SF-01 in TECH-001's design, matching what SF-01's plan §4b delivered | Every row of TECH-001's FR table belongs to exactly one sub-feature. |
| FR-5 | Guard the closed ledgers | System | Add a data manifest of story IDs whose ledgers must stay closed, and a test that runs the gate for each listed story | Removing a `Proves:` tag from any listed story fails a test instead of going unnoticed. |
| FR-6 | Rename story-named tests | System | Rename 9 test files and 3 test functions for the unit and case under test, updating every reference in docs and scripts in the same change | No test file, class or function name contains a registry ID, and no reference to an old name dangles. |
| FR-7 | Extend R5 to every tier | System | Apply R5 across all of `tests/`, add `_sf<N>` to its pattern, extend it to test class and function names, and empty the legacy allowlist — **without** matching validation rule IDs (`c01`–`c13`, `s07`, `s12`), which are domain vocabulary, not registry IDs | `quality.py conventions` fails on any newly introduced registry ID in a test name, in any tier, and still passes the 10 rule-ID-named test files. |
| FR-8 | Require unit test classes to name their subject | System | Add a rule that a unit test class names the class or function under test, ratcheted against a frozen count baseline under `scripts/baselines/`, and mint a follow-up ticket for the sweep | The count of subject-free unit test classes may fall, never rise; the existing 292 are recorded, not silently permitted. |
| FR-9 | Stop the gate crediting fixture data | System | Make `check_fr_coverage.py` skip files that carry an explicit fixture-data marker, and mark `tests/unit/scripts/test_check_fr_coverage.py` | A test whose `FR-N` strings are inputs to the checker under test no longer counts as proof for the stories it happens to name. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | No production change | Zero files modified under `src/specweaver/`. Verified by `git diff --name-only` on each commit. **[proof: meta — rule about tests, docs or the diff]** |
| NFR-2 | Zero regression | Full suite passes. For the rename sub-features specifically, no assertion, fixture or test body changes and the test count is identical before and after. The ledger sub-features may **add** tests where NFR-3 requires one; they may never remove or weaken one. **[proof: meta — rule about tests, docs or the diff]** |
| NFR-3 | Citation honesty | Every `Proves:` tag names a test that would fail if that FR's behaviour regressed. Each implementation plan states, per FR, the specific assertion carrying it. Where none exists, a test is written and confirmed to fail against the broken behaviour before being tagged. **[proof: meta — rule about tests, docs or the diff]** |
| NFR-4 | The guard must not be self-satisfying | The FR-5 test file contains no literal `TECH-001`, `TECH-002` or `TECH-005` string, so it cannot itself satisfy the gate for the stories it checks. Asserted by a test that reads its own module source and matches a registry-ID *pattern* — the pattern permits this ticket's own ID (needed for the `Proves:` tag) and rejects every other, so the assertion cannot be satisfied by deleting the tag. **[proof: meta — rule about tests, docs or the diff]** |
| NFR-5 | IDs confined to one line | A registry ID may appear in a test only in the single trailing `Proves:` docstring line — never in a file, class or function name, and never in an assertion or comment. **[proof: meta — rule about tests, docs or the diff]** |
| NFR-6 | No dangling references | After the renames, a repo-wide search for each of the 9 old filenames returns zero hits outside git history. **`check_skill_references.py` does not cover this** — it scans `.agents/` and `CLAUDE.md` only, and every one of the ~30 references lives under `docs/roadmap/`. The search is the check; `check_skill_references.py` is run as well, but only for the `CLAUDE.md` surface. **[proof: meta — rule about tests, docs or the diff]** |
## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| — | — | — | — | No new or changed external dependency. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Renames land **before** the citations that touch renamed files | Citing a file and then renaming it means editing the same delivered-story docs twice and risks a citation pointing at a path that no longer exists. SF-02 precedes SF-05 and SF-06 for that reason. SF-04 (TECH-001) is deliberately **not** made to wait: none of TECH-001's proofs appear in the rename inventory, and a dependency that buys nothing just serialises work. | No |
| AD-2 | The guard reads story IDs from a data manifest, not from literals in the test | The gate credits an FR to any story whose ID appears in a test file alongside `FR-N`. A guard that hard-coded the three IDs would make their ledgers pass vacuously — the exact gaming the ticket exists to prevent. A `.txt` manifest under `docs/` is never scanned by the gate. Chosen by user 2026-08-08 over split string literals (obscure, silently broken by tidying) and design-doc parsing (couples a test to prose). | No |
| AD-3 | Extend R5 in `check_conventions.py` rather than add a script | R5 already encodes this rule, is already wired into `quality.py`, and already has the allowlist to empty. A second checker would split one rule across two files. | No |
| AD-4 | Editing delivered stories' documents is in scope and explicit | TECH-001/002/005's plans, and the walkthroughs and integration docs of INT-US-02/03/09/21/24, C-EXEC-06, TECH-006, TECH-012 and TECH-021, cite the renamed files by name. `LEGACY_E2E_NAMES`' own comment says this needs a ticket deciding both halves together. This is that ticket; the waiver is named in every commit message. | No |
| AD-5 | The manifest is seeded with the three subject stories **plus INT-US-21** | Keeps the blast radius equal to what this ticket actually audited. TECH-006/019 and INT-US-24 also pass today but were never audited here; a future ticket that closes a ledger adds its line. Chosen by user 2026-08-08. **Amended at SF-01's Phase 4 gate (2026-08-08): `INT-US-21` joins the seed.** SF-01 removes citation credit it currently receives from fixture data, so "INT-US-21 still closes on genuine proof" is SF-01's real assertion — and it cannot be a pytest, because asserting it means naming the story in a file that also carries an `FR-N` token, which would re-credit it. The manifest is the only place that check can live permanently. AD-5's original reason (do not bind stories this ticket never audited) does not apply: SF-01 audits INT-US-21 directly. | No |
| AD-6 | The unit-class-naming rule ratchets; it does not sweep | 292 of 954 existing classes would need renaming, many being reasonable behaviour groupings in a file that already names the unit. Sweeping them inside this ticket would bury the citation work in an unattributable diff. Rule enforced against a frozen baseline; separate ticket minted. Chosen by user 2026-08-08. | No |
| AD-7 | Fix the gate's false-citation hole before closing any ledger against it | Found by this design's Red/Blue review: `tests/unit/scripts/test_check_fr_coverage.py` names `INT-US-21` and `D-INTL-02` and contains `FR-1`…`FR-7`, `FR-10`, `FR-99` **as fixture inputs to the checker under test**. The gate therefore credits 8 of INT-US-21's 10 FRs to a file that proves nothing about it. INT-US-21 does not depend on that credit — every FR has genuine citations too — but closing three ledgers against a gate with this hole would certify exactly the fiction this ticket exists to remove. Fixed by an explicit fixture-data marker the scanner honours. | No |
| AD-8 | The fixture-data marker is not an override | The repo's rule is that an overridable gate becomes a habit. This marker can only ever **remove** citations, never add one, so it cannot be used to make a failing ledger pass — it makes the gate stricter. The stricter alternative (count only `Proves:` tags) was measured and rejected: INT-US-21 and INT-US-24 cite their FRs in prose, so tightening the form would break two of the four ledgers that currently pass, which is a separate ticket's work. | No |
| AD-9 | The count-based ratchet reuses `scripts/baselines/` | `check_suppressions.py` already implements exactly this — a frozen JSON baseline that may fall but never rise, refreshed via `--update-baseline` so the diff is reviewable in git. A 292-name allowlist would be a second mechanism for one idea, and a list is far easier to quietly append to than a number. | No |

No decision places code in a wrong layer, violates a `context.yaml` rule, introduces a cycle or
duplicates infrastructure. Nothing under `src/` changes, so no module boundary moves.

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| 21 FR citations across 3 stories' plans and tests | High — each FR needs its real proof located, and one written where absent | Medium: the temptation to tag a bystander is the main failure mode (NFR-3) |
| 9 file + 3 function renames with full doc reference updates | Medium — mechanical, but ~30 doc references across 10 stories | Low, provided every reference moves in the same commit (NFR-6) |
| R5 extension + `LEGACY_E2E_NAMES` emptied | Low | Low — broader R5 may surface names the measurement missed; it is a fail-loud gate |
| Unit-class rule + 292-entry baseline | Low–Medium | Medium: a baseline that is never drained becomes permanent permission (mitigated by AD-6's follow-up ticket) |
| Manifest + regression guard | Low | Low |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| The three subject stories | Move from "blocked by their own closure gate" to genuinely closed | High — unblocks the #2 slot in the debt order |
| Every later debt ticket | The citation convention is demonstrated on three real stories before TECH-014/020/015/024/023 must each meet it at closure | High |
| Anyone reading `tests/` | Test names say what breaks when they go red, not which ticket paid for them | Medium, compounding |
| Future ledger closures | The manifest is the place to record them, and the guard makes regression loud | Medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| A citation is attached to a test that does not really prove its FR | Medium | High — the gate goes green while traceability stays fictional, which is worse than the current honest failure | NFR-3: each plan names the specific assertion per FR; where absent, write the test and confirm it fails against the broken behaviour |
| The guard makes the three ledgers pass vacuously | Low | High — the ticket would certify itself | NFR-4, asserted by a test, plus AD-2's manifest indirection |
| A renamed file leaves a dangling doc reference | Medium | Medium — exactly the defect TECH-019 removed | NFR-6: `check_skill_references.py` plus a repo-wide search for each old name |
| The 292-entry baseline becomes permanent | Medium | Low | AD-6 mints the follow-up ticket as part of SF-02, not as a promise |
| Broader R5 surfaces names beyond the measured 12 | Low | Low | Gate is fail-loud; any extra name is fixed under FR-6 rather than allowlisted (NFR-5) |
| The widened R5 pattern flags validation rule IDs | **Confirmed, not hypothetical** | High — 10 legitimate files (`test_c01_c02_c03.py`, `test_c05_architecture_integration.py`, `test_c12_…`, `test_s07_…`, `test_s12_…`) would fail the conventions gate, and the likely reaction is a bogus allowlist that reopens the hole this ticket closes | FR-7 states the exclusion explicitly; SF-02's plan pins it with a test asserting each of the 10 passes |
| The ledgers are closed against a gate that credits fixture data | **Confirmed live** | High — three ledgers certified partly on fiction | SF-01 lands first and is a hard dependency of every ledger sub-feature (AD-7) |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| The other 75 failing stories | Same citation gap, never audited | The manifest and guard give them a landing place as each closes; explicitly **not** done here (78-fail measurement) | Out of scope |
| 292 unit test classes | Name a behaviour grouping, not a subject | Baseline recorded here; swept under the ticket AD-6 mints | Out of scope |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| — | No new sub-system, paradigm or extension layer. The conventions are enforced by `check_conventions.py` and `check_fr_coverage.py`, whose failure messages are the documentation. | N/A |

## Sub-Feature Breakdown

### SF-01: Gate Integrity
- **Scope**: Close the false-citation hole in `check_fr_coverage.py` before any ledger is closed against it.
- **FRs**: [FR-9]
- **Inputs**: `scripts/check_fr_coverage.py`'s `cited_frs_in_tests`; `tests/unit/scripts/test_check_fr_coverage.py`, whose `FR-N` strings are fixture inputs.
- **Outputs**: An explicit fixture-data marker honoured by the scanner; the one qualifying file
  marked; INT-US-21's inflated citation counts drop to their real values while its ledger stays
  closed on genuine proof.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf01_implementation_plan.md

### SF-02: Test Naming Closure
- **Scope**: Rename every story-named test file and function for its subject, update all references, and widen R5 so it cannot happen again.
- **FRs**: [FR-6, FR-7]
- **Inputs**: 9 story-named test files and 3 test functions; the ~30 doc references citing them; `scripts/check_conventions.py` R5 and its legacy allowlist.
- **Outputs**: Renamed tests; updated references; R5 covering all tiers, `_sf<N>`, and class/function names; allowlist gone.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf02_implementation_plan.md

### SF-03: Unit Test Class Naming Ratchet
- **Scope**: Require a unit test class to name the class or function under test, ratcheted against the pre-existing 292.
- **FRs**: [FR-8]
- **Inputs**: `scripts/check_conventions.py`; `scripts/baselines/`; the measured 292.
- **Outputs**: New rule + frozen count baseline; a follow-up TECH ticket (via `specweaver-ticket`) for the sweep.
- **Depends on**: SF-02 *(both edit `check_conventions.py`; serialising avoids a conflict, and SF-02's renames must not land against a rule that is still moving)*
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf03_implementation_plan.md

### SF-04: TECH-001 FR Ledger
- **Scope**: Close TECH-001's ledger and adopt its two orphaned FRs.
- **FRs**: [FR-1, FR-4]
- **Inputs**: TECH-001's design FR table (FR-1..FR-8) and its four implementation plans; the existing tests covering config/CLI/sandbox/LLM-DI behaviour.
- **Outputs**: `check_fr_coverage.py TECH-001` exits 0; TECH-001 FR-7/FR-8 assigned to its SF-01.
- **Depends on**: SF-01 *(a leaky gate cannot certify a ledger)*. **Not** SF-02 — none of TECH-001's proofs are in the rename inventory, so this runs in parallel with the renames.
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf04_implementation_plan.md

### SF-05: TECH-002 FR Ledger
- **Scope**: Close TECH-002's ledger.
- **FRs**: [FR-2]
- **Inputs**: TECH-002's design FR table (FR-1..FR-6) and its four plans; `test_sandbox_registry.py` and the two renamed dispatcher integration tests.
- **Outputs**: `check_fr_coverage.py TECH-002` exits 0.
- **Depends on**: SF-01, SF-02 *(cites the renamed dispatcher files)*
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf05_implementation_plan.md

### SF-06: TECH-005 FR Ledger
- **Scope**: Close TECH-005's ledger.
- **FRs**: [FR-3]
- **Inputs**: TECH-005's design FR table (FR-1..FR-7) and its SF-01/SF-02 plans; the renamed migration test, the bootstrap e2e and the lineage e2e.
- **Outputs**: `check_fr_coverage.py TECH-005` exits 0.
- **Depends on**: SF-01, SF-02 *(cites the renamed migration test)*
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf06_implementation_plan.md

### SF-07: Ledger Regression Guard
- **Scope**: Record the closed ledgers in a manifest and fail a test if any of them reopens.
- **FRs**: [FR-5]
- **Inputs**: The three ledgers closed by SF-04..SF-06; `check_fr_coverage.main`.
- **Outputs**: `docs/roadmap/fr_traceability_closed.txt` — seeded with TECH-001, TECH-002, TECH-005
  **and INT-US-21** (AD-5 as amended); a guard test carrying this ticket's `Proves:` tags and
  containing no subject-story literal.
- **Depends on**: SF-04, SF-05, SF-06 *(a ledger cannot be listed as closed before it is closed)*
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf07_implementation_plan.md

## Execution Order

1. **SF-01** and **SF-02** — no dependencies; may run in parallel (disjoint files: SF-01 edits
   `check_fr_coverage.py`, SF-02 edits `check_conventions.py` and the `tests/` tree).
2. **SF-03** once SF-02 is committed; **SF-04** once SF-01 is committed. These two are independent
   of each other.
3. **SF-05** and **SF-06** once both SF-01 and SF-02 are committed. They touch two disjoint stories
   and may run in parallel sessions.
4. **SF-07** once SF-04, SF-05 and SF-06 are committed.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Gate Integrity | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Test Naming Closure | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Unit Test Class Naming Ratchet | SF-02 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-04 | TECH-001 FR Ledger | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-05 | TECH-002 FR Ledger | SF-01, SF-02 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-06 | TECH-005 FR Ledger | SF-01, SF-02 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-07 | Ledger Regression Guard | SF-04, SF-05, SF-06 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Closure

Beyond the standard Phase 4 gate (`check_fr_coverage.py TECH-025` + `tests.py feature TECH-025`),
this ticket must also leave all three subject gates green:

```
python scripts/check_fr_coverage.py TECH-001
python scripts/check_fr_coverage.py TECH-002
python scripts/check_fr_coverage.py TECH-005
python scripts/quality.py cb          # conventions gate, R5 with an empty allowlist
```

~~TECH-025's roadmap section currently has no **Verifiable Proof** field — `check_story_preconditions.py`
warns about it. SF-07's guard test is the natural entry; add it at closure.~~

**Overtaken 2026-08-12.** The roadmap no longer has a section to put it in: `TECH-NNN` entries are
now capability-level one-liners (user's ruling, recorded in `TECH-026`), and a one-line entry has no
`Verifiable Proof` field by construction. The warning is now expected for every TECH ticket rather
than particular to this one, and `TECH-026` owns deciding where those citations belong — the topic
doc, or the design's FR ledger, which `check_fr_coverage` already reads and which for this ticket
now exits 0.

One closure check is peculiar to this ticket and easy to forget: re-run the gate for **INT-US-21**
as well. SF-01 removes citation credit it currently receives from fixture data, and the design's
claim is that it stays green on genuine proof alone. If it does not, SF-01 over-reached.

## Origin

Found running `python scripts/check_fr_coverage.py TECH-001` as the closure gate for TECH-001 SF-04
(2026-08-02). **Widened** the same day after `check_fr_coverage.py TECH-005` surfaced the identical
gap while closing TECH-005 SF-03 — the user's explicit direction was to fold it in here rather than
mint `TECH-026`, since it is one systemic cause under a different story ID. **Widened again**
(2026-08-08) when `check_fr_coverage.py TECH-002` was run while verifying whether that ticket's
amber status still reflected outstanding work; it did not — the work is complete and code-verified —
but the same gap appeared across all four of its sub-features. **Widened a third time** (2026-08-08,
this design) to the test-naming half, on the user's direction that no test may be named after a
registry ID, which `LEGACY_E2E_NAMES`' own comment had been waiting for a ticket to authorise.

All three stories shipped before the citation gate was wired into the closure process. In every
case this is a traceability defect, not a functional one: each story's declared `Verifiable Proof`
passes.

## Spun off from this ticket

- **`TECH-026`** — [Roadmap Placement Contract](../TECH-026/TECH-026_design.md), minted 2026-08-08
  during SF-02. Asked where sub-features were recorded, this session added TECH-025's seven
  design-document sub-features to `master_story_roadmap.md`, having derived the convention from
  `TECH-001`/`TECH-006` — the only two entries that violate it. The rule (one registry ID = one
  line; a design's `SF-NN` never appears) exists nowhere in the repo, so `TECH-026` writes it down,
  ships a checker, and repairs those two entries. **Not** TECH-025's work; TECH-025 owns only
  reverting that edit and its own title drift.

## Session Handoff

**Current status**: Design APPROVED 2026-08-08 after a 2-cycle Red/Blue review that added FR-9 and
SF-01 (the gate credits fixture data — confirmed live) and the rule-ID exclusion in FR-7.
**SF-01 delivered 2026-08-08.** The citation scan now honours a fixture-data marker, so the three
ledger sub-features can close against a gate that no longer credits its own checker's test inputs.
It also cleared two blockers found on the way: `scripts/` had no mirror in `tests.py`, so no
scripts-only change could pass its own commit gate; and `tests.py` sat at exactly 600/600 with no
headroom for any change at all (now 538, via the extracted `_story_resolution.py`).
**SF-03 delivered 2026-08-08.** R6 ratchets unit test class names against a frozen per-directory
baseline (278 across 10 dirs). SF-01 and SF-02 are also delivered: the FR ledger gate no longer
credits its own checker's fixture data, and no test file, class or function name carries a registry
ID.
**SF-04 delivered 2026-08-09** across three commit boundaries. `check_fr_coverage.py TECH-001`
now **exits 0** — the first of the three subject ledgers to close. TECH-002 and TECH-005 were
re-checked at every boundary and both still exit 1, which is the required outcome: a citation in a
shared test file closing someone else's ledger is the false-credit defect SF-01 existed to fix.

Three things SF-04 found that were not in its plan, each fixed rather than deferred:
- **The selector assumed every change is source-shaped** — four instances of one root cause, two
  found by SF-01 and SF-04 being blocked, two more by CB-1's Red/Blue in `domain` scope. Fixed, and
  the path→module mapping extracted to `scripts/_changed_file_mapping.py`. What remains is recorded
  in SF-04's plan §Finding: nothing enumerates the (tier × scope × change-shape) space.
- **Four of the five new invariants passed against a tree that does not exist.** The synthetic
  probes proved the logic; nothing proved the live invocation pointed anywhere. One guard test now
  does. Generalised as vacuous-proof **pattern 8** in `test-quality.md`.
- **`test_architecture.py` was crediting `TECH-022`** through a story ID sitting in prose, and
  carried an ID in an assertion message and a comment. All three were NFR-5 violations and the
  first was a live false credit — the SF-01 defect class, found in the file this ticket was adding
  citations to.

**SF-05 delivered 2026-08-12** across two commit boundaries. `check_fr_coverage.py TECH-002` now
**exits 0** — the second subject ledger closed. CB-1 proved the two absence claims; CB-2 linked all
six requirements and repaired two NFR-5 violations, one of them caught before it could pay out.
Its Red/Blue found that the plan's chosen file already named `TECH-001`, so the intended citations
would have credited TECH-002 with a borrowed FR-4 — and that the plan's own verification could not
have detected it, because a count cannot distinguish a borrowed citation from a real one. Both the
new test file and the verification method changed as a result.

**SF-06 delivered 2026-08-12.** `check_fr_coverage.py TECH-005` exits 0 — **all three subject
ledgers are now closed**, which was this ticket's substantive goal. Five of its seven open
requirements already had a genuine proof in the alembic migration test; only FR-4 and FR-5 needed
new invariants. Its research found the plan-side twin of SF-05's false-credit trap: `FR-6` was
reported as planned from a *disclaimer* in SF-03's plan, because `planned_frs` unions tokens without
asking which sub-feature claims them.

**SF-07 delivered 2026-08-12, and the ticket is COMPLETE.** `check_fr_coverage.py TECH-025` exits
0 — nine of nine. Widened at its Phase 4 gate to close this ticket's own ledger, because R5 showed
nothing came after it and no natural host existed: every candidate file already named another story
and would have credited it with TECH-025's tokens. Two files name only TECH-025; the manifest keeps
the subject ids in data the guard reads at run time, which is the only way the guard could exist.
FR-4 was generalised — *every requirement a design declares is assigned to some sub-feature* — since
any test asserting TECH-001's specific case must name a path containing that story's id.

**Superseded next step**: SF-07 — the regression manifest,
and may run in parallel sessions. Neither has an implementation plan yet. SF-07 waits on both.
Note for whoever takes them: SF-04's CB-1 removed the wall that made a tests-and-docs boundary
impossible to commit, so neither should hit it.

**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and
resume from there using the appropriate skill.

## Carried down from the topic entry (2026-08-13, `TECH-044`)

Moved here verbatim when the entry was shortened to four lines — recorded rather than dropped.

- [Description](../features/topic_07_technical_debt/TECH-025/TECH-025_design.md) | _(2026-08-02,
  widened same day — found running `check_fr_coverage.py TECH-001` as SF-04's closure gate, then
  again running `check_fr_coverage.py TECH-005` as SF-03's closure gate; widened a second time
  2026-08-08 when verifying TECH-002's status)_ | None of `TECH-001_design.md`'s FR-1–8
  (SF-01/02/03), `TECH-002_design.md`'s FR-1–6 (all four sub-features) or `TECH-005_design.md`'s
  FR-1–7 (SF-01/2) are cited by the literal string `FR-N` in any implementation plan or test file
  naming their story — the citation *convention* was never followed for either, most plausibly
  because this gate didn't exist yet when they shipped.
