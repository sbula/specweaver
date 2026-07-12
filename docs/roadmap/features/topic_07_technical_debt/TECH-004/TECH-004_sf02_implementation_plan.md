# Implementation Plan: Architectural Refactoring of `graph/` [SF-02: CLI Logic Extraction, Cross-Interface Fix & LineageRepository Cleanup]

- **Feature ID**: TECH-004
- **Sub-Feature**: SF-02 — CLI Logic Extraction & Cleanup
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-004/TECH-004_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-004/TECH-004_sf02_implementation_plan.md
- **Status**: AUDITED (2 rounds of RT/BT complete — awaiting HITL approval)
- **Audit Artifacts**:
  - Round 1: TECH-004_sf02_rt_bt_analysis.md
  - Round 2 (DDD/KISS/DRY/Hex): C:\Users\steve\.gemini\antigravity\brain\6e7fd6be-43f1-4fd2-9b6e-15ad482b5797\TECH-004_sf02_rt_bt_analysis_round2.md

## Commit Boundaries

### CB-1: Distribute CLI Logic to Natural Owners (FR-6, FR-7, FR-8, FR-12)

Extract orchestration logic from `graph/interfaces/cli.py` into domain-owning modules. Move `check_lineage` to `graph/lineage/scanner.py`. Slim CLI to thin adapter. Delete `AbstractGraphRepository`. Fix repository `flush_to_db` / `load_from_db` signatures to use semantic digraphs properly.

---

#### Files Modified

##### [MODIFY] `src/specweaver/graph/core/builder/orchestrator.py`

**Changes:**
1. Add `collect_files(target_path: Path) -> set[str]` method:
   - Encapsulates target resolution/globbing logic inside the application layer.
   - If `target_path.is_file()`: return `{str(target_path)}`.
   - If `target_path.is_dir()`: return `{str(fp) for fp in target_path.rglob("*") if fp.is_file()}`.
   - Else: return `{str(target_path)}`.
2. Add `ingest_target(target_path: Path) -> int` method:
   - Resolve target files via `collect_files(target_path)`.
   - Iterate and call `self.ingest_file(filepath)` for each file.
   - Return total count of files ingested.
   - No console output. Pure application orchestration.
3. No changes to existing `ingest_file()` or `ingest_ast()`.

**Rationale:** Moves target-to-files resolution and batch iteration from the CLI (AP-1) to `GraphBuilder`. Keeps the CLI completely independent of globbing and discovery logic.

##### [MODIFY] `src/specweaver/graph/core/store/repository.py`

**Changes:**
1. **Delete `AbstractGraphRepository`** class entirely (AP-9, FR-5 from SF-01 — was deferred).
2. Remove `class SqliteGraphRepository(AbstractGraphRepository)` inheritance → `class SqliteGraphRepository:`.
3. **Add `purge_stale_entries(known_file_ids: set[str]) -> list[str]`**:
   - **Normalize `known_file_ids`** to match DB convention: uses static `SemanticHasher.normalize_path(fid)` to lowercase and forward-slash them (RT-R1-05: cross-platform path normalization, DRY-01).
   - **Reuse `self.get_all_file_hashes()`** to get DB file_ids (DRY — RT-R2-02). Compute stale original file_ids by checking if their normalized forms do not exist in the normalized known set.
   - For each stale file_id (using original DB casing): call `self.purge_file(file_id)`.
   - Return sorted list of purged file_ids.
   - No console output. No filesystem I/O.
4. **Rename `flush_to_db(nx_graph: Any)` → `persist_semantic_digraph(semantic_digraph: nx.DiGraph)`** (FR-4):
   - Change parameter name from `nx_graph` to `semantic_digraph` (AD-6 compliance).
   - Type hint: `semantic_digraph: nx.DiGraph` instead of `Any`.
   - Internal logic unchanged (already works with hash-keyed graph after SF-01).
