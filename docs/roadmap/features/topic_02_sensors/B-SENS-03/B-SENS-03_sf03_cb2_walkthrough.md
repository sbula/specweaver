# B-SENS-03 SF-03 CB-2 — Walkthrough

**Commit boundary:** CB-2 of 2 · **DAL-B** · 2026-08-26 · **Proves**: `FR-18`. Closes SF-03 · Plan:
[sf03](B-SENS-03_sf03_implementation_plan.md)

## Delivered

`pub trait Shape { fn area(&self) -> f64; fn name(&self) -> f64 {1.0} }` had reported
`['Shape', 'name']`. Two independent defects, both fixed:

1. **A required method is a `function_signature_item`**; the query named only `function_item`. The
   part of a trait that **is** the contract had no symbol, no chunk, no graph node — and Rust has no
   struct inheritance, so a trait is where its abstraction lives.
2. **`_get_symbol_scope` walked up for `impl_item` only**, so a defaulted method arrived as the bare
   `name`, colliding with every other `name` in an estate.

`impl Shape for C` puts a trait and an impl in scope and the method belongs to `C`: the walk checks
`impl_item` first. `_process_symbol_match` accepts the new node types, so every reported name
resolves. SF-01 and SF-02 needed no change.

Both parsers now report the names they have: the graph and the chunker see a qualified SQL object as
one node, and a Rust trait's contract at all.

## Proof

| Test | Guards |
|---|---|
| `test_a_trait_impl_scopes_to_the_type_not_the_trait` | branch order; its mutant R3 objected to by 28 tests |
| `test_a_trait_member_is_public` | `FR-1`'s trait rule on the new node |
| `test_a_required_method_yields_its_description` | `FR-5`'s climb on the new node |
| resolution tests (2) | the case, and the rule that **every** reported name resolves |

The corpus carries a mutant for each defect — fixing either alone still gives a wrong answer.

| Check | Result |
|---|---|
| Full suite | **8,861 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication: none new |
| Corpus | **23 judged, 23 protected, 0 unprotected, 0 stale** |
| New tests | 34 |

Test classes named for `list_symbols`, `extract_symbol` and `_get_symbol_scope` — the surface each
guards (`R6`).

Handed to SF-04 (closed in its CB-3): `chunking.py:50` dropped every name containing a dot, and
`public.orders` is a top-level object with a dot.
