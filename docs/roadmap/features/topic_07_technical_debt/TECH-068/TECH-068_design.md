# Design: The Knowledge Graph Emits One of Its Nine Declared Edge Kinds

- **Feature ID**: TECH-068
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED (2026-08-21)
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_design.md

## Feature Overview

`TECH-068` adds dependency edges to the Knowledge Graph's builder. It solves a graph that declares
nine edge kinds and writes one — so every dependency traversal returns a trivial result — by
emitting `IMPORTS`, `CALLS`, `EXTENDS` and `IMPLEMENTS` from data the language parsers already
produce. It interacts with `workspace/ast/parsers`, `workspace/ast/adapters` and
`graph/core/builder`, and does NOT touch framework-semantic edges, the dataflow edge kinds, or any
reader of the graph. Key constraints: build-time targets in `NFR-1`/`NFR-2`; resolution stays pure.

## Problem Statement

`B-SENS-02` is delivered as a "deep class/function-level semantic Knowledge Graph". The delivered
graph is a containment inventory:

- `graph/core/engine/ontology.py` declares nine edge kinds.
- `graph/core/builder/mapper.py` is the only `GraphEdge` construction site. It emits `CONTAINS`
  (file → symbol) and nothing else.
- **In the database it is worse.** `SF-01`'s Phase 0 research found the engine writes the kind under
  `kind` and the store reads `type`, so `repository.py`'s `"CALLS"` fallback fires on every edge.
  Measured: a real build of `src/specweaver/graph` persisted **108 edges, all typed `CALLS`**, and
  every one is a `CONTAINS` edge. The persisted graph claims a call graph it does not have and holds
  no `CONTAINS` rows at all. `FR-14` owns this.

Every planned reader needs dependency edges, not containment: blast radius needs `CALLS`/`IMPORTS`
closure, context packing needs caller/callee traversal (`B-SENS-09`), post-generation verification
needs `CALLS`/`IMPLEMENTS`/`EXTENDS` to find broken dependents (`B-VAL-07`). With one edge kind
each traversal returns an empty or trivial result, and every consumer built on it would be green
and useless.

Per `finished-stories-immutable` the gap becomes this ticket, not an edit to `B-SENS-02`'s closed
scope.

**The mapper is not where the work starts.** `extract_ast_dict` hands the mapper
`{"type", "name"}` per symbol and nothing else — no import, no base type, no call site — so there
is nothing for the mapper to build an edge from. This is a seam contract change first and an
edge-construction change second.

## Decisions taken with the user

Every trigger in `.agents/PRINCIPLES.md` §2 is accounted for below.

- `T-SPEND`, `T-BOUNDARY`, `T-UNDO`, `T-DATA`, `T-PROVEN`: not touched. No spend, no change to what
  untrusted input can reach, nothing deleted or migrated, no new retained or exported data, and
  nothing is declared proven by this document.
- `T-ORDER`: not touched. The Debt Sequencing section of the roadmap already places `TECH-068`
  ahead of `B-SENS-08`, `B-SENS-09` and `B-VAL-07`, so reading it is the answer.
- `T-DIVERGE`: not touched, and considered rather than skipped. The capability's title names the defect at origin. After
  delivery the graph emits five of nine kinds; the remaining four are dataflow kinds owned by
  `B-SENS-08` and `B-SENS-05` and are recorded as Non-Goals below, so nothing this ticket ships
  falls short of its own FR table or of what its name promises to fix.
- `T-OBLIGATION`: not touched, and considered rather than skipped — no new dependency is added. `SF-04` writes `.scm`
  queries as original work against the published grammars. **If a query is instead adapted from an
  upstream repository, that is a fresh trigger and returns to the user.**
- `T-SCOPE`: fired. All four syntactic edge kinds are in scope, `CALLS` included, because every
  named reader needs `CALLS` specifically and `IMPORTS` closure alone is too coarse for any of them.
  Every language is covered uniformly rather than Python-first, because `TECH-061` is `🟢` and its
  subject was exactly "the Knowledge Graph Is Python-Only".
