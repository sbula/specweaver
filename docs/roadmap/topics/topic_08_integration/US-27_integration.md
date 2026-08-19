# US-27: Autonomous Production Self-Healing - Integration Contracts

## Base Story Contract (`INT-US-27`)
* **Status:** ⬜ Pending — migration `INT-US-27-MIG` discharged 2026-08-17; no path
  waits on this contract, so closure is a scope decision
* **Integration Description:** US-27's only closed capability is `B-SENS-02` (Persistent Knowledge
  Graph Builder). Everything else it needs is unbuilt, so this contract's whole content is a path
  inventory plus one deferred journey.
* **Verifiable Proof:** P-1 by `check_fr_coverage.py B-SENS-02` (5 of 5 cited, each behind a killed
  mutant); P-2 by `tests/integration/graph/test_real_extraction_to_graph.py`.

### Path Inventory (`ADR-004`)

| # | Path | Span | Owner | Runnable today | Blocker |
|---|---|---|---|---|---|
| P-1 | AST dicts → nodes; dedup; SQLite persist; subgraph query; GraphML export | single feature | `B-SENS-02` | yes — **done** | — |
| P-2 | Real polyglot extraction → graph nodes | cross-feature | `INT-US-10` FR-1 | yes — **done** | — |
| P-3 | Journey: a production stack trace resolves to an AST node through the graph | cross-feature | `A-SENS-05` | retired | `ADR-003` — owned by `A-SENS-05`, which declares this seam as its own FR |

**This contract declares no cross-feature FR of its own, and has no design document as a result.**
Both runnable rows were discharged elsewhere — P-1 is `B-SENS-02`'s own requirement, backfilled once
from `INT-US-10-MIG` under `specweaver-dev` §3.2c; P-2 is the extraction seam, proven by `INT-US-10`
FR-1. Restating either here would put a capability's claims in a second place, which is what
`ADR-003` measured and forbade. Six base contracts share `B-SENS-02` and the work was done once,
which is what ordering the migration by capability cluster bought.

P-3 generates no FR yet: `A-SENS-05` (APM Telemetry Ingestion (Sentry/Datadog)) is unbuilt, so its
interface is undefined. A test written against an undefined
interface cannot fail for the right reason (`ADR-004` clause 4), and `check_xfail_blockers.py` holds
the obligation the moment it is defined.

**`INT-US-27-MIG` is discharged, and every deferred path now names the ticket that owns it.**
No path waits on this contract. Whether it closes is a scope decision under `ADR-004`, which
reopened the one `CLOSED EMPTY` of this shape: a contract over closed capabilities is not empty
while their cross-feature paths are unproven.

## Sub-Story Add-Ons

* No explicit sub-story contracts defined yet.
