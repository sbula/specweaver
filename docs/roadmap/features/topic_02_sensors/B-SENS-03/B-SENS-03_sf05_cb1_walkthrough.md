# B-SENS-03 SF-05 CB-1 — Walkthrough

**Commit boundary:** CB-1 of 2 · **DAL-B** · 2026-08-26 · **Proves**: `FR-15` · Plan:
[sf05](B-SENS-03_sf05_implementation_plan.md)

## Delivered

The text before the first symbol — docstring, imports, top-level constants — is emitted as
`symbol="<module>"`. It was `symbol=''`, indistinguishable from a blank line between methods and
from a binary blob. **617 top-level assignments in `src/`** are reported by no parser, so this chunk
is the only place they are addressable.

`<module>` names **only** the run before the first symbol `[agreed 2026-08-26]`:

- a stray comment between two functions stays **unnamed**;
- a `class Foo:` header, emitted as a gap by a split class, is **inside** a symbol, not the head of
  the file.

`<module>` is not a legal identifier in any of the eight target languages; a file containing the
literal `"<module>"` still yields no chunk of that name. A file that does not parse gets no
`<module>` — there is no first symbol — and gets `FR-16`'s line window instead.

## Proof

| # | Neutralised | Objections |
|---|---|---|
| P1 | the preamble loses its name | 5 |
| P2 | **every** gap gains it | 3 |

One alone proves nothing: a rule naming everything passes P1's tests, naming nothing passes P2's.

`FR-8`'s `a-dot-means-nested-again` re-pointed at `tops = [n for n in order if parents[n] is None]`
after `UNMEASURED [symbol-drifted]`.

| Check | Result |
|---|---|
| Full suite | **8,902 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication none new |
| Corpus | 32 judged, **32 protected**, 0 unprotected, 0 stale |
| Ledger | `FR-15` carries a test file |
