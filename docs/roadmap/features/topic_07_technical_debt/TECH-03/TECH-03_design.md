# Design: Architectural Refactoring of `graph/` Bounded Context

- **Feature ID**: TECH-03
- **Phase**: Technical Debt
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-03/TECH-03_design.md
- **Audit History**: 3 rounds of Red Team / Blue Team adversarial audit

## Feature Overview

Feature TECH-03 is a comprehensive architectural cleanup of the `specweaver.graph` bounded context. Three rounds of adversarial audit revealed **11 anti-patterns** including two **data integrity bugs**, a premature optimization that is the root cause of all ID confusion, systematic encapsulation violations, and a YAGNI abstract class.

**The central insight (Round 3)**: The `InMemoryGraphEngine`'s integer remapping layer (`_hash_to_int`, `_int_to_hash`, `_next_int_id`) provides zero performance benefit — there is no matrix math in the codebase — and is the **sole root cause** of all three data integrity bugs. The fix is not to patch the integer layer with more methods, but to **delete it entirely** and use semantic hash strings as native NetworkX node keys. This eliminates 70+ lines of translation code and makes all three bugs structurally impossible.

Additionally, a `GraphEngineProtocol` is introduced as the Rust readiness seam — 15 lines of code that makes the future Rust engine (petgraph via PyO3) a mechanical drop-in replacement.

## Data Model: Simplified to Two ID Spaces

After dropping the integer remapping, only **two** independent ID spaces remain, each strictly confined to its owner:

```
┌─────────────────────────────────────────────────────────────┐
│  ID SPACE 1: Semantic Hash Strings (THE canonical identity) │
│  ─────────────────────────────────────────────────────────   │
│  Example: "default:a3f8c1e2..."                             │
│  Owner:   SemanticHasher                                    │
│  Meaning: Deterministic identity of a code node.            │
│           Derived from file path + qualified name.          │
│  Used by: Engine, Builder, Repository API, CLI              │
│  Rule:    ALL public APIs speak this language.               │
│           Native node key in nx.DiGraph.                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  ID SPACE 2: DB Autoincrement Integers (storage only)       │
│  Example: 1, 2, 3, ... (SQLite ROWID)                      │
│  Owner:   SqliteGraphRepository (nodes.id column)           │
│  Meaning: Internal FK for edges table. Never exposed.       │
│  Used by: Repository internals ONLY                         │
│  Rule:    NEVER appears outside SqliteGraphRepository.      │
└─────────────────────────────────────────────────────────────┘
```

**Eliminated**: ID Space 2 (engine internal integers) — the root cause of AP-4, AP-10, AP-11. The `_hash_to_int`, `_int_to_hash`, `_next_int_id` infrastructure is deleted.

### How This Eliminates All Three Bugs

| Bug | Before (integer remapping) | After (semantic hash keys) |
|-----|---------------------------|---------------------------|
| **AP-4** | `flush_to_db(engine)` crashes — engine has no `.nodes()` | `flush_to_db(engine._nx_graph)` works — `_nx_graph` IS an `nx.DiGraph` with hash keys |
| **AP-10** | `engine._graph = loaded_graph` corrupts ID maps | `engine.load_semantic_digraph(g)` → `self._nx_graph = g.copy()` — no maps to corrupt |
| **AP-11** | `load_from_db` returns int-keyed graph, `flush_to_db` expects hash-keyed → incompatible | Both use hash-keyed graphs — perfect roundtrip |

## Research Findings

### Anti-Patterns Catalogue

---

#### AP-1: Orchestration Logic in CLI (50+ lines) — DDD violation

The `build()` command in `graph/interfaces/cli.py` (lines 63–134) contains the full graph ingestion pipeline: engine creation, DB path resolution, topology loading, service name resolution, repository creation, stale purging, state loading, builder injection, file iteration, persistence. None of this is CLI-specific.

**Fix**: Distribute logic to natural owners (builder method, repository method, topology facade). CLI remains sole Composition Root per ADR-002.

---

#### AP-2: Cross-Interface Import (`check_lineage`) — DDD/SOLID violation

`check_lineage(src_dir)` is defined in `graph/interfaces/cli.py` but imported by `assurance/validation/interfaces/cli.py`. Domain function in wrong layer.

**Fix**: Move to `graph/lineage/scanner.py`.

---

#### AP-3: `_purge_stale_nodes` — Domain Logic with Console Output — SRP violation

`_purge_stale_nodes()` mixes domain logic with presentation (`console.print()`).

**Fix**: Add as `SqliteGraphRepository.purge_stale_entries(known_file_ids)`. Caller provides known files and handles presentation.

