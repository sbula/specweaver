# Design: Integration-Contract Proof Audit (Test Tier Must Match Story Tier)

- **Feature ID**: TECH-017
- **Epic**: Topic 07 (Technical Debt)
- **Status**: APPROVED 2026-08-13 — designed via `specweaver-design`, Phase 6 gate passed.
- **Design Doc**: `docs/roadmap/features/topic_07_technical_debt/TECH-017/TECH-017_design.md`
- **Origin**: User mandate, 2026-07-26, after INT-US-21 SF-02 CB-1 was implemented with 16 unit
  tests and **zero** integration or e2e tests.

## Feature Overview

`TECH-017` adds a **per-story proof matrix** to the integration-contract registry. It solves
contracts claiming coverage that no test provides, by recording for each delivered claim whether an
integration or e2e test proves it — and **verifying or fixing in place rather than filing**. It
covers the 13 delivered entries in `topic_08_integration` and their 30 cited proof files, and does
not touch `INT-US-21-SUB` (`TECH-018`), capability FR coverage (`TECH-047`), or the wording of
delivered entries. Key constraints: findings are verified, cited or tested — never filed unless a
decision is needed that the auditor cannot take; finished-stories-immutable.

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

## Research Findings

### What has already shipped

Three of this ticket's four phasing steps were delivered on 2026-08-13 and are **not** re-designed
here:

| Step | Outcome |
|---|---|
| `INT-US-25` marker contradiction | Corrected; the roadmap said `✅` while the contract said `⬜ Pending`. Real delivered count was 8 of 28, not 9. |
| Skip-guard | `R8 NO SILENT SKIP` in `check_conventions.py`; four armed guards converted to hard failures. |
| Tier guardrail | `scripts/check_proof_tier.py` in the `doc` gate — a **sweep**, because the story-scoped check it replaced never fired. |

### The registry as it stands

13 delivered entries, 30 cited proof files, all of which exist.

| Entry | Proof files | Tests | Tiers |
|---|---|---|---|
| `INT-US-01` | 1 | 5 | e2e |
| `INT-US-02` | 1 | 7 | e2e |
| `INT-US-03` | 2 | 7 | e2e + integration |
| `INT-US-04` | 1 | 4 | e2e |
| `INT-US-05` | 1 | 6 | e2e |
| `INT-US-09` | 1 | 5 | e2e |
| `INT-US-21` | 3 | 61 | e2e + integration |
| `INT-US-24` | 2 | 13 | e2e + integration |
| `INT-US-25` | 9 | 75 | e2e + integration |
| `INT-US-28` | 9 | 88 | **integration + unit** |
| `INT-US-05-SF03`, `-SF04`, `INT-US-21-SUB` | 0 | 0 | — (frozen in `proof_tier.json`) |

### New finding this research surfaced

**`INT-US-28` cites 5 unit-tier files of 9.** The mix passes `check_proof_tier` because it is not
unit-*only*, but for an integration contract more than half the proof being unit-tier is precisely
the defect this ticket names. `TECH-017`'s 2026-07-26 assessment called `INT-US-28` *"Strong (OCC
races, DAG cycles, zombies)"* — that judgement was made on the integration files and did not look at
the tier split.

### What no gate can answer