- `T-SCOPE`: fired again on the build-time target. The ≤250 ms single-file incremental target left
  this ticket — no incremental path exists to build on, and how fast the graph updates is a
  separate concern from what it contains. A successor ticket owns it, sequenced ahead of
  `B-SENS-09`.
- `T-DEFAULT`: fired. A target outside the parsed set becomes a `GHOST` edge rather than being
  dropped, so a traversal can tell "no callers" from "callers unknown". A target matching more than
  one node also becomes one `GHOST` edge rather than one edge per candidate: `ADR-006` makes the
  graph the truth store, and a wrong edge is worse than a visible unknown.
- `T-DEFAULT`: fired again on the build-time targets, and **the user delegated them to the agent**.
  They are derived from a measured 2.8 ms/file over a reference workload, not agreed, so a
  measurement that contradicts them changes them. Basis is recorded under `NFR-1`.
- `T-POSTURE`: fired. A file the parser cannot read leaves the build running and the file marked
  unparsed, so a reader can tell an absent edge from an unread file. The alternative — continuing
  silently, which is what the code does today — reproduces the silent-empty result this ticket
  exists to remove.
- `T-ARCH`: fired. `graph/core/builder` reaching into `workspace.ast.adapters` is an approved
  Architectural Switch — see `AD-3`.
- `T-NAME`: fired. `extract_supertypes` and `extract_call_sites` are new methods on the parser
  interface rather than a widening of `extract_framework_markers`, whose return shape three callers
  outside this feature depend on — one of them an agent-facing tool intent. See `AD-2` and `NFR-7`.

## Research Findings

### Codebase Patterns

Reusable, and currently discarded:

- `AbstractParser.extract_imports(code) -> list[str]` is on the interface and implemented. Run on a
  Python fixture it returned `['a.b', 'os']`. `extract_ast_dict` never calls it, so `IMPORTS` is a
  wiring job rather than an extraction job.
- `extract_framework_markers` returns base type NAMES —
  `{"Derived": {"decorators": [], "extends": ["Plain", "C"]}}`. The adapter reads that key only to
  choose a node type and drops the names.
- `list_symbols` already returns qualified names (`Derived.m`), which is what call resolution needs.
- The store already does the `GHOST` work. An edge whose target hash is not a known node
  auto-materialises a ghost: run against a temporary DB, an edge to `unknown-target` produced
  `('unknown-target', is_active=0)` and stored `{"raw": "os.getcwd"}` on the edge.
- `graph_edges` already carries a `metadata` column, and node, ghost and edge writes are already
  chunked at 5,000 rows, so RT-4 is satisfied without new work.

Gaps:

- No call-site extraction exists anywhere — no interface method, no query, no implementation.
- `extract_framework_markers` cannot separate extension from implementation. Run on Java,
  `class Impl extends Base implements Runner` returns `"extends": ["Base", "Runner"]`; the kinds
  are lost even though the syntax distinguishes them.
- `extract_ast_dict` is the choke point. Every edge kind needs a field its dict does not have.

Constraints:

- `graph/core/engine/context.yaml` forbids `os`, `pathlib` and `sqlite3`, so resolution may not
  read the filesystem.
- `GraphNode.metadata` is capped at 2 KB by `validate_metadata_size` (RT-25).
- `normalize_file_id` lowercases `file_id` (RT-21), so two files differing only in case collide —
  a live hazard for cross-file resolution.
- Nodes are tombstoned rather than deleted (RT-13), so stale edges must not resurrect.

Contradictions found in delivered work, all pre-existing:

- `docs/dev_guides/ontology_mapping.md` says an unresolved import should be mapped with
  `target_id = -1` and the raw string "in the metadata". `GraphEdge` is
  `{source_hash: str, target_hash: str, kind: EdgeKind}` — no integer ids and no metadata field.
  The intent is satisfiable today at the storage layer; only the domain model is too narrow.
