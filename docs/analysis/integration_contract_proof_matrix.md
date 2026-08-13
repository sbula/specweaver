# Integration-contract proof matrix

`TECH-017` SF-01, CB-1. **Skeleton only — no verdict is asserted yet.**

For every delivered integration contract, what it *claims* versus what a test *proves*. One claim
is **one assertion about behaviour at a seam**, not one sentence (`SF-01` D-1) — otherwise verdicts
are not comparable between entries.

> [!IMPORTANT]
> **What a verdict will mean.** `proven` names the **test function**, not the file: a file-level
> citation is what let 8 of `INT-US-21`'s 10 requirements be credited to a file asserting nothing
> about it. `unproven` means no such function exists. `unprovable` means the claim cannot be tested
> as written — recorded, never re-worded, because a delivered contract is immutable (`NFR-1`).
>
> **An `unproven` verdict is not a ticket.** The boundary that finds one cites an existing test
> after reading it, or writes the missing integration/e2e test. A ticket is filed only where a
> decision is needed that the auditor cannot take.

## Coverage at a glance

| Entry | Proof files | Tests | Tiers | Claims |
|---|---|---|---|---|
| `INT-US-01` | 1 | 5 | e2e | 3 |
| `INT-US-02` | 1 | 7 | e2e | 2 |
| `INT-US-03` | 2 | 7 | e2e, integration | 5 |
| `INT-US-04` | 1 | 4 | e2e | 2 |
| `INT-US-05` | 1 | 6 | e2e | 2 |
| `INT-US-05-SF03` | 0 | 0 | — | 1 |
| `INT-US-05-SF04` | 0 | 0 | — | 1 |
| `INT-US-09` | 1 | 5 | e2e | 3 |
| `INT-US-21` | 3 | 61 | e2e, integration | 4 |
| `INT-US-21-SUB` | 0 | 0 | — | 1 |
| `INT-US-24` | 2 | 13 | e2e, integration | 3 |
| `INT-US-25` | 9 | 75 | e2e, integration | 9 |
| `INT-US-28` | 9 | 88 | integration, unit | 6 |

**13 entries, 42 claims, 271 tests across 30 cited files.**


## `INT-US-01` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/assurance/test_standards_e2e.py` | e2e | 5 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | The CLI parses the target file using Loom (`E-SENS-01`). | `unassessed` | — |
| C2 | The CLI passes the parsed result to the Validation Engine (`E-VAL-01`). | `unassessed` | — |
| C3 | No unvalidated LLM generation can occur. | `unassessed` | — |

## `INT-US-02` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/workflows/test_drafter_loop_e2e.py` | e2e | 7 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | The interactive loop (`E-INTL-02`) hands the generated context to the Review Engine. | `unassessed` | — |
| C2 | No manual copy-pasting is required between the two. | `unassessed` | — |

## `INT-US-03` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/sandbox/test_implement_loop_worktree_isolation_e2e.py` | e2e | 2 |
| `tests/integration/interfaces/cli/test_cli_implement_isolation.py` | integration | 5 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | `sw implement` generates code **and** tests. | `unassessed` | — |
| C2 | It runs the generated tests. | `unassessed` | — |
| C3 | It runs code rules C01-C08. | `unassessed` | — |
| C4 | It auto-fixes lint, all in one autonomous loop. | `unassessed` | — |
| C5 | QA/test execution runs **exclusively** inside the US-9 zero-trust worktree sandbox, container-free. | `unassessed` | — |

## `INT-US-04` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/assurance/test_mcp_flow_e2e.py` | e2e | 4 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | The SQLite Config DB (`E-FLOW-01`) statefully persists Validation Engine outputs. | `unassessed` | — |
| C2 | The Pipeline Runner passes sanitized, verified context into subsequent prompt steps. | `unassessed` | — |

## `INT-US-05` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/core/test_lineage_e2e.py` | e2e | 6 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | The AST Skeleton Extractor resolves edges against the Git Worktree Bouncer. | `unassessed` | — |
| C2 | Extracted context reflects the current filesystem state, with no hallucinatory paths. | `unassessed` | — |

## `INT-US-05-SF03` — Intelligent Code Exclusions

**No test file cited.** Frozen in `scripts/baselines/proof_tier.json` with a named owner.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | The `.specweaverignore` engine feeds deterministic exclusions into the Extractor. | `unassessed` | — |

## `INT-US-05-SF04` — Framework Native Understanding

**No test file cited.** Frozen in `scripts/baselines/proof_tier.json` with a named owner.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | The Macro Evaluator detects framework context boundaries natively. | `unassessed` | — |