`check_proof_tier` proves a contract cites integration/e2e **files**. It cannot read the contract's
prose claims and decide whether those files prove *them*. That gap is the whole of this ticket, and
it is why the deliverable is a human-read matrix rather than another checker.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Claim extraction | Auditor | Decompose each delivered contract's Integration Description into discrete, individually checkable claims | Every entry has a numbered claim list; a claim is one assertion about behaviour. |
| FR-2 | Per-claim verdict | Auditor | Read the cited tests and mark each claim proven / unproven / unprovable, naming the test function that proves it | No verdict without a named test function or an explicit statement that none exists. |
| FR-3 | Tier verdict | Auditor | Record, per entry, the tier of each proving test | An entry whose claims are carried by unit tests is reported even when `check_proof_tier` passes it. |
| FR-4 | Fix in place | Auditor | For an unproven claim: cite an existing test after reading it, or write the missing test | The matrix's unproven count falls by work, not by re-wording claims. |
| FR-5 | Escalate only decisions | Auditor | File a ticket only where a scope or descope decision is required | Every filed item names the decision and who takes it. |
| FR-6 | Capability findings | Auditor | Where an entry's gap traces to an incomplete capability, record it against that capability | The diagnostic half is captured, not just the contract half. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|------------------------|
| NFR-1 | Immutability | No delivered entry's claims are re-worded to match its tests. The matrix records the mismatch; it does not erase it. |
| NFR-2 | Evidence | Every verdict names a test function or states that none exists. A verdict without evidence is an opinion. |
| NFR-3 | No net ticket growth | The audit must not end with more open tickets than it started with, absent a genuine decision. |
| NFR-4 | Incremental | Each entry is independently auditable and committable; the audit must not require one large landing. |

## External Dependencies

None. `check_proof_tier.py`, `check_fr_coverage.py` and `check_fr_sweep.py` already exist and are
inputs, not dependencies to build.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|---|---|---|
| AD-1 | The matrix is a document, not a checker | Reading a prose claim against a test is a judgement; a mechanical proxy for it would be argued with rather than obeyed | No |
| AD-2 | Findings are verified and fixed in place, not filed | Reverses the July Goal. 13 entries × several claims would have produced dozens of unverified tickets — the inflation `closure-contract.md` now forbids | No |
| AD-3 | `docs/analysis/` is the matrix's home | It is a standalone measurement with a different audience from the ticket, per the layer map | No |
| AD-4 | Audit entry by entry, worst-first | NFR-4; also lets the diagnostic half surface capability findings early | No |

## ROI Analysis

**Investment.** 13 entries; the four largest (`INT-US-21`, `25`, `28`, `24`) carry 237 of the 271
tests. Realistically several sessions, one entry per commit.

**Returns.** The registry currently asserts 13 delivered contracts. After the audit it asserts what
is actually proven — and every unproven claim either gains a test or gains a stated decision. The
diagnostic half is the larger return: each gap that traces to an incomplete capability is a defect
found without waiting for it to bite.

**Risk.** The main one is scope creep into remediation of capability defects. NFR-3 and the
non-goals bound it.

**Refactoring opportunities.** None sought; this ticket writes tests and records verdicts.

## Developer Guides Required

None new. `closure-contract.md` already states the standard the matrix applies. The tier rule it
enforces is also stated at planning time in `.agents/AGENTS.md` and the `specweaver-dev` /
`specweaver-implementation-plan` skills — recording a rule only as a review check is what let
SF-02 CB-1 be planned unit-only the day after the rule was written, and is why `TECH-032`'s
silent-success lesson applies here too.

## Sub-Feature Breakdown

### SF-01: Matrix skeleton and the two largest contracts
Claim extraction for all 13 entries (FR-1), then full verdicts for `INT-US-28` and `INT-US-21`.
`INT-US-28` first because the tier finding above is already open against it.

### SF-02: The thin proofs
`INT-US-01`, `03`, `04`, `05`, `09` — the entries flagged in 2026-07-26 as citing capability suites
or being happy-path only. Highest expected yield of unproven claims.

### SF-03: The remainder and the capability findings
`INT-US-02`, `24`, `25`, the three zero-proof entries, and consolidation of FR-6 findings.

### SF-04: The `sw implement` loop e2e
**Scoped 2026-08-14 from SF-02 CB-3.** Four of `INT-US-03`'s eight claims — C1, C3, C4, C6 — are
unproven for one shared reason: the contract's central promise, *"generates code + tests, runs the
tests, runs C01–C08, and auto-fixes lint **in one autonomous loop**"*, is proven only as a **declared
pipeline shape** at unit tier. `test_implement_loop_worktree_isolation_e2e.py` is a real e2e but
substitutes a bash script for `D-INTL-01`, so generation never runs and only the isolation half is
exercised. **The loop has never been observed to loop**, `validate_code` has never run, and the
`D-INTL-01 → D-VAL-01`/`D-VAL-05` pipe has never carried anything.