5. **Rename `_extract_nodes(nx_graph)` → `_extract_nodes(semantic_digraph)`** (AD-6, FR-11 — RT-R1-06).
6. **Fix `load_from_db()` return type** → `nx.DiGraph` (FR-4: **drop `hash_to_id` tuple — unused**):
   - Rename internal `nx_graph` variable → `semantic_digraph` (AD-6).
   - **CRITICAL**: `load_from_db()` currently returns integer-keyed graph (uses `node_id` as key in `add_node(node_id, ...)`). Must change to use `semantic_hash` as key:
     - `semantic_digraph.add_node(semantic_hash, clone_hash=..., file_id=..., ...)` instead of `nx_graph.add_node(node_id, semantic_hash=..., ...)`.
     - Edges: build internal `int_to_hash` lookup during node loading. Then `semantic_digraph.add_edge(int_to_hash[source_id], int_to_hash[target_id], ...)` using the lookup.
   - **Drop `hash_to_id` from return** — per FR-4 "drop hash_to_id tuple — unused". `persist_semantic_digraph` builds its own `_get_hash_to_id_map` internally.
   - Return type: `nx.DiGraph`.
7. **Add `PRAGMA busy_timeout=5000`** in `_get_connection()` (FR-4).
8. **Hoist lazy imports** (FR-9):
   - Move `import json` to module level (currently lazy in `_extract_nodes`, `flush_to_db`, `load_from_db`).
   - Move `import networkx as nx` to module level (currently lazy in `load_from_db`).
9. Remove `from abc import ABC, abstractmethod` import (no longer needed).

##### [NEW] `src/specweaver/graph/lineage/scanner.py`

**Changes:**
1. Move `check_lineage(src_dir: Path) -> list[str]` function from `graph/interfaces/cli.py` to this new file (FR-7).
2. Copy the function verbatim. Only change: update the import of `logging`.
3. This is a pure-logic scanner — no CLI or I/O dependencies beyond `Path.rglob()` and `Path.read_text()` (both are standard file-reading, acceptable in the lineage domain scope).

##### [MODIFY] `src/specweaver/assurance/graph/loader.py`

**Changes:**
1. Add `resolve_service_name(topology: TopologyGraph | None, project_path: Path) -> str` function (FR-6c):
   - If topology is None or `topology.nodes` is empty: return `"default"`.
   - Iterate `topology.nodes.values()`. If `node.yaml_path` exists and `str(node.yaml_path.parent) == str(project_path.resolve())`: return `node.name`.
   - Fallback: return `"default"`.
2. This is pure-logic topology resolution — no CLI imports, no console output.

##### [MODIFY] `src/specweaver/graph/interfaces/cli.py`

**Changes (FR-8 — Slim to thin adapter):**
1. **Delete** `_purge_stale_nodes()` function entirely (moved to `SqliteGraphRepository.purge_stale_entries()`).
2. **Delete** `check_lineage()` function entirely (moved to `graph/lineage/scanner.py`).
3. **Rewrite `build()` command** to ≤15 lines:
    ```python
    @graph_app.command()
    def build(target: ..., project_path: ...) -> None:
        try:
            engine = InMemoryGraphEngine()
            db_path = str(project_path / ".specweaver" / "graph.db")
            
            topology = load_topology(project_path)
            service_name = resolve_service_name(topology, project_path)
            if topology is None:
                console.print("[dim]No context.yaml files found -- topology context disabled.[/dim]")
            
            repo = SqliteGraphRepository(db_path, service_name)
            builder = GraphBuilder(engine=engine, parser=extract_ast_dict, id_prefix=service_name)

            # Purge stale entries
            target_path = Path(target)
            known_file_ids = builder.collect_files(target_path)
            purged = repo.purge_stale_entries(known_file_ids)
            for f in purged:
                console.print(f"[dim]Purging deleted file from Knowledge Graph: {f}[/dim]")

            # Load existing state (returns hash-keyed nx.DiGraph per FR-4)
            semantic_digraph = repo.load_from_db()
            engine.load_semantic_digraph(semantic_digraph)

            # Ingest
            count = builder.ingest_target(target_path)

            # Persist
            repo.persist_semantic_digraph(engine.export_semantic_digraph())

            console.print(f"[green]Successfully built graph for {target} ({count} file(s))[/green]")
        except Exception as e:
            console.print(f"[red]Failed to build graph: {e}[/red]")
            sys.exit(1)
    ```