---

#### AP-4: `flush_to_db(engine)` Type Mismatch — RUNTIME BUG 🔴

CLI passes `InMemoryGraphEngine` to `flush_to_db(nx_graph: Any)`. Would crash with `AttributeError` at runtime. **Eliminated by dropping integer remapping** — engine's `_nx_graph` is directly usable.

---

#### AP-5: Encapsulation Violations — OOP/SOLID violation

`GraphBuilder` accesses `engine._lock`, `engine._int_to_hash`, `engine._graph`. CLI mutates `engine._graph`. Builder accesses `self.hasher._normalize_path()`.

**Fix**: Public engine API (`get_nodes_for_file`, `get_edges_involving`). Make `normalize_path` public.

---

#### AP-6: Duplicate `_ensure_gitignore` — NOT a DRY violation

Two versions append **different entries** (`*.graphml` vs `/.specweaver/`). No consolidation needed.

---

#### AP-7: Lazy Stdlib Imports — KISS violation

`import json` 3× inside method bodies. **Fix**: Hoist to module level.

---

#### AP-8: `LineageRepository` Sync-over-Async — KISS violation

Every method wraps `anyio.run()` + new `Database()` per call. **Fix**: Direct sync DB access.

---

#### AP-9: `AbstractGraphRepository` — YAGNI

One implementation. Uses `Any` everywhere, erasing type safety. Directly enabled AP-4.

**Fix**: Delete. Use `SqliteGraphRepository` directly with typed signatures.

---

#### AP-10: ID Space Collision — DATA INTEGRITY BUG 🔴

`load_from_db()` returns DB-integer-keyed graph. CLI sets `engine._graph = graph` corrupting internal ID maps. **Root cause: integer remapping layer. Eliminated by deletion.**

---

#### AP-11: Non-roundtrippable Load/Flush — Data Integrity Risk

`load_from_db()` returns int-keyed, `flush_to_db()` expects hash-keyed. **Root cause: integer remapping. Eliminated by deletion.**

---

#### AP-12: Premature Integer Optimization — KISS violation (Root Cause)

The `_hash_to_int` / `_int_to_hash` / `_next_int_id` infrastructure (70+ lines) was designed for "RT-17: fast matrix math" that does not exist. The engine uses NetworkX for: `add_node`, `add_edge`, `remove_node`, `remove_edge`, `has_node`, `has_edge`, `nodes()`, `edges()`, `ego_graph`, `generate_graphml`. None of these benefit from integer keys over string keys. NetworkX uses Python dicts internally — O(1) hash lookup regardless of key type.

**Fix**: Delete the integer remapping. Use semantic hash strings as native `nx.DiGraph` node keys.

---

#### AP-13: Mixed Concurrency Model — Design Smell

Engine has both `threading.Lock` (sync) and `asyncio.Semaphore` (async) in `__init__`. Only `extract_subgraph` is async. Mixed models create confusion.

**Fix**: Keep `threading.Lock`. Move semaphore to the caller of `extract_subgraph`.

---

### Honest Architecture Assessment

**NetworkX is overkill.** The engine uses 9 of ~500+ NetworkX functions. The actual API surface is an adjacency list with attribute storage — equivalent to `dict[str, dict]` + `dict[str, set[str]]`. This is exactly what `TopologyEngine` already implements with raw Python dicts.

**Two graph engines exist** in the same bounded context (`InMemoryGraphEngine` + `TopologyEngine`) doing the same thing differently. This is the deeper DRY violation. Not addressed in TECH-03, but documented as future TECH-04 candidate.

**Scale ceiling.** At 100K files (~1M nodes), Python's memory overhead (~2GB for 1M-node DiGraph) and GIL (no true concurrent ingestion) become hard limits. The `GraphEngineProtocol` introduced here ensures the Rust engine (via PyO3) can replace the Python engine mechanically when that threshold is reached.

### What Already Exists & Can Be Reused

| Component | Location | Status | Reusable? |
|---|---|---|---|
| `GraphBuilder` | `graph/core/builder/orchestrator.py` | ✅ | Yes — after encapsulation fix |
| `InMemoryGraphEngine` | `graph/core/engine/core.py` | ✅ | Yes — after simplification |
| `SqliteGraphRepository` | `graph/core/store/repository.py` | ✅ | Yes — after type + roundtrip fix |
| `extract_ast_dict` | `workspace/ast/adapters/graph_adapter.py` | ✅ | Yes |
| `load_topology()` | `assurance/graph/loader.py` | ✅ | Yes |

### ROI Analysis