- The same guide lists six edge kinds where the enum declares nine, and attributes the mapping to
  parsers when it happens in `graph/core/builder/mapper.py`.
- `graph/core/builder/context.yaml` does not allow `specweaver.workspace`, yet
  `GraphOrchestrator.build_target` imports `workspace.ast.adapters.graph_adapter` inline. See
  `AD-3`.

### External Tools

| Tool | Version | Key API Surface | Source |
|---|---|---|---|
| tree-sitter | 0.25.2 | `Query`, capture names | `pyproject.toml`, installed metadata |
| tree-sitter tags convention | — | `@reference.call`, `@reference.implementation` | tree-sitter `docs/src/4-code-navigation.md` |

`@reference.call` ships in the installed wheels for **python, rust, java, go**. It is absent from
**typescript, c, cpp**, and **tree-sitter-kotlin 1.1.0 ships no `.scm` file of any kind**.

### Blueprint References

Tree-sitter's own code-navigation tags convention is the blueprint for call extraction. Name-based
resolution is known to lose accuracy where a call has a receiver, pointer indirection or an implicit
`this`; the published remedy is a type-resolution pass, which is out of scope here and is why an
ambiguous target becomes a `GHOST` rather than a guess.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|---|---|---|---|
| FR-1 | Call-site extraction on the contract | `AbstractParser` | expose `extract_call_sites(code)` | each qualified caller symbol maps to the callee names it invokes |
| FR-2 | Upstream call queries | python/rust/java/go parsers | derive call sites from the grammar package's `TAGS_QUERY` constant, which carries `@reference.call` | no call query for these languages is maintained here, and no file is read — the query is an imported string, so `ast.parsers` stays pure-logic |
| FR-3 | Local call queries | typescript/c/cpp/kotlin parsers | derive call sites from a query held in this repository | call sites are returned for languages upstream does not cover. **The cost is asymmetric**: `c` and `cpp` expose a `TAGS_QUERY` carrying definitions only, so their call patterns extend an existing query; `typescript` and `kotlin` expose no constant at all and start from the grammar |
| FR-4 | Supertypes on the contract | `AbstractParser` | expose `extract_supertypes(code)` | each type's supertypes are reported with extension and implementation distinguished |
| FR-5 | Imports cross the seam | `extract_ast_dict` | emit the file's imported module paths from `extract_imports` | the mapper receives imports it currently never sees |
| FR-6 | Supertypes cross the seam | `extract_ast_dict` | emit each symbol's supertypes with their kind | the mapper can tell an extended class from an implemented interface |
| FR-7 | Call sites cross the seam | `extract_ast_dict` | emit each symbol's call sites | the mapper receives call sites it currently never sees |
| FR-8 | `IMPORTS` edges | the mapper | resolve each imported module path against the `file_id`s already in the parsed set — never against the filesystem (`NFR-4`) — and emit one `IMPORTS` edge from the importing file's node to the resolved file's node | an import traversal returns the files a file depends on; a module outside the parsed set becomes a `GHOST` under `FR-12` |
| FR-9 | `EXTENDS` edges | the mapper | emit one `EXTENDS` edge from a type to each class it extends | a type hierarchy is traversable |
| FR-10 | `IMPLEMENTS` edges | the mapper | emit one `IMPLEMENTS` edge from a type to each interface it implements | interface fulfilment is distinguishable from class extension |
| FR-11 | `CALLS` edges | the mapper | emit one `CALLS` edge from the calling procedure's node to the called procedure's node | caller/callee traversal returns real results |
| FR-12 | Unresolved targets | the mapper | emit an edge to a `GHOST` node carrying the unresolved raw name in edge metadata | a reader distinguishes "no callers" from "callers outside the parsed set" |
| FR-13 | Ambiguous targets | the mapper | emit exactly one `GHOST` edge when a name matches more than one node | a name collision never becomes a fabricated dependency |
| FR-14 | Explicit edge kinds | the mapper | set `EdgeKind` on every edge it constructs | the persistence fallback never supplies a kind for an edge that omits one |
| FR-15 | Unparsed files are visible | the builder | mark a file whose parse failed as unparsed on its node | a reader distinguishes an absent edge from an unread file |
| FR-16 | Stale edges are removed | the store | delete an edge that the rebuilt graph no longer contains, rather than only inserting the ones it does | a call deleted from the source stops being a dependency |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-5 | module paths a file imports | `workspace/ast` · `AbstractParser.extract_imports(code) -> list[str]` | **ran** it — returned `['a.b', 'os']` |
| FR-6 | a type's supertypes, by kind | `workspace/ast` · `extract_framework_markers` returns one flat `extends` list | **ran** it on Java — `extends Base implements Runner` gave `["Base", "Runner"]`; kinds lost. Provides half the FR, so `FR-4` adds the surface |
| FR-7 | call sites per symbol | none — no interface method exists | read `workspace/ast/parsers/interfaces.py`; no such method |
| FR-2 | a call query per grammar | grammar wheels · `queries/tags.scm` | **ran** a scan of the installed wheels — present in python, rust, java, go; absent in ts, c, cpp; kotlin ships no `.scm` |
| FR-12 | a node for an unresolved target | `graph/core/store` · `SqliteGraphRepository.persist_semantic_digraph` | **ran** it — an edge to an unknown hash created `('unknown-target', is_active=0)` and stored `{"raw": "os.getcwd"}` on the edge |
| FR-14 | an explicit edge kind | `graph/core/store` · `graph_edges.type` | read `graph/core/store/repository.py` — `data.get("type", "CALLS")` |
| FR-16 | removal of an edge the graph no longer holds | `graph/core/store` · `persist_semantic_digraph` | **ran** it — persisted a graph with an `a→b` edge, then the same graph without it; the row survived. `persist` only `INSERT OR REPLACE`s and nothing deletes edges |
| FR-2 | the call query as a value, not a file | grammar packages · `TAGS_QUERY` | **ran** it — `tree_sitter_python.TAGS_QUERY` is a 350-char module constant; rust, java and go likewise |
| FR-5/6/7 | the seam itself | `workspace/ast/adapters` · `extract_ast_dict(filepath) -> dict[str, Any]` | **ran** it — emits `{"type", "name"}` per child and nothing more |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|---|---|
| NFR-1 | Cold build time | A cold build of ~3,000 source files SHALL complete in ≤ 60 s. Basis: 2.8 ms/file measured on 358 Python files here (`CONTAINS` only, serial) × 3,000 = 8.4 s, × 4 for four more kinds plus resolution ≈ 34 s, leaving ~1.8× for heavier grammars. **Delegated to the agent by the user; derived, not agreed** |
| NFR-2 | Per-service build time | A single service of ~190 files SHALL complete in ≤ 5 s, on the same basis |
| NFR-3 | *(withdrawn)* | The ≤ 250 ms single-file incremental target left this ticket. No incremental path exists — `build_target` re-ingests every file — and `TECH-070` owns it, sequenced ahead of `B-SENS-09` |
| NFR-4 | Resolution purity | Resolution SHALL NOT read the filesystem. **[proof: arch — `graph/core/engine/context.yaml` forbids `os` and `pathlib`]** |
| NFR-5 | Ghost metadata size | A `GHOST` node's metadata SHALL stay under the 2 KB cap enforced by `GraphNode.validate_metadata_size` (RT-25) |
| NFR-6 | Parse failure is visible | A parser raising on one file SHALL leave the build running and the file marked unparsed, never abort the build and never fail silently |
| NFR-7 | Contract stability | `extract_framework_markers`' return shape SHALL remain unchanged. Three callers outside this feature depend on it — `core/flow/handlers/validation.py` and twice `sandbox/code_structure/core/atom.py`, where it is an agent-facing tool intent |
| NFR-8 | Case collision | Two files differing only in case share a `file_id` and therefore a node, because `normalize_file_id` lowercases it by design (RT-21). Resolution inherits that and this design does not correct it — doing so means changing RT-21, which is out of scope. **[proof: none — a scope statement, not a requirement]** |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|---|---|---|---|---|
| tree-sitter | 0.25.2 | `Query`, captures | Yes | installed 0.25.2, nothing deprecated |
| tree-sitter-python | 0.25.0 | `queries/tags.scm` | Yes | ships `@reference.call` |
| tree-sitter-rust | 0.24.0 | `queries/tags.scm` | Yes | ships `@reference.call`, `@reference.implementation` |
| tree-sitter-java | 0.23.0 | `queries/tags.scm` | Yes | ships `@reference.call`, `@reference.implementation` |
| tree-sitter-go | 0.23.0 | `queries/tags.scm` | Yes | ships `@reference.call` |
| tree-sitter-typescript | 0.23.2 | grammar only | Yes | `tags.scm` has definitions, no `@reference.call` |
| tree-sitter-c / -cpp | 0.23.0 | grammar only | Yes | `tags.scm` has definitions only |
| tree-sitter-kotlin | 1.1.0 | grammar only | Yes | **ships no `.scm` of any kind**; the query is original work here |

