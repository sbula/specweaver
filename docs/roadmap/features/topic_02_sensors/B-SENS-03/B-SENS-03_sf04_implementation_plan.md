# Implementation Plan: AST Semantic Chunking [SF-04: Code is cut into whole units]

- **Feature ID**: B-SENS-03
- **Sub-Feature**: SF-04 — Code is cut into whole units
- **Design Document**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_design.md
- **Design Section**: §Sub-Feature Breakdown → Group B → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf04_implementation_plan.md
- **Status**: DRAFT
- **FRs**: FR-8, FR-9, FR-10, FR-11 · **Depends on**: none

## Research Notes

### The ledger is lying, and it is the third appearance of one defect

`check_fr_coverage.py B-SENS-03`, run 2026-08-26:

```
FR-1    plan     2 test file(s)
FR-2    plan     2 test file(s)
FR-3    plan     2 test file(s)
FR-4    plan     2 test file(s)
FR-5    plan     2 test file(s)
```

One file in each pair is right. The other is `test_semantic_chunking.py`, whose header still reads
`Proves: B-SENS-03 FR-1, FR-2, FR-3, FR-4, FR-5` — **the numbers before the renumbering**. So today
`FR-3` (*TypeScript's export is not accessibility*) reads as covered by a chunking test, and `FR-4`
(*Go has no private*) likewise. `test_chunking_properties.py` has the same problem with `NFR-2`,
which used to mean *Total* and now means *Pure*.

The corpus caught this twice — retiring `FR-1`/`FR-3`, then re-keying `FR-4`/`FR-5`. It was in the
**test citations** the whole time and nobody looked. Fixed first, before any chunker work
`[agreed 2026-08-26]`.

**Making it honest cannot make it redder**: the gate already fails with ten FRs uncited, which is
true — `FR-8`–`FR-17` are not built.

### Nesting is text containment, not punctuation

`chunking.py:50` is one line:

```python
return [name for name in symbols if "." not in name]
```

`FR-7` made that false: `public.orders` is a **top-level** SQL object whose name contains a dot, so
today's chunker drops every qualified table and function.

Measured 2026-08-26, the rule that holds instead:

| | `list_symbols` | is `Beta.go` inside `Beta`'s text? | is the prefix itself a symbol? |
|---|---|---|---|
| Python | `['Beta', 'Beta.go', 'free']` | **yes** — nested | yes |
| SQL | `['public.orders']` | — | **no**, there is no symbol `public` |

Both signals agree and either alone is enough, so the rule is about **tree position** as promised in
SF-03's plan, and the dot never enters into it.

### Visibility must be fetched per level, not per symbol

`FR-9` merges only within one visibility level, so the chunker needs each symbol's level.
`extract_symbol_visibility` calls `_declared_names`, which **re-parses the file on every call** — so
asking per symbol is O(N) parses of the same file, 1,000 of them for a 1,000-symbol file.

`list_symbols(visibility=[level])` answers for a whole level in one call. Five calls per file, whatever
its size. The vocabulary is closed (`VISIBILITY`), so five is the bound rather than a guess.

### What exists, and what the existing tests become

`chunk_source(code, *, path, parser, language, max_chars=4000)` — pure, `parser` injected, no I/O.
Its tests:

| File | Today | After |
|---|---|---|
| `test_semantic_chunking.py` | 14 tests, stale `Proves:` | re-tagged where the claim survives, rewritten where SF-04 replaces the behaviour |
| `test_chunking_properties.py` | totality, purity, determinism | claims survive; `NFR` numbers move |

`test_a_class_survives_a_parser_that_lists_its_method_first` uses a stub parser with hostile
ordering. That test is the reason the nested-symbol filter is not redundant, and it must keep
working under the new rule.

## Commit boundaries

### CB-1 — The ledger stops lying

| Task | |
|---|---|
| 1 | Re-tag the claims that still hold: unreadable-file → `FR-16`, nothing-dropped → `FR-17` |
| 2 | Strip the tags whose requirement no longer exists, rather than inventing a new number for them |
| 3 | `test_chunking_properties.py`: `NFR-2` (*Total*) is now `FR-17`; `NFR-1`/`NFR-3` keep their meaning |
| 4 | Record the before/after ledger in the walkthrough |

**No source changes. No tier — this boundary writes no assertion**, it corrects what existing ones
claim to prove. Its exit condition is `check_fr_coverage.py` showing **one** test file per SF-01 and
SF-02 requirement, and `FR-8`–`FR-11` reading `NO TEST` honestly.

### CB-2 — Size is non-whitespace characters (`FR-11`)

**Red first**: a symbol of 4,001 characters that is 3,000 spaces must **not** split; one of 4,001
non-whitespace characters must.

> **Expected mutant**: the count reverts to `len(text)`. **Done when** the indented-versus-flat pair
> objects — a fixture with the same code at two indentation levels, which is the only shape that
> can tell the two measures apart.

### CB-3 — An oversized symbol splits on structure (`FR-8`, `FR-10`)

| Task | |
|---|---|
| 1 | Nesting from **containment**, replacing the dot filter |
| 2 | A symbol over budget splits into its nested symbols; each is then subject to the same rule. **The recursion terminates by construction** — each level's text is strictly smaller than its parent's — and bottoms out at task 3 |
| 3 | Line cutting only when a symbol has no nested symbols and is still over budget |

**Red first**: `ContainerSubprocessExecutor` is 22,991 characters and becomes **6 line-cut parts**
today, part 3 starting mid-method. It must become its methods. And `public.orders` must appear at
all, which it does not today.

> **Expected mutants**: the containment test always says *not nested* → the class stops splitting
> into methods; the dot filter is restored → `public.orders` disappears from the index.

### CB-4 — Small neighbours merge (`FR-9`)

| Task | |
|---|---|
| 1 | Greedily combine adjacent siblings up to the budget, **within one visibility level**. *Adjacent* means consecutive in source order with no unmergeable symbol between them: two public methods on either side of a private one are **not** neighbours, or the merge would reorder the file |
| 2 | A merged chunk spans from the first symbol's start to the last one's end, **including the text between them** — otherwise a comment between two merged methods becomes its own chunk and `FR-17` gets harder for no gain |
| 3 | Levels come from five `list_symbols` calls, not from N per-symbol ones |

**Split-then-merge does not undo itself, and that is worth stating because it looks like it should.**
A class over budget splits into its methods (`FR-8`); those methods are then small adjacent siblings,
which is exactly what `FR-9` merges. The two do not fight, because **merging respects the same
budget the split was triggered by**: the class was over it, so its methods cannot all merge back.
Twelve getters become two or three chunks rather than twelve or one. cAST's order — split first,
then merge — is what makes that true, and reversing it would not converge.

**Red first**: twelve three-line getters must become few chunks, not twelve, **and more than one**.
A public getter beside a private helper must **not** merge.

> **Expected mutants**: the visibility guard is dropped → the public-beside-private case objects;
> merging is disabled → the twelve-getters case objects.

## Risks

| Risk | Mitigation |
|---|---|
| Merging hides a private symbol inside a public chunk | The visibility guard, its own test, and its own mutant. It is the one thing `FR-9` can get dangerously wrong |
| Merge undoes the split it just performed | Both obey one budget, so it cannot. Asserted directly: an oversized class yields **more than one** chunk after both passes, not one |
| The nesting rule mis-reads a language nobody tested | Containment is checked against a stub parser with hostile ordering, which is an existing test |
| Re-tagging invents coverage | CB-1 **strips** rather than re-points anything whose requirement is gone. A tag is only moved where the claim is unchanged |
| Per-symbol visibility makes a scan quadratic | Five calls per file, measured against the closed vocabulary rather than the symbol count |

## Not in this sub-feature

- The preamble, the unreadable file, and totality — **SF-05**
- Layers, identity, scope labels — **SF-06**
- Chunk overlap: rejected `[agreed 2026-08-26]`
