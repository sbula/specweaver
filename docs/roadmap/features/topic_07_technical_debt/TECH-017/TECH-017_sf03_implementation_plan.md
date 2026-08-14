# Implementation Plan: Integration-Contract Proof Audit [SF-03: The remainder and the capability findings]

- **Feature ID**: TECH-017
- **Sub-Feature**: SF-03 — The remainder and the capability findings
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-017/TECH-017_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-017/TECH-017_sf03_implementation_plan.md
- **Status**: APPROVED 2026-08-14

## Scope

The last six entries — `INT-US-02`, `INT-US-24`, `INT-US-25`, and the three zero-proof entries
`INT-US-05-SF03`, `INT-US-05-SF04`, `INT-US-21-SUB` — plus consolidation of every `FR-6` capability
finding SF-01 and SF-02 produced. **17 unassessed claims**, and the audit closes with this.

## What Phase 0 found

### 1. CB-1's length predictor ranks the work, and it has held twice

Under-extraction tracked the Integration Description's length exactly: one-sentence contracts were
extracted correctly, and `INT-US-09` — the longest in the tree — had been read from the wrong
paragraph entirely (3 → 11). Applied here:

| Entry | Description | CB-1 claims | Cited proof | Expectation |
|---|---|---|---|---|
| `INT-US-25` | **249 words** | 9 | 9 files / 75 tests | heaviest; `INT-US-09` went 3 → 11 at comparable length |
| `INT-US-24` | 93 words | 3 | 2 / 13 | under-extracted, as `INT-US-03` was (5 → 8) at 89 |
| `INT-US-02` | 32 words | 2 | 1 / 7 | probably complete |

### 2. The auditor wrote `INT-US-25`'s contract

It was authored earlier in the same session that is now auditing it, when the US-25 epic was closed.
Verdicting it is self-review: reading one's own claims against proof one selected. That is precisely
the condition under which this week's four vacuous assertions were written — every one by someone
who believed the claim.

### 3. The three zero-proof entries are not equivalent

`INT-US-05-SF03` and `INT-US-05-SF04` cite no test file and are frozen in
`scripts/baselines/proof_tier.json` with named owners; they integrate `C-SENS-02` and `B-INTL-02`,
both of which have their own suites, so proof may exist and simply be uncited. `INT-US-21-SUB` is
different in kind: `TECH-038` already established that its "Recursive Planning" claim describes
behaviour that was never built and never descoped, so its verdict is likely `unprovable`, not
`unproven`.

### 4. Mutation testing exists now, and it changes what a `proven` verdict can mean

SF-02 closed without it. Since then `scripts/_mutate.py` and `_mutate_campaign.py` landed, and the
first campaign found that `INT-US-05` C1's survivor was a **live defect** — the context assembler
read a key the atom never exports, so skeleton context had never reached a generation or review
prompt. Reading the contract, grepping its proof and counting subject words all missed it.

## Decisions taken at the Phase 4 gate

- **D-1 — Audit `INT-US-25`, and mutation-verify every claim marked `proven` on it.** Mutation is
  indifferent to who wrote the claim, which is the bias-independent check self-review lacks. The
  declaration alone would change nothing about how the verdicts were reached.
- **D-2 — Mutation is required for `proven` verdicts, everywhere in SF-03.** A `proven` verdict is
  the claim the *audit* makes, so it is the one worth falsifying. `unproven` and `unprovable` need
  no mutant — there is nothing being asserted to break. Doubt is explicitly **not** the trigger:
  every vacuous assertion this week was written without any.
- **D-3 — Zero-proof entries get FR-4's treatment**: search for proof elsewhere, cite it after
  reading, and record `unproven` only if none exists. `INT-US-21-SUB` is expected to resolve
  `unprovable` on `TECH-038`'s evidence.

## What this plan carries

Added at the Phase 5.0 pre-check, which found six of these covered in substance but not traceably —
the same omission that lost `FR-6` from SF-02's first draft entirely.

| | Where it lands |
|---|---|
| `FR-1` claim extraction | CB-1 |
| `FR-2` per-claim verdict | CB-2, CB-3, CB-4 — `proven` naming the function, `unproven`, or `unprovable` with the reason |
| `FR-3` tier verdict | recorded with each verdict |
| `FR-4` fix in place | cite after reading, or write the test; D-3 for the zero-proof entries |
| `FR-5` escalate only decisions | *What is NOT filed*, below |
| `FR-6` capability findings | **CB-5**, its own boundary |
| `NFR-1` immutability | no contract is re-worded; mismatches are recorded |
| `NFR-2` evidence | every verdict names a test function or states that none exists; `proven` additionally names a killed mutant (D-2) |
| `NFR-3` no net ticket growth | *What is NOT filed* |
| `NFR-4` incremental | five boundaries, each independently committable |
| `AD-1` the matrix is a document | mutation reports go to `.tmp/`; conclusions are copied in by hand, never written by a tool |
| `AD-2` verified and fixed in place | `FR-4`; findings are not filed in place of being fixed |
| `AD-3` `docs/analysis/` is the matrix's home | all verdicts land there |
| `AD-4` worst-first | CB-2 takes `INT-US-25`, the largest |