No version conflict and nothing deprecated. The only Section C finding is an absence.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|---|---|---|
| AD-1 | The seam contract is widened once, in `SF-01`, declaring imports, supertypes and call sites together; later sub-features populate fields rather than reshape the dict | Every sub-feature otherwise edits `extract_ast_dict`, which serialises work that is not actually coupled. One contract change lets `SF-02` and `SF-03` run in parallel, and `B-SENS-08` inherits the same contract instead of repeating this ticket's first half | No |
| AD-2 | `extract_supertypes` and `extract_call_sites` are NEW methods on `AbstractParser`; `extract_framework_markers` is left unchanged | Its return shape is consumed by three callers outside this feature, one of which exposes it as an agent tool intent. Widening it is a breaking change to a contract agents call. The cost is two methods reading related syntax | No |
| AD-3 | `specweaver.workspace.ast.adapters` is added to `graph/core/builder`'s `allowed_imports`, the inline import in `build_target` is lifted to module level, and the pre-existing undeclared crossing is recorded in Known Boundary Violations as resolved | The dependency direction is already correct — `builder` is Application, `adapters` is Domain — and the import already exists; it was only ever undeclared and hidden inline, which is the recorded "hiding dependencies via inline imports" anti-pattern. `tach` cannot see it because the rule lives in `context.yaml` | **Yes — approved by the user on 2026-08-21** |
| AD-4 | An unresolved or ambiguous target becomes an edge to a `GHOST` node, replacing `ontology_mapping.md`'s `target_id = -1` guidance | `GraphEdge` has no integer ids and no metadata field, so the guide describes a mechanism the model cannot express. `GHOST` is already a declared `NodeKind`, the store already materialises ghosts automatically, and `graph_edges` already has a metadata column. The guide is corrected as part of this ticket | No |
| AD-5 | `FR-14` lands in `SF-01`, before any `CALLS` work | `repository.py` defaults a kindless edge to `"CALLS"`. The trap is unreachable while nothing writes `CALLS` and goes live the moment `SF-03` lands. Fixing it first means it is never reachable | No |

