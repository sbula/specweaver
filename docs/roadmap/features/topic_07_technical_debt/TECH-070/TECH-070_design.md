# Design: Every Graph Build Re-Ingests Every File

- **Feature ID**: TECH-070
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: 2026-08-21, `TECH-068` Phase 3 gate G2. The ≤250 ms single-file target was withdrawn
  from that ticket because no incremental path exists to build it on, and how fast the graph updates
  is a separate concern from what it contains.

## Problem Statement

`GraphOrchestrator.build_target` re-ingests every file it collects, every time. There is no
incremental path — `ingest_target` is a plain `for f in files: self.ingest_file(f)` over the whole
collection, and the store's stale-entry purge works on files rather than on a changed set.

Measured 2026-08-21 on `src/specweaver` (358 files, 57.8k LOC, single-threaded):

| Run | Time | Per file |
|---|---|---|
| cold | 1.00 s | 2.8 ms |
| second run against the same DB | 0.84 s | 2.3 ms |

The second run is **not an incremental update**. It re-parses all 358 files and re-persists the
graph; it is faster only because the DB already exists. Nothing consults file mtimes or hashes to
skip unchanged work, so `get_all_file_hashes` — which returns exactly the `clone_hash` per file that
would make skipping possible — has no caller in the build path.

This is a gap in delivered work: `B-SENS-02` shipped the builder without an incremental path, and
`finished-stories-immutable` bars editing its closed scope, so the gap becomes this ticket.

## Goal

A graph build that re-parses only what changed, so re-indexing after a single edit costs
milliseconds rather than a full pass over the repository.

## Relationship

- `TECH-068` withdrew this at its gate G2 and owns the edge kinds instead. Its `NFR-3` row records
  the withdrawal and points here. It does not depend on this ticket.
- `B-SENS-09` (deterministic context packing) is the reader that makes this urgent: it packs context
  **per agent turn**, so a full rebuild per turn compounds across a run. **This ticket is sequenced
  ahead of it.**
- `B-VAL-07` and the blast-radius seam owners read the graph less often and are not blocked.

## Candidate Approaches (not yet designed)

1. **Hash-gated skip.** `get_all_file_hashes` already returns a `clone_hash` per file. Compare it
   against the file's current hash and skip ingestion when they match. Cheapest path; correctness
   turns on the hash covering everything an edge depends on, which `TECH-068`'s new edge kinds
   change — a file whose own bytes are unchanged can still need re-resolution when a file it calls
   into moves.
2. **Changed-set ingestion.** Give `ingest_target` an explicit set of paths and let the caller
   decide what changed (git diff, a watcher, an explicit argument). Puts the decision where the
   knowledge is, and makes the incremental path testable without a filesystem clock.
3. **Dependency-aware invalidation.** Re-ingest the changed file *and* whatever the graph says
   depends on it. Only becomes possible once `TECH-068` lands, because today the graph holds no
   dependency edges to invalidate along.

## Non-Goals (proposed, pending design)

- Parallelising the build. `ingest_target` is serial and that is headroom this ticket does not
  spend; a separate concern from doing less work.
- Watching the filesystem. Deciding *when* to rebuild is the caller's, not the builder's.
- Changing what the graph contains. `TECH-068` owns the edge kinds.
- A cross-service or distributed index.

## Next Step

Run `specweaver-design` for `TECH-070`. Its first test: build a graph, touch one file, rebuild, and
assert the other files were not re-parsed — red today, because nothing in the build path can skip a
file.

**The performance target is not set.** `TECH-068` carried a ≤250 ms single-file figure that the user
delegated to the agent and that this ticket did not inherit. Setting it is a decision for the
grilling, not an inheritance.
