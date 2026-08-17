# US-18: Productionizing External Targets - Integration Contracts

## Base Story Contract (`INT-US-18`)
* **Status:** ⬜ Pending — migration `INT-US-18-MIG` discharged 2026-08-17; the contract stays open
* **Integration Description:** US-18 proves the platform by building an external proprietary trading
  system. Its only closed capability is `C-FLOW-03` (Multi-Spec Pipeline Fan-Out); `US-13 Core`,
  `US-14 Core` and `B-UI-02` are all unbuilt.
* **Verifiable Proof:** P-1 by `check_fr_coverage.py C-FLOW-03`, which exits 0 with all four
surviving
  FRs behind killed mutants.

### Path Inventory (`ADR-004`)

| # | Path | Span | Owner | Runnable today | Blocker |
|---|---|---|---|---|---|
| P-1 | Wave scheduling, RESERVE locking, deferred JOIN synthesis, cascading aborts | single feature | `C-FLOW-03` | yes — **done** | — |
| P-2 | Port and git-lock collision safety under real concurrent fan-out | single feature | `TECH-062` | no — **not built** | `TECH-062` |
| P-3 | Journey: build and manage an external proprietary system end to end | cross-feature | this contract, deferred | no | `US-13 Core`, `US-14 Core`, `B-UI-02` |

**P-2 is the finding, and it is not a coverage gap — it is absent code.** `C-FLOW-03` declared six
FRs;
two described mechanisms that do not exist in `src/`: `SW_PORT_OFFSET` port-offset injection, and
`gc.auto 0` plus serialised worktree creation. `run_fan_out` IS genuinely concurrent
(`asyncio.gather`) and its sub-runs can each call `git worktree add`, so both hazards are live. The
FR
rows are deleted from the design per `TECH-046`'s precedent and the work is `TECH-062`.

Found only because `ADR-004` requires every FR to be cited with a killed mutant. **There is no
mutant
to kill for code that does not exist** — which is exactly how both claims survived delivery.

**`INT-US-18-MIG` is discharged; the contract stays open** on `TECH-062` and on its three unbuilt
prerequisites.

## Sub-Story Add-Ons

* No explicit sub-story contracts defined yet.