## ROI Analysis

### Investment Cost

| Item | Effort | Risk |
|---|---|---|
| Widen the seam contract, `IMPORTS` edges | Low | Low — data already extracted |
| `extract_supertypes` across 10 parsers | Medium | Low — base extraction exists in 5, syntax is declarative |
| `CALLS` for python/rust/java/go | Medium | Medium — resolution is the hard part, not extraction |
| `CALLS` queries for ts/c/cpp | Medium | Medium — hand-written queries per grammar |
| `CALLS` query for kotlin | Medium-High | **High — the grammar ships nothing to start from** |

### Returns

| Beneficiary | Benefit | Magnitude |
|---|---|---|
| `B-SENS-09` | caller/callee traversal for context packing | Unblocks |
| `B-VAL-07` | broken-dependent detection after generation | Unblocks |
| `B-SENS-08` | inherits the widened seam contract | Large |
| `C-UI-01`, `US-10` | a dependency graph to draw instead of a containment tree | Large |
| blast-radius seam owners | `CALLS`/`IMPORTS` closure | Large |

Not a beneficiary: this repository's own `tach`-based architecture gates. Those are development
tooling on a separate track from the product graph, and wiring one to the other would conflate them.

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Kotlin call query proves intractable | Medium | Medium | `FR-3` is alone in `SF-04`, last. A Kotlin dead end costs one language, not the other edge kinds |
| Name-based resolution over-reports | Medium | High | Ambiguity becomes one `GHOST` edge, never one edge per candidate (`FR-13`) |
| Edge volume degrades build time | Medium | Medium | `NFR-1`/`NFR-2` are measured, and the 5,000-row chunking that RT-4 requires already exists |
| A kindless edge becomes a phantom `CALLS` | High if unfixed | High | `FR-14`, landed in `SF-01` before any `CALLS` edge can be written |
| Case-only filename collision merges two files | Low | Medium | `NFR-8` |

