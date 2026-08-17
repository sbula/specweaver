# US-19: Microservice Fleet Orchestration - Integration Contracts

## Base Story Contract (`INT-US-19`)
* **Status:** ⬜ Pending
* **Integration Description:** [Pending definition...]
* **Verifiable Proof:** [Pending]

## Sub-Story Add-Ons

* **`INT-US-19-SF01` — Distributed Topology Scaling:** the add-on's contract under `ADR-004` — its
path inventory and any
  cross-feature (N)FRs the inventory generates.

  ### Path Inventory

  | # | Path | Span | Owner | Runnable today | Blocker |
  |---|---|---|---|---|---|
  | P-1 | Merkle hashing over a dependency boundary; staleness cache; upward invalidation | single feature | `A-SENS-01` | yes — **done** | — |
  | P-2 | Journey: topology scales across independent repositories without a local rebuild | cross-feature | this contract, deferred | no | `A-SENS-02` |

  **No cross-feature FR of its own, and so no design document.** P-1 is `A-SENS-01`'s own
  requirement: three FRs, all cited, each behind a killed mutant — `check_fr_coverage.py A-SENS-01`
  exits 0 — backfilled once from `INT-US-11-SF01-MIG` under `specweaver-dev` §3.2c. Restating it
  here
  would put a capability's claims in a second place, which `ADR-003` forbade.

  P-2 generates no FR yet: `A-SENS-02` (Postgres (Apache AGE + pgvector) sidecar) is unbuilt, so its
  interface is undefined. A test written against an
  undefined interface cannot fail for the right reason (`ADR-004` clause 4), and
  `check_xfail_blockers.py` holds the obligation once it is defined.

  **`INT-US-19-SF01-MIG` is discharged (2026-08-17); the contract stays open** until `A-SENS-02`
  lands and P-2
  is written.

