# Implementation Plan: Architectural Refactoring of `graph/` [SF-01: Engine Simplification, ID Safety & Rust Seam]

- **Feature ID**: TECH-03
- **Sub-Feature**: SF-01 — Engine Simplification, ID Safety & Rust Seam
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-03/TECH-03_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-03/TECH-03_sf01_implementation_plan.md
- **Status**: DRAFT

## Commit Boundaries

### CB-1: Engine Simplification + Protocol (FR-1, FR-2, FR-3)

Delete integer remapping from `InMemoryGraphEngine`. Use semantic hash strings as native NetworkX node keys. Add `_file_index`, public query methods, snapshot methods. Add `GraphEngineProtocol`. Make `normalize_path` public. Remove `asyncio.Semaphore`. Refactor `GraphBuilder` to use public API only.

#### Files Modified

##### [MODIFY] `src/specweaver/graph/core/engine/core.py`

**Changes:**
1. Delete `_hash_to_int`, `_int_to_hash`, `_next_int_id`, `_get_or_create_int_id()`
2. Delete `_extraction_semaphore` (asyncio.Semaphore)
3. Rename `_graph` → `_nx_graph`
4. Add `_file_index: dict[str, set[str]]` — maps normalized `file_id → set[semantic_hash]`
5. Rewrite `upsert_node()`: `self._nx_graph.add_node(node.semantic_hash, **node.model_dump())` + update `_file_index`
6. Rewrite `upsert_edge()`: `self._nx_graph.add_edge(edge.source_hash, edge.target_hash, kind=edge.kind.value)`
7. Rewrite `remove_node()`: remove from `_nx_graph` + remove from `_file_index`
8. Rewrite `remove_edge()`: direct `self._nx_graph.has_edge(source_hash, target_hash)`
9. Rewrite `clear_cache()`: clear `_nx_graph`, `_file_index`
10. Rewrite `extract_subgraph()`: Make sync (remove async/semaphore). `nx.ego_graph` directly on semantic keys. No int→hash translation.
11. Rewrite `to_graphml_string()`: iterate `_nx_graph` directly (keys already semantic hashes). No int→hash translation.
12. Add `export_semantic_digraph() -> nx.DiGraph`: `with self._lock: return nx.DiGraph(self._nx_graph)` (shallow copy for performance, read-only assumption)
13. Add `load_semantic_digraph(semantic_digraph: nx.DiGraph) -> None`: REPLACE semantics — clear, rebuild `_nx_graph` and `_file_index`, atomic under `_lock`
14. Add `get_nodes_for_file(file_id: str) -> set[str]`: O(1) via `_file_index`
15. Add `get_edges_involving(semantic_hashes: set[str]) -> set[tuple[str, str]]`: return `set(self._nx_graph.edges(semantic_hashes))` (leverages optimized internal NetworkX nbunch API)

##### [NEW] `src/specweaver/graph/core/engine/protocol.py`

```python
from typing import Protocol
import networkx as nx
from specweaver.graph.core.engine.models import GraphEdge, GraphNode

class GraphEngineProtocol(Protocol):
    def upsert_node(self, node: GraphNode) -> None: ...
    def upsert_edge(self, edge: GraphEdge) -> None: ...
    def remove_node(self, semantic_hash: str) -> None: ...
    def remove_edge(self, source_hash: str, target_hash: str) -> None: ...
    def get_nodes_for_file(self, file_id: str) -> set[str]: ...
    def get_edges_involving(self, semantic_hashes: set[str]) -> set[tuple[str, str]]: ...
    def export_semantic_digraph(self) -> nx.DiGraph: ...
    def load_semantic_digraph(self, semantic_digraph: nx.DiGraph) -> None: ...
    def extract_subgraph(self, start_hash: str, depth: int) -> nx.DiGraph: ...
    def to_graphml_string(self) -> str: ...
    def clear_cache(self) -> None: ...
```

##### [MODIFY] `src/specweaver/graph/core/engine/hashing.py`

Rename `_normalize_path` → `normalize_path` (remove leading underscore). Static method, no other changes.

##### [MODIFY] `src/specweaver/graph/core/builder/orchestrator.py`

1. Replace `self.engine._lock` / `self.engine._graph` / `self.engine._int_to_hash` access in `_get_existing_elements()` with:
   - `self.engine.get_nodes_for_file(file_id)` for existing hashes
   - `self.engine.get_edges_involving(existing_hashes)` for existing edges