4. **No local file-collecting helper** in CLI module — globbing is fully encapsulated inside the `GraphBuilder.collect_files()` domain-logic orchestrator.
5. **Update imports**: Add `from specweaver.assurance.graph.loader import resolve_service_name`. Remove `from specweaver.interfaces.cli._core import console, get_db` → keep only `console` import via `_core`. Remove `uuid` import (only used in lineage commands).
6. **Lineage commands** (`tag`, `tree_command`, `lineage_app`) remain unchanged in this file — they are genuinely CLI adapter code for the lineage domain.
7. **Update `load_from_db()` call**: `engine._graph = graph` → `semantic_digraph = repo.load_from_db()` then `engine.load_semantic_digraph(semantic_digraph)`. Note: `load_from_db()` now returns `nx.DiGraph` directly (no tuple).
8. **Update `flush_to_db()` call**: `repo.flush_to_db(engine)` → `repo.persist_semantic_digraph(engine.export_semantic_digraph())`.

##### [MODIFY] `src/specweaver/assurance/validation/interfaces/cli.py`

**Changes:**
1. Update `check_lineage` import from `specweaver.graph.interfaces.cli` → `specweaver.graph.lineage.scanner` (line 197).
2. No other changes.

##### [MODIFY] `src/specweaver/graph/interfaces/context.yaml`

**Changes:**
1. Remove `specweaver.graph.lineage.store` from dependencies (CLI no longer directly accesses LineageRepository store for check_lineage — it was moved).
2. Add `specweaver.assurance.graph.loader` if not already present (for `resolve_service_name`).

##### [MODIFY] `tach.toml`

**Changes:**
1. Add `lineage.scanner` to the `graph` module's `expose` list:
   ```toml
   expose = [
       "core.engine.core",
       "core.engine.models",
       "core.engine.protocol",
       "lineage.engine",
       "lineage.repository",
       "lineage.scanner",
   ]
   ```
2. This allows `assurance.validation.interfaces.cli` to import `check_lineage` from the new location.

---

### CB-2: LineageRepository Sync Fix (FR-10)

Fix the `LineageRepository` sync-over-async pattern (AP-8). Replace `anyio.run()` + per-call `Database()` instantiation with direct synchronous SQLite access.

#### Files Modified

##### [MODIFY] `src/specweaver/graph/lineage/store/lineage_repository.py`