## Commit boundaries

### CB-1 — Re-extract `INT-US-02`, `INT-US-24`, `INT-US-25`

Read each contract's **entire** entry — Status, Integration Description, Verifiable Proof, notes —
weighting effort by length per finding 1. Add a row per falsifiable assertion, including exclusions
and universal negatives. Every new row `unassessed`; no verdicts here.

No tests: this boundary changes one analysis document (design D-3, as SF-01 and SF-02 CB-1).

Done when: every assertion in all three contracts is a row, and the census names the before/after
counts per entry.

### CB-2 — `INT-US-25`, the largest and the self-reviewed

Worst-first per `AD-4`. Run the cited files in isolation first — that is how SF-02 found the
`INT-US-05` width-flake, and nothing else does it.

Verdict each claim (`proven` naming the test **function**, `unproven`, `unprovable` with the
reason), record the tier (FR-3), and for **every** claim marked `proven`, kill a mutant (D-1/D-2).
State the mutant and its result in the matrix entry, not just the verdict.

Where a gap traces to a capability, record it against that capability (FR-6) for CB-5.

Done when: every `INT-US-25` claim has a verdict with evidence, every `proven` one names a killed
mutant, and every `unproven` one carries a citation or a new test.

### CB-3 — `INT-US-24`

Same steps. Expect re-extraction to have grown its claim count.

### CB-4 — `INT-US-02` and the three zero-proof entries

`INT-US-02` as above. For the zero-proof three, D-3 applies: search `C-SENS-02`'s and `B-INTL-02`'s
suites for proof of what each entry claims, cite after reading, else `unproven` with the owner
named. `INT-US-21-SUB` is verdicted on `TECH-038`'s evidence and is **not** re-litigated — that
ticket's finding is this audit's result for that add-on (design Non-Goals).

### CB-5 — Consolidate the `FR-6` capability findings

The audit's second deliverable, and the one most easily dropped: every finding recorded *against a
capability* rather than a contract, gathered into one place so the capabilities' owners can act.

Already outstanding from SF-01 and SF-02:

| Capability | Finding |
|---|---|
| `B-INTL-09`, `D-INTL-06` | their own tests were written under `INT-US-28` and credited to it; re-attributed, and 7 requirements remain uncited |
| `D-EXEC-02` | `INT-US-09` C8/C9 — the Main-Branch-Wins reconcile seam is proven only at unit tier |
| `D-INTL-01` | `INT-US-03` C1/C6 — no test drives it into the QA runner; the loop is proven as a declared shape (owned by SF-04) |
| `D-VAL-05` | `INT-US-03` C3 — `validate_code` is declared and never exercised through the loop |
| `E-FLOW-01` | `INT-US-04` C1 — the config DB has **no table** for validation output; the claimed surface does not exist |

Plus whatever CB-2 to CB-4 add. Consolidation means one section in the matrix listing them by
capability with their evidence — **not** a ticket each (FR-5, NFR-3).

Done when: every `FR-6` finding from all three sub-features appears once, attributed to a capability,
with the entry that surfaced it named.

## What is NOT filed (FR-5, NFR-3)

An `unproven` verdict is not a ticket. A ticket is filed only where a claim is `unprovable` **and**
its contract would have to change to become provable — the user's call, because `NFR-1` forbids
re-wording a delivered contract.

SF-02 closed with **zero** net ticket growth and two escalated decisions, one of which
(`INT-US-04` C1) the mutation run then answered outright. SF-03 holds the same bar.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | Self-review makes `INT-US-25` read better than it is | D-1: every `proven` must kill a mutant. If a mutant survives, the verdict is not `proven` regardless of what the contract or I say |
| R-2 | A surviving mutant is treated as a coverage gap when it is equivalent | Confirm the edit changes observable behaviour before recording — `INT-US-05` C1's survivor was neither equivalent nor a coverage gap but a live defect, and only checking told them apart |
| R-3 | Mutation cost inflates the boundaries | Only `proven` verdicts need one, ~40s each. `INT-US-25`'s 9+ claims is the worst case at roughly 6 minutes; run them as one campaign, not nine invocations |
| R-4 | `FR-6` consolidation is dropped, as it was omitted from SF-02's first draft entirely | It has its own boundary (CB-5) with its own Done-when, rather than being a step inside another |
| R-5 | Re-extraction inflates claims beyond what the boundaries can verdict | CB-1 is extraction-only, so counts are known before verdict work begins; split CB-2 if `INT-US-25` exceeds ~14 claims |

## Session Handoff

SF-01 delivered the skeleton and the two largest contracts; SF-02 delivered the five thin entries,
escalated the `sw implement` loop e2e as SF-04, and produced the mutation tooling. Matrix census:
13 entries, 57 claims, of which 17 remain unassessed — all of them SF-03's. SF-04 is independent and
may be taken before or after.
