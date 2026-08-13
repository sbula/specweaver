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

## Problem Statement — measured 2026-07-26, **re-measured 2026-08-13**

> [!IMPORTANT]
> **Re-measured 2026-08-13 before planning, against a tree ~30 tickets younger.** Four of the six
> findings below are unchanged, one is substantially closed by work this ticket did not do, and one
> is no longer comparable. Each is annotated inline. **Plan from the annotations, not from the
> 2026-07-26 body** — the original numbers are kept as the record of what was found, not as a
> current worklist. The same re-measurement discharged `TECH-018` in one session.
>
> One scope change: **`INT-US-21-SUB` is out of scope here** — `TECH-018` audited it on 2026-08-13
> and its finding 2 is this ticket's result for that add-on. The two were required not to
> double-cover it.

**9 of 28 integration base contracts are delivered:** `INT-US-01, 02, 03, 04, 05, 09, 24, 25, 28`.
Audit of their declared proof and of the **148** test files then present (104 integration / 44 e2e)
found:

### 1. A delivered contract with no proof at all

`US-25_integration.md` — **`Verifiable Proof: [Pending]`**, while `master_story_roadmap.md` marks
`INT-US-25` as `✅`. The proof mandate was simply never satisfied.

> **2026-08-13 — still open, and worse than recorded: the two documents contradict each other.**
> `master_story_roadmap.md:594` still marks `INT-US-25` `✅`, while `US-25_integration.md` reads
> `Status: ⬜ Pending`, `Integration Description: [Pending definition...]`, `Verifiable Proof:
> [Pending]`. So this is not a delivered contract missing its proof — it is a contract that was
> **never started** and is marked delivered in the roadmap. The roadmap ✅ is the wrong one, which
> makes the real count **8 of 28 delivered, not 9**. **Marker corrected 2026-08-13** — the roadmap
> line is now `[ ]`, matching its contract file and the convention every other pending contract
> follows.
>
> **Left standing deliberately, for this audit to rule on:** `US-25` the *epic* is still headed
> `### 🟢`, and all five of its capabilities (`C-VAL-01`, `C-VAL-02`, `D-VAL-02`, `D-VAL-04`,
> `C-VAL-03`) genuinely are ✅. So the capability work shipped and the integration contract was
> never written — **built-but-not-integrated, the exact shape `INT-US-21` exposed and closed**. That
> is a finding about the epic, not a marker typo, so it was not changed silently. Whether a 🟢 epic
> may have an undefined integration contract is this audit's call.

### 2. Contracts whose "proof" is a capability suite, not a contract journey

`INT-US-01` → `test_standards_e2e.py` · `INT-US-04` → `test_mcp_flow_e2e.py` ·
`INT-US-05` → `test_lineage_e2e.py`

These are pre-existing suites proving the *capability* works. None was written to prove the
*integration contract's journey* works. This is the same tier-mismatch one level up: pointing at
someone else's test instead of proving the seam.

> **2026-08-13 — unchanged.** All three contracts still cite the same three files, which still
> exist (relocated under `tests/e2e/capabilities/`) at 6, 4 and 6 tests respectively. No
> contract-journey test has been added for any of them.

### 3. Thin or happy-path-dominated contract proofs

| Story | Tests | Assessment |
|---|---|---|
| `INT-US-03` | 3 e2e | 2 happy paths + 1 host-execution assertion. **No failure mode at all** — for a story about sandboxed execution |
| `INT-US-09` | 6 e2e | All six are happy-path isolation variants. No worktree-creation failure, dirty worktree, or teardown failure |
| `INT-US-02` | 7 e2e | Good spread, but E6/E7 were **vacuous until 2026-07-25** — exit-code-only assertions, a fixture that could never pass its own battery, and **live paid Gemini calls in a "mocked" test** |
| `INT-US-24` | 9 e2e | **The standard to hold others to** — includes retries-exhausted, zero-collected, resume-heals, resume-without-LLM-degrades, generator exhaustion |
| `INT-US-28` | 20 integration | Strong (OCC races, DAG cycles, zombies) |

> **2026-08-13 — unchanged.** `INT-US-03` still cites 3 e2e (plus 5 integration tests in
> `test_cli_implement_isolation.py`); `INT-US-09` still 6 e2e, still all isolation happy paths.
> `INT-US-21` has since joined `INT-US-24` and `INT-US-28` as a benchmark: **24 e2e scenarios**
> including interrupt survival, and every assertion reads the persisted run status rather than the
> exit code — because `PARKED` and `COMPLETED` both exit `0`, which is why `INT-US-02`'s E6/E7 were
> green for months without advancing past their first gate. Hold the thin proofs to that.

### 4. Systemic holes in the flow suite

- **Graceful shutdown is effectively unproven.** `CancelledError`: **0 files**. `atexit`: **0**.
  `KeyboardInterrupt`/`SIGINT`/`SIGTERM`: 2 files — and the only e2e one
  (`test_cqrs_e2e.py:44`) **skips on Windows**, the development platform. `PipelineRunner`
  saves handover and flushes telemetry in a `finally:`; nothing verifies either survives a Ctrl-C.
  The fan-out spawns `asyncio.Task`s and no test cancels one.

  > **2026-08-13 — substantially CLOSED, by work this ticket did not do.** `INT-US-21` SF-03 CB-4
  > (`39aa3860`, 2026-07-28) shipped `TestE12InterruptSurvival` (4 tests) and
  > `TestTeardownActuallyRuns` in `test_feature_decomposition_e2e.py`, which assert **handover is
  > saved** and **telemetry is flushed** on the interrupt path — precisely the `finally:` contract
  > this finding said nothing verified. `KeyboardInterrupt` is now in **6** test files, not 2, and
  > `SIGBREAK` routes through the same graceful-cleanup handler so the SIGINT e2e branches
  > per-platform instead of skipping on Windows.
  >
  > That Windows half was corrected earlier, on **2026-08-01**, and is recorded here so the
  > original finding is not re-raised: `test_cqrs_e2e.py::test_story_9_sigint_survival` no longer
  > skips on Windows because `_signals.py` now routes Ctrl+Break (`SIGBREAK`) through the same
  > handler as SIGINT/SIGTERM. That closes ONE instance of "graceful shutdown effectively
  > unproven", not the finding.
  > **What remains open:** `CancelledError` is still **0 files** and `atexit` still **0**, and the
  > fan-out still spawns `asyncio.Task`s that no test cancels. Scope this finding to task
  > cancellation only — the process-signal half is done.