## `INT-US-09` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/sandbox/test_step_worktree_isolation_e2e.py` | e2e | 5 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | Per-step worktree isolation works for the single-step case. | `unassessed` | — |
| C2 | Session mode runs a whole untrusted span in one worktree with a single authorized reconcile. | `unassessed` | — |
| C3 | The legacy per-step model remains single-step-only — a documented limitation, not a defect. | `unassessed` | — |

## `INT-US-21` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/workflows/test_feature_decomposition_e2e.py` | e2e | 24 |
| `tests/integration/core/flow/handlers/test_decomposition_artifacts_integration.py` | integration | 33 |
| `tests/integration/core/flow/engine/test_seam_pins.py` | integration | 4 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | `sw run feature_decomposition` is a working three-session journey: draft (exists-skip) -> park -> resume-as-approval -> validate -> decompose -> park -> resume -> COMPLETED. | `unassessed` | — |
| C2 | It produces a durable uuid-tagged `<stem>_decomposition.yaml`. | `unassessed` | — |
| C3 | It produces one never-overwritten stub component spec per DAG node. | `unassessed` | — |
| C4 | The journey costs **exactly one** LLM call. | `unassessed` | — |

## `INT-US-21-SUB` — Recursive Planning

**No test file cited.** Frozen in `scripts/baselines/proof_tier.json` with a named owner.

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | `C-INTL-01` implements iterative decomposition, resolving the AST graph into sub-tasks. **(Out of SF-01 scope — `TECH-018`/`TECH-038` already established this claim is false; recorded for completeness.)** | `unassessed` | — |

## `INT-US-24` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/workflows/test_scenario_verification_e2e.py` | e2e | 9 |
| `tests/integration/workflows/scenarios/test_converter_execution.py` | integration | 4 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | `sw run scenario_integration <spec>` is a real working journey through the QA Runner on the shipped US-3 loop. | `unassessed` | — |
| C2 | A green verification round costs **zero** arbitration LLM calls. | `unassessed` | — |
| C3 | A parked `spec_ambiguity` heals through the loop on `sw resume`, with evidence re-published on the fresh round. | `unassessed` | — |

## `INT-US-25` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/e2e/capabilities/workspace/test_constitution_e2e.py` | e2e | 15 |
| `tests/integration/interfaces/cli/test_cli_constitution.py` | integration | 8 |
| `tests/integration/interfaces/cli/test_profile_check_seam.py` | integration | 6 |
| `tests/e2e/capabilities/workspace/test_domain_profile_e2e.py` | e2e | 10 |
| `tests/e2e/capabilities/workflows/test_dal_e2e_pipeline.py` | e2e | 5 |
| `tests/e2e/capabilities/assurance/test_validation_dal_enforcement.py` | e2e | 2 |
| `tests/e2e/capabilities/assurance/test_validation_pipeline_e2e.py` | e2e | 11 |
| `tests/e2e/capabilities/assurance/test_standards_e2e.py` | e2e | 5 |
| `tests/integration/interfaces/cli/test_cli_standards_integration.py` | integration | 13 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | `CONSTITUTION.md` is resolved by walk-up. | `unassessed` | — |
| C2 | It is size-capped via `sw config set-constitution-max-size`. | `unassessed` | — |
| C3 | It is injected into the prompt of `review spec`, `review code` and `implement`. | `unassessed` | — |
| C4 | Absence of the file means no injection, not a broken prompt. | `unassessed` | — |
| C5 | A project-local file overrides the default. | `unassessed` | — |
| C6 | `sw config set-profile` makes `sw check --level component` load that profile's pipeline YAML. | `unassessed` | — |
| C7 | `--pipeline` and `--level feature` both override the active profile. | `unassessed` | — |
| C8 | A nested `operational.dal_level` makes a warn-only spec FAIL under `DAL_A` and pass under `DAL_E`. | `unassessed` | — |
| C9 | The standards scan upserts rather than duplicates, and honours `.specweaverignore`. | `unassessed` | — |

## `INT-US-28` — Base Contract