2. Replace `self.hasher._normalize_path(filepath)` → `self.hasher.normalize_path(filepath)`
3. Update type hint: `engine: Any` → `engine: GraphEngineProtocol` (TYPE_CHECKING import)

#### Test Changes

##### [MODIFY] `tests/unit/graph/core/engine/test_core.py`

1. `test_engine_thread_safety`: Change `engine._graph.nodes` → `engine._nx_graph.nodes` (or better: use `len(engine.export_semantic_digraph().nodes)`)
2. `test_clear_cache`: Change `engine._graph.nodes` → `engine._nx_graph.nodes`, remove `engine._hash_to_int` assertion
3. `test_extract_subgraph_max_depth`: Remove `async` — method is now sync. Change `await engine.extract_subgraph(...)` → `engine.extract_subgraph(...)`

##### [NEW] `tests/unit/graph/core/engine/test_engine_public_api.py`

New test file covering:
1. `test_export_semantic_digraph_returns_copy` — mutating returned graph doesn't affect engine
2. `test_load_semantic_digraph_replaces_state` — REPLACE semantics, old data gone
3. `test_load_semantic_digraph_rebuilds_file_index` — file_index correct after load
4. `test_get_nodes_for_file_returns_correct_hashes` — O(1) lookup works
5. `test_get_edges_involving` — returns correct edge tuples
6. `test_roundtrip_export_load` — export → load → export produces identical graph
7. `test_protocol_structural_conformance` — `InMemoryGraphEngine` satisfies `GraphEngineProtocol`

##### [MODIFY] `tests/unit/graph/core/builder/test_orchestrator.py`

1. Change `engine._graph.nodes` assertions → use `engine.export_semantic_digraph().nodes` or `engine._nx_graph.nodes`

##### [MODIFY] `tests/integration/graph/test_builder_integration.py`

1. Change all `engine._graph.nodes` and `engine._graph.edges` assertions → use `engine.export_semantic_digraph()`

---

### CB-2: Repository ID Fix + Abstract Class Deletion (FR-4, FR-5, FR-9, FR-11)

Fix `load_from_db` to return semantic-hash-keyed graph. Rename `flush_to_db` → `persist_semantic_digraph`. Delete `AbstractGraphRepository`. Add `busy_timeout`. Hoist imports. Apply naming convention.

#### Files Modified

##### [MODIFY] `src/specweaver/graph/core/store/repository.py`

1. Delete `AbstractGraphRepository` class (lines 6-23)
2. Remove `ABC` import, remove inheritance from `SqliteGraphRepository`
3. Add `import json` and `import networkx as nx` at module level (hoist from method bodies)
4. Add `conn.execute("PRAGMA busy_timeout=5000;")` in `_get_connection()`
5. Rename `flush_to_db(nx_graph: Any)` → `persist_semantic_digraph(semantic_digraph: nx.DiGraph)`
6. Rename parameter `nx_graph` → `semantic_digraph` throughout
7. Fix `load_from_db()`:
   - Return type: `nx.DiGraph` (not `tuple[Any, dict[str, int]]`)
   - Use `semantic_hash` as node key: `nx_graph.add_node(semantic_hash, ...)` instead of `node_id`
   - Build edges using SQL JOIN: `SELECT n1.semantic_hash, n2.semantic_hash, e.type, e.metadata FROM edges e JOIN nodes n1 ON e.source_id = n1.id AND n1.is_active = 1 JOIN nodes n2 ON e.target_id = n2.id AND n2.is_active = 1`. **CRITICAL (RT-1)**: Filtering by `is_active=1` prevents NetworkX from silently generating empty ghost nodes upon `add_edge`.
   - **NOTE (RT-2)**: Loading directly into raw `nx.DiGraph` bypasses Pydantic `GraphNode` validation. This is an explicit performance optimization; we trust the DB schema perfectly mirrors `GraphNode.model_dump()`.
   - Drop `hash_to_id` from return
8. Remove `Any` from all type hints — use `nx.DiGraph`, `str`, `int` explicitly

##### [MODIFY] `src/specweaver/graph/interfaces/cli.py` (SF-01 portion only)

1. Change `engine._graph = graph` → `engine.load_semantic_digraph(semantic_digraph)`
2. Change `repo.flush_to_db(engine)` → `repo.persist_semantic_digraph(engine.export_semantic_digraph())`
3. Update variable names: `graph, _ = repo.load_from_db()` → `semantic_digraph = repo.load_from_db()`

#### Test Changes

##### [MODIFY] `tests/unit/graph/core/store/test_repository_load.py`

