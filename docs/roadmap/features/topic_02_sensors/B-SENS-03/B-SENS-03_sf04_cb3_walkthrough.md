# B-SENS-03 SF-04 CB-3 — Walkthrough

**Commit boundary:** CB-3 of 4 · **DAL-B** · 2026-08-26 · **Proves**: `FR-8`, `FR-10` · Plan:
[sf04](B-SENS-03_sf04_implementation_plan.md)

## Delivered

An oversized symbol splits into its nested symbols; lines are cut only when nothing nested is left.
The failure the module's docstring exists to prevent — *a fragment that never existed as code* — had
been happening one level down, on 97 of 1,102 symbols.

| | before | after |
|---|---|---|
| `container_executor.py` | **6 line-cut parts**, part 3 starting mid-method | **0** — 15 named chunks |
| line-cut chunks across `src/` | ~9% of top-level symbols | **0.2% of chunks** |

**Nesting is containment; the name is a fast path.** Replaces `if "." not in name`, which `FR-7`
made false (`public.orders`). The parent is the **smallest** symbol whose text contains this one's.
Containment alone answers depth two: Python reports a nested class's method as `Inner.deep_0`, never
`Outer.Inner.deep_0`, so a prefix rule finds no parent.

Cutting a file and cutting a class share one loop, `_walk`, with a frozen `_Cut` carrying the
recursion's state — one function, not two clones.

## Proof

`test_splitting_recurses` asserts the six nested methods are reached whole, none line-cut — the
boundary's claim, not the parser's naming.

| # | Neutralised | Objections |
|---|---|---|
| C1 | nothing is ever nested | 5 |
| C2 | a dot means nested again | 2 |
| C3 | lines are cut before structure is tried | 4 |

`FR-16`'s mutant anchor (`symbols = []`, renamed `order = []`) reported
`UNMEASURED [symbol-drifted]` and was re-anchored.

| Check | Result |
|---|---|
| Full suite | **8,880 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication none new |
| Corpus | **27 judged, 27 protected, 0 unprotected, 0 stale** |
| Ledger | `FR-8`, `FR-10`, `FR-11` each carry a test file |

## Findings still open

- One-level scoping: `Inner.deep_0` cannot say which `Inner` it came from. Recorded for `FR-13`.
