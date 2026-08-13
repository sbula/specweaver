# Design: Nothing Runs the FR-Coverage Gate Across Delivered Work

- **Feature ID**: TECH-047
- **Epic**: Topic 07 (Technical Debt)
- **Status**: 🟢 **DELIVERED 2026-08-13.** Option 2 taken — the ratchet counts requirements, not
  capabilities. `scripts/check_fr_sweep.py`, in the `doc` gate.
- **Origin**: 2026-08-13, from the audit in
  `docs/analysis/test_coverage_audit_2026-08-13.md`. One of the two systemic causes it isolated;
  the other is `TECH-048`.

## Problem Statement

`scripts/check_fr_coverage.py` works, is correct, and has existed since `TECH-025`. It takes a
story ID. **Nothing runs it across delivered work**, so it fires only when a human remembers a
particular story — and nobody remembers 82 of them.

Measured 2026-08-13 across every capability with a design document: **43 of 82 delivered
capabilities exit `BLOCKED`**, carrying 337 declared FRs of which **331 are cited by no test file**.
`C-INTL-01` is the worked example — five FRs, zero tests, two never carried by any plan, marked ✅
for months.

### This is the third instance of one disease

The pattern is the point, not this instance of it:

| Check | Would have caught | Why it did not |
|---|---|---|
| `check_story_preconditions.py` | `INT-US-25` marked ✅ with `[Pending]` proof | story-scoped; nobody passed that ID |
| `check_class_health.py` | 23 incohesive classes | `changed` scope; reported *"nothing in scope"* all session |
| `check_fr_coverage.py` | `C-INTL-01` and 42 others | story-scoped; nobody passed those IDs |

**A check that must be invoked to fire is a check that reports success by not running.** Two of the
three were fixed by making the check a sweep — `check_proof_tier.py` takes no argument for exactly
this reason, and `check_class_health` was widened. This is the third.

## Candidate Approaches — option 2 taken

**The sweep is a dozen lines. The hard part is what to do with its output.**

A sweep is a dozen lines. **The hard part is that turning it on today produces 43 failures**, which
leaves only bad options:

- **Freeze all 43 in a ratchet.** The ratchet then says "43 capabilities are unverified and that is
  fine", which is what a ratchet nobody can act on becomes. `check_useless_asserts.py`'s docstring
  warns about precisely this for detectors: one you cannot trust is as bad as a test you cannot
  trust.
- **Block until they are fixed.** Nothing merges for weeks.
- **Warn only.** A warning nobody must act on is read once and then never again.

So the design question is **not "should this be swept"** — it is *what makes a 43-failure sweep
actionable*. Candidates:

1. **Sweep as a report, not a gate**, run on demand and in the `doc` gate's output but not its exit
   code, with the ratchet applied only to *newly delivered* capabilities. New work is held to the
   bar; existing work is measured and visible without blocking.
2. **Ratchet on the FR count, not the capability count.** "331 uncited FRs, may fall, never rise"
   is actionable in a way that "43 blocked capabilities" is not — any story that adds a test moves
   it, so the number is a live signal rather than a frozen list.
3. **Gate only what a commit touches.** If a commit changes code owned by a delivered capability,
   that capability's FR ledger must pass. Scopes the pain to where work is already happening — but
   needs an FR→code map, which does not exist and is `TECH-046`'s adjacent problem.

(2) is the most promising and the cheapest to trust.

## Non-Goals — all held

- **Fixing the 43.** That is verification work, itemised per FR by the existing tool, and belongs to
  `TECH-017`'s matrix — not to the ticket that makes it visible.
- Capabilities with **no FR table at all** (31 of them). The gate cannot run there and no sweep
  changes that; `TECH-048`.
- Making `check_fr_coverage` stricter. Its file-level attribution over-credits — a known
  `TECH-025` finding — but that is a separate change and would raise the 43, not lower it.
- Anything about test *strength*. Coverage proves attribution only; see `closure-contract.md`.

## Delivery, 2026-08-13

### The decision: count requirements, not capabilities

**Option 2.** The ratchet holds one number — requirements cited by no test — rather than a list of
blocked capabilities. A list of names moves only when a whole capability is finished, which is
never, so it would have sat frozen saying *"45 unverified capabilities is fine"*. A requirement
count moves the moment one real test lands, and **rises the moment a new FR ships untested**, which
is the regression that actually matters.

`scripts/check_fr_sweep.py`, in the `doc` gate. Probed: appending one untested FR gives
`REGRESSION of 1` and exit 1.

### The limitation, stated in the checker itself

This measures **attribution**, not strength: a citation on an `assert True` counts. An increase is a
real signal and blocks; **a decrease is not evidence of quality.** The failure message names the
three legitimate answers — write the test, delete the FR row so the descope is visible, or cite an
existing test **after reading it and confirming it proves the requirement** — and the one that is
not: bulk citation without reading.

That fourth line was a correction. The first draft forbade citing existing tests outright, which
would have blocked the legitimate case: `D-VAL-01` FR-1 was already proven by
`test_code_validation_pipeline`, which drives the real CLI and asserts the C-series rule ids appear.
The proof existed; only the pointer was missing.

### Fixed same day: the ratchet punished writing requirements down

The first version counted uncited FRs across *every* design, so adding four FRs to `C-FLOW-12` —
unbuilt, and the new owner of `C-INTL-01`'s descoped `FR-3` — raised the total and blocked the
commit that **improved the specification**. An unbuilt capability's requirements are correctly
uncited; there is nothing to test yet. The census now reads the roadmap's markers and counts
delivered stories only: 263 → 251, a change in what is counted and **not** evidence of testing.

### What this ticket did not do

The remaining 251 are verification work, itemised per FR by `check_fr_coverage.py <ID>`, and belong
to `TECH-017`'s matrix. Making them visible and stopping them growing is this ticket; closing them
is not.
