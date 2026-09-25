# B-SENS-03 SF-02 CB-2 — Walkthrough

**Commit boundary:** CB-2 of 2 · **DAL-B** · 2026-08-26 · **Proves**: `FR-6`. Closes SF-02 · Plan:
[sf02](B-SENS-03_sf02_implementation_plan.md)

## Delivered

`extract_symbol_signature(code, symbol_name) -> str`: the description, then the declaration with the
body removed — the per-symbol form of `extract_skeleton`. A whole file's skeleton is a poor retrieval
unit: a 27,000-character file's skeleton is large and vague, so it matches everything.

- **No `{ ... }` placeholder** — it would be the same three characters in every skeleton chunk.
- **The description is stripped**, per `[agreed 2026-08-26]` Q40.
- **Composes `FR-5` for real**: `test_the_description_is_the_one_fr5_returns` asserts the pair.

Nothing consumes it yet; the skeleton layer is **SF-06** — the shape SF-01 shipped under and the
user approved.

## Proof

`test_the_body_is_gone` (body token **absent**) and `test_the_signature_itself_is_present` are a
pair: absence passes for free on `""`, presence passes for free when nothing was elided.

| # | Neutralised | Objections |
|---|---|---|
| S1 | the body elision | 20 |
| S2 | the description is not prepended | 7 |
| S3 | a language with no body raises instead of coping | **1** |

S3 is SQL (`extract_symbol_body` raises there); one raise would take a whole-repository scan down.

Old `FR-4` and `FR-5` mutants re-keyed to `FR-16`/`FR-17` here, each with reason and date — the
corpus showed seven mutants under one `FR-5` once this campaign landed (design §Old FR numbers).
Ledger: `FR-1` 4 · `FR-2` 3 · `FR-5` 6 · `FR-6` 3 · `FR-16` 1 · `FR-17` 1 — **18 judged, 18
protected, 0 unprotected, 0 stale.**

| Check | Result |
|---|---|
| Full suite | **8,834 passed, 11 skipped** |
| `tests.py cb B-SENS-03` | unit ok · integration ok |
| `quality.py cb` | 15/15 · `doc` 13/13 · `mypy` clean · duplication: **none new** |
| New tests | 39 |

## Findings still open

- **S3 has a single point of protection.**
