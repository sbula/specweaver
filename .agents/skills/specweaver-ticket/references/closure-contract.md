# What it takes to close something

A `🟢` or a `✅` is a claim that the implementation stands up to the ticket's promise. It is not a
claim that work happened, that a commit landed, or that a follow-up was filed.

This contract exists because none of that was written down and the artifact says so. Measured
2026-08-13 with `scripts/check_fr_coverage.py` across every capability that has a design document:

| | |
|---|---|
| capabilities with a design | 103 |
| **clean** | **8** |
| `BLOCKED` — an FR carried by no plan, or cited by no test | **46** |
| could not run | 49 |

`C-INTL-01` is the worked example. It is marked `✅`. Its design specifies recursive multi-level
decomposition three separate ways — `FR-3`, `AD-2`, and an agent-sized split heuristic. **None of it
was built, none of it was descoped, and all five of its FRs are cited by no test.** Two were never
carried by any implementation plan. The `✅` was taken on trust for months.

## The four conditions

All four, before any status becomes `🟢` / `✅`:

1. **Every FR has a test that proves it.** `python scripts/check_fr_coverage.py <ID>` exits 0. A
   design saying the behaviour exists is not evidence that it does.
2. **Every FR you are not building is deleted from the design's FR table**, so the descope is
   visible in the artifact rather than inferred from its absence. The checker's own failure message
   says this; follow it.
3. **The `Verifiable Proof` field names test FILES**, and those tests pass and do not skip. A
   directory, a bare `pytest -m integration`, or a suite named in prose is not a proof — nothing
   pins which test carries the claim. `scripts/check_proof_tier.py` enforces the tier; it cannot
   enforce the truth.
4. **The proof is at the right tier.** An `INT-US-NN` story is an integration contract, so its proof
   is integration and e2e tests. Unit tests belong there only to fill a narrow gap found while
   integrating.

## Filing a follow-up ticket is not one of the conditions

**A new ticket is not a resolution. It is a deferral, and deferrals do not close anything.**

On 2026-08-13 six tickets were filed in a single day, several of them as the "outcome" of resolving
an earlier one. That is inflation: the backlog grows, the verification does not, and each ticket
carries the appearance of progress.

Before filing, answer out loud:

- **Can I verify this now?** Then verify it. A finding backed by a failing test beats a ticket that
  says someone should look.
- **Can I fix this now?** Then fix it. "It is out of scope for the current commit" is a real answer;
  "it deserves its own ticket" usually is not.
- **Does this need a decision I cannot take?** That is the one good reason to file — a scope
  question, a descope, anything that changes what the product does. Say in the ticket which decision
  is needed and who takes it.

A ticket that only records a fact you could have checked is a note, and notes belong in the design
document of the thing they concern.

## Do not rush the close

The pressure runs the other way: closing looks like delivery. Two counters worth keeping.

**A specification is a claim under test, not a given.** `C-INTL-01`'s design was read as evidence of
recursion for months. Read the FRs against the code, then against the tests. Where they disagree,
the code is what shipped.

**Verify what the check verifies.** `check_story_preconditions.py` would have caught `INT-US-25`'s
delivered-with-no-proof state any day and never ran; `check_class_health.py` reported *"nothing in
scope"* for a whole session while 23 classes failed; `check_fr_coverage.py` could have blocked
`C-INTL-01` since it was written. All three are story-scoped, and a story-scoped check only fires
when a human remembers the story. **Run it, read its output, and confirm it examined what you think
it examined.**
