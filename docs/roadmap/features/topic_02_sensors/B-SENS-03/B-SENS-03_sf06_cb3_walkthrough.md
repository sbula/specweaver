# Walkthrough: `B-SENS-03` SF-06 CB-3 — a chunk can be identified

- **Story**: `B-SENS-03` SF-06, commit boundary 3 of 3 · **DAL-B** · 2026-08-27
- **Proves**: `FR-13`. **Closes SF-06 and the story.**

## What shipped

`content_hash` — sha256 over the text **and every other label**.

`path + symbol + part` already said *which* chunk this is. What was missing is *did it change*, and
without that a re-index means wiping the store and embedding an estate again. Same cost `TECH-070`
is about, on the vector side.

**Every label, not only the text**, and that is the requirement rather than a flourish. A chunk whose
text is unchanged and whose `visibility` was corrected from `public` to `private` is a **different
row** — hash the text alone and the stale one looks current while a consumer keeps serving the old
answer.

**The hash is not its own input.** A hash that fed on its own field would depend on whatever the
field held, so checking a stored chunk for freshness would answer differently from computing it
fresh — every row would read as stale. There is a test that tampers with the field and asserts the
result does not move.

## One case per label, because *every label* is the claim

`TestContentHashCoversEveryLabel` is parameterised over all twelve. A summary assertion would have
been satisfied by hashing two of them, and `the-hash-covers-text-only` — the mutant — is objected to
by twelve tests precisely because each label has its own.

## The same editing mistake, twice, in two boundaries

`layer: str = "body"` is a prefix of `_emit`'s parameter `layer: str = "body",`, so a substring
replace aimed at the dataclass hit the function signature too — the identical mistake CB-2 made with
the same line. Both times the parser caught it immediately; neither reached a test run. Recorded
because it is a habit, not an accident: **anchor on unique context, not on a line that is a prefix
of another.**

## Mutants — four, all killed

| # | Neutralised | Objections |
|---|---|---|
| H1 | the hash covers text only | 12 |
| H2 | the hash is constant | 13 |
| H3 | the hash feeds on itself | 2 |
| H4 | chunks are emitted unsealed | 3 |

H2 and H1 are a pair and neither is enough alone: a constant hash satisfies *same input, same hash*,
and a text-only hash satisfies *different text, different hash*.

## The closure gate

```
B-SENS-03: every declared FR is planned and cited by at least one test.

Summary — B-SENS-03 @ feature (DAL-B)
  ok    unit         scope=all
  ok    integration  scope=all
  ok    e2e          scope=all
```

**The FR ledger is green for the first time in this story.** It began the day crediting chunking
tests to visibility requirements.

## Results

| Check | Result |
|---|---|
| Full suite | **8,977 passed, 11 skipped** |
| `tests.py feature B-SENS-03` | unit · integration · e2e, all `scope=all`, all ok |
| `check_fr_coverage` | **green** — 18 FRs, every one planned and cited |
| `quality.py cb` | 15/15 · `doc` 13/13 |
| file sizes · mypy · ruff · complexity · class health · duplication · conventions · tach | all clean |
| Corpus | **51 judged, 51 protected, 0 unprotected, 0 stale** |
