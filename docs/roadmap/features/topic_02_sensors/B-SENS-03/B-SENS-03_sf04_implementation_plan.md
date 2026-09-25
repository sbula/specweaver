# B-SENS-03 SF-04 — Code is cut into whole units

**Status**: DRAFT · **FRs owned**: FR-8, FR-9, FR-10, FR-11 · **Depends on**: none · Design:
[B-SENS-03_design.md](B-SENS-03_design.md) §Sub-features → SF-04

## Goal

Split-then-merge on the AST: an oversized symbol splits into its nested symbols, small neighbours of
one visibility level merge up to the budget, line cutting is the last resort, and size is counted in
non-whitespace characters. First, make the FR ledger honest.

## Where it plugs in

| Fact | Where |
|---|---|
| `chunk_source(code, *, path, parser, language, max_chars=4000)` — pure, `parser` injected, no I/O | `analyzers/chunking.py` |
| Nesting was one line (below). `FR-7` made it false: `public.orders` is a **top-level** SQL object with a dot, so every qualified table and function was dropped | `chunking.py:50` |
| `extract_symbol_visibility` calls `_declared_names`, which **re-parses the file on every call** — per symbol is O(N) parses, 1,000 for a 1,000-symbol file. `list_symbols(visibility=[level])` answers a whole level in one call: five per file (`VISIBILITY` is closed) | parsers |
| `test_semantic_chunking.py` — 14 tests, stale header `Proves: B-SENS-03 FR-1, FR-2, FR-3, FR-4, FR-5` (pre-renumbering), so the ledger credited `FR-3` (*TypeScript's export is not accessibility*) and `FR-4` (*Go has no private*) to a chunking test. `test_chunking_properties.py` (totality, purity, determinism) cited `NFR-2`, which meant *Total* and now means *Pure* | tests |
| `test_a_class_survives_a_parser_that_lists_its_method_first` — stub parser with hostile ordering; the new nesting rule must keep it working | tests |

```python
return [name for name in symbols if "." not in name]
```

`check_fr_coverage.py B-SENS-03`, run 2026-08-26:

```
FR-1    plan     2 test file(s)
FR-2    plan     2 test file(s)
FR-3    plan     2 test file(s)
FR-4    plan     2 test file(s)
FR-5    plan     2 test file(s)
```

Nesting, measured 2026-08-26:

| | `list_symbols` | is `Beta.go` inside `Beta`'s text? | is the prefix itself a symbol? |
|---|---|---|---|
| Python | `['Beta', 'Beta.go', 'free']` | **yes** — nested | yes |
| SQL | `['public.orders']` | — | **no**, there is no symbol `public` |

## Changes

### CB-1 — The ledger stops lying (no source change) `[agreed 2026-08-26]`

| Task | |
|---|---|
| 1 | Re-tag claims that still hold: unreadable-file → `FR-16`, nothing-dropped → `FR-17` |
| 2 | Strip tags whose requirement no longer exists, rather than inventing a new number |
| 3 | `test_chunking_properties.py`: `NFR-2` (*Total*) is now `FR-17`; `NFR-1`/`NFR-3` keep their meaning |
| 4 | Record the before/after ledger in the walkthrough |

Writes no assertion. Exit: **one** test file per SF-01/SF-02 requirement, `FR-8`–`FR-11` reading
`NO TEST`. Honesty cannot make it redder: the gate already failed with ten FRs uncited
(`FR-8`–`FR-17` unbuilt).

### CB-2 — Size is non-whitespace characters (`FR-11`)

**Red first**: a 4,001-character symbol that is 3,000 spaces must **not** split; 4,001
non-whitespace characters must. Required mutant: the count reverts to `len(text)` — killed by the
same code at two indentation levels, the only shape that tells the measures apart.

### CB-3 — An oversized symbol splits on structure (`FR-8`, `FR-10`)

| Task | |
|---|---|
| 1 | Nesting from **containment**, replacing the dot filter |
| 2 | A symbol over budget splits into its nested symbols, recursively. **Terminates by construction** — each level's text is strictly smaller — and bottoms out at task 3 |
| 3 | Line cutting only when a symbol has no nested symbols and is still over budget |

**Red first**: `ContainerSubprocessExecutor` (22,991 characters) became **6 line-cut parts**, part 3
mid-method; it must become its methods. `public.orders` must appear at all. Mutants: containment
always *not nested*; the dot filter restored.

### CB-4 — Small neighbours merge (`FR-9`)

| Task | |
|---|---|
| 1 | Greedily combine adjacent siblings up to the budget, **within one visibility level**. *Adjacent* = consecutive in source order with no unmergeable symbol between: two public methods around a private one are **not** neighbours, or the merge would reorder the file |
| 2 | A merged chunk spans first symbol's start to last one's end, **including the text between** — else a comment between merged methods becomes its own chunk |
| 3 | Levels from five `list_symbols` calls, not N per-symbol ones |

**Split-then-merge does not undo itself**: merging respects the budget the split was triggered by,
so an oversized class's methods cannot all merge back. Twelve getters become two or three chunks.
cAST's order — split, then merge — makes that true; reversed, it would not converge.

**Red first**: twelve three-line getters → few chunks, **more than one**; a public getter beside a
private helper must **not** merge. Mutants: visibility guard dropped; merging disabled.

## Tests

| Tier | File | Covers |
|---|---|---|
| Unit | `tests/unit/workspace/analyzers/test_chunking_budget.py` | `FR-11` |
| Unit | `tests/unit/workspace/analyzers/test_chunking_structure.py` | `FR-8`, `FR-10` |
| Unit | `tests/unit/workspace/analyzers/test_chunking_merge.py` | `FR-9` |
| Unit | `test_semantic_chunking.py`, `test_chunking_properties.py` | re-tagged (CB-1), rewritten where behaviour changed |

## Decisions (audit)

| Risk | Mitigation |
|---|---|
| Merging hides a private symbol inside a public chunk | The visibility guard, its own test, its own mutant — the one thing `FR-9` can get dangerously wrong |
| Merge undoes the split | One budget; asserted: an oversized class yields **more than one** chunk after both passes |
| The nesting rule mis-reads an untested language | Checked against the hostile-ordering stub parser |
| Re-tagging invents coverage | CB-1 **strips** anything whose requirement is gone; moves a tag only where the claim is unchanged |
| Per-symbol visibility makes a scan quadratic | Five calls per file, bounded by the closed vocabulary |

Not here: preamble, unreadable file, totality (SF-05); layers, identity, scope labels (SF-06);
chunk overlap — rejected `[agreed 2026-08-26]`.

## As built (2026-08-26)

| Where | What |
|---|---|
| nesting | **containment decides**: the parent is the **smallest** symbol whose text contains this one's; the dotted prefix is a fast path. Only containment answers depth two — Python scopes to the *immediately* enclosing class, so a nested class's method is `Inner.deep_0`, never `Outer.Inner.deep_0`. Top-level rule: `tops = [n for n in order if parents[n] is None]` |
| `_walk` + `_Cut` | cutting a file and cutting a class are one loop (a run of symbols with text around them); `_Cut` is a small frozen holder for the recursion's state |
| `_Run` | the merge state: three methods, all touching all state. Replaced a `_merge` at complexity 19 (ceiling 15) |
| `Chunk.symbols` | added here, not SF-06: a merged chunk holds several symbols, so `symbol` cannot name it; anonymous merged chunks lose more than merging gains. Content hash, package, unit stay SF-06's |
| between-text | whitespace-only gaps are kept, so merged text is a verbatim slice (a dropped gap once produced `... return 1clas s Beta:`). Caught by **containment**, not by `FR-17`'s non-whitespace totality |
| `_levels` | one `list_symbols(visibility=[…])` per level; a test asserts the call count. The minimal stub parser accepts this third call shape |
| `weight` | non-whitespace count; the `4000` default asserted unchanged |

Measured on this repository: `container_executor.py` went from **6 line-cut parts** to **0** — 15
named chunks; line-cut chunks across `src/` from ~9% of top-level symbols to **0.2% of chunks**.

Open: `Inner.deep_0` cannot say which `Inner` it came from (one-level scoping) — recorded for
`FR-13`.

Since moved (2026-08-27, SF-06 CB-2): `_weight` → `weight` in `analyzers/_sizing.py`; `_levels` →
`levels_of` in `analyzers/_scope.py`.

Walkthroughs: [cb1](B-SENS-03_sf04_cb1_walkthrough.md) · [cb2](B-SENS-03_sf04_cb2_walkthrough.md) ·
[cb3](B-SENS-03_sf04_cb3_walkthrough.md) · [cb4](B-SENS-03_sf04_cb4_walkthrough.md).
