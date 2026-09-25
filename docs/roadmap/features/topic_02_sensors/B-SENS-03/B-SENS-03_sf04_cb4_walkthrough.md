# B-SENS-03 SF-04 CB-4 — Walkthrough

**Commit boundary:** CB-4 of 4 · **DAL-B** · 2026-08-26 · **Proves**: `FR-9`. Closes SF-04 · Plan:
[sf04](B-SENS-03_sf04_implementation_plan.md)

## Delivered

Consecutive small symbols combine up to the budget, **within one visibility level**, carrying the
text between them. Twelve three-line getters stop being twelve near-identical chunks.

- **`Chunk.symbols` arrives here, not SF-06**: a merged chunk holds several symbols, so `symbol`
  cannot name it. Content hash, package, unit stay SF-06's.
- **Merged text is a verbatim slice.** `_walk` keeps whitespace-only gaps; dropping them spliced
  text that never existed (`... return 1clas s Beta:`). `FR-17`'s totality cannot catch that — it
  counts non-whitespace — so **containment** asserts it.
- **Split-then-merge does not undo itself**: same budget. Asserted: an oversized class yields more
  than one chunk after both passes, none over budget.
- **`_Run`** holds the *may this piece join the run?* state — three methods, all touching all state,
  `check_class_health` clean. Replaces a `_merge` that `check_complexity` put at **19** (ceiling 15).
- **Visibility is asked five times per file, not once per symbol**: `_levels` calls
  `list_symbols(visibility=[…])` per level; a test asserts the call count. The minimal stub parser
  accepts this third call shape.

## Proof

`test_a_public_getter_is_not_merged_with_a_private_helper` runs at `max_chars=60` and first asserts
the class **split** (at `max_chars=90` it fitted whole and the guard was never exercised).

| # | Neutralised | Objections |
|---|---|---|
| M1 | the visibility guard | **1** |
| M2 | merging entirely | 3 |
| M3 | the between-text | 2 |

Three anchors re-pointed; `FR-17`'s `preamble-dropped` no longer shares `if head.strip():` with
`FR-9`'s between-text mutant.

| Check | Result |
|---|---|
| Full suite | **8,892 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication none new · complexity clean · class health clean |
| Corpus | **30 judged, 30 protected, 0 unprotected, 0 stale** |
| Ledger | `FR-8`–`FR-11` all carry a test file |

## Findings still open

- **M1 has a single point of protection**, and it is the one that matters most.

A parser that cannot answer the per-level call made every symbol `unknown` and merged everything;
fixed by the [red/blue review](B-SENS-03_red_blue_review.md) — `_levels` returns `None`, nothing
merges.