1. `test_load_happy_path`: Remove `hash_to_id` from return. Assert node keys are strings (semantic hashes). Remove `isinstance(node_ids[0], int)` assertion.
2. `test_load_ignores_tombstoned_nodes`: Remove `hash_to_id`
3. `test_load_ignores_ghost_nodes`: Remove `_hash_to_id`
4. `test_load_corrupted_node_metadata`: Assert using semantic hash key directly
5. `test_load_corrupted_edge_metadata`: Assert edges using semantic hash keys

##### [MODIFY] `tests/unit/graph/core/store/test_repository_flush.py`

1. Rename `flush_to_db` → `persist_semantic_digraph` in all test calls

##### [MODIFY] `tests/unit/graph/interfaces/test_cli_graph.py`

1. `test_graph_build_success`: Change `mock_repo.flush_to_db.assert_called_once_with(mock_engine)` to assert the new call pattern
2. Update `mock_repo.load_from_db.return_value` to return single `nx.DiGraph` (not tuple)

##### [NEW] `tests/unit/graph/core/store/test_repository_roundtrip.py`

New test file covering:
1. `test_roundtrip_preserves_nodes` — flush → load → same nodes
2. `test_roundtrip_preserves_edges` — flush → load → same edges
3. `test_roundtrip_preserves_metadata` — flush → load → same metadata
4. `test_roundtrip_hash_keyed` — loaded graph uses semantic hash keys

## Research Notes

### Phase 0 Findings

1. **`flush_to_db` already expects semantic hash keys** (line 76: `for semantic_hash, data in nx_graph.nodes(data=True)`). After dropping integer remapping, the engine's `_nx_graph` will natively have hash keys — the flush method works as-is. Only rename needed.

2. **`load_from_db` returns DB integer keys** (line 197: `nx_graph.add_node(node_id, ...)`). This is the primary change: iterate DB rows, but use `semantic_hash` as the node key instead of `node_id`.

3. **`load_from_db` edges use integer IDs** (line 225: `nx_graph.add_edge(source_id, target_id, ...)`). Need to build a reverse lookup `db_id → semantic_hash` and use semantic hashes for edges.

4. **Test `test_load_happy_path` explicitly asserts integer keys** (line 46: `assert isinstance(node_ids[0], int)`). This assertion must flip to `isinstance(node_ids[0], str)`.

5. **Integration test accesses `engine._graph` 8 times**. All must use public API.

6. **`_normalize_path` used in builder** (line 39: `self.hasher._normalize_path(filepath)`). Private access violation — rename to public.

7. **`extract_subgraph` is async with semaphore**. After making it sync, the `@pytest.mark.asyncio` and `await` in tests must be removed.

8. **`GraphNode.model_dump()` includes `semantic_hash` as a field**. When stored as a node attribute AND used as the node key, there's redundancy but no conflict. The `semantic_hash` attribute is needed for downstream consumers that read node attributes.

## Audit Findings (Red Team / Blue Team)

*A full Red Team / Blue Team audit was conducted, focusing on Hexagonal Architecture, DDD, KISS, DRY, and Separation of Concerns. The findings have been merged into the plan above.*

### Key Architectural Decisions (Merged)

1. **[CRITICAL] Ghost Node Injection (RT-1):** The SQL JOIN for edge loading must explicitly filter `WHERE n1.is_active=1 AND n2.is_active=1`. Without this, NetworkX's `add_edge` would silently instantiate empty ghost nodes in the engine's memory space, corrupting data integrity.
2. **[HIGH] Pydantic Validation Bypass (RT-2):** `load_from_db` populates the engine's raw `nx.DiGraph` directly, bypassing the `GraphNode` domain model validation. This DDD violation is an accepted performance optimization (KISS), assuming the DB perfectly mirrors the Pydantic schema.
3. **[HIGH] NetworkX Protocol Leak (RT-3):** `GraphEngineProtocol` exposes `nx.DiGraph`. This violates strict Hexagonal Architecture by leaking the internal DTO type. This is an accepted tradeoff; even the future Rust PyO3 engine will be forced to map its state to NetworkX to satisfy Python consumers.
4. **[LOW] Edge Delta Extraction (RT-4):** `get_edges_involving` leverages NetworkX's optimized `edges(nbunch)` API (O(k)) instead of O(E) manual iteration.
5. **[LOW] Export Copy Depth (RT-5):** `export_semantic_digraph` uses `nx.DiGraph(self._nx_graph)` for a shallow copy instead of deep-copying node attribute dicts. This prevents a massive performance penalty during CLI export, under the strict assumption that callers treat the exported graph as read-only.
