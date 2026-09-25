# B-SENS-03 SF-03 CB-1 — Walkthrough

**Commit boundary:** CB-1 of 2 · **DAL-B** · 2026-08-26 · **Proves**: `FR-7` · Plan:
[sf03](B-SENS-03_sf03_implementation_plan.md)

## Delivered

`CREATE TABLE public.orders` reports **one** symbol, `public.orders`. The query captured each
`identifier` inside the `object_reference`:

```
(create_table (object_reference (identifier) @name))
```

The reference's own text is already `'public.orders'`; the capture moved up one level, in all three
rules. `extract_symbol` and `list_symbols` moved together: `_find_symbol_node` now resolves the
reference itself, and every name `list_symbols` reports must resolve.

Strictness lives in `_named_nodes`' exact text match (`base.py:244`). The `object_reference` type
guard in the SQL parser was removed: the query captures nothing else, so it could never be false.

## Proof

Every assertion is on the full list (`"public.orders" in symbols` passes with both fragments present); one test states the harm directly — no schema fragment is ever
reported. `test_symbol_docs.py` re-keyed SQL's no-doc case to `public.orders`.

The `FR-7` corpus mutant targets `_named_nodes`: `endswith` instead of exact match makes `orders`
resolve to `public.orders`, and SQL's tests kill it — the bare-name matching behind the knowledge
graph's measured 48% ghost rate. (Its first target, the type guard, came back **UNPROTECTED**: an
equivalent mutant, not missing coverage.)

| Check | Result |
|---|---|
| Full suite | **8,846 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication: none new |
| Corpus | **20 judged, 20 protected, 0 unprotected, 0 stale** |
| New tests | 19 |
