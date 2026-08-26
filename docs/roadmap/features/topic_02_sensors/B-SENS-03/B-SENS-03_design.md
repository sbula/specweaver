# Design: AST Semantic Chunking

- **Feature ID**: B-SENS-03
- **Phase**: Topic 02 (Sensors)
- **Status**: APPROVED 2026-08-26 — rewritten after the approval grilling that was never run
- **DAL**: B (Severe failure) `[agreed 2026-08-26]`
- **Design Doc**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_design.md

> **Supersedes the 2026-08-2x design of the same capability.** That version shipped, was proven,
> and was never approved — `🔧`, not `✅`. The grilling below is what the `specweaver-design`
> Phase 1 gate should have produced before a line was written. Rewritten in place rather than
> superseded by a new ID `[agreed 2026-08-26]`: a `✅` describing behaviour we are about to replace
> is the rotten-record failure `TECH-069` was retired for.

## Feature Overview

`B-SENS-03` adds **labelled, whole-unit chunking** to the workspace analyzers. It solves *"a
retrieval hit is a fragment nobody can place"* by cutting source on nested-symbol boundaries and
stamping every piece with its scoped name, visibility, package and unit. It interacts with
`workspace/ast/parsers` and does **not** touch embedding, storage, retrieval scoring, or where data
is sent. Key constraints: DAL-B · **non-whitespace** characters, not tokens · no overlap · never
the same lines twice within a layer.

The consumer is the **LLM, through the vector half of the RAG** `[agreed 2026-08-26]` — not a
human, and not a gate. `ADR-006` puts vectors on the discovery side; nothing here may ever decide
correctness.

## Why the visibility label exists

**Information hiding, not security and not tidiness** `[agreed 2026-08-26]`. A user of a class,
module or service should not know about its internals, so those internals stay free to change while
the interface holds. The label's job is to stop the agent *depending* on an internal, which is a
different and stronger claim than "keep noise out of results".

It is **not a security boundary** `[agreed 2026-08-26]`. Anyone holding the repository reads the
private code regardless; the index is not a permission system. Sold as security while built as
relevance, it would be exactly the promise-you-cannot-keep this repo retired a capability over.

`B-SENS-03` only **carries** the label. The filter runs at query time, scoped by where the asker
sits `[agreed 2026-08-26]` — inside a module you must see its internals, because you are changing
them; outside you must not.

## Research Findings

### Codebase patterns — measured, not recalled

Every figure below was extracted from this tree on 2026-08-26.

| Finding | Measurement |
|---|---|
| Oversized top-level symbols in `src/` | **97 of 1,102 (8.8%)** exceed 4,000 chars and are cut **on line boundaries** today. `ContainerSubprocessExecutor` becomes 6 parts; part 3 starts mid-method |
| Splitting on nested symbols instead | leaves only **15** still oversized — **85% of the problem gone** |
| Scoped names already available | **7 of 8** target languages report `Beta.go` from `list_symbols`. Only SQL does not |
| SQL qualified names are torn | `CREATE TABLE public.orders` reports **two** symbols, `public` and `orders`. Root cause: `(create_table (object_reference (identifier) @name))` captures both identifiers — `sql/codestructure.py:34` |
| Visibility filter **fails open** | `_is_symbol_valid` at `_reading.py:116` reads `visibility and "public" in visibility`. Every other value falls through to `return True`. Asking for `["private"]` returns **everything** |
| TypeScript ignores visibility | `_is_symbol_hidden` walks up for an `export_statement` (`typescript/codestructure.py:79`), so every member of an exported class reads as public |
| C fails **closed** to empty | `return visibility is None` (`c/codestructure.py:90`) — any filter returns nothing. Out of implementation focus; recorded, not fixed |
| Doc comments dropped | `extract_symbol` loses them in Java, Kotlin, TypeScript, Rust and Go. Python passes only because a docstring lives *inside* the body. `extract_skeleton` keeps them in all six |
| Preambles | **351 of 351** files have one; median **767** chars; 6 over 4,000 |
| Unnamed constants | **617** top-level assignments in `src/` are reported as symbols by nothing |
| Nothing consumes chunking | zero callers of `chunk_source` in `src/` |

**The reuse that shapes SF-01.** C++ already has the accessor the other languages need:
`_get_symbol_visibility(name_node) -> str` at `cpp/codestructure.py:133`, returning a **string**
and handling `class`-defaults-private vs `struct`-defaults-public. Promoting that shape to the base
— replacing the boolean `_is_symbol_hidden` — fixes the fail-open for every language at once and
produces the vocabulary in the same change.

