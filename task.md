# Task: a type is a type in every language

**Skill**: `specweaver-dev` · **Story**: defect in `TECH-068`'s delivered classifier · **Kind**: bugfix

`graph_adapter.py:112` decides `is_class = symbol in supertypes or "extends" in markers`. That asks
*"does it inherit?"* and reads the silence as *"it is not a type."* Two different questions, one
answer — so every language with types but no inheritance mis-files everything it declares.

## Research (measured — do not re-derive)

| Fact | Evidence |
|---|---|
| `extract_supertypes` DOES record a type that inherits nothing | `base.py` — `setdefault(name, {"extends": [], "implements": []})` runs BEFORE the supertype loop |
| It returns `{}` early when the parser declares no type nodes | `base.py:116` — `if not code.strip() or not self.TYPE_DECLARATION_NODES` |
| 7 of 10 parsers declare them | cpp, go, java, kotlin, python, rust, typescript — and all 7 classify correctly |
| 3 declare none | **c, sql, markdown** — so every symbol they report becomes a `PROCEDURE` |
| C reports `struct`, `enum`, `union` as symbols | `c/codestructure.py` `SCM_SYMBOL_QUERY` |
| SQL reports `create_table`, `create_view`, `create_function` | `sql/codestructure.py` `SCM_SYMBOL_QUERY` |
| Markdown reports every heading | `markdown/codestructure.py` — `(section (atx_heading ...))` |
| All three ARE collected | `parseable_suffixes()` returns `.c .h .sql .md .mdx` among 17 |
| Nothing consumes markdown symbols | grep across `src/` — every hit is unrelated prose handling |
| The base REFUSES a type-declaring parser with no `_supertypes_of` | `base.py:179` — so "has types, no inheritance" must be said out loud |
| `NodeKind` was never the problem | `DATA_STRUCTURE`, not `CLASS` — paradigm-neutral, simply never reached |

## Decisions

- C `struct`/`enum`/`union` and SQL `TABLE`/`VIEW` are `DATA_STRUCTURE` `[agreed 2026-08-24]` —
  each is "a named shape other things refer to", which is what the kind means. SQL `FUNCTION` stays
  a `PROCEDURE`, which it already was.
- **Markdown stops reporting headings as symbols** `[agreed 2026-08-24]`. A heading is neither a
  shape nor a procedure; nothing reads them and no edge kind connects them. Inventing a vocabulary
  entry for an unused concept is what `TECH-069` was retired for. If document structure becomes
  useful it arrives with the reader that needs it.

## Commit boundary 1 — every language's types are types

- [ ] 1 — Integration seam test FIRST: a C struct, a SQL table and a Rust trait each reach the graph
      as `DATA_STRUCTURE` — **RED**, C and SQL are `PROCEDURE` today
- [ ] 2 — C declares `TYPE_DECLARATION_NODES` and answers `_supertypes_of` -> `{}` — the language
      has types and no inheritance, said explicitly rather than by silence
- [ ] 3 — SQL declares `TABLE`/`VIEW` as type nodes, same explicit `{}`; `FUNCTION` untouched
- [ ] 4 — Markdown stops reporting headings as symbols
- [ ] 5 — The contract test gains its missing third category: **has types, has no inheritance**.
      Today it has only *must report a type* and *no type concept*, and C sits in the wrong one
- [ ] **CB-1 — a struct, a table and a trait are all data structures**

## Notes on tiers and proof

- **Task 1 is integration and it is the point.** The claim spans parser -> adapter -> mapper ->
  engine. A unit test that `extract_supertypes` now returns a key proves one end; the defect lives
  in the seam, where `is_class` reads one function's silence as another question's answer. That is
  the `TECH-056` shape the dev skill names, and it is why the seam test is written first.
- Unit tests per parser follow, for the boundary each language draws.
- **Not in scope, named:** the `class_definition` / `function_definition` strings the adapter uses
  are object-oriented names for a paradigm-neutral idea. Renaming them touches every parser test
  and proves nothing new. Recorded, not done.
