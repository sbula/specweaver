# US-07 Integration - Integration Contracts

## Base Story Contract (`INT-US-07`)
* **Status:** ⬜ Pending — migration `INT-US-07-MIG` discharged 2026-08-17; no path
  waits on this contract, so closure is a scope decision
* **Integration Description:** US-7 is the IDE copilot. Its only closed capability is `C-FLOW-02`
  (router-based flow control); both `D-UI-01` (`sw serve`) and `D-UI-03` (the VS Code extension) are
  unbuilt.
* **Verifiable Proof:** P-1 by `check_fr_coverage.py C-FLOW-02`, which exits 0 with all five FRs
behind
  killed mutants.

### Path Inventory (`ADR-004`)

| # | Path | Span | Owner | Runnable today | Blocker |
|---|---|---|---|---|---|
| P-1 | Router parsed, validated, evaluated, jumped, audited | single feature | `C-FLOW-02` | yes — **done** | — |
| P-2 | Editor approves or rejects generated code through a served API | cross-feature | `D-UI-01` and `D-UI-03` | retired | `ADR-003` — owned by `D-UI-01` and `D-UI-03`, which declare this seam as its own FR |
| P-3 | Journey: approve generated code inside VS Code without the terminal | cross-feature | `D-UI-01` and `D-UI-03` | retired | `ADR-003` — owned by `D-UI-01` and `D-UI-03`, which declare this seam as its own FR |

**No cross-feature FR of its own.** P-1 is `C-FLOW-02`'s own requirement, backfilled once from
`INT-US-06-MIG` and cited by both stories rather than twice. Restating it here would put a
capability's claims in a second place, which `ADR-003` forbade.

P-2 and P-3 generate no FR yet: `D-UI-01` and `D-UI-03` are unbuilt, so their interfaces are
undefined and a test written against them could not fail for the right reason (`ADR-004` clause 4).

**`INT-US-07-MIG` is discharged, and every deferred path now names the ticket that owns it.**
No path waits on this contract. Whether it closes is a scope decision under `ADR-004`, which
reopened the one `CLOSED EMPTY` of this shape: a contract over closed capabilities is not empty
while their cross-feature paths are unproven.

## Sub-Story Add-Ons

* No explicit sub-story contracts defined yet.