### Refactoring Opportunities

| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|---|---|---|---|
| `extract_ast_dict` | untyped dict, lossy by construction, the choke point for every future edge kind | a declared contract that `B-SENS-08` reuses instead of repeating | Low, inside `SF-01` |
| `ontology_mapping.md` | describes `target_id = -1` and metadata that `GraphEdge` cannot hold; lists six of nine edge kinds | corrected to the mechanism that exists | Low |
| `GraphOrchestrator.build_target` | inline import hiding a real module dependency | declared, module-level, visible to `tach` | Low, inside `SF-01` |

## Developer Guides Required

| Guide Topic | Description | Status |
|---|---|---|
| Guide-1 | Adding a call query for a new language — which grammars ship `tags.scm`, and how to write one when none exists | ⬜ To be written during Pre-Commit |
| Guide-2 | `docs/dev_guides/ontology_mapping.md` correction — `GHOST` replaces `target_id = -1`, and the full nine edge kinds | ⬜ To be written during Pre-Commit |

## Sub-Feature Breakdown

> Restructured during the Phase 6 red/blue review. `FR-16` took `SF-01` to six FRs, past the
> agent-sized bound — and the two edge-write traps are persistence correctness, independent of the
> seam, so they became a sub-feature of their own that lands before anything writes a new edge kind.

### SF-01: Close the edge-write traps
- **Scope**: Make the persistence layer safe for edge kinds it has never carried.
- **FRs**: [FR-14, FR-16]
- **Inputs**: the existing `persist_semantic_digraph` and `graph_edges` table.
- **Outputs**: every edge carries an explicit kind; an edge the rebuilt graph no longer holds is deleted rather than left behind.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_sf01_implementation_plan.md

### SF-02: The seam carries dependencies, and `IMPORTS` lands through it
- **Scope**: Widen the AST-to-graph contract once and prove it end to end with the cheapest edge kind.
- **FRs**: [FR-5, FR-8, FR-12, FR-15]
- **Inputs**: `AbstractParser.extract_imports`; the existing `extract_ast_dict`; `SF-01`'s edge-write guarantees.
- **Outputs**: a declared seam contract carrying imports, supertypes and call sites; `IMPORTS` edges; `GHOST` edges for unresolved targets; unparsed files marked; the `AD-3` boundary declared.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_sf02_implementation_plan.md

### SF-03: Supertypes, with extension and implementation told apart
- **Scope**: Add the supertype surface and emit `EXTENDS` and `IMPLEMENTS`.
- **FRs**: [FR-4, FR-6, FR-9, FR-10]
- **Inputs**: `SF-02`'s seam contract; the existing per-language base extraction.
- **Outputs**: `extract_supertypes` on every parser; `EXTENDS` and `IMPLEMENTS` edges.
- **Depends on**: SF-02
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_sf03_implementation_plan.md