**Changes:**
1. **Delete** all `anyio.run()` wrappers, all `async def _log()` / `async def _get()` inner functions.
2. **Delete** all `from specweaver.core.config.database import Database` lazy imports.
3. **Delete** all `from specweaver.core.flow.store import FlowRepository` lazy imports.
4. **Replace with direct synchronous SQLite access** using `sqlite3`:
   ```python
   import json
   import logging
   import sqlite3
   from datetime import UTC, datetime
   from typing import Any

   logger = logging.getLogger(__name__)

   def _now_iso() -> str:
       return datetime.now(tz=UTC).isoformat()

   class LineageRepository:
       """Synchronous SQLite adapter for artifact lineage events."""

       def __init__(self, db_path: str):
           self.db_path = db_path

       def _get_connection(self) -> sqlite3.Connection:
           conn = sqlite3.connect(self.db_path)
           conn.execute("PRAGMA journal_mode=WAL;")
           conn.execute("PRAGMA foreign_keys=ON;")
           conn.execute("PRAGMA busy_timeout=5000;")
           conn.row_factory = sqlite3.Row
           return conn

       def log_artifact_event(
           self, artifact_id: str, parent_id: str | None,
           run_id: str, event_type: str, model_id: str,
       ) -> None:
           # Validation
           if not artifact_id or not artifact_id.strip():
               raise ValueError("artifact_id cannot be empty")
           if not run_id or not run_id.strip():
               raise ValueError("run_id cannot be empty")
           if not event_type or not event_type.strip():
               raise ValueError("event_type cannot be empty")
           if not model_id or not model_id.strip():
               raise ValueError("model_id cannot be empty")

           with self._get_connection() as conn:
               conn.execute(
                   """INSERT INTO artifact_events
                      (artifact_id, parent_id, run_id, event_type, model_id, timestamp)
                      VALUES (?, ?, ?, ?, ?, ?)""",
                   (artifact_id, parent_id, run_id, event_type, model_id, _now_iso()),
               )
               conn.commit()

       def get_artifact_history(self, artifact_id: str) -> list[dict[str, Any]]:
           with self._get_connection() as conn:
               cursor = conn.execute(
                   """SELECT id, artifact_id, parent_id, run_id, event_type,
                          model_id, timestamp
                   FROM artifact_events
                   WHERE artifact_id = ?
                   ORDER BY id ASC""",
                   (artifact_id,),
               )
               return [dict(row) for row in cursor.fetchall()]

       def get_children(self, parent_id: str) -> list[dict[str, Any]]:
           with self._get_connection() as conn:
               cursor = conn.execute(
                   """SELECT id, artifact_id, parent_id, run_id, event_type,
                          model_id, timestamp
                   FROM artifact_events
                   WHERE parent_id = ?
                   ORDER BY id ASC""",
                   (parent_id,),
               )
               return [dict(row) for row in cursor.fetchall()]
   ```
5. **Key design decision**: Keep the `LineageRepositoryProtocol` in `graph/lineage/repository.py` unchanged. The sync `LineageRepository` structurally satisfies it.
6. **Remove `anyio` dependency** from this module (no longer imported).

---

## Test Changes

### CB-1 Tests

#### [MODIFY] `tests/unit/graph/interfaces/test_cli_graph.py`

1. Update mock targets:
   - `mock_repo.flush_to_db` → `mock_repo.persist_semantic_digraph`
   - `mock_repo.load_from_db` → returns `MagicMock()` (was tuple, now single `nx.DiGraph`)
   - `mock_builder.ingest_file` → `mock_builder.ingest_target` (returns int count)
   - Add mock for `_collect_known_file_ids`
   - Add mock for `resolve_service_name` returning `"default"`
2. `test_graph_build_directory` can be simplified since directory iteration is now inside `builder.ingest_target()`.
3. Verify `builder.ingest_target` called with `target_path` instead of `builder.ingest_file`.
4. Verify `repo.persist_semantic_digraph` called with `engine.export_semantic_digraph()`.

#### [NEW] `tests/unit/graph/core/builder/test_ingest_target.py`

1. `test_ingest_target_single_file` — file path, returns 1, `ingest_file` called once.
2. `test_ingest_target_directory` — directory with 3 files, returns 3, `ingest_file` called 3x.
3. `test_ingest_target_nonexistent` — non-existent path, returns 1, `ingest_file` called once.
4. `test_ingest_target_empty_directory` — empty dir, returns 0, `ingest_file` not called.

#### [NEW] `tests/unit/graph/core/store/test_purge_stale.py`

1. `test_purge_stale_entries_removes_deleted_files` — insert 3 files, pass known_file_ids for 2, verify 1 purged.
2. `test_purge_stale_entries_no_stale` — all files known, returns empty list.
3. `test_purge_stale_entries_empty_db` — no files in DB, returns empty list.
4. `test_purge_stale_entries_all_stale` — no files known, all purged.

