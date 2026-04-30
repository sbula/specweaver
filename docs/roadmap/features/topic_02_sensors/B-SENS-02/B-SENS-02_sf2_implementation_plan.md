# Implementation Plan: Knowledge Graph Builder [SF-2: Persistent Storage Adapter]
- **Feature ID**: B-SENS-02
- **Sub-Feature**: SF-2 — Persistent Storage Adapter (SQLite Backup)
- **Design Document**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_sf2_implementation_plan.md
- **Status**: APPROVED

## User Review Required
*This plan incorporates the decisions made during the Phase 4/5 HITL Gate (Option B Refactoring + Artifact Lineage Merge). No further review required to begin Dev.*

## Research Notes
- **NetworkX to SQLite Performance:** The fastest pure-Python approach (without an ORM overhead) is to extract the nodes/edges from NetworkX into lists of dictionaries and perform batch `executemany` inserts within a single SQL transaction (`BEGIN...COMMIT`).
- **SQLite Pragmas:** `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` are mandatory for high-concurrency multi-agent access without lock contention.
- **Tombstoning vs Hard Deletes:** The schema will use an `is_active` integer column for soft deletes to preserve metadata across branch switches.

## Edge Cases & Mitigations (Critical)
1. **The Stale Branch Trap (RT-11):** If the user switches git branches, the SQLite DB will contain code that no longer exists. **Mitigation:** `load_from_db()` MUST verify that the `file_path` of a node actually exists on disk. If it doesn't, or if the `A-SENS-01` file hash has changed, it must set `is_active=0` and trigger a re-parse.
2. **Foreign Key Ghost Node Crashes:** SF-1 creates "LAZY" edges for unresolved imports. If `PRAGMA foreign_keys=ON` is active on `edges.target_id`, the batch insert will instantly crash because the target node doesn't exist. **Mitigation:** The `edges` table schema MUST NOT enforce a strict SQLite `FOREIGN KEY` on the `target_id` column, allowing lazy targets to be stored.
3. **The Idempotency Crash:** Calling `flush_to_db` twice on the same graph will crash with `UNIQUE constraint failed: nodes.semantic_hash`. **Mitigation:** The batch insert MUST use `INSERT INTO ... ON CONFLICT(semantic_hash) DO UPDATE SET ...` to guarantee pure idempotency.
4. **JSON Serialization Poisoning:** If the AST `metadata` dictionary contains a non-serializable object (like a raw Tree-Sitter node or `set`), `executemany` will throw an `InterfaceError`. **Mitigation:** `flush_to_db` must enforce `json.dumps(metadata, default=str)` during serialization.

## Proposed Changes

---
### 1. The Generic Database Layer (Refactoring)
Extract the battle-tested SQLite connection and migration logic from the global config DB so it can be reused by the new local Graph DB.

#### [NEW] src/specweaver/core/db/sqlite_base.py
- Implement `SqliteBase` class.
- Handles `connect()` with WAL and Foreign Key pragmas.
- Handles `_apply_migrations(conn, version, migration_scripts)`.

#### [MODIFY] src/specweaver/core/config/database.py
- Refactor the `Database` class to inherit from `SqliteBase`.
- Remove duplicated `connect()` and `_apply_migrations()` logic.
- Ensure the 14 existing global schema migrations remain untouched.

---
### 2. The Graph Storage Adapter
Create the actual persistent backup mechanism for the NetworkX graph.

#### [NEW] src/specweaver/graph/repository.py
- Define a generic `GraphRepository` interface (for future Postgres extensibility).
- Implement `SqliteGraphRepository(SqliteBase)`.
- Defines the local schema migrations (`nodes`, `edges`, and the merged `artifact_events`).
- `nodes` schema will include explicit columns for `service_name` and `package_name` (to support SF-3 routing).
- Implement `flush_to_db(nx_graph)`: Uses **chunked `executemany` inserts** (batch size = 5,000) to prevent `database is locked` deadlock traps (Red Team Mitigation).
- Implement `load_from_db()`: Rebuilds the `nx.DiGraph` from the SQL tables on boot.

---
### 3. The Artifact Lineage Merge
Move the execution lineage graph into the new local Graph DB.

#### [NEW] scripts/migrate_v14_to_v15_lineage.py
- A standalone data migration pipeline that iterates over all registered projects, connects to their `.specweaver/graph.db`, and safely `INSERT`s their historical `artifact_events` rows from the global DB to prevent Data Loss (Red Team Mitigation).

#### [MODIFY] src/specweaver/core/config/_schema.py
- Create a `SCHEMA_V15` migration for the *global* DB that `DROP TABLE IF EXISTS artifact_events`. **This must only be executed AFTER the script above has run.**

## Verification Plan

### Automated Tests
1. **Refactoring Blast Radius Test:** Run `pytest tests/core/config/` *before* modifying `database.py` and run it after every commit boundary to mathematically prove the `SqliteBase` refactor did not break the global configuration database.
2. **Performance Test:** Generate a synthetic NetworkX graph of 5,000 nodes and 10,000 edges. Assert `flush_to_db` completes in < 500ms using batch inserts.
3. **Deadlock Prevention Test:** Verify that `flush_to_db` correctly chunks transactions when passing a graph > 5,000 nodes.
4. **Data Parity Test:** Assert that `load_from_db(flush_to_db(graph))` returns a NetworkX graph mathematically identical to the original input.