**Boundary rules that constrain this.** `ast/parsers/context.yaml` declares `archetype: pure-logic`
and *"must not execute code"*, `consumes: []`. `analyzers/context.yaml` declares
`archetype: adapter`. Neither may read the filesystem for scope resolution — see `AD-3`.

### External tools

| Tool | Version | Key API surface | Source |
|---|---|---|---|
| tree-sitter | as declared in `pyproject.toml` | `Query`, `QueryCursor`, node `.type` / `.text` / `.parent` | already in use, no change |
| **cAST** (method, not a dependency) | EMNLP 2025 Findings | split-then-merge over the AST; size measured in **non-whitespace characters** | [arXiv 2506.15655](https://arxiv.org/abs/2506.15655) · [ACL](https://aclanthology.org/2025.findings-emnlp.430/) |

**cAST is the peer-reviewed form of this design** and reports **+4.3 Recall@5** on RepoEval and
**+2.67 Pass@1** on SWE-bench against fixed-size chunking. Two things it does that this capability
did not: it **merges** adjacent small siblings *"to maximise per-chunk information density"*, and it
measures size by **non-whitespace character count** *"rather than by lines… for consistency across
coding styles and languages"*. Both adopted `[agreed 2026-08-26]`.

It publishes **no chunk-size ablation**, so its budget is not evidence for ours — see `NFR-3`.

### Blueprint references

`ADR-006` (graphs are truth, vectors are discovery) · `docs/analysis/language_families_and_the_graph_2026-08-25.md`
for the per-language classification measurements this design does not repeat.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Visibility is a value | Parser | Reports a symbol's access level as one of `public` · `protected` · `internal` · `private` · `unknown`, via a single value hook. **A member with no modifier takes its container's rule** — inside a class it is the language's default, inside an interface or trait it is implicitly public and inherits the container's own level. It replaces the visibility role of **both** existing shapes — the boolean `_is_symbol_hidden` (Java, Kotlin, Rust, TypeScript) and the inline `"public" in visibility` test inside the `_is_symbol_valid` overrides (C, C++, Go, Python) | A consumer can ask *what* a symbol's visibility is, not only *is it public* |
| FR-2 | The filter cannot fail open | Parser | `list_symbols(visibility=[...])` returns exactly the symbols whose level is in the request; `unknown` matches a request containing `public` | Asking for `["private"]` returns private symbols — today it returns the entire file |
| FR-3 | Export is not accessibility | TypeScript parser | Reports a `private` member of an exported class as `private`, and a non-exported top-level declaration as `internal` | The two independent axes stop being collapsed into one |
| FR-4 | Go has no private | Go parser | Maps a lowercase identifier to `internal`, never to `private` | A package-mate's legitimate use is not hidden from it |
| FR-5 | A symbol yields its description | Parser | A new accessor returns the doc comment attached to a symbol. **`extract_symbol` is not changed** | Descriptions reach the index in every language, not only Python |
| FR-6 | A symbol yields its signature | Parser | A new accessor returns signature plus doc comment, body elided — the per-symbol form of `extract_skeleton` | The skeleton layer of `FR-12` has something to be built from |
| FR-7 | One object, one name | SQL parser | Reports `public.orders` as a single symbol | The index stops containing a chunk named `public` |
| FR-18 | A parser does not lose names | Rust parser | Reports a trait's **required** and **defaulted** methods, each with its scoped name (`T.x`, `T.y`) | Measured 2026-08-26: `pub trait T { fn x(&self); fn y(&self)->i32 {1} }` reports `['T', 'y', ...]` — `T.x` is absent entirely and `y` carries no scope. `FR-8` cannot split a trait and `FR-13` cannot name its parts until this holds |
| FR-8 | An oversized symbol splits on structure | Chunker | Splits a symbol over budget into its **nested symbols** | A class becomes its methods, each one whole code — not lines 400–500 of something |
| FR-9 | Small neighbours merge | Chunker | Greedily combines adjacent small siblings up to the budget, **only where they share one visibility level and one layer** | Twelve three-line getters stop being twelve near-identical chunks that match everything — without a public getter smuggling a private helper into a public-filtered result |
| FR-10 | Line cutting is the last resort | Chunker | Cuts on line boundaries into numbered `part`/`parts` only when a single symbol is still over budget after `FR-8` | Measured: this path drops from 97 symbols to 15 |
| FR-11 | Size is non-whitespace characters | Chunker | Measures every budget decision by non-whitespace character count | Indented Java and flat Python are judged alike, and reformatting a file stops moving the cuts |
| FR-12 | Two layers | Chunker | Emits a **skeleton** chunk and a **body** chunk per symbol, each labelled with its layer. Splitting and merging run **independently per layer** | A signature is deliberately in both. "Never the same lines twice" holds **within** a layer, not across |
| FR-13 | A chunk can be identified | Chunker | Carries the symbol names it contains, a scoped name when exactly one symbol is inside, and a content hash **over the text and every label** | `Beta.go` is findable even when it merged into a neighbour's chunk or is too small to own one. A merged chunk has **no** single scoped name — the contained list is its identity. Hashing the labels too means a corrected visibility invalidates the row instead of leaving a stale one |
| FR-14 | A chunk knows its scope | Chunker | Carries visibility, **package** (its directory) and **unit** (nearest ancestor holding `Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle`, `package.json` or `pyproject.toml`), resolved by a pure rule from a marker set the caller supplies | A query-time filter can ask *"am I inside this?"* at either radius |
| FR-15 | The preamble is a chunk | Chunker | Emits whatever belongs to no symbol as one chunk named `<module>` | The docstring, imports and 617 constants are addressable instead of anonymous |
| FR-16 | An unreadable file is still indexed | Chunker | Falls back to line windows, **flagged as a line window**, visibility `unknown` | A missing grammar does not look like *this code does not exist*, and a consumer can rank it below real code |
| FR-17 | Nothing is dropped | Chunker | Every non-blank character of a file lands in some **body-layer** chunk | Retrieval over a file is retrieval over all of it. The skeleton layer is a projection and is deliberately incomplete, so the guarantee binds the body layer alone |

**Seam note (`ADR-003`).** `FR-8`–`FR-17` consume `FR-1`–`FR-7`'s parser surfaces. That crossing is
proven by **integration** tests inside this feature, not deferred. `US-11`'s `P-3` journey remains
owned by `A-SENS-02`; nothing here claims it.

## What happened to the old FR numbers

> **Found by the Phase 6 red team, and it was the CRITICAL one.** This design reuses `FR-1`–`FR-5`
> for entirely different requirements, and `B-SENS-03_mutants.json` pins four campaigns to those
> numbers. Left alone, the nightly would keep reporting `B-SENS-03 FR-1 PASSED` — proving *"a symbol
> is chunked once, as a whole"* while the ledger reads it as proof of *"visibility is a value"*.
> A green record for a claim nobody made is the exact failure `TECH-069` was retired over.

| Old FR | Old claim | Fate | Pinned mutant |
|---|---|---|---|
| FR-1 | A symbol is chunked once, as a whole | **replaced** by FR-8 + FR-12 — a chunk may now hold several whole units, and lines are deliberately in two layers | **retire** |
| FR-2 | A chunk can be cited | **replaced** by FR-13 + FR-14 — citation now needs scope, not only path and symbol | none |
| FR-3 | An oversized symbol splits rather than truncating | **replaced** by FR-10 — line splitting is demoted to a last resort behind FR-8 | **retire** |
| FR-4 | An unreadable file is still indexed | **survives** as FR-16, plus the line-window flag | **re-key**, do not retire — the protection is still real |
| FR-5 | Nothing is dropped | **survives** as FR-17, narrowed to the body layer | **re-key**, and re-check the mutant still fails under the narrowed claim |

Re-keying and retiring both go through `scripts/_corpus.py`; `--retire` takes a reason and a date so
the removal is a recorded decision rather than a deletion.

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | A per-language access level | this feature · promoted from `_get_symbol_visibility(name_node) -> str` | **read** `cpp/codestructure.py:133` — already returns a string and handles class/struct defaults |
| FR-2 | The current filter | `_is_symbol_valid(sym_name, name_node, visibility, decorator_filter, framework_markers) -> bool` | **read** `_reading.py:98-128`; **ran** all five visibility values against Java and TypeScript — `["protected"]` and `["private"]` returned the full file |
| FR-3 | TS export vs member access | `_is_symbol_hidden(parent) -> bool` | **read** `typescript/codestructure.py:77-83` — walks up for `export_statement` only; **ran** `export class B { private b(){} }` → `b` reported |
| FR-4 | Go identifier case | `_is_symbol_valid` override | **read** `go/codestructure.py:123-138`; **ran** `func (b B) priv()` → dropped under `["public"]` |
| FR-5 | The doc comment | `SCM_COMMENT_QUERY` on every parser | **read** `java/codestructure.py:64`; **ran** `extract_symbol` on six languages — only Python kept the doc |
| FR-6 | Signature without body | `extract_skeleton(code) -> str` | **read** `interfaces.py:35`; **ran** on Java — emits `public int send(String s, int q) { ... }` with its `/** */` |
| FR-7 | The SQL symbol query | `SCM_SYMBOL_QUERY` | **read** `sql/codestructure.py:32-37` — `(object_reference (identifier) @name)` captures every identifier in a qualified name |
| FR-8, FR-13 | Nested symbol names | `list_symbols(code) -> list[str]` | **read** `_reading.py:222`, `_scoped_name` at `:216`; **ran** on eight languages — seven return `Beta.go` |
| FR-14 | Which files are marker files | the caller, as a supplied set | **read** `graph/core/builder/orchestrator.py:151` `collect_files(target_path) -> set[str]` — already rglobs the tree, so it can supply markers without a second walk. `walk_up_dirs` at `workspace/project/directory_walk.py:20` is the existing nearest-ancestor pattern |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Polyglot | Chunking depends only on the parser interface. No per-language branch in `chunking.py` — a stub parser must exercise every path **[proof: unit]** |
| NFR-2 | Pure | Text in, chunks out. No filesystem, no network, no embedding, no storage. Package and unit arrive as data **[proof: arch — archetype/tach gate]** |
| NFR-3 | Budget | A parameter, default **4,000 non-whitespace characters**. **This number is a guess and is agreed to stay one** `[agreed 2026-08-26]` — cAST publishes no size ablation, and no scan has ever run on a real target. Recalibrating it is a written precondition on `A-SENS-02` **[proof: unit — the default and its unit]**. Consequence, stated rather than discovered: a non-whitespace budget leaves **raw** chunk length unbounded, so deeply indented source produces physically larger chunks than flat source. cAST accepts the same trade; a model with a hard input cap is `A-SENS-02`'s problem to clamp |
| NFR-4 | Deterministic | The same input yields the same chunks, in the same order, with the same hashes. Merging makes this load-bearing: it depends on `list_symbols` returning source order, which must be asserted rather than assumed **[proof: unit]** |
| NFR-5 | Backward compatible | `list_symbols(visibility=["public"])` returns the identical set to today for **all ten** parsers, **except four deltas agreed on 2026-08-26 and enumerated in SF-01's plan**: Python's `__secret` leaves the public set, C stops returning empty, and Java interface members and Rust trait members join it. Two live callers depend on this surface — `analyzers/factory.py:191`, which feeds the generated `context.yaml` `exposes:` list, and the agent-facing `sandbox/code_structure/core/atom.py:139` **[proof: integration — the claim crosses into `workspace/context`, so a unit test of the parser cannot make it]** |
| NFR-6 | Separable layers | Skeleton and body chunks are independently selectable, so `A-SENS-02` can decide what leaves the machine. **That decision is not taken here** `[agreed 2026-08-26]` **[proof: unit — layer field is set and filterable]** |
| NFR-7 | Never a gate | No output of this feature may reach a correctness decision (`ADR-006` decision 3) **[proof: none — scope statement, no threshold to assert]** |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|---|---|---|---|---|
| tree-sitter | unchanged | node traversal, `Query` | Y | No new dependency. cAST is a **method**, not a package |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|---|---|---|
| AD-1 | The visibility hook becomes a **value** accessor, replacing the boolean `_is_symbol_hidden` | One change fixes the fail-open for four shared languages and produces `FR-1`'s vocabulary. Promotes a shape C++ already ships. Fixing the shared helper rather than copying it per language `[agreed 2026-08-26]` — four copies of one rule is how the SQL bug happens twice | No — `_is_symbol_hidden` is a private hook with one caller |
| AD-2 | `extract_symbol` is **not** changed; the doc comment arrives via a new accessor `[agreed 2026-08-26]` | It is paired with `replace_symbol` for editing code. If extraction silently starts including the comment above a declaration, every editing caller changes what it overwrites | No |
| AD-3 | Chunking stays **pure**; `package` and `unit` are passed in, resolved by a pure rule over a marker set the caller already globbed | `analyzers` and `ast.parsers` both forbid I/O. The alternative — walking the filesystem inside the chunker — would break `NFR-2` and the module's archetype | No — this is the choice that **avoids** a switch |
| AD-4 | The SQL fix is confined to `sql/codestructure.py` `[agreed 2026-08-26]` | SQL's failure is its own query, unlike the visibility filter which is genuinely shared. Nothing common or another language's parser is touched | No |
| AD-5 | `unknown` visibility is treated as **visible** `[agreed 2026-08-26]` | SQL and markdown have no access concept. Hiding them would empty the index for two of the eight target languages. Recorded as `unknown` rather than as `public`, so nothing later reads it as a claim the language never made | No |

## ROI Analysis

### Investment cost

| Item | Effort | Risk |
|---|---|---|
| Visibility as a value, six languages | Medium | Low — one hook, one caller, `NFR-5` pins the existing behaviour |
| Doc + signature accessors | Medium | Low — additive, `extract_symbol` untouched |
| SQL qualified names | Small | Low — one query, one file |
| Split-then-merge chunker | Medium | Medium — `FR-9` merging is new behaviour with no local precedent |
| Chunk metadata + layers | Medium | Low |

### Returns

| Beneficiary | Benefit | Magnitude |
|---|---|---|
| `A-SENS-02` | receives chunks it can index, filter and update incrementally instead of rebuilding | **High** — it is the only planned consumer and cannot be built on today's output |
| `B-FLOW-04` | has a visibility and scope to rank on | High |
| `A-SENS-04` | the `unit` radius is exactly its "external interfaces alone" question | Medium — it is `🔮` |
| The graph (`B-SENS-02`) | `FR-1`–`FR-7` fix parser truth the graph reads too | **Spillover** — the fail-open filter and torn SQL names are wrong for every consumer |
| Any agent using `sw` code tools | `sandbox/code_structure/core/atom.py` stops silently returning everything when an agent asks for `private` | Medium, and it is a correctness fix |

### Risk assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| `FR-9` merging degrades retrieval instead of helping | Low | Medium | cAST measured the opposite; the budget is a parameter and merging is a distinct code path that can be disabled |
| `NFR-5` regression — a language's `["public"]` set changes | Medium | High | A pinned per-language fixture asserting today's exact output, written **before** the hook changes |
| `4,000` is wrong for a real estate | **High** | Low | Already declared a guess; recalibration is `A-SENS-02`'s precondition |
| Chunk count roughly doubles under `FR-12` | High | Low | Skeleton chunks are small by construction; `FR-9` merging pulls the other way |

### Refactoring opportunities

| Existing feature | Current issue | Benefit from this feature | Effort |
|---|---|---|---|
| `graph/core/builder` | classifies six languages' types wrongly | shares the corrected parser surfaces | Not taken here — the graph classifier is its own owner |
| `sandbox/code_structure/core/atom.py` | passes an agent's visibility request into a filter that fails open | fixed by `FR-2` with no change at the call site | Free |
| `analyzers/factory.py:191` | uses `visibility=["public"]`, the one value that works | unchanged by `NFR-5`, and now correct by construction rather than by luck | Free |

## Developer Guides Required

| Guide Topic | Description | Status |
|---|---|---|
| Guide-1 | Adding a language to the visibility vocabulary — what `internal` means and why Go lowercase is not `private` | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

> **Two groups were agreed** `[agreed 2026-08-26]` — *the parsers tell the truth*, then *the chunks
> carry it*. The group boundary is unchanged. Inside each group the FR count exceeds the
> agent-sized heuristic (Phase 4 rule 4.5: ≤5 FRs), so each splits further. Six sub-features, two
> groups, same line between them.

### Group A — the parsers tell the truth

### SF-01: Visibility is a value, not a guess
- **Scope**: replace the boolean hidden-check with a normalised access level, and make the filter honest
- **FRs**: [FR-1, FR-2, FR-3, FR-4]
- **Inputs**: source text; the existing `_is_symbol_hidden` overrides in Java, Kotlin, Rust, TypeScript and the `_is_symbol_valid` overrides in C, C++, Go, Python
- **Outputs**: `public` · `protected` · `internal` · `private` · `unknown` per symbol, plus a `list_symbols` filter that cannot return more than was asked for
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf01_implementation_plan.md

### SF-02: A symbol yields its signature and its description
- **Scope**: two additive accessors, leaving the editing primitives alone
- **FRs**: [FR-5, FR-6]
- **Inputs**: `SCM_COMMENT_QUERY`, `extract_skeleton`
- **Outputs**: doc comment per symbol; signature-plus-doc per symbol
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf02_implementation_plan.md

### SF-03: A parser does not lose names
- **Scope**: the two places a symbol query drops or mangles a name. Two tree-sitter queries in two files — no shared code is touched, so the Q9 rule holds `[agreed 2026-08-26]`
- **FRs**: [FR-7, FR-18]
- **Inputs**: `sql/codestructure.py` and `rust/codestructure.py` `SCM_SYMBOL_QUERY`
- **Outputs**: `public.orders` as one symbol; `T.x` and `T.y` reported and scoped
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf03_implementation_plan.md

### Group B — the chunks carry it

### SF-04: Code is cut into whole units
- **Scope**: split-then-merge on the AST, with line cutting demoted to a last resort
- **FRs**: [FR-8, FR-9, FR-10, FR-11]
- **Inputs**: source text; scoped symbol names from `list_symbols`
- **Outputs**: chunks that are whole units or whole runs of units
- **Depends on**: none — but its **SQL and Rust-trait** output stays wrong until SF-03 lands,
  because `FR-8` splits on names those two parsers report incorrectly. Not a cycle: SF-04 is fully testable on the other seven
  languages, and SF-06 already depends on SF-03
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf04_implementation_plan.md

### SF-05: Nothing is lost
- **Scope**: the preamble, the unreadable file, and the totality guarantee
- **FRs**: [FR-15, FR-16, FR-17]
- **Inputs**: SF-04's cut points
- **Outputs**: a `<module>` chunk, flagged line windows, and every non-blank character placed
- **Depends on**: SF-04
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf05_implementation_plan.md

### SF-06: Every chunk is labelled
- **Scope**: the two layers, and everything a consumer needs to place and filter a hit
- **FRs**: [FR-12, FR-13, FR-14]
- **Inputs**: SF-01's visibility values, SF-02's signatures, SF-03's recovered names, SF-04's chunks, and a marker set from the caller
- **Outputs**: skeleton and body chunks carrying scoped name, contained names, content hash, visibility, package, unit, layer
- **Depends on**: SF-01, SF-02, SF-03, SF-04
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf06_implementation_plan.md

## Execution Order

1. **SF-01, SF-02, SF-03, SF-04 in parallel** — none depends on another
2. **SF-05** — after SF-04
3. **SF-06** — after SF-01, SF-02, SF-03 and SF-04

The graph is acyclic. Group A never depends on Group B; SF-06 is the single point where they meet,
which is the boundary that was agreed.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Visibility is a value | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-02 | Signature and description | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-03 | A parser does not lose names | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-04 | Code is cut into whole units | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-05 | Nothing is lost | SF-04 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-06 | Every chunk is labelled | SF-01..04 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Non-Goals

- **Embedding, storage, retrieval scoring, and what leaves the machine.** `A-SENS-02` and
  `B-FLOW-04`. This feature makes the choice *possible* and does not take it `[agreed 2026-08-26]`
- **Naming the 617 top-level constants.** The same parser-query gap as TypeScript interfaces; one
  owner, one ticket `[agreed 2026-08-26]`
- **TypeScript interfaces becoming symbols.** Never reported at all today. Parked with the graph
  classifier, which owns the same gap `[agreed 2026-08-26]`
- **C and C++ visibility.** C fails closed to empty; both are outside the eight-language
  implementation focus `[agreed 2026-08-25]`
- **Methods that are 7,889 characters long.** A code-health finding, and `C-VAL-06`'s job
- **Chunk overlap.** Rejected: it buys nothing on AST cuts and would break the one rule that keeps
  a hit unambiguous `[agreed 2026-08-26]`
- **Tokens as the size unit.** Would mean choosing the embedding model here, which is
  `A-SENS-02`'s decision `[agreed 2026-08-26]`

## Session Handoff

**Current status**: Design **APPROVED** 2026-08-26. SF-01 is in planning.
**Next step**: `specweaver-implementation-plan` for SF-01, then dev. SF-02, SF-03 and SF-04 may run in parallel sessions — the Progress Tracker prevents double work.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and
resume from there. The 32 grilling decisions are recorded inline, each marked `[agreed 2026-08-26]`
beside the fact it governs — do not re-ask them.
