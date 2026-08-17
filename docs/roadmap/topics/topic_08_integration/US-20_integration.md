# US-20: Enterprise Architecture Enforcement - Integration Contracts

## Base Story Contract (`INT-US-20`)
* **Status:** ⬜ Pending
* **Integration Description:** [Pending definition...]
* **Verifiable Proof:** [Pending]

## Sub-Story Add-Ons

* **`INT-US-20` base — Enterprise Architecture Enforcement:** the story's contract under `ADR-004`.

  ### Path Inventory

  | # | Path | Span | Owner | Runnable today | Blocker |
  |---|---|---|---|---|---|
  | P-1 | A project's declared `context.yaml` boundaries become a queryable graph | single feature | `D-SENS-01` | yes — **done** | — |
  | P-2 | That graph is persisted and re-read as a knowledge graph, extraction through store | cross-module | `B-SENS-02` | yes — **done** | — |
  | P-3 | Those boundaries are expressed as `tach.toml` in the analysed project, rebuilt from the graph | cross-feature | `C-EXEC-01` | yes — **done** | — |
  | P-4 | A boundary violation in the analysed project becomes an ERROR finding in its review | cross-feature | `C-EXEC-01` | yes — **done** | — |
  | P-5 | Journey: an undocumented enterprise repository is mapped, given boundaries, and then reviewed against them in one run | cross-feature | this contract, deferred | no | none — needs an e2e over the whole chain |
  | P-6 | The graph covers a polyglot repository, not only its Python files | cross-feature | `TECH-061` | no | `TECH-061` — `collect_files` filters `.py` |

  **Three capabilities, all now cited and mutant-verified**: `D-SENS-01` (`INT-US-08-MIG`, seven FRs
  written from scratch — it had no design document at all), `B-SENS-02` (cited in an earlier pass), and
  `C-EXEC-01` (`INT-US-01-SF02-MIG`).

  **The chain is real and each link is proven; the chain itself is not.** P-1 through P-4 are the
  enterprise story end to end — map the repository, persist the map, emit boundaries, enforce them — and
  every link has a killed mutant. Nothing walks all four in one run, which is P-5, and that is a test
  nobody has written rather than a feature nobody has built.

  **P-6 is where the story actually stops.** `TECH-061` records that `GraphOrchestrator.collect_files`
  accepts `.py` and nothing else, while every layer beneath it is polyglot. An *enterprise* architecture
  enforcement story that only sees Python sees a fraction of the repositories it is aimed at, so this row
  is not cosmetic — it bounds the claim.

  **`INT-US-20-MIG` is discharged (2026-08-17); the contract stays open** on P-5 and P-6.
