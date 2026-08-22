# Implementation Plan: The Knowledge Graph Emits One of Its Nine Declared Edge Kinds [SF-05: CALLS where no upstream query exists]

- **Feature ID**: TECH-068
- **Sub-Feature**: SF-05 — `CALLS` where no upstream query exists
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-05
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_sf05_implementation_plan.md
- **Status**: APPROVED (2026-08-22)

## Scope

`FR-3` — call queries for typescript, c, cpp and kotlin, whose grammars ship none.
Depends on `SF-04`, which is committed. This is the last sub-feature.

## Research Notes

### All four use `call_expression`, and three of them name the callee

Spiked against the real grammars:

| Language | Call node | Callee position |
|---|---|---|
| typescript | `call_expression` | `function:` field — `identifier` or `member_expression` |
| c | `call_expression` | `function:` field — `identifier` |
| cpp | `call_expression` | `function:` field — `identifier` |
| kotlin | `call_expression` | **no field names at all** |

So typescript, c and cpp share one field-addressed query. The mechanism `SF-04` built needs no
change: each language sets `TAGS_QUERY` to a query held here instead of the grammar's own, and
`extract_call_sites` is untouched.

### Kotlin is the risk this decomposition isolated, and it is real but tractable

`field_name_for_child` returns `None` for both children of a Kotlin `call_expression`, so the query
must be positional. Written naively it is wrong:

```
(call_expression (navigation_expression (identifier) @name))
```

on `obj.deep()` captures **both** `obj` and `deep` — the receiver is not a call. Constraining the
pattern to an identifier that follows something fixes it:

```
(call_expression (identifier) @name) @reference.call
(call_expression (navigation_expression (_) (identifier) @name)) @reference.call
```

Verified against `helper()`, `this.other()`, `obj.deep()`, `a.b.c()`, `build(x, y)` and a top-level
`top()`: exactly the six real calls, no receivers, no arguments. Arguments live under
`value_arguments` rather than as direct children, which is what keeps `build(x, y)` from
contributing `x` and `y`.

**The fragility is that a positional pattern cannot be checked against a named contract.** A grammar
change that inserts a child would break it silently, where a field-addressed query would fail loudly.
The tests pin the exact shapes above so the breakage surfaces as a red rather than as a thinner
graph.

### These queries are original work

Written from the grammars by inspection, not adapted from any upstream repository. The design's
`T-OBLIGATION` note makes an adapted query a fresh trigger; this does not fire it.

### An adjacent gap this sub-feature would be editing anyway

`SF-03` gave `extract_supertypes` to python, java, kotlin and typescript. **C++ declares
`base_class_clause` and reports `{}`** — measured. `SF-05` edits `cpp/codestructure.py` for the call
query regardless, so closing it here costs one `TYPE_DECLARATION_NODES` line and one
`_supertypes_of`. Left alone, the graph reports no inheritance at all for C++.

## Decision taken with the user at the Phase 4 gate

**The C++ supertype gap closes here.** `SF-05` opens `cpp/codestructure.py` for the call query
regardless, and leaving it would close `TECH-068` with a language whose inheritance the ticket said
it would cover and does not.

## Red/Blue findings, merged

- **C++ has two top nodes, not one.** `class Impl : ...` is a `class_specifier` and
  `struct S : ...` is a `struct_specifier`, and both carry `base_class_clause`. Declaring only the
  first would silently cover half the language.
- **`access_specifier` is its own node type**, so `public` and `private` cannot be mistaken for base
  names by `_type_names_in`, which captures only `type_identifier` and `identifier`. Verified rather
  than assumed, because a supertype called `public` would be invisible nonsense in the graph.
- **Multiple inheritance yields multiple `type_identifier`s** under one clause, which the existing
  walk already handles — `struct S : private A, public B` gives `A` and `B`.
- **C++ has no interfaces**, so every base is extension. Same shape as Python and Kotlin.
- **TypeScript's `member_expression` carries the same receiver trap as Kotlin**, but it is
  field-addressed — `property:` names the method — so the pattern says what it means rather than
  relying on position.

## Commit Boundaries

### CB-1 — typescript, c and cpp report calls

**Proves**: `FR-3` for the three field-addressed grammars. **Tier**: unit per language.

1. Red first: each returns `{}` today. The query is field-addressed, so `obj.deep()` contributes
   `deep` and never `obj`.
2. `TAGS_QUERY` points at a query held here; `extract_call_sites` is untouched.

**Done when**: green, and a mutant capturing the receiver instead of the property goes red.

### CB-2 — kotlin reports calls

**Proves**: `FR-3` for the positional grammar. **Tier**: unit, with the exact shapes pinned.
Separate from CB-1 because the risk differs in kind, not in language.

1. Red first: kotlin returns `{}` today. The test pins `helper()`, `this.other()`, `obj.deep()`,
   `a.b.c()`, `build(x, y)` and a top-level call, so a grammar change that inserts a child surfaces
   as a red rather than as a thinner graph.

**Done when**: green, and two mutants go red — the navigation pattern unconstrained, which captures
receivers, and the plain pattern removed.

### CB-3 — C++ reports supertypes

**Proves**: `FR-4` for C++, the gap `SF-03` left. **Tier**: unit.

1. Red first: `extract_supertypes` returns `{}` for C++ today. Both `class_specifier` and
   `struct_specifier`, multiple bases, and `public`/`private` never appearing as a base.

**Done when**: green, and a mutant declaring only `class_specifier` goes red.

### CB-4 — Every language's dependencies reach the graph

**Proves**: `FR-3` end to end. **Tier**: integration, and it re-measures `NFR-1`/`NFR-2` on a real
build now that every language contributes.

**Done when**: green, the build time is recorded against the 60 s budget, and a mutant dropping one
language's query goes red.

## Test Plan

| Test | Tier | Proves | Goes red because |
|---|---|---|---|
| typescript reports calls, not receivers | unit | FR-3 | it returns `{}` |
| c reports calls | unit | FR-3 | same |
| cpp reports calls | unit | FR-3 | same |
| kotlin reports calls, not receivers | unit | FR-3 | same, and the naive pattern captures `obj` |
| kotlin's exact shapes are pinned | unit | FR-3 | a positional pattern cannot be checked otherwise |
| cpp reports supertypes from both node kinds | unit | FR-4 | it returns `{}` |
| an access specifier is never a base | unit | FR-4 | a naive walk would capture `public` |
| every language's calls reach the graph | integration | FR-3 | four languages contribute nothing today |

Four buckets: happy path (a plain call in each language), boundary (a method call, a chained call,
a call with arguments, multiple inheritance), graceful degradation (a language with no calls to
find), hostile input (a receiver that must not be reported, an access specifier that must not be a
base).

## Non-Goals

- Resolving a call through its receiver's type. `obj.deep()` contributes `deep`, and which `obj`
  is out of scope for this ticket entirely.
- Any language beyond the four. `sql` and `markdown` have no calls to find.
- `IMPLEMENTS` for C++. It has no interfaces, so every base is extension.
