# B-SENS-03 SF-03 — A parser does not lose names

**Status**: DRAFT · **FRs owned**: FR-7 (SQL), FR-18 (Rust) · **Depends on**: none · Design:
[B-SENS-03_design.md](B-SENS-03_design.md) §Sub-features → SF-03

## Goal

SQL reports `public.orders` as one symbol; Rust reports a trait's required and defaulted methods,
scoped. Two defects, two files, no shared code — so the Q9 rule *"keep the SQL fix out of common
code"* `[agreed 2026-08-26]` holds.

## Where it plugs in

| Fact | Where |
|---|---|
| SQL query captures `identifier`; `object_reference` for `public.orders` holds two (`identifier('public')`, `.`, `identifier('orders')`), and its own text is exactly `'public.orders'`. Capturing `object_reference` yields the whole name; unqualified `CREATE VIEW summary` still yields `summary` | `sql/codestructure.py:34` |
| `_find_symbol_node` resolves by a name node whose **parent** is an `object_reference`; once the capture moves up, the name node **is** the `object_reference` | `sql/codestructure.py:44` |
| Rust symbol query (whole, below). `function_signature_item` — a trait's **required** method — is not in it | `rust/codestructure.py:118` |
| `_get_symbol_scope` walks up for `impl_item` only, returning `None` otherwise, so a defaulted trait method arrives as `name`, not `Shape.name`. Its guard demands `name_node.parent.type == "function_item"`, excluding signature items | `rust/codestructure.py:163` |
| Before: `['Shape', 'name', 'Circle', 'Circle.area', ...]` — `Shape.area` absent, `Shape.name` unscoped | — |
| SF-01 visibility (`_visibility_of`): a `function_signature_item` has no `visibility_modifier`, so the trait rule reports `public`. SF-02 description (`_anchor`): its parent `declaration_list` starts on a different row, so the climb stops and the previous sibling is the doc comment. Neither needs a change | `_visibility.py`, `_docs.py` |
| The nets pin the defect: `UNFILTERED["rust"]`, `PUBLIC_ONLY["rust"]` in `test_visibility_vocabulary.py`, `EXPECTED["rust"]` in `test_visibility_mapping.py` | tests |
| `chunking.py:50` — `return [name for name in symbols if "." not in name]` — would drop every qualified SQL object once `FR-7` lands. Nothing calls `chunk_source`; SF-04 replaces the line with a rule about **tree position**, not punctuation | `chunking.py` |
| **No stored data migrates**: `graph_nodes` has no `name` column (`docs/analysis/language_families_and_the_graph_2026-08-25.md`) | — |

```
(create_table (object_reference (identifier) @name))
```

```
(struct_item name: (type_identifier) @name)
(trait_item name: (type_identifier) @name)
(impl_item type: (type_identifier) @name)
(impl_item type: (generic_type (type_identifier) @name))
(function_item name: (identifier) @name)
```

Measured on `pub trait Shape { fn area(&self) -> f64; fn name(&self) -> f64 { 1.0 } }`:

```
trait_item
  declaration_list
    function_signature_item     <- `fn area(&self) -> f64;`   REQUIRED, no body
    function_item               <- `fn name(&self) -> f64 {}` DEFAULTED
```

```python
return [name for name in symbols if "." not in name]
```

## Changes

### CB-1 — SQL reports one name per object (`FR-7`)

| Task | |
|---|---|
| 1 | Capture `object_reference` rather than its `identifier` children, all three rules |
| 2 | Move `_find_symbol_node`'s resolution up with the capture; assert `extract_symbol(code, "public.orders")` |
| 3 | Update the characterization net's SQL literals, reason beside them |

**Red first**: `list_symbols` returns `['public.orders', 'summary', 'analytics.total']` — five names
before, two of them schema fragments. Assertions are on the **exact list**
(`'public.orders' in symbols` passes with the fragments still there). Expected mutant: the capture
reverts to `identifier`.

### CB-2 — Rust reports its trait members (`FR-18`)

| Task | |
|---|---|
| 1 | Add `function_signature_item name: (identifier) @name` to the query (field name checked against the tree) |
| 2 | `_get_symbol_scope`: accept both item types; walk up for `trait_item` as well as `impl_item` |
| 2b | `extract_symbol(code, "Shape.area")` resolves to the signature item — `_process_symbol_match` was written when only `function_item` could carry a scope |
| 3 | Update the three Rust literals in the two nets, reason beside them |

**Red first**: `Shape.area` and `Shape.name` both reported and both scoped. **Two causes, two
assertions**: the query alone gives `Shape.area` unscoped; the scope alone leaves it missing.
Required mutants: `function_signature_item` removed from the query; the `trait_item` branch removed
from the scope walk.

## Tests

| Tier | File | Covers |
|---|---|---|
| Unit | `tests/unit/workspace/ast/parsers/sql/test_sql_qualified_names.py` | `FR-7` |
| Unit | `tests/unit/workspace/ast/parsers/rust/test_rust_trait_members.py` | `FR-18` |
| Unit | `test_visibility_vocabulary.py`, `test_visibility_mapping.py`, `test_symbol_docs.py` | updated literals |

## Decisions (audit)

| Risk / question | Resolution |
|---|---|
| An agent asks for `orders` and no longer finds it | **Strict resolution** `[agreed 2026-08-26]`: only the exact name resolves. `list_symbols` is documented as *"run it first, copy the exact string returned"*; a bare-name fallback is the matching that gives the graph its measured 48% ghost rate |
| SF-04 inherits *"a dot means nested"* | Recorded above |
| A quoted SQL identifier (`"my table"`) carries its quotes | A CB-1 test case |
| More Rust symbols change visibility or description | Checked against the new node type — no change needed |
| Nets "fixed" by editing literals unread | Each changed literal carries its reason; the diff is the review |

Not here: TypeScript interfaces (parked with the graph classifier `[agreed 2026-08-26]`); the 617
unnamed top-level constants (same owner); anything in `chunking.py`.

## As built (2026-08-26)

| Where | What |
|---|---|
| `sql/codestructure.py` | captures `object_reference`; `_find_symbol_node` resolves the reference itself. No `if name_node.type == "object_reference":` guard — `_named_nodes` (`base.py:244`) yields only `name` captures, and this query captures nothing else, so the guard could never be false |
| `base.py` `_named_nodes` | exact text match is what enforces strict resolution; its mutant (`endswith`, which makes `orders` resolve to `public.orders`) is the permanent guard |
| `rust/codestructure.py` | `function_signature_item` in the query; `_get_symbol_scope` walks to `impl_item` **first**, then `trait_item` — `impl Shape for C` puts both in scope and the method belongs to `C`; `_process_symbol_match` accepts both new node types |
| `test_symbol_docs.py` | SQL's no-doc case keyed on `public.orders` (`orders` no longer exists) |

Walkthroughs: [cb1](B-SENS-03_sf03_cb1_walkthrough.md) · [cb2](B-SENS-03_sf03_cb2_walkthrough.md).
