# Walkthrough: `B-SENS-03` SF-02 CB-2 — a symbol yields its signature

- **Story**: `B-SENS-03` SF-02, commit boundary 2 of 2 · **DAL-B** · 2026-08-26
- **Proves**: `FR-6`. Closes SF-02.

## What shipped

`extract_symbol_signature(code, symbol_name) -> str`: the description, then the declaration with the
body removed. The per-symbol form of `extract_skeleton`, which produces this shape for a whole file —
a poor retrieval unit, because a 27,000-character file's skeleton is large and vague, so it matches
everything and discriminates nothing.

Two shape decisions, recorded rather than assumed:

- **No `{ ... }` placeholder**, unlike `extract_skeleton`. `FR-12` labels the chunk as a skeleton, so
  a placeholder would be the same three characters in every skeleton chunk in the corpus.
- **The description is stripped**, per `[agreed 2026-08-26]` Q40, for the same reason it is in `FR-5`.

## It composes `FR-5` for real

`FR-6` is `FR-5` plus an elision. The tests do not hand-build the description — the gap check, the
marker stripping and the wrapper climb all live in that half, and a test that assembled the doc
itself would prove the easy part and mock the hard one. `test_the_description_is_the_one_fr5_returns`
asserts the pair.

## The absent-and-present pair

`test_the_body_is_gone` asserts a body token is **absent**; `test_the_signature_itself_is_present`
asserts the signature is **there**. Neither is a test alone: absence passes for free when the
accessor returns `""`, and presence passes for free when nothing was elided.

## Mutants — three, all killed

| # | Neutralised | Objections |
|---|---|---|
| S1 | the body elision | 20 |
| S2 | the description is not prepended | 7 |
| S3 | a language with no body raises instead of coping | **1** |

S3 is SQL, whose declarative tier has no target block, so `extract_symbol_body` raises there. Single
point of protection, and it matters: this is called once per symbol during a whole-repository scan,
where one raise takes the scan down.

## The corpus caught the design's CRITICAL finding a second time

The design predicted `FR-1`/`FR-3` would be conflated by renumbering, and they were retired in
SF-01 CB-3. `FR-4` and `FR-5` were planned to be re-keyed later, *"when SF-05 changes the code they
pin"*.

That was wrong, and running the corpus is what said so. The moment SF-02's `FR-5` campaign landed,
the runner reported **seven mutants under one requirement** — six about descriptions and one about
chunking, sharing a key and nothing else. **A number is conflated when two claims hold it, not when
the code beneath one of them changes.** Both were re-keyed on the spot, each carrying the reason and
the date.

The ledger now reads: `FR-1` 4 · `FR-2` 3 · `FR-5` 6 · `FR-6` 3 · `FR-16` 1 · `FR-17` 1.
**18 judged, 18 protected, 0 unprotected, 0 stale.**

## Results

| Check | Result |
|---|---|
| Full suite | **8,834 passed, 11 skipped** |
| `tests.py cb B-SENS-03` | unit ok · integration ok |
| `quality.py cb` | 15/15 · `doc` 13/13 · `mypy` clean · duplication: **none new** |
| New tests | 39 |

## SF-02 is delivered

`FR-5` and `FR-6` are green and pinned. What they exist for — the skeleton layer — is **SF-06**, and
nothing consumes them yet, which is the shape SF-01 shipped under and the user approved.
