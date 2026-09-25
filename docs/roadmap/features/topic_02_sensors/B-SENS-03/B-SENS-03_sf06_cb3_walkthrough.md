# B-SENS-03 SF-06 CB-3 — Walkthrough

**Commit boundary:** CB-3 of 3 · **DAL-B** · 2026-08-27 · **Proves**: `FR-13`. **Closes SF-06 and
the story** · Plan: [sf06](B-SENS-03_sf06_implementation_plan.md)

## Delivered

`content_hash` — sha256 over the text **and every other label**. `path + symbol + part` says *which*
chunk; the hash says *did it change*, so a re-index need not wipe the store and re-embed an estate
(the cost `TECH-070` is about, on the vector side).

- **Every label**: unchanged text with `visibility` corrected from `public` to `private` is a
  **different row**; a text-only hash leaves the stale one looking current.
- **Not its own input**: otherwise a freshness check on a stored chunk would differ from a fresh
  computation and every row would read stale. A test tampers with the field and asserts the result
  does not move.

## Proof

`TestContentHashCoversEveryLabel` is parameterised over all twelve labels — a summary assertion
would pass on hashing two.

| # | Neutralised | Objections |
|---|---|---|
| H1 | the hash covers text only (`the-hash-covers-text-only`) | 12 |
| H2 | the hash is constant | 13 |
| H3 | the hash feeds on itself | 2 |
| H4 | chunks are emitted unsealed | 3 |

H1 and H2 are a pair: a constant hash satisfies *same input, same hash*; a text-only hash satisfies
*different text, different hash*.

Closure gate:

```
B-SENS-03: every declared FR is planned and cited by at least one test.

Summary — B-SENS-03 @ feature (DAL-B)
  ok    unit         scope=all
  ok    integration  scope=all
  ok    e2e          scope=all
```

| Check | Result |
|---|---|
| Full suite | **8,977 passed, 11 skipped** |
| `tests.py feature B-SENS-03` | unit · integration · e2e, all `scope=all`, all ok |
| `check_fr_coverage` | **green** — 18 FRs, every one planned and cited |
| `quality.py cb` | 15/15 · `doc` 13/13 |
| file sizes · mypy · ruff · complexity · class health · duplication · conventions · tach | all clean |
| Corpus | **51 judged, 51 protected, 0 unprotected, 0 stale** |