| # | Fix | What It Fixes | Effort | ROI |
|---|---|---|---|---|
| 1 | **Delete integer remapping** + simplify engine | AP-4, AP-5, AP-10, AP-11, AP-12, AP-13 | Medium (~2h) | **Critical** — eliminates root cause |
| 2 | Fix `load_from_db` to return hash-keyed graph | AP-10, AP-11 (completeness) | Medium (~1.5h) | **Critical** |
| 3 | Add `GraphEngineProtocol` | Rust readiness | Low (~15 min) | High — saves 200h later |
| 4 | Delete `AbstractGraphRepository` | AP-9 | Low (~15 min) | High |
| 5 | Distribute CLI logic to natural owners | AP-1, AP-3 | Medium (~1.5h) | High |
| 6 | Move `check_lineage` | AP-2 | Low (~30 min) | Medium |
| 7 | Fix `LineageRepository` | AP-8 | Medium (~1.5h) | Medium |
| 8 | Hoist lazy imports | AP-7 | Low (~10 min) | Low |

**Total: ~8 hours. Net code reduction: ~50 lines. Fixes 2 data integrity bugs at root cause. Adds Rust seam.**

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Delete integer remapping, simplify engine | System | Remove `_hash_to_int`, `_int_to_hash`, `_next_int_id`. Rename `_graph` to `_nx_graph`. Use semantic hash strings as native `nx.DiGraph` node keys. Add `_file_index: dict[str, set[str]]` (hash→set of hashes by file_id) for O(1) file-based lookups, maintained on upsert/remove. Keep `_lock`. Remove `asyncio.Semaphore` from engine (move to caller). Simplify all existing methods. Add `export_semantic_digraph() -> nx.DiGraph` (returns `dict(data)` copy, read-only snapshot) and `load_semantic_digraph(semantic_digraph: nx.DiGraph) -> None` (REPLACE semantics: clears state, rebuilds `_file_index`, atomic under `_lock`). Add `get_nodes_for_file(file_id) -> set[str]` (O(1) via `_file_index`) and `get_edges_involving(hashes) -> set[tuple[str,str]]`. | Engine shrinks from ~140 to ~80 lines. All ID confusion eliminated. Builder uses public API only. |
| FR-2 | Add `GraphEngineProtocol` | System | Define a `typing.Protocol` with all public engine methods. `InMemoryGraphEngine` satisfies it structurally. Future Rust engine implements it via PyO3. | Rust migration becomes mechanical. 15 lines. |
| FR-3 | Make `SemanticHasher.normalize_path()` public | System | Rename `_normalize_path` to `normalize_path` | Builder no longer accesses private method |
| FR-4 | Fix load/flush roundtrip | System | `load_from_db()` returns `nx.DiGraph` with semantic hash string keys (drop `hash_to_id` tuple — unused). Rename `flush_to_db` to `persist_semantic_digraph(semantic_digraph: nx.DiGraph)`. Add `PRAGMA busy_timeout=5000`. | Roundtrip works. AP-4, AP-10, AP-11 eliminated. |
| FR-5 | Delete `AbstractGraphRepository` | System | Remove abstract class. Use `SqliteGraphRepository` directly with typed signatures. No `Any` in public API. | Type safety at mypy level. |
| FR-6 | Distribute CLI logic to natural owners | System | (a) `GraphBuilder.ingest_target(target_path: Path) -> int` (extends `ingest_file`). (b) `SqliteGraphRepository.purge_stale_entries(known_file_ids: set[str]) -> list[str]` (caller provides known files). (c) `resolve_service_name(topology, project_path) -> str` in `assurance/graph/loader.py`. **No `helpers.py` file.** | Each function on natural owner. CLI slim. |
| FR-7 | Move `check_lineage` | System | Move from `graph/interfaces/cli.py` to `graph/lineage/scanner.py`. Update import in `assurance/validation/interfaces/cli.py`. | Cross-interface violation eliminated. |
| FR-8 | Slim CLI to thin adapter | System | `build()` wires engine + repo + builder + calls helpers. ≤15 lines. | CLI = I/O + presentation only. |
| FR-9 | Hoist lazy stdlib imports | System | Move `import json` and `import networkx` to module level in `repository.py` | KISS |
| FR-10 | Fix `LineageRepository` sync pattern | System | Replace `anyio.run()` with direct synchronous DB access. Eliminate per-call `Database()` instantiation. | Removes fragility |
| FR-11 | Enforce naming convention | System | Apply AD-6 across all `graph/` files | ID confusion prevention |
| FR-12 | Preserve backward compatibility | System | `sw graph build <target> -p <path>` produces correct results | Zero regressions |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | **Data Integrity** | `load → modify → persist` roundtrip SHALL preserve all nodes and edges with correct identity. |
| NFR-2 | **ID Isolation** | DB autoincrement integers SHALL NEVER appear outside `SqliteGraphRepository`. |
| NFR-3 | **Canonical ID** | ALL public APIs across engine, builder, repository SHALL use semantic hash strings as node identity. |
| NFR-4 | Architecture | Must pass `tach check` with zero boundary violations. |
| NFR-5 | Architecture | No interface module SHALL import domain functions from another interface module. |
| NFR-6 | Architecture | CLI remains sole Composition Root (ADR-002). |
| NFR-7 | Encapsulation | No module outside `graph/core/engine/` SHALL access `_nx_graph`, `_lock`, `_file_index`. |
| NFR-8 | Testing | Coverage for new/modified code ≥ 80%. |
| NFR-9 | Performance | No regression. `_file_index` for O(1) file-based lookups. |
| NFR-10 | Rust Readiness | `GraphEngineProtocol` SHALL be satisfiable by a PyO3 Rust engine without changing builder/repo/CLI. |
| NFR-11 | Scale Threshold | Document that Python engine is viable to ~10K files. Beyond that, Rust engine needed. |

