# Walkthrough: `B-SENS-03` SF-04 CB-1 — the ledger stops lying

- **Story**: `B-SENS-03` SF-04, commit boundary 1 of 4 · **DAL-B** · 2026-08-26
- **Serves**: no FR. **No source file changed and no assertion was added.** This boundary corrects
  what existing tests *claim to prove*.

## The defect, and it is the same one three times

`check_fr_coverage.py B-SENS-03`, before:

```
FR-1    plan     2 test file(s)      FR-4    plan     2 test file(s)
FR-2    plan     2 test file(s)      FR-5    plan     2 test file(s)
FR-3    plan     2 test file(s)
```

One file in each pair was right. The other was `test_semantic_chunking.py`, whose header still read
`Proves: B-SENS-03 FR-1, FR-2, FR-3, FR-4, FR-5` — the numbers from before the renumbering. So the
ledger asserted that **`FR-3`, TypeScript's export-versus-accessibility rule, was proven by a
chunking test**, and `FR-4`, Go's lack of a `private`, likewise.

`test_chunking_properties.py` had it too: `NFR-2` used to mean *Total* and now means *Pure*, so the
file claimed the chunker proves a **budget it does not measure**.

The design predicted this failure mode and the mutation corpus caught it twice — retiring `FR-1` and
`FR-3` in SF-01 CB-3, re-keying `FR-4` and `FR-5` in SF-02 CB-2. **It was in the test citations the
whole time and nobody looked**, because the corpus and the coverage ledger are two different readers
of the same numbers and only one of them was being run against the change.

## What was moved, and what was not

A `Proves:` tag is **file-level and exhaustive** for the story it names, so the question is what each
file may honestly claim *today*.

| Claim | Then | Now |
|---|---|---|
| An unreadable file is still indexed | `FR-4` | **`FR-16`** — survives verbatim |
| A split loses no lines | `FR-5` | **`FR-17`** — survives verbatim |
| Every non-blank character survives | `NFR-2` (*Total*) | **`FR-17`** |
| The chunker never opens a file | `NFR-3` (*Pure*) | **`NFR-2`** |
| The same input gives the same chunks | — | **`NFR-4`** |
| Polyglot via a two-method stub parser | `NFR-1` | `NFR-1`, unchanged |

**Everything else was stripped rather than re-pointed.** Nine tests in `test_semantic_chunking.py`
assert behaviour SF-04 is about to replace — a class is one chunk, an oversized symbol splits on
lines. Giving them a new number would say `FR-8` and `FR-10` are proven when they are not built,
which is the same defect wearing a correction's clothes. They still guard real behaviour and claim
no requirement, and CB-2 through CB-4 rewrite and tag them.

## After

```
FR-1..FR-7, FR-18   1 test file each      FR-16   1 test file
FR-8..FR-11         plan, NO TEST         FR-17   2 test files
FR-12..FR-15        NO PLAN, NO TEST
```

`FR-8`–`FR-11` reading **NO TEST** is the honest state: SF-04 has not built them. `FR-12`–`FR-15`
reading **NO PLAN** is likewise true — they belong to SF-05 and SF-06.

`check_fr_coverage` still exits non-zero, and should: the story is not finished. **Making the ledger
honest could not make it redder**, which is why this went first rather than per sub-feature.

## Results

| Check | Result |
|---|---|
| Full suite | **8,861 passed, 11 skipped** — unchanged, as expected from a boundary that changes no behaviour |
| `quality.py cb` | 14 passed, 1 skipped · `doc` 13/13 |
| Duplication · NFR sweep | none new |

## The lesson, stated plainly

Renumbering a requirement breaks **every** reader of that number, and this repo has at least three:
the mutation corpus, the FR coverage ledger, and the NFR sweep. Fixing one is not fixing it. The
design's *"What happened to the old FR numbers"* table named two of the three, and the third was
found only by running the gate that reads it.
