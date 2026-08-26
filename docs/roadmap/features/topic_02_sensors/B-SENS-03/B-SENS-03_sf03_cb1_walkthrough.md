# Walkthrough: `B-SENS-03` SF-03 CB-1 — SQL reports one name per object

- **Story**: `B-SENS-03` SF-03, commit boundary 1 of 2 · **DAL-B** · 2026-08-26
- **Proves**: `FR-7`

## The defect, and how small it was

`CREATE TABLE public.orders` reported **two** symbols: `public` and `orders`. The index gained a
chunk named after a schema, and the table lost its qualification.

One node's depth:

```
(create_table (object_reference (identifier) @name))
```

An `object_reference` holds one `identifier` per name part, and the capture sat on the identifier.
The reference's own text is already `'public.orders'` — the whole name was in the tree, one level
above where the query looked. Three rules, one word each.

## The assertions are on the exact list, and that is the point

`"public.orders" in symbols` passes with **both fragments still present** — the entire defect
surviving a green test. Every assertion here is on the full list, and one test says the harm
directly: no schema fragment is ever reported.

## `extract_symbol` and `list_symbols` had to move together

They share `_declared_names`, but `_find_symbol_node` does not — and it resolved by looking for a
name node whose *parent* is an `object_reference`. Once the capture moved up, the name node **is**
the reference. Asserted rather than assumed: every name `list_symbols` reports must resolve, and the
qualified one specifically.

## A test that was passing for the wrong reason

`test_symbol_docs.py` keyed SQL's no-doc-concept case on `"orders"`. After this change that name
does not exist, so the assertion `== ""` was true for a symbol that is not there — nothing to do
with SQL having no doc-comment concept. Re-keyed to `public.orders`, with the reason inline.

## The corpus found an equivalent mutant, and the guard it aimed at was decoration

`FR-7`'s second mutant targeted `if name_node.type == "object_reference":` in the SQL parser, on the
claim that it enforced strict resolution. It came back **UNPROTECTED — no test noticed the
behaviour disappearing**.

Checked before acting, as the skill requires: `_named_nodes` (`base.py:244`) yields only `name`
captures from `SCM_SYMBOL_QUERY`, and this query captures nothing but `object_reference`. **The
guard can never be false.** Neutralising it changes nothing observable, which is what an equivalent
mutant looks like — not missing coverage.

Two things followed:

1. **The guard was removed.** A branch that cannot be taken is decoration for the same reason a
   test that cannot fail is.
2. **The mutant was re-pointed at what actually enforces strictness** — `_named_nodes`' exact text
   match. Changing it to `endswith` makes `orders` resolve to `public.orders`, and SQL's tests kill
   it. That is the bare-name matching giving the knowledge graph its measured 48% ghost rate, so it
   is worth a permanent guard.

The claim was right and my location for it was wrong. Nothing but running the mutant would have
said so.

## Results

| Check | Result |
|---|---|
| Full suite | **8,846 passed, 11 skipped** |
| `quality.py cb` | 15/15 · duplication: none new |
| Corpus | **20 judged, 20 protected, 0 unprotected, 0 stale** |
| New tests | 19 |

## Not done here

- Rust's lost trait members — **CB-2**
- `chunking.py` drops every dotted name, so `public.orders` would vanish from the index. Nothing
  calls it yet; recorded in the plan for **SF-04**, which replaces that line