## Architectural Decisions

| # | Decision | Rationale | Arch Switch? |
|---|----------|-----------|-------------|
| AD-1 | **Delete integer remapping** — use semantic hashes as native NetworkX keys | Root cause elimination. The "fast matrix math" optimization (RT-17) has no consumer. Integer IDs cause all three data integrity bugs. | No |
| AD-2 | **No `GraphBuildService`** — CLI remains sole Composition Root | ADR-002 compliance. Extract logic to natural owners, not a new service. | No |
| AD-3 | **Delete `AbstractGraphRepository`** | YAGNI. One implementation. `Any` types enabled AP-4. | No |
| AD-4 | `load_from_db()` returns semantic-hash-keyed `nx.DiGraph` | Canonical ID everywhere. DB integers internal only. | No |
| AD-5 | **Add `GraphEngineProtocol`** | Costs 15 lines. Makes Rust engine a mechanical drop-in. Doesn't force Rust timeline. | No |
| AD-6 | **Naming Convention** (see below) | Python lacks enforced type safety. Naming is the first line of defense. | No |
| AD-7 | `_ensure_gitignore` is NOT duplicated | Two distinct operations (different entries). No consolidation. | No |
| AD-8 | `LineageRepository`: direct sync DB access | Sync CLI. `anyio.run()` overhead and fragility for no benefit. | No |
| AD-9 | **`TopologyEngine` ≠ `InMemoryGraphEngine`** — NOT tech debt | Different abstraction levels (~50 module nodes vs 1M+ AST nodes), incompatible APIs (`add_node(str)` vs `upsert_node(GraphNode)`), separate `Protocol`s. Unification would be forced coupling. | No |
| AD-10 | Move `asyncio.Semaphore` out of engine | Engine is synchronous. Concurrency limiting is a caller concern. | No |
| AD-11 | Connection pooling deferred | SQLite connect ~100µs. At current scale (278 files), negligible. Revisit with Rust engine. | No |

### AD-6: Naming Convention for Graph Data Structures

| Concept | Variable Name | Type | Node Key |
|---------|--------------|------|----------|
| Engine wrapper object | `engine` | `InMemoryGraphEngine` | N/A |
| NetworkX graph with semantic hash keys | `semantic_digraph` | `nx.DiGraph` | `str` (semantic hash) |
| Private engine internal graph | `self._nx_graph` | `nx.DiGraph` | `str` (semantic hash) |
| Private DB-keyed graph (repo internal) | `db_digraph` | `nx.DiGraph` | `int` (DB autoincrement) |
| Topology engine | `topology_engine` | `TopologyEngine` | N/A |

**Rules:**
1. **BANNED**: `nx_graph: Any`, bare `graph`, any unqualified `DiGraph` parameter.
2. Any function accepting `nx.DiGraph` MUST name the parameter `semantic_digraph`.
3. `engine` ALWAYS means `InMemoryGraphEngine`, never a raw graph.

## Scale Planning & Rust Readiness

### Current Scale

- **278 source files**, ~739 test files
- Estimated graph: ~3K nodes — Python handles in milliseconds

### Growth Trajectory

| Files | Nodes | Python Viable? | Bottleneck |
|-------|-------|---------------|------------|
| 1K | 10K | ✅ Yes | None |
| 10K | 100K | ⚠️ Marginal | Memory (~200MB), ingestion time |
| 100K | 1M | ❌ No | Memory (~2GB), O(n) iteration, GIL |

