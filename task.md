# task.md — B-SENS-03 SF-04, CB-1: the ledger stops lying

**Plan**: `docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf04_implementation_plan.md`
**Boundary**: CB-1 of 4 · **No source change, no new assertion.**

This boundary corrects what existing tests *claim to prove*. Its exit condition is
`check_fr_coverage.py` showing one test file per SF-01/SF-02 requirement, and `FR-8`–`FR-11`
reading `NO TEST` — which is true.

- [x] **T1** — `test_semantic_chunking.py`: tag only the claims that survive verbatim
- [x] **T2** — `test_chunking_properties.py`: the NFR numbers moved under it
- [x] **T3** — Re-run the ledger, before and after, into the walkthrough

---

# CB-2 — size is non-whitespace characters  (FR-11)

- [x] **T1** — Red: `tests/unit/workspace/analyzers/test_chunking_budget.py`
- [x] **T2** — `_split` measures non-whitespace; `max_chars` keeps its name and its default
- [x] **T3** — Mutant: the count reverts to `len(text)`. Killed by the indented-versus-flat pair,
      which is the only shape that can tell the two measures apart

---

# CB-3 — an oversized symbol splits on structure  (FR-8, FR-10)

- [x] **T1** — Red: `tests/unit/workspace/analyzers/test_chunking_structure.py`
- [x] **T2** — Nesting rule: `S` is inside `P` when **`P` is a reported symbol**, `S` is named
      `P.<rest>`, **and** `S`'s text lies within `P`'s. All three, ANDed. A dot is a hint, never
      the rule — `public.orders` has one and no parent
- [x] **T3** — Over budget → split into nested symbols, recursively; line cutting only when there
      are none left
- [x] **T4** — Mutants: containment always false (the class stops splitting into methods) · the
      dot filter restored (`public.orders` disappears)

---

# CB-4 — small neighbours merge  (FR-9)

**Pulled forward, and stated rather than slipped in:** `Chunk` gains `symbols: tuple[str, ...]`,
which is the *contained names* half of `FR-13` (SF-06). `FR-9` cannot be honest without it — a
merged chunk holds several symbols, so `symbol` cannot name it, and merging twelve getters into
three **anonymous** chunks loses more than it gains. The rest of `FR-13` — content hash, package,
unit — stays in SF-06.

- [x] **T1** — Red: `tests/unit/workspace/analyzers/test_chunking_merge.py`
- [x] **T2** — `Chunk.symbols`, set for every chunk including unmerged ones
- [x] **T3** — Greedy merge of consecutive units, **within one visibility level**, including the
      text between them so `FR-17` stays trivially true
- [x] **T4** — Visibility fetched **five times per file**, not once per symbol
- [x] **T5** — Mutants: the visibility guard dropped · merging disabled
