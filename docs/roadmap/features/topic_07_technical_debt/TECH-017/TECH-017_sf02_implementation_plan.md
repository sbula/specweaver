# Implementation Plan: Integration-Contract Proof Audit [SF-02: The thin proofs]

- **Feature ID**: TECH-017
- **Sub-Feature**: SF-02 — The thin proofs
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-017/TECH-017_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-017/TECH-017_sf02_implementation_plan.md
- **Status**: APPROVED 2026-08-14

## Scope

`INT-US-01`, `INT-US-03`, `INT-US-04`, `INT-US-05`, `INT-US-09` — the five entries flagged
2026-07-26 as citing capability suites or being happy-path only. Their `-SF*` add-ons are **not** in
scope; the three zero-proof entries belong to SF-03.

Current state, measured 2026-08-14: **15 claims (CB-1's count, a lower bound) across 27 tests in 6
cited files.**

Boundary order is **worst-first per `AD-4`**: CB-1 re-extracts all five, then CB-2 `INT-US-09`,
CB-3 `INT-US-03`, CB-4 the thin trio. An earlier draft ran cheapest-first; the Phase 5.0 pre-check
caught that it contradicted `AD-4`'s stated rationale — *surface capability findings early* — and
the order was corrected at the Phase 5 gate.

## What Phase 0 found

### 1. Re-extraction is the bulk of the work, and it is uneven

`CB-3` established that CB-1 read the first sentence of each Integration Description and stopped.
Measured across these five, that under-extraction is **not uniform**, so a flat "re-read everything"
would waste effort on three of them and under-serve two:

| Contract | CB-1 | Where CB-1 read | Expected after re-extraction |
|---|---|---|---|
| `INT-US-09` | 3 | the **Status** paragraph — the Integration Description is untouched | ~10 |
| `INT-US-03` | 5 | first sentence; the description also carries an explicit **exclusion** | ~8 |
| `INT-US-01` | 3 | the whole contract — it is one sentence | 3 |
| `INT-US-04` | 2 | the whole contract — one sentence | 2 |
| `INT-US-05` | 2 | the whole contract — one sentence | 2 |

`INT-US-09` is the important row. Its three matrix claims (*"per-step works for the single-step
case"*, *"session mode runs a span in one worktree"*, *"the legacy per-step model is
single-step-only"*) are all from the Status paragraph. The Integration Description asserts a
different set entirely: the `SubprocessExecutor` boundary **rebound to the worktree path**, bash
actions *and* QA execution both worktree-bounded, Main-Branch-Wins strip-merge with out-of-bounds
hunks stripped, the opt-in policy resolved at the composition root, and default-off preserving
behaviour *exactly*.

**Exclusions are claims.** `INT-US-03` states container/Podman execution is out of scope. A contract
that says "X must not happen" is falsifiable and belongs in the matrix.

### 2. A cited proof is width-dependent flaky — `INT-US-05`

`tests/e2e/capabilities/core/test_lineage_e2e.py::TestLineageE2EFlow::test_sw_check_lineage_flag_detects_orphans`
asserts `"orphan.py" in result.output`. Rich soft-wraps the path, and at some widths the rendered
output contains `orp\nhan.py`:

```
COLUMNS=60   passed        COLUMNS=100  passed
COLUMNS=80   FAILED        COLUMNS=200  passed
```

80 is the no-TTY default. The full suite is green only because xdist sets a different width — the
failure appears when the cited files are run **on their own**, which is exactly what an audit does
and nothing else does. Running a contract's cited proof in isolation is therefore a step, not a
side-effect (see CB-2).

### 3. Two `skipif` guards are legitimate

`test_step_worktree_isolation_e2e.py` and `test_implement_loop_worktree_isolation_e2e.py` skip on
missing `git`/`bash` — environment capability, R8-legal, and both run in this environment.

## Decisions taken at the Phase 4 gate

- **D-1 — Re-extract first, in its own boundary.** Verdicts assessed against CB-1's list would
  assess the wrong list. Extraction format was settled by SF-01 and is not re-opened per contract;
  re-cutting it mid-audit would invalidate SF-01's verdicts (design §Execution Order).
- **D-2 — Fix the `INT-US-05` width-flake here.** It is a defect in another story's test file, and
  taking it is the `_finalize` precedent: found in passing, small, safe, already covered. Normalise
  the rendered output before asserting rather than widening the terminal, because pinning `COLUMNS`
  hides the same class of bug next time.
- **D-3 — Universal negatives get a structural guard where an invariant exists, `unprovable`
  otherwise.** `INT-US-28` C4 (*"every LLM prompt"*) was proven by asserting only one call path
  constructs a `PromptBuilder`. Where no such invariant exists the claim is recorded `unprovable`
  with the reason — the contract is never re-worded (NFR-1).

## Commit boundaries

### CB-1 — Re-extract all five contracts

Steps:
1. Read each contract's **entire** entry — Status, Integration Description, Verifiable Proof, and
   any notes — not the first sentence.
2. Add a matrix row per assertion, including exclusions and universal negatives.
3. Mark every new row `unassessed`; assign no verdicts in this boundary.
4. Update the coverage census and state plainly which entries' counts changed and why.

No tests: this boundary changes one analysis document. Same rule as SF-01 CB-1 (design D-3).

Done when: every falsifiable assertion in all five contracts is a row, and the census names the
before/after counts.

### CB-2 — `INT-US-09`, the worst entry

**Worst-first per `AD-4`**, whose rationale is that the diagnostic half should surface capability
findings early. `INT-US-09` is worst by every measure: 3 extracted claims against ~10 assertions,
and its Integration Description claims are seams into `D-EXEC-02`, `E-EXEC-01` and `C-EXEC-02`, so
it carries the highest expected `FR-6` yield. Settling the re-extracted-verdict format on the
hardest contract is the accepted cost.

Steps:
1. **Run the cited files in isolation first.** Finding 2 exists only because that was done; a proof
   that passes only inside the full suite is not proof of the contract.
2. Verdict each re-extracted claim per SF-01's rules — `proven` naming the test **function**,
   `unproven`, or `unprovable` with the reason. Record the tier (FR-3).
3. Where a gap traces to `D-EXEC-02`, `E-EXEC-01` or `C-EXEC-02`, record it against that capability
   (FR-6), not against the contract.
4. Write the integration or e2e test for any claim still `unproven`.

**Watch for the CB-2-of-SF-01 shape:** *"the `SubprocessExecutor` boundary rebound to the worktree
path"* is exactly the kind of claim proven in two halves — a unit test that the policy sets a path,
another that the executor honours a path it is given, and nothing driving the two together. Check
for it explicitly.

Tier: seam and journey claims, so **integration and e2e**. A unit test here is the `ADR-003`
diagnostic, not coverage.

Done when: every re-extracted `INT-US-09` claim has a verdict with evidence, and each `unproven` one
carries a citation or a new test.

### CB-3 — `INT-US-03`

Same steps. Additionally verdict the **exclusion** (no container/Podman path) — a universal negative,
so D-3 applies: the invariant is that no container code path is reachable from the implement loop.

Done when: as CB-2, for `INT-US-03`'s re-extracted claim set.

### CB-4 — The thin trio: `INT-US-01`, `INT-US-04`, `INT-US-05`

Same steps, plus the two items that belong to these three specifically:

* `INT-US-01`'s *"no unvalidated LLM generation can occur"* is D-3's first case: look for a
  structural invariant (does a single path gate generation?). Guard it if one exists — and probe the
  guard by planting the violation it forbids (R-3) — otherwise `unprovable`.
* Fix the `INT-US-05` width-flake (D-2). Assert against output with soft wraps normalised, not
  against a pinned `COLUMNS`.

Done when: 7 claims verdicted, the flake fixed and probed at COLUMNS 60/80/100/200, and every
`unproven` claim carries a citation or a new test.

## Capability findings (FR-6) — carried by every boundary

Where a claim's gap traces to an incomplete capability, the finding is recorded **against that
capability**, not against the contract. This was missing from the first draft of this plan and was
caught by the Phase 5.0 pre-check.

`INT-US-09` is where the yield is expected: its Integration Description claims are seams into
`D-EXEC-02`, `E-EXEC-01` and `C-EXEC-02`, so a claim that turns out to be unproven is at least as
likely to be a hole in one of those three as a hole in the contract. `SF-01` set the shape —
`B-INTL-09` and `D-INTL-06` read as having zero tests until their own tests were attributed back to
them.

Recording is a `Proves:` citation plus a note in the capability's design; it is **not** a ticket
(FR-5).

## What is NOT filed (FR-5, NFR-3)

An `unproven` verdict is not a ticket; the boundary that finds it cites a test after reading one or
writes the test. A ticket is filed only for a claim that is `unprovable` **and** whose contract would
have to change to become provable — that is the user's call, because NFR-1 forbids re-wording a
delivered contract.

**Success condition for NFR-3:** SF-02 ends with the same number of open tickets it started with, or
the difference is a list of named decisions.

The width-flake is explicitly **not** a ticket under D-2.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | Re-extraction inflates the claim count so far that verdicts do not fit the boundary | CB-1 is extraction-only, so the count is known before any verdict work is planned. If `INT-US-09` exceeds ~12 claims, split CB-4 rather than compress it |
| R-2 | Fixing the width-flake masks a real product defect in the lineage error output | The fix normalises the **test's** view of rendered output; it must not change `src/`. If the product genuinely truncates the path, that is a finding, not a test fix — check which before editing |
| R-3 | A structural guard for a universal negative is vacuous | The `INT-US-28` C4 guard passed with a bypass planted until it was probed. Every guard written here is probed by planting the violation it forbids |
| R-4 | Running cited files in isolation surfaces more flakes, expanding scope | Record each as a finding with its verdict; fix only those as small as D-2's. Anything larger is a named decision at SF-02's close |

## Session Handoff

SF-01 delivered CB-1 (skeleton, 13 entries), CB-2 (`INT-US-28`, 6 claims) and CB-3 (`INT-US-21`,
4 claims extracted → 8 after CB-3 found the extraction gap). Matrix census: 13 entries, 46 claims.
SF-02 starts at CB-1 above.