### Rust Migration Strategy

The `GraphEngineProtocol` ensures migration is mechanical:

```python
class GraphEngineProtocol(Protocol):
    """Contract for graph engines. Python (NetworkX) or Rust (petgraph via PyO3)."""
    def upsert_node(self, node: GraphNode) -> None: ...
    def upsert_edge(self, edge: GraphEdge) -> None: ...
    def remove_node(self, semantic_hash: str) -> None: ...
    def remove_edge(self, source_hash: str, target_hash: str) -> None: ...
    def get_nodes_for_file(self, file_id: str) -> set[str]: ...
    def get_edges_involving(self, hashes: set[str]) -> set[tuple[str, str]]: ...
    def export_semantic_digraph(self) -> nx.DiGraph: ...
    def load_semantic_digraph(self, semantic_digraph: nx.DiGraph) -> None: ...
    def extract_subgraph(self, start_hash: str, depth: int) -> nx.DiGraph: ...
    def to_graphml_string(self) -> str: ...
    def clear_cache(self) -> None: ...
```

When Rust arrives: `RustGraphEngine` implements this Protocol. Zero changes to builder, repository, or CLI. The Rust engine will use compact integer IDs internally (petgraph), but that translation stays inside the Rust boundary.

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Update `knowledge_graph_querying.md` | Document new public engine API, naming convention, `GraphEngineProtocol` | ⬜ During Pre-commit |

## Sub-Feature Breakdown

### SF-01: Engine Simplification, ID Safety & Rust Seam

- **Scope**: Delete integer remapping (`_hash_to_int`, `_int_to_hash`, `_next_int_id`). Use semantic hashes as native NetworkX keys. Rename `_graph` → `_nx_graph`. Add `_file_index` for O(1) file lookup. Add `export_semantic_digraph()` / `load_semantic_digraph()` (trivial with hash keys). Add `get_nodes_for_file()` / `get_edges_involving()`. Remove `asyncio.Semaphore` from engine. Add `GraphEngineProtocol`. Refactor builder to use public API only. Delete `AbstractGraphRepository`. Fix `load_from_db` to return hash-keyed graph. Rename `flush_to_db` → `persist_semantic_digraph`. Add `busy_timeout=5000`. Make `normalize_path` public. Hoist lazy imports. Apply naming convention.
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-9, FR-11]
- **Inputs**: `graph/core/engine/core.py`, `graph/core/store/repository.py`, `graph/core/builder/orchestrator.py`, `graph/core/engine/hashing.py`
- **Outputs**: Simplified engine (~80 lines), `GraphEngineProtocol`, typed repository, builder using public API only
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-03/TECH-03_sf01_implementation_plan.md

### SF-02: CLI Logic Extraction, Cross-Interface Fix & LineageRepository Cleanup

- **Scope**: Distribute CLI logic to natural owners: (a) `GraphBuilder.ingest_target()`, (b) `SqliteGraphRepository.purge_stale_entries(known_file_ids)`, (c) `resolve_service_name()` in `assurance/graph/loader.py`. Move `check_lineage` to `graph/lineage/scanner.py`. Slim CLI to thin adapter. Fix `LineageRepository` sync-over-async. **No `helpers.py` file.**
- **FRs**: [FR-6, FR-7, FR-8, FR-10, FR-12]
- **Inputs**: SF-01 output, `graph/interfaces/cli.py`, `graph/lineage/store/lineage_repository.py`, `assurance/graph/loader.py`
- **Outputs**: Thin CLI, builder with `ingest_target()`, repo with `purge_stale_entries()`, loader with `resolve_service_name()`, moved `check_lineage`, clean lineage repository
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-03/TECH-03_sf02_implementation_plan.md

## Execution Order

1. SF-01 (no deps — start immediately)
2. SF-02 (depends on SF-01)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Engine Simplification, ID Safety & Rust Seam | — | ✅ | ✅ | ✅ | ✅ | ⬜ |
| SF-02 | CLI Logic Extraction & Cleanup | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Future Tech Debt (Identified, Not In Scope)

| ID | Issue | Why Deferred |
|----|-------|-------------|
| A-EXEC-03 (roadmap) | Rust PyO3 graph engine | `GraphEngineProtocol` makes this mechanical. Trigger: >10K files. |

## Session Handoff

**Current status**: Impl Plan for SF-01 APPROVED.
**Next step**: Run `/dev docs/roadmap/features/topic_07_technical_debt/TECH-03/TECH-03_sf01_implementation_plan.md` to begin TDD implementation.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ and resume.