#### [MODIFY] `tests/unit/graph/interfaces/test_cli_lineage.py`

1. Update `from specweaver.graph.interfaces.cli import check_lineage` → `from specweaver.graph.lineage.scanner import check_lineage`.
2. All test logic unchanged (function signature is identical).

#### [NEW] `tests/unit/graph/core/store/test_repository_roundtrip.py`

1. `test_load_returns_semantic_hash_keyed_graph` — flush hash-keyed graph, load it back, verify node keys are semantic hashes (strings), not integers.
2. `test_roundtrip_preserves_nodes_and_edges` — flush → load → verify same node count, edge count, and attribute values.
3. `test_roundtrip_preserves_metadata` — verify `metadata` dict survives roundtrip.

#### [MODIFY] `tests/unit/graph/core/store/test_repository_load.py`

1. `test_load_happy_path`: 
   - `load_from_db()` now returns `nx.DiGraph` (not tuple). Update call: `g_out = repo.load_from_db()`.
   - Node IDs in loaded graph are now semantic hash strings, not integers. Update all assertions:
     - `assert isinstance(node_ids[0], str)` not `int`
     - Remove all `hash_to_id` usage — access nodes directly by hash string
     - `g_out.nodes["test_service:ast:123"]["metadata"]` instead of `g_out.nodes[id_123]["metadata"]`
2. `test_load_ignores_tombstoned_nodes`: Update `g_out, hash_to_id = ...` → `g_out = ...`. Check hash-based keys.
3. `test_load_ignores_ghost_nodes`: Update call site + assertions for hash-based graph.
4. `test_load_corrupted_node_metadata`: Update call site + use hash-based key lookup.
5. `test_load_corrupted_edge_metadata`: Update call site + edge key assertions for hash-based graph.

#### [MODIFY] `tests/unit/graph/core/store/test_repository_flush.py`

1. Rename `flush_to_db` calls → `persist_semantic_digraph`.
2. No logic changes — flush still accepts hash-keyed `nx.DiGraph`.

#### [MODIFY] `tests/unit/graph/core/store/test_repository_helpers.py` (RT-R1-02)

1. Rename `flush_to_db` calls → `persist_semantic_digraph` (lines 26, 46, 68, 82).
2. Update `load_from_db()` call sites — now returns `nx.DiGraph` (not tuple):
   - `g_out, _ = repo.load_from_db()` → `g_out = repo.load_from_db()`
   - `g_out_2, id_map = repo.load_from_db()` → `g_out_2 = repo.load_from_db()`
   - `g_out_3, _id_map_3 = repo.load_from_db()` → `g_out_3 = repo.load_from_db()`
3. Replace `id_map` assertions with direct node key checks:
   - `assert "test_service:ast:1_new" in id_map` → `assert "test_service:ast:1_new" in g_out_2.nodes`
   - `assert "test_service:ast:1" not in id_map` → `assert "test_service:ast:1" not in g_out_2.nodes`

#### [NEW] `tests/unit/assurance/graph/test_loader_service_name.py`

1. `test_resolve_service_name_no_topology` — None topology → "default".
2. `test_resolve_service_name_matching_node` — topology with matching node → node name.
3. `test_resolve_service_name_no_match` — topology with non-matching nodes → "default".
4. `test_resolve_service_name_empty_nodes` — topology with empty nodes dict → "default".

### CB-2 Tests

#### [MODIFY] `tests/unit/graph/lineage/store/test_lineage_repository.py`

1. Update fixture to use direct SQLite DB bootstrap that creates `artifact_events` table.
2. **Critical**: The current fixture uses `bootstrap_database(db_path)` which creates the async SQLAlchemy schema. We need to ensure the `artifact_events` table is created.
   - Option A: Keep using `bootstrap_database` (it creates tables synchronously via Alembic-like init).
   - Option B: Create the table directly with raw SQL in the fixture.
   - **Decision**: Keep `bootstrap_database` — it creates all tables including `artifact_events`. The sync LineageRepository just queries them directly.
