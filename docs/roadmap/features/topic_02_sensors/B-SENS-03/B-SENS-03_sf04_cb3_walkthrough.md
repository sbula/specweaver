# Walkthrough: `B-SENS-03` SF-04 CB-3 — code is cut where it has a seam

- **Story**: `B-SENS-03` SF-04, commit boundary 3 of 4 · **DAL-B** · 2026-08-26
- **Proves**: `FR-8`, `FR-10`

## Measured before and after, on this repository

| | before | after |
|---|---|---|
| `container_executor.py` | **6 line-cut parts**, part 3 starting mid-method | **0** — 15 named chunks |
| line-cut chunks across `src/` | ~9% of top-level symbols | **0.2% of chunks** |

An oversized class is now its methods. The failure this module's own docstring says it exists to
prevent — *a fragment that never existed as code* — was happening one level down, on 97 of 1,102
symbols.

## Nesting is containment, and the name is only a fast path

The rule this replaced was one line: `if "." not in name`. `FR-7` had just made that false —
`public.orders` is a **top-level** SQL object whose name contains a dot, so every qualified table
and function would have vanished from the index with nothing to show it.

The first replacement was *"the dotted prefix must be a reported symbol, and the text must be
inside it"*. **That failed at depth two**, and a test caught it: Python scopes a symbol to its
*immediately* enclosing class only, so a nested class's method is reported as `Inner.deep_0`, never
`Outer.Inner.deep_0`. At depth two the name has no prefix that is a symbol at all.

So containment decides and the parent is the **smallest** symbol whose text contains this one's.
The dotted prefix stays as a fast path for the common case. Both answers agree where both apply,
and only containment answers depth two.

## A test of mine claimed something it did not own

`test_splitting_recurses` first asserted `c.symbol.startswith("Outer.Inner.")`. That is a **parser**
property, not this boundary's claim, and it is not even true. Rewritten to assert what the boundary
does own: the six nested methods are reached whole, none of them line-cut.

The one-level scoping is a real gap — `Inner.deep_0` cannot say which `Inner` it came from — and it
is recorded for SF-06's `FR-13`, not smuggled into an assertion here.

## The duplication gate found a real duplication, and the fix was better code

Cutting a file and cutting a class are the same problem at two scales: a run of symbols with text
around them. I wrote that loop twice, and `check_duplication` said so — two clones, ten and thirteen
lines, both inside `chunking.py`.

Extracted into `_walk`, with a small frozen `_Cut` holding what the mutual recursion would otherwise
pass six arguments deep. **Not re-frozen** — unlike the sibling-module boilerplate in SF-01, this
was one function written out twice, which is what the ratchet is for.

## Mutants — three, all killed

| # | Neutralised | Objections |
|---|---|---|
| C1 | nothing is ever nested | 5 |
| C2 | a dot means nested again | 2 |
| C3 | lines are cut before structure is tried | 4 |

**And the drift check earned its keep.** `FR-16`'s mutant anchored on `symbols = []`, which this
boundary renamed to `order = []`. It reported `UNMEASURED [symbol-drifted]` rather than letting a
stale anchor read as a pass. Re-anchored, with the rename recorded in the mutant's own text.

## Results

| Check | Result |
|---|---|
| Full suite | **8,880 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication none new |
| Corpus | **27 judged, 27 protected, 0 unprotected, 0 stale** |
| Ledger | `FR-8`, `FR-10`, `FR-11` each carry a test file. `FR-9` reads `NO TEST` — CB-4 |

## Not done here

- Merging small neighbours — **CB-4**, and until it lands a class of twelve getters is twelve chunks
- The preamble's name, the line-window flag, totality as a stated requirement — **SF-05**