| Cited proof file | Tier | Tests |
|---|---|---|
| `tests/integration/workspace/test_memory_integration.py` | integration | 26 |
| `tests/integration/workspace/test_memory_hydration_flow.py` | integration | 1 |
| `tests/integration/core/flow/handlers/test_prompt_hydration.py` | integration | 2 |
| `tests/integration/core/flow/engine/test_handover_persistence.py` | integration | 3 |
| `tests/unit/workspace/test_memory_hydrator.py` | unit | 15 |
| `tests/unit/workspace/test_bootstrap_protocol.py` | unit | 5 |
| `tests/unit/core/flow/engine/test_handover.py` | unit | 20 |
| `tests/unit/core/flow/engine/test_runner_handover.py` | unit | 7 |
| `tests/unit/core/flow/handlers/test_build_base_prompt.py` | unit | 9 |

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| C1 | `B-INTL-09` provides a persistent SQLite schema with CRUD, a formal state machine, OCC concurrency, circuit breakers, zombie recovery and upstream DAG propagation. | `unassessed` | — |
| C2 | `D-INTL-06` provides read-side retrieval, trust-tagged XML formatting with 8KB payload limits, and fail-safe handover (save on completion, bootstrap on hydration). | `unassessed` | — |
| C3 | **Seam:** the `handover_context` JSON column on `Task` is the shared surface — `B-INTL-09` owns write-side validation (Pydantic schema, 8KB limit, truncation on ARCHIVED), `D-INTL-06` owns read-side. | `unassessed` | — |
| C4 | **Seam:** `_build_base_prompt()` calls `MemoryHydrator` to inject memory context into **every** LLM prompt. | `unassessed` | — |
| C5 | **Seam:** `save_handover_context()` persists pipeline telemetry in the runner's `finally` block. | `unassessed` | — |
| C6 | **Boundary:** `core.flow` consumes `workspace.memory` via `core/flow/context.yaml`, clean under `tach check`. | `unassessed` | — |

### Finding: 5 of the 9 cited files are capability tests, not seam tests (`FR-6`)

Raised 2026-08-13 when the tier column read `integration, unit` — the only entry in the matrix with
a `unit` tier, which the plan's own guidance calls a **diagnostic** rather than a style choice.

`git log` settles what happened. **4 of the 5 unit files were created 2026-05-10, the day
`INT-US-28` was delivered** (`test_bootstrap_protocol.py` 5, `test_handover.py` 20,
`test_runner_handover.py` 7, `test_build_base_prompt.py` 9); only `test_memory_hydrator.py` (15)
predates it. So **41 of the 56 unit tests were written during the integration story** — the story
did not merely cite existing unit tests, it wrote them.

They are real tests and they pass. What was wrong was the **attribution**: they prove `B-INTL-09`
and `D-INTL-06`'s own requirements (hydrator sanitisation and truncation, handover save fail-safes,
`_build_base_prompt` assembly), and were credited only to the contract that consumed them. Both
capabilities therefore read as having **9 FRs and zero cited tests** — `check_fr_coverage.py`
reported both `BLOCKED` — while the contract read as proven by 88 tests when its seam has 6.

**Handled, not filed.** Each file was read against each FR and given a `Proves:` citation for the
requirements it actually demonstrates — `B-INTL-09` FR-2/3/4/5/8/9 (from the *integration* file,
which is where that capability's proof genuinely lives) and `D-INTL-06` FR-4/5/6/8/9. The remaining
seven (`B-INTL-09` FR-1/6/7, `D-INTL-06` FR-1/2/3/7) are **left uncited on purpose**: no test here
proves them, and citing them to green a ledger is the gaming the sweep's failure message forbids.
`check_fr_sweep` fell **251 → 240** as a result (11 requirements honestly cited), and the baseline
was tightened to match.

**A trap worth recording, because this audit walked into it.** The first attempt put the citations
in the *first* `"""` of each file — which in all five was a fixture's or function's docstring, not
the module's, because none of these files had a module docstring. The second put a disclaimer in the
test naming the requirements deliberately left uncited. `check_fr_coverage.py` credits **any**
`FR-N` mentioned in a file that names the story, so that disclaimer silently marked all three
covered and the sweep read 237 instead of 240 — a *better* number produced by writing down that
something was untested. Both are fixed; the uncited requirements are named in the capability
designs, never in the tests.

The gate was then checked rather than blamed: across all 18 delivered stories that cite anything,
**102 of 104 declared-FR credits carry a deliberate attribution** (`Proves:`, `[Boundary/FR-5]`,
`(FR-2 producer)`), and the two exceptions are attributions this sweep's own regex failed to
recognise, not false credits. So the ledger is sound and no gate change is warranted — the hazard is
narrow: **a file that *discusses* a story's requirements is credited as proving them.**

This changes no verdict below and re-words nothing in `US-28_integration.md` (`NFR-1`). It is
recorded here because C1 and C2 are claims **about the capabilities**, and CB-2 must not credit
their seam with proof that belongs upstream of it.
