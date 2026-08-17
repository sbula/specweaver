# US-15: Enterprise Audit & Traceability - Integration Contracts

## Base Story Contract (`INT-US-15`)
* **Status:** ⬜ Pending — migration `INT-US-15-MIG` discharged 2026-08-17; the contract stays open
* **Integration Description:** US-15's only closed capability is `B-SENS-02` (Persistent Knowledge
  Graph Builder). Everything else it needs is unbuilt, so this contract's whole content is a path
  inventory plus one deferred journey.
* **Verifiable Proof:** P-1 by `check_fr_coverage.py B-SENS-02` (5 of 5 cited, each behind a killed
  mutant); P-2 by `tests/integration/graph/test_real_extraction_to_graph.py`.

### Path Inventory (`ADR-004`)

| # | Path | Span | Owner | Runnable today | Blocker |
|---|---|---|---|---|---|
| P-1 | AST dicts → nodes; dedup; SQLite persist; subgraph query; GraphML export | single feature | `B-SENS-02` | yes — **done** | — |
| P-2 | Real polyglot extraction → graph nodes | cross-feature | `INT-US-10` FR-1 | yes — **done** | — |
| P-3 | Journey: the traceability matrix renders a requirement-to-line chain out of the graph | cross-feature | this contract, deferred | no | `C-UI-02` |

**This contract declares no cross-feature FR of its own, and has no design document as a result.**
Both runnable rows were discharged elsewhere — P-1 is `B-SENS-02`'s own requirement, backfilled once
from `INT-US-10-MIG` under `specweaver-dev` §3.2c; P-2 is the extraction seam, proven by `INT-US-10`
FR-1. Restating either here would put a capability's claims in a second place, which is what
`ADR-003` measured and forbade. Six base contracts share `B-SENS-02` and the work was done once,
which is what ordering the migration by capability cluster bought.

P-3 generates no FR yet: `C-UI-02` (Traceability Matrix UX) is unbuilt, so its interface is
undefined. A test written against an undefined
interface cannot fail for the right reason (`ADR-004` clause 4), and `check_xfail_blockers.py` holds
the obligation the moment it is defined.

**`INT-US-15-MIG` is discharged; the contract stays open.** A migration finishes; a contract keeps
its
deferred rows until every path in the story is proven. US-15 closes when `C-UI-02` lands and P-3 is
written.

## Sub-Story Add-Ons

* **`INT-US-15-SF01` — Enterprise Compliance Protocols:** the add-on's contract under `ADR-004`.

  ### Path Inventory

  | # | Path | Span | Owner | Runnable today | Blocker |
  |---|---|---|---|---|---|
  | P-1 | An artifact event row: `artifact_id`, `parent_id`, `run_id`, `model_id`, `event_type`, timestamp, persisted in `specweaver.db` | single feature | `B-SENS-01` | yes — **done** | — |
  | P-2 | Seam: every write site — drafting, generation, decomposition artifacts, lint-fix — tags its output, and a *regenerated* artifact keeps the identity already on disk rather than minting a second one | cross-module | `B-SENS-01` | yes — **done** | — |
  | P-3 | Seam: `sw lineage tree` resolves a uuid or a path, walks the graph up to its root through `LineageEngine`, and renders it | cross-module | `B-SENS-01` | yes — **done** | — |
  | P-4 | Journey: `sw check --lineage` fails CI on untracked source, and `sw lineage tag` adopts it | cross-module | `B-SENS-01` | yes — **done** | — |

  **All six FRs are cited and each is behind a killed mutant** — `check_fr_coverage.py B-SENS-01`
  exits 0. **No test had to be written, and no FR had to be descoped.** That makes this the first
  capability in the migration to have been genuinely finished when it was marked finished, and it is
  worth saying so: the pattern of the previous three was not universal.

  Two mutants are worth keeping on the record because of what they *don't* break.

  **FR-3: `run_id` and `model_id` swapped in the INSERT tuple** — 6 fail. Both columns stay
  populated, every row still validates, nothing raises. Only the meaning is exchanged, so a test
  that counted rows or asserted the write succeeded would pass a database attributing every event to
  the wrong model on the wrong run. Completeness is not correctness.

  **FR-5: the orphan scan's tag test forced false** — 4 fail. The scan still runs, still walks the
  whole tree, still reports. It simply never finds anything, which from the exit code is
  indistinguishable from a clean repository. The FR's actor is CI, and CI reads exit codes.

  **FR-2's mutant fails 15 files across three tiers**, the widest blast radius in this migration.
  That breadth is the measure of "every generated file": the tag is applied at four write sites and
  read back at more, so its removal is visible almost everywhere. A capability whose mutant kills one
  test is narrow; this one is structural.

  **One wording drift, recorded not reconciled.** FR-4 declares `sw lineage <file>`; the shipped
  command is `sw lineage tree <file>`. Mechanism, output and data source are exactly as designed. It
  is noted here because a reader checking the FR against the CLI would find no such command and
  reasonably conclude the capability was never built.

  **`INT-US-15-SF01-MIG` is discharged (2026-08-17), and this contract closes with it** — every path
  in the inventory is proven, with no deferred row. The first in the migration to do so.
