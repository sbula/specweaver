# B-SENS-02 SF-02 — Persistent Storage Adapter (SQLite Backup)

**Status**: APPROVED · **FRs owned**: FR-2, FR-3 · **Depends on**: SF-01 · Design:
[B-SENS-02_design.md](B-SENS-02_design.md) §Sub-features → SF-02

FR-2 is dedup on `semantic_hash`; FR-3 is SQLite persistence. Ownership recorded 2026-08-17 under
`specweaver-dev` §3.2c, from `INT-US-10-MIG`: the plan predated the FR ledger, so
`check_fr_coverage.py` read all five FRs as unplanned. Proof and the mutants that verify it:
`tests/unit/graph/core/store/test_repository_roundtrip.py`.

## Goal

A persistent backup for the NetworkX graph. Strict DDD: the `graph` domain is isolated from `config`
— no imports from `core/config`, no shared base classes; it manages its own SQLite connections.

Inputs from the HITL gate: Strict DDD, Deferred Lineage Merge, RT-17/26 mitigations, Option A
Tombstoning.

## Changes

**[NEW] `src/specweaver/graph/core/store/repository.py`**

1. `AbstractGraphRepository` — generic interface (future Postgres, AD-12).
2. `SqliteGraphRepository(AbstractGraphRepository)`:
   - `connect()` sets `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` — mandatory for
     multi-agent access without lock contention (RT-4).
   - Schema migrations:
     - `nodes`: `id INTEGER PRIMARY KEY AUTOINCREMENT`, `semantic_hash TEXT UNIQUE`,
       `clone_hash TEXT`, `file_id TEXT`, `service_name TEXT`, `package_name TEXT`,
       `is_active INTEGER DEFAULT 1`, `metadata JSON`.
     - `edges`: `source_id INTEGER`, `target_id INTEGER`, `type TEXT`, `metadata JSON`,
       `PRIMARY KEY (source_id, target_id, type)`.
   - `flush_to_db(nx_graph)`: overwrites node `service_name` (RT-26); **chunked `executemany`
     inserts** (batch size = 5,000) inside a single SQL transaction (`BEGIN...COMMIT`), to avoid
     `database is locked` deadlocks; `ON CONFLICT DO UPDATE SET is_active=1` (AD-13).
   - `load_from_db()`: rebuilds the `nx.DiGraph` with `id` as the primary key (RT-17). Returns
     `(nx_graph, hash_to_id_map)`.
   - `purge_file(file_id)`: hard-deletes or tombstones a stale file's nodes (for RT-11).
   - `get_all_file_hashes()`: all distinct `file_id` and their hashes (for RT-11).

Batch `executemany` from lists of dictionaries extracted from NetworkX is the fastest pure-Python
path, without ORM overhead.

Lineage: the migration of `artifact_events` from the global DB and the `sw lineage` CLI update are
deferred to **SF-03**, so this commit boundary does not break the `main` test suite.

## Edge cases (critical)

1. **Idempotency & Tombstoning (AD-13).** A plain insert crashes a second `flush_to_db` with
   `UNIQUE constraint failed: nodes.semantic_hash`. Rule: the batch insert uses the UPSERT below —
   idempotent, and LLM metadata survives Git branch switches.
2. **Foreign-key ghost nodes.** SF-01 creates "LAZY" edges for unresolved imports; their target node
   does not exist, so `PRAGMA foreign_keys=ON` on `edges.target_id` would crash the batch insert.
   Rule: the `edges` table MUST NOT enforce a SQLite `FOREIGN KEY` on `target_id`, so lazy targets
   can be stored.
3. **JSON serialization poisoning (RT-25).** A non-serializable `metadata` value (raw Tree-Sitter
   node, `set`) makes `executemany` throw `InterfaceError`. Rule: `flush_to_db` serializes with
   `json.dumps(metadata, default=str)`.
4. **Namespace prefix spoofing (RT-26).** Rule: `GraphRepository` overwrites each node's
   `service_name` with its own `self.validated_service_name` (injected at instantiation) before
   insert.
5. **Centrality math collapse (RT-17).** Rule: `load_from_db()` uses the SQLite integer `id` as the
   NetworkX node identifier, stores `semantic_hash` as a node attribute (`nx.set_node_attributes`),
   and returns a `dict[str, int]` hash-to-ID map.

Edge case 1 UPSERT:
`INSERT INTO ... ON CONFLICT(semantic_hash) DO UPDATE SET is_active=1, clone_hash=excluded.clone_hash, metadata=excluded.metadata`

## Tests

| # | Test | Asserts | Implemented as |
|---|---|---|---|
| 1 | Performance | synthetic graph of 5,000 nodes / 10,000 edges; `flush_to_db` < 500ms with batch inserts | `test_flush_large_graph_chunking` (6,000 nodes and edges) |
| 2 | Deadlock prevention | `flush_to_db` chunks transactions for a graph > 5,000 nodes | `test_flush_large_graph_chunking` |
| 3 | Data parity | `load_from_db(flush_to_db(graph))` returns a graph identical to the input | `test_full_graph_lifecycle`, `test_load_happy_path` |
| 4 | Tombstone recovery | insert, tombstone, re-insert → `is_active=1`, original metadata kept | `test_flush_upserts_existing_nodes` |
| 5 | Prefix spoofing | a malicious `service_name` is overwritten by the validated one | `test_flush_overwrites_service_name_preventing_spoofing` |

Plus 3 Graceful Degradation tests for hostile JSON corruption.
