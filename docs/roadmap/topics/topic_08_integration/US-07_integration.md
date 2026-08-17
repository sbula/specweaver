# US-07 Integration - Integration Contracts

## Base Story Contract (`INT-US-07`)
* **Status:** ⬜ Pending — migration `INT-US-07-MIG` discharged 2026-08-17; the contract stays open
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
| P-2 | Editor approves or rejects generated code through a served API | cross-feature | this contract, deferred | no | `D-UI-01`, `D-UI-03` |
| P-3 | Journey: approve generated code inside VS Code without the terminal | cross-feature | this contract, deferred | no | `D-UI-01`, `D-UI-03` |

**No cross-feature FR of its own.** P-1 is `C-FLOW-02`'s own requirement, backfilled once from
`INT-US-06-MIG` and cited by both stories rather than twice. Restating it here would put a
capability's claims in a second place, which `ADR-003` forbade.

P-2 and P-3 generate no FR yet: `D-UI-01` and `D-UI-03` are unbuilt, so their interfaces are
undefined and a test written against them could not fail for the right reason (`ADR-004` clause 4).

**`INT-US-07-MIG` is discharged; the contract stays open** until both land.

## Sub-Story Add-Ons

* No explicit sub-story contracts defined yet.