3. All existing test assertions should pass unchanged because the function signatures and return types are identical.
4. **Add new tests:**
   - `test_busy_timeout_set` — verify connection has busy_timeout pragma.
   - `test_wal_mode_set` — verify WAL journal mode.

---

## Architecture Verification

### Mechanism vs. Constraint Matrix

| Module | Mechanism | Constraint | Violation? |
|--------|-----------|------------|------------|
| `graph/core/builder/orchestrator.py` | `pathlib.Path.rglob()`, `Path.is_file()`, `Path.is_dir()` | `context.yaml` allows `pathlib` | ✅ No |
| `graph/core/store/repository.py` | `sqlite3`, `json`, `networkx` | `context.yaml` allows `sqlite3`, `specweaver.graph.core.engine` | ✅ No |
| `graph/lineage/scanner.py` | `pathlib.Path.rglob()`, `Path.read_text()` | Lineage domain — file scanning is its purpose | ✅ No |
| `assurance/graph/loader.py` | Pure logic on `TopologyGraph` model | Already declared dependency | ✅ No |
| `graph/interfaces/cli.py` | Imports from `assurance.graph.loader` | Declared in `context.yaml` dependencies | ✅ No |
| `assurance/validation/interfaces/cli.py` | Imports `check_lineage` from `graph.lineage.scanner` | `graph` module exposes `lineage.scanner` via `tach.toml` | ✅ No (after tach.toml update) |

### Acyclic Dependencies

- `graph/core/builder` → `graph/core/engine` (downward ✅)
- `graph/core/store` → `graph/core/engine` (downward ✅)
- `graph/interfaces/cli` → `graph/core/builder`, `graph/core/engine`, `graph/core/store`, `assurance/graph/loader` (interface→domain ✅)
- `graph/lineage/scanner` → only `pathlib`, `logging` (leaf ✅)
- `assurance/validation/interfaces/cli` → `graph/lineage/scanner` (interface→domain, via tach expose ✅)
- No circular dependencies introduced.

### NFR Compliance Checklist

| NFR | Compliance |
|-----|-----------|
| NFR-1 (Data Integrity) | `load_from_db` returns hash-keyed graph → `engine.load_semantic_digraph()` → perfect roundtrip |
| NFR-2 (ID Isolation) | DB integers never leave `SqliteGraphRepository`. `load_from_db` now returns hash-keyed graph. |
| NFR-3 (Canonical ID) | All APIs use semantic hash strings |
| NFR-4 (tach check) | `tach.toml` updated with `lineage.scanner` export |
| NFR-5 (No cross-interface) | `check_lineage` moved out of CLI → validation no longer imports from graph CLI |
| NFR-6 (CLI = Composition Root) | CLI wires dependencies, delegates to builder/repo/loader |
| NFR-7 (Encapsulation) | No `_nx_graph` access outside engine. CLI uses `export_semantic_digraph()` / `load_semantic_digraph()` |
| NFR-8 (Coverage ≥ 80%) | 4 new test files + updates to 4 existing files |
| NFR-12 (Backward compat) | `sw graph build <target> -p <path>` still works, same output format |

---

## Research Notes

### Finding 1: `load_from_db()` Still Returns Integer-Keyed Graph
**Impact**: CRITICAL. Despite SF-01 converting the engine to hash-based keys, `load_from_db()` in `repository.py` (line 197-205) still uses `nx_graph.add_node(node_id, ...)` where `node_id` is the DB integer. The CLI then does `engine._graph = graph` which injects integer-keyed nodes into a hash-based engine. This is **AP-10 still alive**. SF-02 MUST fix this.

