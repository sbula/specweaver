# B-SENS-03 — Red/Blue Review (SF-01…SF-05)

**Target**: `c06693c7~1..HEAD` — 7 source files, 582 insertions · **Cycles**: 2 · **Findings**: 8 ·
**Critical/High fixed**: 2 · **Refuted**: 3

Run retrospectively: the pre-commit Phase 7.5 red/blue had run on **2 of 11** boundaries (where it
caught a vacuous test and a pattern-7 self-comparison).

## Fixed

Neither was reachable by a mutant — both are paths **no line was written for**; 37 protected
mutants and a green suite of 8,926 sat on top of both.

### 🔴 CRITICAL — the visibility guard failed **open**

`_levels` caught every exception per level and fell back to every symbol reading `unknown`;
`unknown == unknown`, so **everything merged**:

```
parser with no visibility support, max_chars=60
  ('Bag.get_a', 'Bag.__secret')     ← a private symbol inside a public chunk
```

**Now**: `_levels` returns `None` when it cannot answer, and `_Run.absorb` merges nothing. Not
knowing is not knowing they are alike; failing closed costs a few more chunks.

### 🔴 HIGH — a file with no newlines was one chunk, whatever its size

```
800,000 chars in, budget 4,000  →  1 piece, 800,000 chars
```

A minified bundle or single-line JSON has no line boundaries (`NFR-3`'s unbounded raw length is
about indentation, not this). **Now**: `_slice_long_line` cuts a line that alone exceeds the budget
— 200 pieces in 1 ms, flagged `is_line_window`, nothing lost.

Since moved (2026-08-27, SF-06 CB-2 split): `_levels` → `levels_of` in `analyzers/_scope.py`;
`_slice_long_line` → `slice_long_line` in `analyzers/_sizing.py`.

## Refuted

| Finding | Verdict |
|---|---|
| Duplicate symbol bodies are silently dropped | **INVALID** — `partition` consumes to the first occurrence and the second lookup finds the second. Ran it |
| One visibility level failing lets private merge with public | **INVALID** — the failing level becomes `unknown`, which differs from `public`, so it over-separates. Only *all* levels failing was dangerous |
| `_parent_of` is quadratic / the performance problem | **INVALID** — 400 symbols in **3.5 ms**. The real cost is one full parse per `extract_symbol` call: 201 calls, 359 ms, for 7.7 KB → recorded as **`NFR-8`** |

## Accepted risks

| Risk | Why |
|---|---|
| `NFR-8` — one parse per symbol | Performance, not correctness. The fix is a new interface method across ten parsers and belongs to a requirement |
| `_Cut` is `frozen=True` but holds mutable dicts | No live defect: nothing mutates it. Not worth a `MappingProxyType` wrapper on a private type |
| `chunking.py` is pure logic in an `adapter` module | Pre-existing, unchanged by this work |

## Finding still open

Mutants, lint, complexity, mypy, tach and 8,926 tests do not ask *"what happens on a path nobody
wrote a line for?"*. The adversarial review is the check the others cannot replace; nine boundaries
skipped it.
