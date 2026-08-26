# Walkthrough: `B-SENS-03` SF-03 CB-2 — Rust reports its trait members

- **Story**: `B-SENS-03` SF-03, commit boundary 2 of 2 · **DAL-B** · 2026-08-26
- **Proves**: `FR-18`. Closes SF-03.

## Two defects, and they were independent

`pub trait Shape { fn area(&self) -> f64; fn name(&self) -> f64 {1.0} }` reported `['Shape', 'name']`.

1. **A required method is a `function_signature_item`**, and the symbol query named only
   `function_item`. The part of a trait that **is** the contract had no symbol, no chunk, and no
   node in the graph. Rust has no struct inheritance, so a trait is where its abstraction lives.
2. **`_get_symbol_scope` walked up for `impl_item` and nothing else.** A defaulted method arrived
   as the bare name `name` — colliding with every other `name` in an estate.

**Fixing either alone still gives a wrong answer**: the query alone yields `Shape.area` unscoped,
the scope alone leaves it missing. So the tests assert both, and the corpus carries a mutant for
each.

## The case that decides whether the scope walk is right

`impl Shape for C` puts **both** a trait and an impl in scope, and the method belongs to `C`. The
walk finds the `impl_item` first, so the branches are ordered rather than preferred by type — and
`test_a_trait_impl_scopes_to_the_type_not_the_trait` is what says so. Its mutant (R3) is objected to
by 28 tests.

## A reported name that cannot be looked up is not a symbol

`list_symbols` started reporting `Shape.area` before `extract_symbol` could resolve it:
`_process_symbol_match` accepted `function_item`, `struct_item` and `impl_item`, and neither new
node type was on the list. Two tests caught it — one for the case, one for the rule that **every**
reported name resolves.

The plan predicted this and made it a task rather than a discovery.

## SF-01 and SF-02 needed no change, and that was checked

Both walk the same tree, and both were verified against the new node type **before** the plan was
written: a `function_signature_item` carries no `visibility_modifier`, so `FR-1`'s trait rule
reports it `public`; its parent is a `declaration_list` on a different row, so `FR-2`'s climb stops
and finds the doc comment. Asserted here rather than left as a prediction —
`test_a_trait_member_is_public` and `test_a_required_method_yields_its_description`.

## Results

| Check | Result |
|---|---|
| Full suite | **8,861 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication: none new |
| Corpus | **23 judged, 23 protected, 0 unprotected, 0 stale** |
| New tests | 34 |

`R6` (test-class naming) fired on four class names that described the behaviour rather than the
symbol under test. Renamed to name `list_symbols`, `extract_symbol` and `_get_symbol_scope` — which
is also more honest about which surface each one is guarding.

## SF-03 is delivered

Both parsers report the names they have. The graph and the chunker will see a qualified SQL object
as one node, and a Rust trait's contract at all.

**Still standing for SF-04**: `chunking.py:50` drops every name containing a dot, on the assumption
that a dot means *nested*. `public.orders` is a top-level object with a dot, so that assumption is
now false — recorded in SF-03's plan, and SF-04 replaces the line.