Closing it is `FR-4` work — *write the missing test* — but it is a sub-feature's worth, not a commit
boundary's: a scripted-LLM e2e driving `sw implement` through generate → lint_fix → run_tests →
validate_code **including a loop-back iteration**, over real `ruff` and real `pytest`. It also needs
the `ScriptedLLM` / `scripted_world` harness extracted out of
`test_feature_decomposition_e2e.py`, where it is currently file-local — which is why this is scoped
rather than bolted onto SF-02.

This does not widen `TECH-017`. `FR-4` already obliges the audit to write the missing test; `AD-2`
already rejects filing findings instead of fixing them. SF-04 is where that obligation lands when
the test is large enough to need its own boundaries.

## Execution Order

SF-01 → SF-02 → SF-03 → SF-04. Strictly sequential for the first three: SF-01 establishes the
claim-extraction format the others follow, and re-cutting that format mid-audit would invalidate
earlier verdicts.

**SF-04 is sequenced last but is not blocked by SF-03.** It is the only sub-feature that builds
rather than assesses, and its scope was fixed by SF-02 CB-3; it may be taken before SF-03 if the
`INT-US-03` gap is judged more urgent than the remaining six entries' verdicts.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Skeleton + two largest | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | The thin proofs | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Remainder + capability findings | SF-02 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-04 | The `sw implement` loop e2e | SF-02 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Non-Goals

- **`INT-US-21-SUB`** — `TECH-018` audited it 2026-08-13; its finding 2 is this ticket's result for
  that add-on.
- **Capability FR coverage** — `TECH-047` swept it; 251 uncited requirements are its matrix, not
  this one.
- **Remediating capability defects** the audit exposes. Record them (FR-6); fixing them is theirs.
- **Re-wording any delivered contract** to match its tests (NFR-1).
- **A checker for claim-vs-proof.** AD-1.

## Session Handoff

Next action: Phase 6 approval, then `specweaver-implementation-plan TECH-017 SF-01`. The matrix
lands at `docs/analysis/integration_contract_proof_matrix.md`. Read the 2026-08-13 annotations in
git history for the three delivered steps before touching anything.


---

# Appendix — the measurement this design is built on

Preserved verbatim from the pre-design stub (2026-07-26, re-measured 2026-08-13) when
`specweaver-design` restructured this document. **Not superseded:** the FRs above are derived from
these findings, and a reader who plans SF-01 without them will re-measure a tree that has already
been measured twice. The annotations are the live worklist; the 2026-07-26 body is the record of
what was found then.

