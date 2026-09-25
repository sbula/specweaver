# B-SENS-03 SF-04 CB-1 — Walkthrough

**Commit boundary:** CB-1 of 4 · **DAL-B** · 2026-08-26 · **Serves**: no FR. **No source file
changed and no assertion added** — this corrects what existing tests *claim to prove* · Plan:
[sf04](B-SENS-03_sf04_implementation_plan.md)

## Delivered

`test_semantic_chunking.py` carried `Proves: B-SENS-03 FR-1, FR-2, FR-3, FR-4, FR-5` — the numbers
from before the renumbering — so the ledger credited `FR-3` and `FR-4` to a chunking test.
`test_chunking_properties.py` cited `NFR-2`, which used to mean *Total* and now means *Pure*.

A `Proves:` tag is **file-level and exhaustive** for the story it names:

| Claim | Then | Now |
|---|---|---|
| An unreadable file is still indexed | `FR-4` | **`FR-16`** — survives verbatim |
| A split loses no lines | `FR-5` | **`FR-17`** — survives verbatim |
| Every non-blank character survives | `NFR-2` (*Total*) | **`FR-17`** |
| The chunker never opens a file | `NFR-3` (*Pure*) | **`NFR-2`** |
| The same input gives the same chunks | — | **`NFR-4`** |
| Polyglot via a two-method stub parser | `NFR-1` | `NFR-1`, unchanged |

**Everything else was stripped, not re-pointed.** Nine tests in `test_semantic_chunking.py` asserted
behaviour SF-04 replaces (a class is one chunk, an oversized symbol splits on lines); a new number
would claim `FR-8` and `FR-10` before they were built. CB-2 through CB-4 rewrite and tag them.

Every reader of a renumbered FR must move — mutation corpus, FR coverage ledger, NFR sweep. The
design's old-FR table named two; this gate found the third.

## Proof

`check_fr_coverage.py B-SENS-03` before:

```
FR-1    plan     2 test file(s)      FR-4    plan     2 test file(s)
FR-2    plan     2 test file(s)      FR-5    plan     2 test file(s)
FR-3    plan     2 test file(s)
```

After:

```
FR-1..FR-7, FR-18   1 test file each      FR-16   1 test file
FR-8..FR-11         plan, NO TEST         FR-17   2 test files
FR-12..FR-15        NO PLAN, NO TEST
```

`NO TEST` / `NO PLAN` is the true state at this boundary; the gate still exits non-zero.

| Check | Result |
|---|---|
| Full suite | **8,861 passed, 11 skipped** — unchanged |
| `quality.py cb` | 14 passed, 1 skipped · `doc` 13/13 |
| Duplication · NFR sweep | none new |
