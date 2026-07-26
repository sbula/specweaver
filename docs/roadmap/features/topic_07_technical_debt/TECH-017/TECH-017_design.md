# Design: Integration-Contract Proof Audit (Test Tier Must Match Story Tier)

- **Feature ID**: TECH-017
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: User mandate, 2026-07-26, after INT-US-21 SF-02 CB-1 was implemented with 16 unit
  tests and **zero** integration or e2e tests.

## The Principle Being Enforced

**An `INT-US-NN` story is an integration contract. Its proof must therefore be integration and e2e
tests.** Unit tests are the right tool for TDD of a *unit*, and are legitimate inside an integration
story only to fix a specific behaviour or fill a narrow gap discovered while integrating.

The corollary is a **diagnostic, and it is the more valuable half**:

> If an integration story needs a large amount of unit testing, something went wrong *earlier*. The
> capability stories it was supposed to be integrating shipped incomplete.

INT-US-21 demonstrated this three times over — every one a capability defect, not an integration
gap:

| Found while integrating | Should have been caught by |
|---|---|
| `draft+feature` / `validate+feature` never registered, so the shipped `feature_decomposition.yaml` could not run at all | `D-INTL-02` |
| `RunContext.plan` documented as "set by runner hook" with **zero writes anywhere in `src/`** | `D-INTL-03` |
| `DecompositionPlan.proposed_dal` is a required enum that **cannot be serialized to YAML** (`RepresenterError`, 100% of plans) | `C-INTL-01` / `D-INTL-02` |

So this audit must produce findings against the **capability** stories too, not only the integration
contracts. A unit-test-heavy integration story is a *symptom*; the ticket exists to find the disease.

## Problem Statement — measured 2026-07-26

**9 of 28 integration base contracts are delivered:** `INT-US-01, 02, 03, 04, 05, 09, 24, 25, 28`.
Audit of their declared proof and of the 104 integration / 44 e2e test files found:

### 1. A delivered contract with no proof at all

`US-25_integration.md` — **`Verifiable Proof: [Pending]`**, while `master_story_roadmap.md` marks
`INT-US-25` as `✅`. The proof mandate was simply never satisfied.

### 2. Contracts whose "proof" is a capability suite, not a contract journey

`INT-US-01` → `test_standards_e2e.py` · `INT-US-04` → `test_mcp_flow_e2e.py` ·
`INT-US-05` → `test_lineage_e2e.py`

These are pre-existing suites proving the *capability* works. None was written to prove the
*integration contract's journey* works. This is the same tier-mismatch one level up: pointing at
someone else's test instead of proving the seam.

### 3. Thin or happy-path-dominated contract proofs

| Story | Tests | Assessment |
|---|---|---|
| `INT-US-03` | 3 e2e | 2 happy paths + 1 host-execution assertion. **No failure mode at all** — for a story about sandboxed execution |
| `INT-US-09` | 6 e2e | All six are happy-path isolation variants. No worktree-creation failure, dirty worktree, or teardown failure |
| `INT-US-02` | 7 e2e | Good spread, but E6/E7 were **vacuous until 2026-07-25** — exit-code-only assertions, a fixture that could never pass its own battery, and **live paid Gemini calls in a "mocked" test** |
| `INT-US-24` | 9 e2e | **The standard to hold others to** — includes retries-exhausted, zero-collected, resume-heals, resume-without-LLM-degrades, generator exhaustion |
| `INT-US-28` | 20 integration | Strong (OCC races, DAG cycles, zombies) |

### 4. Systemic holes in the flow suite

- **Graceful shutdown is effectively unproven.** `CancelledError`: **0 files**. `atexit`: **0**.
  `KeyboardInterrupt`/`SIGINT`/`SIGTERM`: 2 files — and the only e2e one
  (`test_cqrs_e2e.py:44`) **skips on Windows**, the development platform. `PipelineRunner`
  saves handover and flushes telemetry in a `finally:`; nothing verifies either survives a Ctrl-C.
  The fan-out spawns `asyncio.Task`s and no test cancels one.
- **11 of 43 flow/workflow test files have zero failure-path tests**, including
  `test_orchestration_integration.py` — the *only* integration coverage of the fan-out that
  `TECH-014` says is already mis-attributing telemetry — and
  `test_session_policy_fullchain.py`, where the C-EXEC-06 policy layer is unprotected while the
  mechanism layer beneath it is tested.
- **12 tests verify essentially nothing** — 3 with no assertion of any kind, 9 asserting only
  `exit_code == 0` (which cannot distinguish PARKED from COMPLETED from "did nothing"). Includes a
  **zombie-process** test whose sole assertion is an exit code.
- **Latent skip guards.** `test_feature_pipeline.py:144,240` still carry
  `if not path.exists(): pytest.skip(...)`. A wrong `PIPELINES_DIR` made two tests skip **silently
  for months** until 2026-07-25; the guard that allowed it is still armed. Separately, four suites
  are `skipif`-gated on `git`+`bash` — on a machine lacking them, the entire delivered proof for
  `INT-US-03`, `INT-US-09` and `C-EXEC-06` vanishes behind a green suite.

## Goal

For **every** delivered integration contract, a per-story matrix of *what the contract claims* versus
*what an integration or e2e test actually proves* — with each unproven claim becoming a filed finding.
Plus findings against the capability stories whose incompleteness the audit exposes.

## Candidate Approaches (not yet designed)

1. **Per-story audit, `INT-US-24` as the benchmark.** For each contract: read its FRs and Verifiable
   Proof, then read the cited tests and classify each FR as proven-by-e2e / proven-by-integration /
   **claimed-only**. Cheapest and directly actionable; produces one findings list per story.
2. **Traceability enforcement.** Require every `INT-US-NN` FR to name the integration/e2e test that
   proves it, and add a check that the named test exists and is not skipped. Stronger, but needs a
   convention for the linkage.
3. **Tier-ratio guardrail.** A check that flags an `INT-US` commit boundary adding unit tests but no
   integration/e2e tests. Mechanical, catches the exact regression that triggered this ticket, and
   its false positives are the cases worth a human glance anyway.

## Non-Goals (proposed, pending design)

- Rewriting the capability-level unit suites. Their unit tests are correct *for units*.
- Retro-fixing every thin proof in one pass — expect a phased breakdown, delivered story by story.
- Changing any delivered story's entry. **Findings become new stories or TECH tickets**
  (finished-stories-immutable), never edits to the delivered contract.

## Guardrail to Ship With the Fix

Approach 3, plus wording in `.agents/AGENTS.md` and the `specweaver-implementation-plan` /
`specweaver-dev` skills making the tier rule explicit **at planning time**, not just at review time.
Recording it as a review check was already tried on 2026-07-25 (the pre-commit Vacuous Proof Check)
and did not prevent SF-02 CB-1 from being planned unit-only the very next day — because the test plan
had already deferred all integration work to a single later commit boundary.

## Next Step

Run the `specweaver-design` skill against this stub before any implementation.
