# US-06 Integration - Integration Contracts

## Base Story Contract (`INT-US-06`)
* **Status:** ⬜ Pending — migration `INT-US-06-MIG` discharged 2026-08-17; the contract stays open
* **Integration Description:** US-6 is the "tablet on a train" story. It holds **two** closed
  capabilities — `C-FLOW-02` (router-based flow control) and `E-UI-02` (web dashboard) — and the
  bridge between them, `D-UI-01` (`sw serve` Core Orchestration API), is unbuilt.
* **Verifiable Proof:** P-1 and P-2 by `check_fr_coverage.py C-FLOW-02` and `... E-UI-02`, both now
  exit 0 with every FR behind a killed mutant.

### Path Inventory (`ADR-004`)

| # | Path | Span | Owner | Runnable today | Blocker |
|---|---|---|---|---|---|
| P-1 | Router parsed, validated, evaluated, jumped, audited | single feature | `C-FLOW-02` | yes — **done** | — |
| P-2 | Dashboard lists runs, resolves a HITL gate, refuses an unknown run | single feature | `E-UI-02` | yes — **done** | — |
| P-3 | Dashboard reads and steers a run through a served API | cross-feature | this contract, deferred | no | `D-UI-01` |
| P-4 | Journey: review specs and control pipelines from a browser, engine not local | cross-feature | this contract, deferred | no | `D-UI-01` |

**Two closed capabilities and still no runnable cross-feature path, which is the finding.** The
dashboard talks to the state store directly and the router runs inside the engine; nothing joins
them
today. `D-UI-01` is that join, and it is unbuilt — so P-3 and P-4 wait, and the contract holds them.

`E-UI-02` shipped with a design declaring **no requirements at all**. It now has three, written from
why it exists rather than from what the code does (§3.2c), and FR-1 needed a new test before it
could
be declared: its mutant survived because the runs page always rendered and the only assertion was
that
the words "Pipeline Runs" appeared.

**`INT-US-06-MIG` is discharged; the contract stays open** until `D-UI-01` lands and P-3/P-4 are
written.

## Sub-Story Add-Ons

* No explicit sub-story contracts defined yet.
