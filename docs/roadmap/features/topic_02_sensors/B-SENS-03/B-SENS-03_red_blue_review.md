# Red/Blue Team Review Report — `B-SENS-03` SF-01…SF-05

## Summary

- **Target**: the whole code change, `c06693c7~1..HEAD` — 7 source files, 582 insertions
- **Why retrospective**: the pre-commit skill's Phase 7.5 red/blue ran on **2 of 11** boundaries.
  Nine were skipped. This is that review, run late.
- **Cycles**: 2 · **Findings**: 8 · **Critical/High fixed**: 2 · **Refuted**: 3

## The two that mattered, and neither was reachable by a mutant

The mutation corpus asks *"is this line load-bearing?"*. Both of these are paths **no line was
written for**, so no mutant could have found them and none did — 37 protected mutants and a green
suite of 8,926 sat on top of both.

### 🔴 CRITICAL — the visibility guard failed **open**

`_levels` caught every exception per level and fell back to a dict where every symbol read
`unknown`. `unknown == unknown`, so **everything merged**:

```
parser with no visibility support, max_chars=60
  ('Bag.get_a', 'Bag.__secret')     ← a private symbol inside a public chunk
```

`FR-2`'s filter undone one layer up, failing in the **same direction** the original defect failed —
and the guard that `FR-9` exists for was the thing that failed.

**Fix**: `_levels` returns `None` when it cannot answer, and `_Run.absorb` merges nothing at all.
*Not knowing is not the same as knowing they are alike.* Failing closed costs a few more chunks;
failing open puts a private symbol into a public one.

### 🔴 HIGH — a file with no newlines was one chunk, whatever its size

Splitting is on line boundaries. A minified bundle or a single-line JSON has none:

```
800,000 chars in, budget 4,000  →  1 piece, 800,000 chars
```

`NFR-3` says raw length is unbounded — that was about **indentation**, not this. Whatever embeds an
800 KB chunk either fails or silently truncates.

**Fix**: `_slice_long_line` cuts a line that alone exceeds the budget — the last resort *after* the
last resort. Now 200 pieces in 1 ms, flagged `is_line_window`, nothing lost.

## What the review got wrong, which is worth as much

**`_parent_of` was accused of being quadratic and is not.** 400 symbols in **3.5 ms**. The profiler
put the cost somewhere else entirely: `chunk_source` calls `extract_symbol` once per symbol and
**each re-parses the whole file** — 201 calls, 359 ms, for 7.7 KB.

Recorded as **`NFR-8`**, with the number, the refuted hypothesis, and the named fix (a batch
accessor on the parser interface, one parse). Not built: a new method across ten parsers, in no FR.

It is the same shape as the `extract_symbol_visibility` cost I fixed for `_levels` in SF-04 — and I
fixed the smaller one while leaving the larger one in place, because I measured one and reasoned
about the other.

## Refuted

| Finding | Verdict |
|---|---|
| Duplicate symbol bodies are silently dropped | **INVALID** — `partition` consumes to the first occurrence and the second lookup finds the second. Ran it |
| One visibility level failing lets private merge with public | **INVALID** — the failing level becomes `unknown`, which differs from `public`, so it over-separates. Safe. Only *all* levels failing was dangerous |
| `_parent_of` is the performance problem | **INVALID** — measured at 3.5 ms for 400 symbols |

## Accepted risks

| Risk | Why |
|---|---|
| `NFR-8` — one parse per symbol | Performance, not correctness. The fix is a new interface method across ten parsers and belongs to a requirement, not to a review |
| `_Cut` is `frozen=True` but holds mutable dicts | False confidence, no live defect: nothing mutates it. Not worth a `MappingProxyType` wrapper on a private type |
| `chunking.py` is pure logic in an `adapter` module | Pre-existing, unchanged by this work |

## The process finding, which is the real one

**Nine boundaries shipped without this review**, and it found a critical fail-open on the tenth
attempt. The two times it *did* run, it caught a vacuous test and a pattern-7 self-comparison.
Three for three.

Mutants, lint, complexity, mypy, tach and 8,926 tests are all necessary and none of them asks
*"what happens on a path nobody wrote a line for?"*. That question has to be asked by something
adversarial, and skipping it was not a shortcut — it was the one check the others cannot replace.