**2026-08-14 — SF-01 delivered, SF-02 planned.** SF-01 closed all three boundaries: the 13-entry
skeleton, `INT-US-28` (6 claims) and `INT-US-21` (4 → 8, after CB-3 found CB-1 had extracted only
each contract's first sentence). Matrix census: 13 entries, 46 claims. SF-02's plan is APPROVED and
ordered worst-first per `AD-4`; it starts at CB-1, re-extraction of all five thin entries.

**2026-08-14 — SF-02 delivered.** CB-1 re-extracted (+11 claims, census 57); CB-2 `INT-US-09` (11
verdicts, C6 `unprovable` as written); CB-3 `INT-US-03` (8 verdicts, 4 unproven → scoped as SF-04);
CB-4 the thin trio (7 verdicts, 4 unproven with no candidate proof anywhere). Two decisions were
escalated rather than filed: the `sw implement` loop e2e (now SF-04) and whether `INT-US-04`'s and
`INT-US-05`'s claimed integrations were ever built — the second was then answered by mutation
(no validation-output table exists).

**2026-08-14 — SF-03 delivered, and the audit is complete.** CB-1 re-extracted the last three
(57 → 64 claims); CB-2 `INT-US-25` (13 verdicts), CB-3 `INT-US-24` (6), CB-4 `INT-US-02` and the
three zero-proof entries (5); CB-5 consolidated the `FR-6` findings across 12 capabilities.
**All 64 claims on all 13 entries carry a verdict.** Zero tickets were filed across all three
sub-features; the only scheduled work is SF-04.

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

### 6. Proof that exists and cannot be seen — a decision this ticket must take

Found 2026-08-13 while re-attributing `INT-US-28`'s tests. `check_fr_coverage.py` skips any test
file that does not **name the story**, and collects `FR-N` only from the files that survive that
filter. So a test can carry a perfectly good attribution and still be invisible:

```
tests/unit/workspace/test_memory_repository_core.py:700
    """FR-7: Transition to ARCHIVED sets handover_context = None."""
```

That is `B-INTL-09` FR-7, deliberately labelled by whoever built it, and the file never says
`B-INTL-09` — so the capability reports FR-7 as uncited. `tests/integration/sandbox/test_worktree_atoms.py`
(*"Verifies FR-1, FR-2, FR-6 natively"*) is the same shape. This is a **third** failure mode beyond
the two in `closure-contract.md`: a missing citation makes a requirement look unproven, and a
citation in an unnamed file makes proof **invisible**.

**The decision — do not implement either side before it is taken.**

- **(a) Fix the naming.** Add the capability id to the files that already prove it. Keeps the gate's
  rule simple and unambiguous — one story name, one ledger — and every citation stays greppable.
  Costs a sweep over the offending files, and nothing stops the next author omitting the name again.
- **(b) Fix the algorithm.** Let a test declare what it proves without naming the story: read a
  structured attribution (`Proves: <ID> FR-N`, already the convention) wherever it appears, and drop
  the file-must-name-the-story precondition for those. Richer, and it is the direction that makes
  "this test tests this requirement" a first-class fact rather than a grep coincidence.

**(b) is not free, and the risk is specific:** the story-name filter is what currently stops an
`FR-2` belonging to one capability being credited to another, and it is also most of what keeps
fixture data out — `test_c09_traceability.py` writes `"Hello FR-1 and NFR-2"` as test *input*, and
`test_polyglot_validation_e2e.py` writes `"Requirements: FR-1, FR-2, FR-3"`. Loosen the precondition
without a strict attribution grammar and those become citations. So (b) means *tightening* what
counts as a citation at the same time as widening where it may live.

Not filed as a ticket: it is a decision, and it belongs to the audit that found it.

### 7. Requirements that are tested badly, or not at all — the audit's actual output

Distinct from finding 6, and easy to conflate with it. Finding 6 is about proof that exists and is
mis-filed. This one is about proof that is **thin or absent**, which no re-filing will fix.

Two populations, and the audit owes a verdict on each rather than a count:

- **Not tested at all.** Requirements with no test anywhere, once finding 6's invisible proof has
  been accounted for. `B-INTL-09` FR-1 (schema definition) and FR-6 (alembic integration) are
  open examples — neither assessed yet in either direction.
- **Not tested well.** Requirements with a citation whose test does not actually establish the
  claim. `D-INTL-06` FR-3 is the live candidate: the hydrator does not filter at all, it delegates
  `max_age_hours=24` to the repository (`hydrator.py:162`), so a hydrator-level test cannot prove
  the filtering rule, and the repository test that could is unnamed (finding 6).

**Order matters.** Resolving finding 6 first is what makes this population measurable — until
invisible proof is either surfaced or ruled out, "untested" and "unnamed" are indistinguishable, and
this ticket already published one claim ("no existing test proves them") that was wrong for exactly
that reason and had to be corrected the same day.

The work is per-requirement verdicts in the matrix and the missing tests written, **not** a ticket
per gap — that is the inflation this backlog was explicitly told to stop.
