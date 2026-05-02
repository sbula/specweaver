# Implementation Plan: Knowledge Graph Builder [SF-2: Persistent Storage Adapter]
- **Feature ID**: B-SENS-02
- **Sub-Feature**: SF-2 — Persistent Storage Adapter (SQLite Backup)
- **Design Document**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_sf2_implementation_plan.md
- **Status**: APPROVED

## User Review Required
*This plan incorporates the final decisions from the Phase 4/5 HITL Gate (Strict DDD, Deferred Lineage Merge, RT-17/26 mitigations, Option A Tombstoning). No further review required to begin Dev.*

## Research Notes
- **NetworkX to SQLite Performance:** The fastest pure-Python approach (without an ORM overhead) is to extract the nodes/edges from NetworkX into lists of dictionaries and perform batch `executemany` inserts within a single SQL transaction (`BEGIN...COMMIT`).
- **SQLite Pragmas:** `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` are mandatory for high-concurrency multi-agent access without lock contention (RT-4).
- **Strict DDD Boundary:** The `graph` domain is strictly isolated from `config`. It manages its own SQLite connections directly without sharing base classes.

## Edge Cases & Mitigations (Critical)
1. **The Idempotency Crash & Tombstoning (AD-13):** Calling `flush_to_db` twice on the same graph will crash with `UNIQUE constraint failed: nodes.semantic_hash`. **Mitigation:** The batch insert MUST use `INSERT INTO ... ON CONFLICT(semantic_hash) DO UPDATE SET is_active=1, clone_hash=excluded.clone_hash, metadata=excluded.metadata` to guarantee pure idempotency AND preserve LLM metadata across Git branch switches.
2. **Foreign Key Ghost Node Crashes:** SF-1 creates "LAZY" edges for unresolved imports. If `PRAGMA foreign_keys=ON` is active on `edges.target_id`, the batch insert will instantly crash because the target node doesn't exist. **Mitigation:** The `edges` table schema MUST NOT enforce a strict SQLite `FOREIGN KEY` on the `target_id` column, allowing lazy targets to be stored.
3. **JSON Serialization Poisoning (RT-25):** If the AST `metadata` dictionary contains a non-serializable object (like a raw Tree-Sitter node or `set`), `executemany` will throw an `InterfaceError`. **Mitigation:** `flush_to_db` must enforce `json.dumps(metadata, default=str)` during serialization.
4. **Namespace Prefix Spoofing (RT-26):** **Mitigation:** `GraphRepository` must silently overwrite the node's `service_name` attribute with its own `self.validated_service_name` injected during instantiation before inserting into the DB.
5. **Centrality Math Collapse (RT-17):** **Mitigation:** `load_from_db()` must construct the `nx.DiGraph` using the SQLite integer `id` as the primary NetworkX node identifier, store the string `semantic_hash` purely as a node attribute (`nx.set_node_attributes`), and return a `dict[str, int]` mapping hash-to-ID for fast lookup.

## Proposed Changes

---
### 1. The Graph Storage Adapter
Create the actual persistent backup mechanism for the NetworkX graph. Strict DDD applies: no imports from `core/config`.

#### [NEW] src/specweaver/graph/core/store/repository.py
- Define a generic `AbstractGraphRepository` interface (for future Postgres extensibility per AD-12).
- Implement `SqliteGraphRepository(AbstractGraphRepository)`.
- Handles `connect()` with WAL and Foreign Key pragmas natively.
- Defines the local schema migrations (`nodes` and `edges`).
  - `nodes` schema: `id INTEGER PRIMARY KEY AUTOINCREMENT`, `semantic_hash TEXT UNIQUE`, `clone_hash TEXT`, `file_id TEXT`, `service_name TEXT`, `package_name TEXT`, `is_active INTEGER DEFAULT 1`, `metadata JSON`.
  - `edges` schema: `source_id INTEGER`, `target_id INTEGER`, `type TEXT`, `metadata JSON`, `PRIMARY KEY (source_id, target_id, type)`.
- Implement `flush_to_db(nx_graph)`: 
  - Overwrites node `service_name` (RT-26).
  - Uses **chunked `executemany` inserts** (batch size = 5,000) to prevent `database is locked` deadlock traps.
  - Implements `ON CONFLICT DO UPDATE SET is_active=1` (AD-13).
- Implement `load_from_db()`: Rebuilds the `nx.DiGraph` using `id` as the primary key (RT-17). Returns `(nx_graph, hash_to_id_map)`.
- Implement `purge_file(file_id)`: Hard deletes or tombstones nodes belonging to a stale file (to support RT-11 orchestration later).
- Implement `get_all_file_hashes()`: Returns a list of all distinct `file_id` and their hashes (to support RT-11 orchestration later).

> [!NOTE]
> **Lineage Deferment:** The migration of `artifact_events` from the global DB, and the updating of the `sw lineage` CLI, have been explicitly deferred to **SF-3** to prevent breaking the `main` test suite at this commit boundary.

## Verification Plan

### Automated Tests
1. `[x]` **Performance Test:** Generate a synthetic NetworkX graph of 5,000 nodes and 10,000 edges. Assert `flush_to_db` completes in < 500ms using batch inserts. (Implemented as `test_flush_large_graph_chunking` — tested 6,000 nodes and edges)
2. `[x]` **Deadlock Prevention Test:** Verify that `flush_to_db` correctly chunks transactions when passing a graph > 5,000 nodes. (Implemented in `test_flush_large_graph_chunking`)
3. `[x]` **Data Parity Test:** Assert that `load_from_db(flush_to_db(graph))` returns a NetworkX graph mathematically identical to the original input. (Implemented in `test_full_graph_lifecycle` and `test_load_happy_path`)
4. `[x]` **Tombstone Recovery Test:** Assert that inserting a node, tombstoning it, and inserting it again correctly updates `is_active=1` and preserves original metadata. (Implemented in `test_flush_upserts_existing_nodes`)
5. `[x]` **Prefix Spoofing Test:** Assert that nodes passed with a malicious `service_name` are overwritten by the repository's validated service name. (Implemented in `test_flush_overwrites_service_name_preventing_spoofing`)

*(Note: We additionally implemented 3 Graceful Degradation tests during Phase 3 to cover hostile JSON corruption scenarios).*
