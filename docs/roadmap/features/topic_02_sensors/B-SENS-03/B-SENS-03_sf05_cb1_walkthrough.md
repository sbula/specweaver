# Walkthrough: `B-SENS-03` SF-05 CB-1 — the head of a file has a name

- **Story**: `B-SENS-03` SF-05, commit boundary 1 of 2 · **DAL-B** · 2026-08-26
- **Proves**: `FR-15`

## What shipped

The run of text before the first symbol — a module's docstring, its imports, its top-level
constants — is emitted as `symbol="<module>"`. It arrived as `symbol=''` before, indistinguishable
from the blank line between two methods and from a binary blob no parser could read.

**617 top-level assignments in `src/` are reported as symbols by no parser at all**, so this chunk
is the only place they are addressable.

## The half that gives the name meaning

`<module>` names the run **before the first symbol** and nothing else `[agreed 2026-08-26]`. Two
tests hold the other side, and they are what a mutant has to get past:

- a stray comment between two functions stays **unnamed** — it is not the module's description, and
  indexing it as one reads as an answer rather than as an absence
- a `class Foo:` header, which a split class emits as a gap, is **inside** a symbol and is
  emphatically not the head of the file

A rule that named every no-symbol run would pass every happy-path assertion in this file.

## Two mutants, both directions, both required

| # | Neutralised | Objections |
|---|---|---|
| P1 | the preamble loses its name | 5 |
| P2 | **every** gap gains it | 3 |

One alone proves nothing: a rule that names everything satisfies P1's tests, and a rule that names
nothing satisfies P2's.

## The name cannot collide

`<module>` is not a legal identifier in any of the eight target languages, so no parser can report
a symbol by it. Asserted rather than assumed — a file containing the literal string `"<module>"`
still produces no chunk named that.

## A file that does not parse gets no `<module>`

There is no *first symbol*, so there is no *before* it. What that file gets instead is `FR-16`'s
line window, in CB-2 — and until then it is still indistinguishable from a preamble, which is
exactly what CB-2 is for.

## Anchors drifted again — the fifth time in this story

`FR-8`'s `a-dot-means-nested-again` anchored on a line this boundary rewrote when the preamble split
moved out of `_walk`'s call. Reported `UNMEASURED [symbol-drifted]` and re-pointed at
`tops = [n for n in order if parents[n] is None]`, which is where the rule now lives.

Worth stating plainly: **every commit that touches a mutated line costs a re-anchor**, and the
drift check is the only reason those have been corrections rather than silent passes.

## Results

| Check | Result |
|---|---|
| Full suite | **8,902 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication none new |
| Corpus | 32 judged, **32 protected**, 0 unprotected, 0 stale |
| Ledger | `FR-15` carries a test file |

## Not done here

- The line-window flag, and totality stated across every path — **CB-2**
