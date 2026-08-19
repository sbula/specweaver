# US-06 Integration - Integration Contracts

## Base Story Contract (`INT-US-06`)
* **Status:** ⬜ Pending — migration `INT-US-06-MIG` discharged 2026-08-17; no path
  waits on this contract, so closure is a scope decision
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
| P-3 | Dashboard reads and steers a run through a served API | cross-feature | `D-UI-01` | retired | `ADR-003` — owned by `D-UI-01`, which declares this seam as its own FR |
| P-4 | Journey: review specs and control pipelines from a browser, engine not local | cross-feature | `D-UI-01` | retired | `ADR-003` — owned by `D-UI-01`, which declares this seam as its own FR |

**Two closed capabilities and still no runnable cross-feature path, which is the finding.** The
dashboard talks to the state store directly and the router runs inside the engine; nothing joins
them
today. `D-UI-01` is that join, and it is unbuilt — so P-3 and P-4 are retired to it, and it
declares them as its own FRs.

`E-UI-02` shipped with a design declaring **no requirements at all**. It now has three, written from
why it exists rather than from what the code does (§3.2c), and FR-1 needed a new test before it
could
be declared: its mutant survived because the runs page always rendered and the only assertion was
that
the words "Pipeline Runs" appeared.

**`INT-US-06-MIG` is discharged, and every deferred path now names the ticket that owns it.**
No path waits on this contract. Whether it closes is a scope decision under `ADR-004`, which
reopened the one `CLOSED EMPTY` of this shape: a contract over closed capabilities is not empty
while their cross-feature paths are unproven.

## Sub-Story Add-Ons

* No explicit sub-story contracts defined yet.
