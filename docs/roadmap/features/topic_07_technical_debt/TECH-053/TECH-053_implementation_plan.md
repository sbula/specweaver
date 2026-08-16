# Implementation Plan: A `✅` Nothing Can Verify

- **Feature ID**: TECH-053
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-053/TECH-053_design.md
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-053/TECH-053_implementation_plan.md
- **Status**: APPROVED (2026-08-16)

**FRs owned: FR-1, FR-2, FR-3.** One commit boundary.

## CB-1 — the check

`scripts/check_delivered_claims.py`, registered in `quality.py doc`. Two rules, one question:
*is this `✅` backed by anything a gate can read?*

- **FR-1**, group flags, **zero-tolerance** — the six known disagreements were corrected in
  `577744b3`, so there is no backlog to excuse and a baseline would only invite one.
- **FR-2/FR-3**, unverifiable capabilities, **ratcheted at 22** — 19 with no design document and 3
  whose design declares no FRs. Writing nineteen designs is a programme, not a boundary.

### Proof, per FR

| FR | Proven by | Tier |
|---|---|---|
| FR-1 | `test_check_delivered_claims.py::TestGroupFlagFindings` (5 synthetic registries) + the live-repo assertion | unit |
| FR-2 | `TestUnverifiableFindings` + `test_delivered_claims_seam.py::TestAgreesWithTheFrLedger` | unit + integration |
| FR-3 | `test_the_two_causes_are_named_separately` + the seam test's cause assertions | unit + integration |

**Integration is warranted, not padding.** The check deliberately does **not** own an FR grammar —
it loads `check_fr_coverage`'s. A synthetic design proves the reader is called; only the real
registry proves the two agree, and that is exactly where the first draft was wrong. The second
integration class covers the gate seam: `quality.py doc` shells out and maps an exit code, so
mocking it would test the mock.

**No e2e**, same reasoning as `TECH-051` CB-3: `quality.py` is a developer gate rather than a `sw`
command, and an e2e would be this subprocess call from a different directory.

### Done when every mutant is killed

| Mutant | Result |
|---|---|
| the group rule never fires | KILLED ×3 |
| parked `🔵` groups judged like the rest | KILLED ×1 |
| `🟢` when merely *some* children are done | KILLED ×5 |
| undelivered capabilities counted as delivered | KILLED ×7 |
| the two causes collapse into one message | KILLED ×3 |
| the ratchet becomes an equality check | **SURVIVED**, then KILLED |

The last one is the finding. `len(caps) > baseline` → `!= baseline` survived the whole suite,
because every test used a count *equal* to its baseline and nothing covered the direction a ratchet
exists to allow. A gate that punishes someone for fixing two of the 22 is a gate they route around.

## Out of scope

- The 39 capabilities whose declared FRs nothing cites. `check_fr_sweep.py` ratchets them at 234
  already, and two gates for one number is two baselines and one argument.
- Fixing any of the 22. That is the ticket's open finding, not its boundary.
- `INT-US-NN` contracts. The matrix is the capability registry; integration contracts are swept by
  `check_proof_tier.py`.