- **11 of 43 flow/workflow test files have zero failure-path tests**, including
  `test_orchestration_integration.py` — the *only* integration coverage of the fan-out that
  `TECH-014` says is already mis-attributing telemetry — and
  `test_session_policy_fullchain.py`, where the C-EXEC-06 policy layer is unprotected while the
  mechanism layer beneath it is tested.

  > **2026-08-13 — re-derive before using.** `TECH-014` has since shipped, so the fan-out race this
  > cites is fixed and the file's coverage question is now "does it prove the fix", not "does it
  > guard the race". The 11/43 ratio itself is not comparable: the test tree was reorganized
  > (`tests/e2e/capabilities/…`) and there are now 149 files matching `*flow*`.

- **12 tests verify essentially nothing** — 3 with no assertion of any kind, 9 asserting only
  `exit_code == 0` (which cannot distinguish PARKED from COMPLETED from "did nothing"). Includes a
  **zombie-process** test whose sole assertion is an exit code.

  > **2026-08-13 — NOT comparable; re-derive.** The tree reorganization means the original 12 cannot
  > be tracked by path. A fresh repo-wide AST scan finds **38** test functions with no assertion of
  > any kind (excluding `tests/manual/`), but most are legitimate *does-not-raise* shapes
  > (`test_stop_is_noop`, `test_..._never_reaches_the_caller`) whose assertion is the absence of an
  > exception. The finding is still real — `test_output_is_valid_python` and `test_registry` assert
  > nothing and name a claim they do not check — but the number must be re-derived with a
  > discriminator that separates *no assertion* from *no-raise is the assertion*, or the audit will
  > report 38 defects where there are a handful.

- **Latent skip guards.** `test_feature_pipeline.py:144,240` still carry
  `if not path.exists(): pytest.skip(...)`. A wrong `PIPELINES_DIR` made two tests skip **silently
  for months** until 2026-07-25; the guard that allowed it is still armed. Separately, four suites
  are `skipif`-gated on `git`+`bash` — on a machine lacking them, the entire delivered proof for
  `INT-US-03`, `INT-US-09` and `C-EXEC-06` vanishes behind a green suite.

  > **2026-08-13 — still armed, unchanged.** Both guards survive verbatim at
  > `tests/integration/core/flow/engine/test_feature_pipeline.py:145` and `:241` (the file moved;
  > the guards did not). The file now carries a comment at `:39` **describing the very incident**
  > and leaves the mechanism that caused it in place — the strongest single argument in this ticket
  > that recording a lesson is not the same as removing its cause. The `skipif` gate is now **11**
  > suites, not four. This is the cheapest guardrail in the ticket: a `pytest.skip` for a path the
  > repo controls should be a failure, not a skip.

### 5. The capability side, measured 2026-08-13

This ticket's own principle says the audit *"must produce findings against the **capability**
stories too, not only the integration contracts"*. That half now has a number.

`scripts/check_fr_coverage.py` run across all **103** capabilities with a design document:

| Result | Count |
|---|---|
| clean | **8** |
| `BLOCKED` — an FR carried by no plan, or cited by no test | **46** |
| could not run | 49 |

The gate has existed since `TECH-025` and is story-scoped, so it only ever fires when a human
passes an ID. `C-INTL-01` is the worked example (`TECH-046`): FR-1 and FR-3 carried by no plan, all
five FRs cited by no test, and the capability marked ✅ — while its design specifies recursive
multi-level decomposition that was never built and never descoped.

**Do not turn this into a gate as-is.** 46 blocked capabilities would be ratcheted on sight and the
ratchet would then mean nothing, which is the failure mode `check_useless_asserts.py`'s docstring
warns about for detectors. It is audit input, not a guardrail — the per-story matrix this ticket
already owes is where each of the 46 gets a verdict.

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

Run the `specweaver-design` skill against this stub before any implementation. **Start from the
2026-08-13 annotations, not the 2026-07-26 body.**

Suggested phasing, cheapest-first — each is independently shippable, so the ticket does not have to
be planned as one multi-session block:

1. **The `INT-US-25` marker contradiction** (§1). One line of evidence, no test reading. Also
   corrects the delivered-contract count the rest of the audit is scoped by: **8 of 28, not 9**.
2. **The skip-guard guardrail** (§4). Mechanical, and the finding this ticket has now watched
   survive its own written-down lesson. Turn a `pytest.skip` on a repo-controlled path into a
   failure; decide separately what the 11 `skipif`-gated suites should do on a machine without
   `git`/`bash` (fail loudly beats vanishing behind a green suite — same shape as `TECH-032`).
3. **The tier-ratio guardrail** (Approach 3 below), which is the half that stops the regression
   recurring while the audit itself is still unscheduled.
4. **The per-story matrix**, the expensive half — 8 contracts, `INT-US-21`/`24`/`28` as the
   benchmark, `INT-US-21-SUB` excluded (`TECH-018`).
