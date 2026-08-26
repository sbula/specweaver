# Implementation Plan: AST Semantic Chunking [SF-03: A parser does not lose names]

- **Feature ID**: B-SENS-03
- **Sub-Feature**: SF-03 — A parser does not lose names
- **Design Document**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_design.md
- **Design Section**: §Sub-Feature Breakdown → Group A → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf03_implementation_plan.md
- **Status**: DRAFT
- **FRs**: FR-7 (SQL), FR-18 (Rust) · **Depends on**: none

## Research Notes

Two defects, two files, no shared code — which is what makes the Q9 rule *"keep the SQL fix out of
common code"* `[agreed 2026-08-26]` hold without effort here.

### FR-7 — SQL tears a qualified name in half

`sql/codestructure.py:34`:

```
(create_table (object_reference (identifier) @name))
```

The capture is on `identifier`, and `object_reference` for `public.orders` holds **two** of them.
Measured — its children are `identifier('public')`, `.`, `identifier('orders')`, and the node's own
text is exactly `'public.orders'`.

So the whole name is already in the tree, one level up from where the query looks. Capturing
`object_reference` instead yields it directly, and an unqualified `CREATE VIEW summary` still yields
`summary`, because the node's text is the name whether it is qualified or not.

`_find_symbol_node` at `sql/codestructure.py:44` resolves by looking for a name node whose
**parent** is an `object_reference`. Once the capture moves up, the name node **is** the
`object_reference`, so that resolution moves with it.

### FR-18 — Rust loses trait members two different ways

`rust/codestructure.py:118`, the whole query:

```
(struct_item name: (type_identifier) @name)
(trait_item name: (type_identifier) @name)
(impl_item type: (type_identifier) @name)
(impl_item type: (generic_type (type_identifier) @name))
(function_item name: (identifier) @name)
```

Measured on `pub trait Shape { fn area(&self) -> f64; fn name(&self) -> f64 { 1.0 } }`, the tree is:

```
trait_item
  declaration_list
    function_signature_item     <- `fn area(&self) -> f64;`   REQUIRED, no body
    function_item               <- `fn name(&self) -> f64 {}` DEFAULTED
```

Two independent causes:

1. **`function_signature_item` is not in the query at all.** A trait's required methods — the part
   that *is* the contract — are invisible to everything downstream.
2. **`_get_symbol_scope` (`rust/codestructure.py:163`) walks up for `impl_item` only**, and returns
   `None` for anything else. So a defaulted trait method arrives as `name` rather than `Shape.name`.
   Its guard also demands `name_node.parent.type == "function_item"`, which excludes the signature
   items from scoping even once they are reported.

Result today: `['Shape', 'name', 'Circle', 'Circle.area', ...]` — `Shape.area` absent, `Shape.name`
unscoped.

### What SF-01 and SF-02 do with the newly reported nodes

Checked rather than assumed, because both walk the same tree:

- **Visibility** (`_visibility_of`, SF-01): a `function_signature_item` carries no
  `visibility_modifier`, so it falls to the trait check and reports `public` — correct, and it is
  the rule `FR-1` already states for trait members.
- **Description** (`_anchor`, SF-02): `function_signature_item`'s parent is `declaration_list`,
  which starts on a different row, so the climb stops immediately and the previous sibling is the
  doc comment. The row rule needs no change.

### This will move CB-1's characterization net, and that is the point

`UNFILTERED["rust"]` and `PUBLIC_ONLY["rust"]` in `test_visibility_vocabulary.py`, and
`EXPECTED["rust"]` in `test_visibility_mapping.py`, all currently pin the defect: `name` unscoped,
`Shape.area` missing. Those literals carry the reason beside them and are updated here, which is
what the net was built for.

### A hazard this hands to SF-04, found by the Phase 5 review

`chunking.py:50` is one line:

```python
return [name for name in symbols if "." not in name]
```

**"A dot means nested" stops being true the moment `FR-7` lands.** `public.orders` is a top-level
SQL object whose name contains a dot, so today's chunker would drop it entirely — every qualified
table and function silently missing from the index.

Nothing breaks here, because nothing calls `chunk_source`. SF-04 replaces that line anyway, and this
is written down so it replaces it with a rule about **tree position** rather than about punctuation.

**No stored data migrates.** `graph_nodes` has no `name` column at all — the graph drops symbol
names at persistence, recorded in `docs/analysis/language_families_and_the_graph_2026-08-25.md`.
Nothing downstream holds a SQL symbol name that could go stale.

## Commit boundaries

### CB-1 — SQL reports one name per object (`FR-7`)

| Task | File |
|---|---|
| 1 | Capture `object_reference` rather than its `identifier` children, all three rules |
| 2 | Move `_find_symbol_node`'s resolution up with the capture — the name node **is** the `object_reference` now, so `extract_symbol(code, "public.orders")` must be asserted, not assumed |
| 3 | Update the characterization net's SQL literals, with the reason beside them |

**Tier**: unit. **Red first**: assert `list_symbols` returns `['public.orders', 'summary',
'analytics.total']` — it returns five names today, two of them schema fragments.

> **Expected mutant**: the capture reverts to `identifier`. **Done when** the one-name-per-object
> assertions object. A test that only checked `'public.orders' in symbols` would pass with the
> fragments still there, so the assertions are on the **exact list**.

### CB-2 — Rust reports its trait members (`FR-18`)

| Task | File |
|---|---|
| 1 | Add `function_signature_item name: (identifier) @name` to the symbol query. The field is called `name`, checked against the tree rather than guessed |
| 2 | `_get_symbol_scope`: accept both item types, and walk up for `trait_item` as well as `impl_item`. Its guard currently demands `parent.type == "function_item"`, which would exclude the signature items from scoping even once they are reported |
| 2b | `extract_symbol(code, "Shape.area")` must resolve to the signature item — asserted, because `_process_symbol_match` was written when only `function_item` could carry a scope |
| 3 | Update the three Rust literals in the two nets, with the reason beside them |

**Tier**: unit.

**Red first**: assert `Shape.area` and `Shape.name` are both reported and both scoped. Today
`Shape.area` is absent and `Shape.name` is called `name`.

**Two causes, two assertions.** Fixing only the query gives `Shape.area` **unscoped**; fixing only
the scope leaves `Shape.area` missing. One test would let either half pass alone.

> **Expected mutants**, both required:
> - `function_signature_item` removed from the query → the required-method assertion objects
> - the `trait_item` branch removed from the scope walk → the scoped-name assertions object

## Risks

| Risk | Mitigation |
|---|---|
| An agent asks for `orders` and no longer finds it | **Strict resolution** `[agreed 2026-08-26]`: only the exact name resolves. `list_symbols` is documented as *"run it first, copy the exact string returned"*, and a bare-name fallback is the matching that gives the graph its measured 48% ghost rate |
| SF-04 inherits *"a dot means nested"* | Recorded above, in the sub-feature that makes it false |
| A quoted SQL identifier (`"my table"`) carries its quotes into the name | Written as a test case in CB-1 rather than discovered later |
| Reporting more Rust symbols changes visibility or description output | Both were checked against the new node type before this plan was written — neither needs a change |
| The nets fail and are "fixed" by editing literals without reading them | Each changed literal carries its reason inline, as SF-01 CB-3's did. The diff is the review |

## Not in this sub-feature

- TypeScript interfaces, still never reported — parked with the graph classifier `[agreed 2026-08-26]`
- The 617 unnamed top-level constants — same owner
- Anything in `chunking.py`