### SF-04: `CALLS` where the grammar already ships the query
- **Scope**: Add call-site extraction and resolution, covering the four languages upstream supports.
- **FRs**: [FR-1, FR-2, FR-7, FR-11, FR-13]
- **Inputs**: `SF-02`'s seam contract; `TAGS_QUERY` from the python, rust, java and go packages.
- **Outputs**: `extract_call_sites` on the interface; `CALLS` edges with resolution and ambiguity handling; `NFR-1`/`NFR-2` measured.
- **Depends on**: SF-02
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_sf04_implementation_plan.md

### SF-05: `CALLS` where no upstream query exists
- **Scope**: Write and maintain call queries for the grammars upstream does not cover.
- **FRs**: [FR-3]
- **Inputs**: `SF-04`'s extraction and resolution mechanism; `c` and `cpp`'s existing `TAGS_QUERY` to extend.
- **Outputs**: repository-held call queries for typescript, c, cpp and kotlin; `NFR-1`/`NFR-2` re-measured.
- **Depends on**: SF-04
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_sf05_implementation_plan.md

## Execution Order

1. `SF-01` — no dependencies. It closes both edge-write traps before any new edge kind is written:
   the `"CALLS"` fallback that would fabricate a kind, and the stale edge that would never be
   removed. Both are unreachable today and both go live the moment `SF-04` lands.
2. `SF-02` — the seam, widened once. `AD-1` is what lets the next two run side by side.
3. `SF-03` and `SF-04` in parallel — both depend only on `SF-02`, and neither reshapes the seam.
4. `SF-05` — depends on `SF-04`. Last on purpose: typescript and kotlin expose no query constant at
   all, so the risk is isolated where it cannot block the other edge kinds.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Close the edge-write traps | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | The seam carries dependencies | SF-01 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-03 | Supertypes told apart | SF-02 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-04 | `CALLS` from upstream queries | SF-02 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-05 | `CALLS` where none ships | SF-04 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Non-Goals

- Framework-semantic edges (`INJECTS`, routes, listeners) — `B-SENS-08`, sequenced behind this.
- `CONSUMES`, `FULFILLS`, `PUBLISHES`, `SUBSCRIBES` — they need framework or dataflow analysis
  (`B-SENS-08`, `B-SENS-05`), not AST syntax.
- Any consumer of the edges. Readers are `B-SENS-09`, `B-VAL-07` and the blast-radius seam owners.
  This ticket makes the graph true; it does not make it used.
- Dynamic dispatch resolution. A `CALLS` edge asserts a syntactic call site and nothing more.
- An incremental build path. Withdrawn at `NFR-3`; `TECH-070` owns it.

## Session Handoff

**Current status**: `SF-01` is committed — three boundaries, both FRs proven, five mutants killed.
`SF-02` onwards are unplanned.

**Next step**: the implementation-plan skill for `SF-02` — *The seam carries dependencies, and
`IMPORTS` lands through it*. Its only dependency, `SF-01`, is committed.

**What `SF-01` changed beyond its own scope**: `FR-14` turned out to be firing rather than latent.
The engine wrote the edge kind under `kind` and the store read `type`, so a real build persisted 108
edges all typed `CALLS` when every one was `CONTAINS`. Eight existing store tests hand-built their
graphs with the store's own key and so could not see it. The attribute is now named once, as
`EDGE_KIND_ATTR`, imported by both sides.

**Also outstanding, and not part of any sub-feature**: `TECH-070` owns the withdrawn `NFR-3` and is
sequenced ahead of `B-SENS-09`. It is minted and un-designed; `TECH-068` does not depend on it.

**If resuming mid-feature**: read the Progress Tracker above. Find the first ⬜ in any row and
resume from there with the skill named for that column. `SF-03` and `SF-04` may run in parallel
sessions once `SF-02` is committed.
