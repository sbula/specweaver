# Implementation Plan: Integration-Contract Proof Audit [SF-01: Skeleton + the two largest]

- **Feature ID**: TECH-017
- **Sub-Feature**: SF-01 — Matrix skeleton and the two largest contracts
- **Design Document**: `docs/roadmap/features/topic_07_technical_debt/TECH-017/TECH-017_design.md`
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: `docs/roadmap/features/topic_07_technical_debt/TECH-017/TECH-017_sf01_implementation_plan.md`
- **Status**: APPROVED 2026-08-13 — Phase 5 gate passed.

## Scope

Claim extraction for all 13 delivered contract entries (FR-1), then full per-claim verdicts for
`INT-US-28` and `INT-US-21` (FR-2, FR-3), fixing in place what is fixable (FR-4).

Output: `docs/analysis/integration_contract_proof_matrix.md`.

## Preconditions — verified 2026-08-13

`python scripts/check_story_preconditions.py TECH-017` exits **0** (2 passed, 2 warnings, 0
failures). The two warnings — no `Core Required (MVS)` list and no `Verifiable Proof` field in the
roadmap section — are expected for a `TECH` ticket and are not blocks.

## Research Notes

Facts established in Phase 0-3; cited so no boundary re-derives them.

**`INT-US-28` — 9 proof files, 88 tests, and the split is the finding.**

| Tier | Files | Tests |
|---|---|---|
| integration | 4 | 32 |
| unit | 5 | 56 |

Of the 32 integration tests, **26 sit in `test_memory_integration.py`**, which covers `B-INTL-09`'s
own lifecycle — the capability, not the seam. The contract claims **two integration seams**
(`handover_context` as the shared surface; `_build_base_prompt` / `save_handover_context` into
`core.flow`), and those are carried by the remaining **6** tests across three files.

The contract is **honest about tiers** — it labels its unit files *"Unit tests for sanitization,
trust tagging, truncation…"*. This is a proof gap, not a disguise, and the matrix must say so in
those terms.

Minor drift to record, not fix: the contract says *"20 integration tests"* where
`test_memory_integration.py` now has **26**.

**`INT-US-21` — 3 proof files, 61 tests.** Already re-measured 2026-08-13 and treated as a
benchmark alongside `INT-US-24`: every assertion reads persisted run status rather than exit code,
because `PARKED` and `COMPLETED` both exit `0`.

## Decisions taken at the Phase 4 gate

| # | Decision |
|---|---|
| D-1 | **A claim = one assertion about behaviour at a seam.** Not one sentence. `INT-US-28` yields ~6 claims, not ~20 fragments. Without this, verdicts are not comparable across entries. |
| D-2 | **Tier is recorded, not prosecuted.** An entry that transparently cites unit tests is reported as a proof gap; the matrix does not accuse a contract of dishonesty it did not commit. |
| D-3 | **Coverage means the tests the audit writes.** A boundary that only records verdicts carries no test; a boundary that finds an unproven claim writes the integration/e2e test that proves it, and that is its coverage. Inventing tests to satisfy a rule about code would be the checkbox behaviour this ticket exists to remove. |

## Commit Boundaries

### CB-1 — Claim extraction, all 13 entries

Establishes the format every later verdict depends on, which is why it lands alone.

Steps:
1. For each delivered entry, read its `Integration Description` and `Integration Seams`.
2. Decompose into numbered claims under D-1. A claim names a behaviour and the seam it crosses.
3. Write the matrix skeleton: one section per entry, a table of `claim | verdict | evidence`,
   every verdict initially `unassessed`.
4. Record each entry's cited proof files and their tiers as a header row.

Tests: **none.** This boundary writes no assertion about behaviour; per D-3 that is correct rather
than a gap. The matrix's own accuracy is checked by review, not by a proxy checker (design AD-1).

Done when: 13 entries present, every claim numbered, no verdict yet asserted.

### CB-2 — `INT-US-28` verdicts

Steps:
1. For each of its claims, read the cited tests and find the test **function** that proves it.
2. Mark `proven` (naming the function), `unproven`, or `unprovable` (the claim is not testable as
   written — record why; do **not** re-word the claim, NFR-1).
3. Record the tier of each proving function (FR-3).
4. For any `unproven` claim whose behaviour is genuinely tested elsewhere: cite that test **after
   reading it** and confirming it proves the claim.
5. For any claim still `unproven`: **write the integration test** that proves it. That test is this
   boundary's coverage.

Expected shape from research: the two seam claims carry 6 tests between them; that is where the
unproven verdicts are most likely.

Done when: every `INT-US-28` claim has a verdict with evidence, and every `unproven` one has either
a citation or a new test.

### CB-3 — `INT-US-21` verdicts

Same steps against `INT-US-21`'s 3 files / 61 tests. Expected to be the cleaner of the two — it is
the benchmark — so a surprise here is worth more attention than a gap in `INT-US-28`.

Done when: as CB-2.

## What is NOT filed (FR-5, NFR-3)

Added at the Phase 5.0 pre-check, which caught both missing from the first draft — the two
requirements most likely to be forgotten precisely because they say *do less*.

An `unproven` verdict is **not** a ticket. It is a claim with a named gap, and the boundary that
finds it either cites a test after reading one, or writes the test. A ticket is filed only where a
**decision** is needed that the auditor cannot take, and there is exactly one shape that qualifies
here: a claim that is `unprovable` **and** whose contract would have to change to become provable —
because re-wording a delivered contract is forbidden by NFR-1 and is therefore the user's call.

**Success condition for NFR-3:** SF-01 ends with the same number of open tickets it started with,
or the difference is a list of named decisions. An audit that ends with more open tickets than it
started with has moved work, not done it — `closure-contract.md`.

`FR-6` findings (a gap tracing to an incomplete capability) are recorded **in the matrix, against
that capability**, not filed. `TECH-047`'s sweep already tracks capability-level FR coverage; a
ticket per finding would duplicate it.

## Test Plan

Only CB-2 and CB-3 produce tests, and only for claims found unproven. Each such test:

- lives in `tests/integration/` or `tests/e2e/` — never `tests/unit/`, since it proves an
  integration contract's claim;
- carries a docstring naming the contract and the claim number it proves;
- asserts the **behaviour at the seam**, not that a command exits 0 — `check_useless_asserts.py`
  pattern 6 rejects a permissive exit code, and a claim proven by one is not proven.

## Non-Goals for SF-01

- The other 11 entries' verdicts — SF-02 and SF-03.
- Remediating capability defects the audit exposes; record under FR-6.
- Re-wording any contract claim to match its tests (NFR-1).
- Correcting the `INT-US-28` "20 integration tests" drift — recorded, not fixed; it is a delivered
  entry and the count is not a claim about behaviour.

## Rollback

Each boundary is a documentation commit plus, for CB-2/CB-3, new test files. Reverting a boundary
removes its verdicts and its tests together; no source code changes, so no runtime rollback risk.