### Finding 2: `flush_to_db(engine)` Type Mismatch Persists
The CLI (line 125) calls `repo.flush_to_db(engine)` passing the engine object instead of a graph. The `flush_to_db` method has `nx_graph: Any` parameter. With SF-01's changes, `engine` no longer has `.nodes(data=True)` directly — it's on `engine._nx_graph`. This will crash at runtime. SF-02 must change to `repo.persist_semantic_digraph(engine.export_semantic_digraph())`.

### Finding 3: `AbstractGraphRepository` Still Exists
SF-01 planned to delete it but deferred. SF-02 must do it now (FR-5 + AP-9).

### Finding 4: `anyio` Dependency in LineageRepository
`anyio` is used solely for `anyio.run()` sync-over-async bridge. After replacing with direct `sqlite3`, the `anyio` import can be removed from this file. `anyio` remains in the project for other modules.

### Finding 5: Tach Boundary for Scanner
Currently `tach.toml` exposes `lineage.engine` and `lineage.repository` from the `graph` module. Adding `lineage.scanner` is required to allow `assurance.validation.interfaces.cli` to import from it without tach violations.

### Finding 6: `_purge_stale_nodes` Cross-References Entire Disk
The current `_purge_stale_nodes` iterates `target_path.rglob("*")` to build a set of on-disk files, then checks every DB file against this set AND also checks `Path(db_file).exists()`. This dual check is redundant — if a file is in `found_on_disk`, it exists. The new `purge_stale_entries` should only compare DB entries against the caller-provided set, without doing its own filesystem checks. The filesystem enumeration stays in the CLI (thin adapter responsibility).

### Finding 7: Test Infrastructure for `load_from_db` Roundtrip
The existing `test_repository_load.py` tests explicitly assert `isinstance(node_ids[0], int)` (line 46). This will break when we fix `load_from_db` to return hash-keyed graphs. All 5 tests in this file need updating.

### Finding 8: `test_repository_helpers.py` Also Uses Old API (RT-R1-02)
Four `flush_to_db` calls and three `load_from_db()` calls in `test_repository_helpers.py`. Uses `id_map` return value in assertions. All need updating for rename + return type change.

### Finding 9: Cross-Platform Path Normalization (RT-R1-05)
`_collect_known_file_ids` builds `{str(target_path)}` using raw `str(Path)` which on Windows produces backslashes. But `file_id` in the DB is normalized to forward-slash + lowercase. `purge_stale_entries` must normalize `known_file_ids` to match DB convention.

### Finding 10: FR-4 Explicitly Says Drop `hash_to_id` (RT-R1-01)
FR-4 states: *"drop `hash_to_id` tuple — unused"*. `load_from_db()` must return `nx.DiGraph` only. `persist_semantic_digraph` builds its own mapping via `_get_hash_to_id_map` internally.

---

## Verification Plan

### Automated Tests

1. `pytest tests/unit/graph/core/builder/test_ingest_target.py -v`
2. `pytest tests/unit/graph/core/store/test_purge_stale.py -v`
3. `pytest tests/unit/graph/core/store/test_repository_roundtrip.py -v`
4. `pytest tests/unit/graph/core/store/test_repository_load.py -v`
5. `pytest tests/unit/graph/core/store/test_repository_flush.py -v`
6. `pytest tests/unit/graph/core/store/test_repository_helpers.py -v`
7. `pytest tests/unit/graph/interfaces/test_cli_graph.py -v`
8. `pytest tests/unit/graph/interfaces/test_cli_lineage.py -v`
9. `pytest tests/unit/graph/lineage/store/test_lineage_repository.py -v`
10. `pytest tests/unit/assurance/graph/test_loader_service_name.py -v`
11. Full suite: `pytest`
12. Architecture check: `tach check`
13. Lint: `ruff check src/specweaver/graph/`
14. Format: `ruff format --check src/specweaver/graph/`

### Manual Verification

- Verify `sw graph build src/ -p .` still works from project root with a real project.
