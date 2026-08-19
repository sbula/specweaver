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
  | P-5 | Journey: an undocumented enterprise repository is mapped, given boundaries, and then reviewed against them in one run | cross-feature | `B-SENS-07` | retired | `ADR-003` — owned by `B-SENS-07`, which declares this seam as its own FR |
  | P-6 | The graph covers a polyglot repository, not only its Python files | cross-feature | `TECH-061` | moved | `TECH-061` owns the fix and its proof |

  **Three capabilities, all now cited and mutant-verified**: `D-SENS-01` (`INT-US-08-MIG`, seven FRs
  written from scratch — it had no design document at all), `B-SENS-02` (cited in an earlier pass), and
  `C-EXEC-01` (`INT-US-01-SF02-MIG`).

  **Corrected 2026-08-18. The 2026-08-17 note called this row "one link short" and recommended writing
  the test by dropping the declared `context.yaml` files from `INT-US-01-SF02` P-7's fixture. That was
  wrong, and the test written from it was deleted rather than committed.**

  It was **circular by construction**. The sequence was: plant a violating import, then run the scan
  that derives the architecture *from the source including that import*. If inference recorded
  dependencies as it is supposed to, the planted violation would have been recorded as a fact about the
  project and legalised on the spot. A dependency cannot violate a description derived from that same
  dependency. What hid this is that inference records **no** dependencies at all, so the derived map
  says every module depends on nothing — making everything look like a violation rather than nothing,
  and making a broken implementation read as evidence that the design was sound.

  The coherent shape is **baseline then drift**: infer once to establish a baseline, let the code
  change, then check the change against the *unchanged* baseline. The product already supports the
  mechanics, since inference skips a directory that already has a `context.yaml`. That is a different
  test from the one recommended here, with a different fixture sequence and a different claim.

  **And it cannot be written yet regardless**, which is why this row now names a blocker like the
  others. The chain it walks exists only for Python, and is broken there too. Measured:
  [analysis](../../analysis/polyglot_dependency_resolution_2026-08-18.md). `B-SENS-07` owns the
  resolver that has to exist first, and should carry this journey as one of its own FRs under
  `ADR-004` rather than leaving it here to be re-litigated after the fact.

  **The chain is real and each link is proven; the chain itself is not.** P-1 through P-4 are the
  enterprise story end to end — map the repository, persist the map, emit boundaries, enforce them — and
  every link has a killed mutant. Nothing walks all four in one run, which is P-5, and that is a test
  nobody has written rather than a feature nobody has built.

  **P-6 is where the story actually stops.** `TECH-061` records that `GraphOrchestrator.collect_files`
  accepts `.py` and nothing else, while every layer beneath it is polyglot. An *enterprise* architecture
  enforcement story that only sees Python sees a fraction of the repositories it is aimed at, so this row
  is not cosmetic — it bounds the claim.

  **`INT-US-20-MIG` is discharged, and every deferred path now names the ticket that owns it.**
  No path waits on this contract. Whether it closes is a scope decision under `ADR-004`, which
  reopened the one `CLOSED EMPTY` of this shape: a contract over closed capabilities is not empty
  while their cross-feature paths are unproven.