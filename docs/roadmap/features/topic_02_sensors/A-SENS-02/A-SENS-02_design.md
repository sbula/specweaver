# Design: Postgres pgvector Sidecar

- **Feature ID**: A-SENS-02
- **Phase**: 3
- **Status**: APPROVED (the user, 2026-11-12, with six changes applied)
- **Design Doc**: docs/roadmap/features/topic_02_sensors/A-SENS-02/A-SENS-02_design.md

## Feature Overview

The code graph moves from a per-project SQLite file to PostgreSQL node and edge tables, with
pgvector beside them, in one local Postgres container. SpecWeaver is built for experienced
developers on large, multi-service projects (the user, Quantivista) `[agreed 2026-11-09]`, and the
graph store is Postgres only: there is no SQLite mode and no "same answers in both modes" check
`[agreed 2026-11-09]` (Q2 B). Each service gets its own Postgres schema and its own login role, so
an agent working on service A cannot read service B's graph, and Postgres itself enforces it
`[agreed 2026-11-12]` (Q30 A). Traversals have no fixed depth: a frontier BFS (breadth-first
search, each node visited once at its shortest distance) runs one query per level from Python and
stops on a time limit `[agreed 2026-11-11]` (Q6 A, Q24 A). The vector half stores and searches
embeddings only; `B-FLOW-04` chooses the model and fills it `[agreed 2026-11-09]` (Q4 A).

**What this feature does not move:** the three other SQLite files (`specweaver.db`,
`pipeline_state.db`, `reservations.db`) move in their own feature after `B-FLOW-04`
`[agreed 2026-11-10]` (Q1 B).

**Evidence:** `docs/analysis/a_sens_02_graph_store_spike_2026-11-11.md` (Kafka Java, 1.14M code
lines, 96,589 nodes, 561,570 edges; bounded, unbounded, BFS-loop and HNSW-lock measurements) and
`ADR-006`'s amendment of 2026-11-11 (tables, not Apache AGE).

## Path List (`ADR-005`)

| # | Path | Span | Owner | Status |
|---|---|---|---|---|
| P-1 | `sw db up` → container by digest, roles, password file → `sw db status` says ready | CLI, sidecar, database | A-SENS-02 (FR-5..FR-8) | ⬜ |
| P-2 | `sw graph build` → parser → the service's schema on Postgres → reload gives the same graph | builder, store | A-SENS-02 (FR-16..FR-19, FR-28) | ⬜ |
| P-3 | a new service is built for the first time → schema, role, grants, migrations for that schema only | store, database | A-SENS-02 (FR-11) | ⬜ |
| P-4 | service A's role queries service B (qualified name, our filter bypassed) → Postgres says permission denied | database | A-SENS-02 (FR-13) | ⬜ |
| P-5 | a traversal with no depth on a 10,000-node chain → complete, or stopped by the time limit with depth N | store | A-SENS-02 (FR-20..FR-22) | ⬜ |
| P-6 | a second process on another worktree reads service A's graph without rebuilding it (`US-19` P-2) | store, builder | A-SENS-02 (FR-19) | ⬜ |
| P-7 | `US-11` P-3, storage half: the store, the BFS tree and the vector search return correct results | store | A-SENS-02 (FR-27) | ⬜ |
| P-7b | `US-11` P-3, retrieval half: a query returns the right context | retrieval | `B-FLOW-04`, which writes the test when it defines its interface; no `xfail` here against an undefined interface (`ADR-004` clause 4) `[agreed 2026-11-12]` | not built here |
| P-8 | the three other SQLite files on Postgres (`TECH-090` P-6) | opener | the later SQLite-move feature `[agreed 2026-11-10]` (Q1 B) | not built here |

## Research Findings

### Codebase Patterns

- **Graph store today:** `SqliteGraphRepository(db_path: str, validated_service_name: str)`
  (`graph/core/store/repository.py:72`), raw sqlite3 through `open_sqlite`, one upgrade step. Public:
  `persist_semantic_digraph(nx.DiGraph)` (:151), `load_from_db() -> nx.DiGraph` (:196),
  `purge_file(file_id)` (:278), `purge_stale_entries(known_file_ids) -> list[str]` (:290),
  `get_all_file_hashes() -> dict[str, str]` (:323). Tables `graph_nodes` (with `service_name`
  column, `semantic_hash` UNIQUE across services) and `graph_edges` (no FK on `target_id`).
- **One caller:** `GraphOrchestrator.build_target(target_path, project_path, *, service_name)`
  (`graph/core/builder/orchestrator.py:253`), path `project/.specweaver/graph.db` (:257). It loads
  the whole graph into networkx, ingests, and persists it all back.
- **No store port exists.** The engine has `GraphEngineProtocol` (`graph/core/engine/protocol.py:18`);
  `LineageRepositoryProtocol` (`graph/lineage/protocol.py:15`) is the precedent for a repository port.
- **`MAX_NEIGHBOURHOOD_DEPTH = 5`** (`graph/core/engine/models.py:83`), applied in
  `core.py:89` (`extract_subgraph`, no production caller) and `topology/engine.py:100`
  (`neighbors_within`, called by three selectors in `selectors.py:73,98,136` with depth 1–2).
  Proven by `tests/unit/graph/test_one_depth_limit.py` (`TECH-088` FR-9).
- **Models:** `GraphEdge(source_hash, target_hash, kind, metadata)` (`models.py:96`); no origin,
  precision or status field. `GraphNode.embedding_id` exists, unused.
- **Chunks:** `chunk_source(...) -> list[Chunk]` (`workspace/analyzers/chunking.py:466`) has no caller;
  nothing persists chunks or vectors today.
- **Alembic is banned by a test:** `tests/unit/test_no_alembic.py` (`TECH-090` FR-10). `TECH-090`
  AD-2 already says "`A-SENS-02` adds it back from a proven starting state" `[agreed 2026-11-07]`.
- **Containers:** `ContainerSubprocessExecutor` (`sandbox/execution/container_executor.py:66`),
  engines `("podman", "docker")` (`sandbox_image.py:54`). The CLI forbids `specweaver/sandbox/*`
  (`interfaces/cli/context.yaml`); `core/flow` consumes the sandbox and the CLI consumes `core/flow`.
- **Agent reads:** `FileExecutor._validate_path` (`sandbox/filesystem/core/executor.py:419-427`)
  rejects absolute paths and anything outside the workspace. Nothing names `keys.env`; it is out of
  reach only by containment.
- **Service name:** `resolve_service_name(topology, project_path)` (`graph/topology/loader.py:64`)
  takes the name in the project root's `context.yaml`, else `"default"`. Two projects without one
  would share the schema `default`; two worktrees of one project share their service's schema
  (FR-28). `context.yaml` has no `library` or `service` level today (levels: system, module,
  sub-module, foundation).
- **Tests:** `SPECWEAVER_DATA_DIR` is a temp dir (`tests/conftest.py:60`); `_no_real_network`
  allows loopback only. 19 test files touch the SQLite graph store. CI: one job `gate`, Python 3.11
  and 3.14, guarded by `tests/unit/test_ci_workflow_keeps_its_promises.py`; "on CI a skip fails the
  run".

### External Tools

| Tool | Version | Key API Surface | Source |
|---|---|---|---|
| psycopg | 3.3.8, LGPL-3.0, Python ≥3.10 | `conn.execute`, `= ANY(%s)` with a list, `cursor.copy()`, `psycopg.sql.Identifier` | pypi.org/pypi/psycopg/json |
| psycopg_pool | 3.3.3, LGPL-3.0 | `ConnectionPool(configure=, reset=, check=, open=)`; the pool does not reset session state on return | psycopg.org/psycopg3/docs/advanced/pool.html |
| Alembic | 1.20.1, MIT; needs SQLAlchemy ≥2.0 (already a dependency) | `context.configure(version_table_schema=, transactional_ddl=)`; programmatic `command.upgrade` | alembic.sqlalchemy.org/en/latest/api/runtime.html |
| pgvector image | `pgvector/pgvector:0.8.7-pg18`, index digest `sha256:c29f30688a9ad961691bdf0ec1650717cc132a5814619d80f80463d6e4c42e47` | HNSW `vector_cosine_ops`; `vector` ≤ 2,000 dims for HNSW, `halfvec` ≤ 4,000 | hub.docker.com tag JSON, 2026-11-12 |
| PostgreSQL | 18 | schema `USAGE`, `REVOKE … FROM PUBLIC`, owner-rights views, `ALTER ROLE … SET statement_timeout` | postgresql.org/docs/18 |

Gotchas carried into the design:
- `ALTER ROLE … SET statement_timeout` is a session **default**: it applies at login, and a session
  can override it with `SET`. It is a guard behind our own limit, not a hard cap. Our tools never
  send `SET` (FR-14).
- The pool keeps `search_path` and any `SET` across checkouts: each pool gets a `reset` callback.
- Alembic documents one transaction per run, but not a loop over schemas in one transaction. FR-10
  proves it with a test; it is not assumed.
- The system catalogs show every schema, table and column name to every role. Roles isolate rows,
  not names (FR-13).

### Blueprint References

- LocAgent (arXiv 2503.09089): graph tools over contain / import / invoke / inherit edges
  (`docs/analysis/b_flow_04_design_input_2026-11-11.md` §1).
- Alembic cookbook, "Rudimental Schema-Level Multi Tenancy for PostgreSQL Databases".

## Functional Requirements

Decisions marked `[agreed …]` were taken by the user in the grilling (Q1–Q36).

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | `extract_subgraph` and `neighbors_within` SHALL take `depth: int \| None`; `None` reaches everything; no fixed depth remains anywhere, and `MAX_NEIGHBOURHOOD_DEPTH` is deleted `[agreed 2026-11-11]` (Q23 A) | in-memory engines | traverse | a 10,000-node chain is reached in full; a hidden cap at 10 or 100 fails the test |
| FR-2 | Both in-memory engines SHALL pass the traversal tests: chains of 7 and 10,000; fan-out 1,000 over 4 levels; self-recursion, mutual recursion, a cycle of 10,000, a cycle with fan-out 1,000; each node once, at its shortest depth `[agreed 2026-11-11]` | in-memory engines | traverse | every case finishes with correct depths |
| FR-3 | `TECH-088` FR-9's test (`test_one_depth_limit.py`) SHALL be replaced by FR-1's test, recorded as a decision on delivered code `[agreed 2026-11-11]` | test suite | prove | no test asserts a limit of 5 |
| FR-4 | The three selectors SHALL pass their depth explicitly and keep their results | `graph/topology` | select | depth 1 and 2 give the same modules as today |
| FR-5 | `sw db up` SHALL start one Postgres container from `pgvector/pgvector:0.8.7-pg18` pinned by digest `[agreed 2026-11-11]` (Q3), port bound to `127.0.0.1` only, data in a named volume, with `maintenance_work_mem` 2 GB and `autovacuum_work_mem` 256 MB, both configurable `[agreed 2026-11-12]` (Q36 A) | user | start | the container runs; `sw db up` again is a no-op |
| FR-6 | `sw db up` SHALL generate the superuser and every role password, store them only in `~/.specweaver/db_roles.env` with mode 0600, and never print or log one `[agreed 2026-11-12]` (Q31 A) | sidecar | create credentials | the file exists with 0600; no password appears in output, logs or exceptions |
| FR-7 | `sw db status` SHALL report running / stopped / missing, the image digest, and each service schema's migration version; `sw db down` SHALL stop the container and keep the volume | user | inspect, stop | status names every schema not at head |
| FR-8 | The agent's file tools SHALL refuse `db_roles.env` and `keys.env` by name, in addition to workspace containment `[agreed 2026-11-12]` (Q31 A) | `sandbox/filesystem` | refuse | a read of either, by any path form, fails with a reason |
| FR-9 | The graph schema SHALL be managed by Alembic from its first version `[agreed 2026-11-12]` (Q7 A); `test_no_alembic.py` is narrowed to "no Alembic on the SQLite files", per `TECH-090` AD-2 `[agreed 2026-11-07]` | migrations | version | Alembic is imported only by the Postgres migration module |
| FR-10 | One migration tree SHALL be applied to every service schema in ONE transaction, each schema with its own version table; a failure in any schema changes nothing anywhere `[agreed 2026-11-12]` (Q32 A) | migrations | upgrade | after a forced failure in schema 3 of 3, all three are at the old version |
| FR-11 | A new service SHALL get, in one transaction: its schema, its tables via the migrations, its read role with `CONNECT` and `USAGE` on its own schema and the contracts schema `[agreed 2026-11-12]`. Its password is written to the file first (temp file + rename); a password for a role that does not exist is ignored, and a role whose password is missing gets a new one. The service name becomes the schema name only if it matches `^[a-z][a-z0-9_]{0,40}$`, and every identifier is composed with `psycopg.sql.Identifier` | store | add a service | the new role reads its own graph at once; a hostile name (`a; DROP`, 64 characters, `pg_x`) is refused |
| FR-12 | The contracts schema SHALL have its own migration tree and version table, separate from the service tree `[agreed 2026-11-12]` | migrations | version | upgrading services does not touch contracts, and the reverse |
| FR-13 | The database SHALL revoke the `PUBLIC` defaults (`CONNECT`, `TEMP` on the database, `USAGE` on `public`). Service A's role SHALL get `permission denied` from Postgres for any object in service B's schema, by qualified name, with our query filter bypassed; through our store, a node ID of service B is refused before any query, because the scope comes from the task's grant, never from a parameter; both are tested `[agreed 2026-11-12]` (Q30 A). The design states that roles hide rows, not names: the catalogs list schema names, which are service names and already public in the service graph `[agreed 2026-11-12]` | Postgres, store | isolate | the hostile test fails at Postgres and at our filter |
| FR-14 | Agent roles SHALL be read only (`SELECT`) `[agreed 2026-11-12]` (Q34 A), each with `statement_timeout` = 2 × the tool time limit X, set again whenever X changes `[agreed 2026-11-12]` (Q35 A): `sw db up` applies it, and `sw db status` names a role whose value differs from 2 × X. `statement_timeout` limits one statement, i.e. one BFS level; the tool limit stays the limit for the whole traversal `[agreed 2026-11-12]` | sidecar | guard | an `INSERT` as an agent role is denied; one level slower than 2 × X is cancelled by Postgres |
| FR-15 | A shared library SHALL get its own schema and role, plus an API schema of owner-rights views over its public symbols, granted only to the services named as its consumers; never `security_invoker` `[agreed 2026-11-12]` (Q33 A). This feature builds and tests the mechanism; `B-FLOW-04` decides, from `context.yaml`, which unit is a library, which symbols are public and who consumes it `[agreed 2026-11-12]` (Q37 A) | store | share | service A reads the library's API view and is denied on its base tables |
| FR-16 | A `GraphStoreProtocol` port SHALL carry today's five repository methods; `PostgresGraphRepository` implements it, and `build_target` uses the port | store, builder | persist, load | `sw graph build` writes to the service's schema |
| FR-17 | Every edge SHALL carry `origin`, `precision` (exact / type-aware / name-only) and `status` (valid / stale), plus `to_ghost` `[agreed 2026-11-11]` (Q12 input, Q3 fix in the spike) | store | persist | the columns survive a persist and a reload |
| FR-18 | `SqliteGraphRepository` and `graph.db` SHALL be removed; the 19 test files that use them move to the Postgres fixture | store | remove | no source or test names `graph.db` |
| FR-19 | A persist SHALL be one transaction: a reader in another connection sees the whole old graph or the whole new graph, never a mix; a second process reads a service's graph without rebuilding it (`US-19` P-2) | store | read while writing | the read-while-write test and the second-process test pass |
| FR-20 | The store SHALL offer `reach(seeds, direction, edge_kinds, max_depth, precision)` and `path(source, target, edge_kinds, max_depth)`, a frontier BFS with one query per level and the visited set in Python `[agreed 2026-11-11]` (Q24 A); paths are never enumerated `[agreed 2026-11-11]` | store | traverse | each reached node once, at its shortest depth |
| FR-21 | With no `max_depth`, a traversal SHALL run until done or until the time limit X (2,000 ms, configurable `[agreed 2026-11-11]`, Q21 A), then report `stopped: time_limit, after_ms, depth` | store | stop | never a silent truncation |
| FR-22 | A traversal result SHALL hold a BFS tree (per node: predecessor, edge kind, precision) and a summary over the whole traversal: counts per depth, per module, per edge kind, per precision `[agreed 2026-11-11]` | store | report | the summary counts every reached node |
| FR-23 | The DB traversal SHALL pass the same depth, width and cycle tests as FR-2, plus a synthetic graph with the shape of Kafka L's densest hub (2,787 callers, depth 7) within the time limit; the real Kafka L hub is measured once in dev and recorded (the Kafka clone is not in the repo) | store | traverse | identical node sets and depths to the in-memory engine on the same graph |
| FR-24 | A vector index SHALL record its model ID and dimension; vectors of another model or dimension are refused; a model change creates a new index and never mixes vectors `[agreed 2026-11-09]` (Q4 A) | store | store vectors | a wrong-dimension write fails with a reason |
| FR-25 | The store SHALL return the k nearest chunks for a query vector inside one service schema, optionally joined to graph nodes in the same statement | store | search | results come only from the caller's schema |
| FR-26 | A migration SHALL NOT contain a statement that cannot run in a transaction (`CREATE INDEX CONCURRENTLY`, `VACUUM`, `CREATE DATABASE`, …); a test fails if one does `[agreed 2026-11-12]` (Q32 A) | migrations | guard | a planted `CONCURRENTLY` fails the test |
| FR-27 | `US-11` P-3's storage half: on one service's graph with its vectors, `reach`, the BFS tree and the kNN search SHALL return the expected nodes, predecessors and chunks. The retrieval half is `B-FLOW-04`'s test, written when it defines its interface `[agreed 2026-11-12]` | store | prove | expected results on a fixed graph; no `xfail` |
| FR-28 | `sw graph build` SHALL refuse, with the reason, a project whose root `context.yaml` gives no name, and any linked git worktree: only the main checkout writes a service's base graph. A linked worktree is detected with git, where `git rev-parse --git-dir` differs from `--git-common-dir`, never by "`.git` is a file", because a submodule's `.git` is a file too `[agreed 2026-11-12]`; git runs through the sandbox's git executor on the CLI path, so `graph` never imports `sandbox`. Tested both ways: a linked worktree is refused, a submodule is accepted. Other worktrees read that base. Limit, stated: a worktree's own changes are not in the graph until the exact-call-edges feature adds per-worktree deltas `[agreed 2026-11-12]` (Q38 A) | builder | refuse | a build from a linked worktree, or with the name `default`, writes nothing and exits 1 |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | the depth cap | `TECH-088` · `MAX_NEIGHBOURHOOD_DEPTH`, `extract_subgraph(start_hash, depth)`, `neighbors_within(module, depth=1)` | read `models.py:83`, `core.py:89`, `topology/engine.py:93-100` |
| FR-4 | selector depths | `graph/topology` · `selectors.py:73,98,136` | read (via research agent, file:line cited) |
| FR-5 | container start | `sandbox/execution` · `ContainerSubprocessExecutor`, `_ENGINES` | read `container_executor.py:66`, `sandbox_image.py:54` |
| FR-6 | data dir | `core/config` · `specweaver_root()` | read `core/config/paths.py:28` |
| FR-8 | read refusal | `E-SENS-03` · `FileExecutor._validate_path` | read `sandbox/filesystem/core/executor.py:419-427` |
| FR-9 | the ban | `TECH-090` FR-10 · `tests/unit/test_no_alembic.py`, AD-2 | read both |
| FR-16 | builder writes | `B-SENS-02` · `GraphOrchestrator.build_target`, `SqliteGraphRepository` methods | read `orchestrator.py:253-276`, `repository.py:72-323` |
| FR-17 | edge fields | `B-SENS-02` · `GraphEdge` | read `models.py:96` |
| FR-25 | chunks | `B-SENS-03` · `Chunk`, `content_hash(chunk)` | read `chunking.py:39,97` |
| FR-27 | store results | this feature · `reach`, kNN (SF-06) | defined in this design |

**Behaviour checked by running, not reading:** the spike ran every traversal form, the BFS loop
locations and the HNSW lock (`.tmp/spike/*.py`, results in the spike analysis). The one-transaction
loop over schemas (FR-10) is not yet run; it is the first red test of SF-03.

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Traversal speed on Kafka L | the densest hub's unbounded callers closure finishes under X (2,000 ms); spike: 17 ms cold, 5.6 ms warm (Python loop) |
| NFR-2 | Round-trip with the real driver over TCP | measured in SF-05 and recorded; the spike used psql over a pipe, 0.035 ms per level `[agreed 2026-11-11]` (Q24 A) **[proof: meta — a measurement recorded in the design]** |
| NFR-3 | Suite time | measured before (146 s, 13,029 passed, 2026-11-08) and after; both numbers recorded `[agreed 2026-11-09]` **[proof: meta — a measurement recorded in the design]** |
| NFR-4 | Test isolation | one database per xdist worker; each test in a transaction rolled back; only the tests in §Tests that commit commit `[agreed 2026-11-12]` (Q28 A) |
| NFR-5 | No network beyond loopback | Postgres binds `127.0.0.1`; the test `_no_real_network` guard stays |
| NFR-6 | Secrets | no password in stdout, logs, exceptions, `sw db status` or the repo; file 0600 |
| NFR-7 | CI | `tests.yml` runs a pgvector service container by digest on 3.11 and 3.14 `[agreed 2026-11-12]` (Q27 A); a skipped database test fails the run |
| NFR-8 | Licence | psycopg and psycopg_pool are LGPL-3.0, used as normal dependencies, not vendored `[agreed 2026-11-12]` (Q26 A) **[proof: meta — a rule about the dependencies]** |
| NFR-9 | Build lock | an index build blocks writes, not reads; measured 21.5 s at 2 GB for 96,589 × 384 (spike Extension 3); measured again in `B-FLOW-04` with the real dimension `[agreed 2026-11-12]` |

### Tests that commit (Q28)

All other tests roll back. These commit, because a second connection must see the work:
1. the permission tests (FR-13, FR-14, FR-15): they log in as a committed role;
2. the new-service test (FR-11);
3. the read-while-write and second-process tests (FR-19);
4. the migration tests (FR-10, FR-12) that log in as a role afterwards.

Roles are server-wide, so each worker prefixes its role names with its worker ID and drops them at
the end of the session.

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| `psycopg[binary]` | 3.3 | connection, COPY, `sql.Identifier` | yes, PyPI classifiers 3.10–3.15 | install is a network fetch: needs the user's consent at dev time |
| `psycopg_pool` | 3.3 | `ConnectionPool(reset=…)` | yes | same |
| `alembic` | 1.20 | `command.upgrade`, `version_table_schema` | yes; SQLAlchemy ≥2.0 already present | same |
| `pgvector/pgvector` image | 0.8.7-pg18 by digest | HNSW, `vector(n)` | tag and digest read 2026-11-12 | pulling it is a network fetch: needs the user's consent |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Plain node/edge tables and pgvector; no Apache AGE `[agreed 2026-11-11]` (Q6 A) | `ADR-006` amendment: AGE 79 s vs 6–14 ms over 2 edge kinds; subtype closure did not finish | Yes — approved by the user on 2026-11-11 (`ADR-006` amendment) |
| AD-2 | One schema and one login role per service, a pool per role `[agreed 2026-11-12]` (Q30 A, Q31 A). Two writer roles `[agreed 2026-11-12]`: the migration role (`sw_migrate`) owns every schema and is the only role with DDL; the indexer role (`sw_index`) has DML (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) on the service schemas and no DDL. Agents get the per-service read roles (FR-14). The superuser is used only by `sw db up` to create roles. Each pool's `reset` callback runs `RESET ALL` | a missed filter or a stale pooled role cannot cross services; the indexer cannot change a schema; neither writer is ever given to an agent | No |
| AD-3 | The Postgres driver and Alembic runner live in `infrastructure/database` (adapter, depends on nothing); the graph tables, their migrations and `PostgresGraphRepository` live in `graph/core/store` | keeps SQL inside the store (`B-SENS-02` AD-12) | No |
| AD-4 | `sw db up/status/down` is a CLI router that calls a sidecar function in `core/flow`, which uses `sandbox/execution`; the CLI never imports the sandbox | `interfaces/cli` forbids `sandbox/*`; `core/flow` consumes it | No |
| AD-5 | The BFS loop runs in Python, one query per level, visited set in Python `[agreed 2026-11-11]` (Q24 A) | spike Extension 2: fastest or near-fastest in every case | No |
| AD-6 | Rendering for agents (budget from the context window, short handles, grouped-by-file paths) belongs to `B-FLOW-04`'s tools; this store returns the BFS tree and the summary. Q22 C and Q29 A are recorded for `B-FLOW-04` in its input document §10–§11 `[agreed 2026-11-11]` | the store has no caller model to size a budget for | No |
| AD-7 | Existing `graph.db` files are not copied: the next `sw graph build` rebuilds the graph in Postgres; an old `graph.db` is left in place and named once in the output | the graph is derived data, rebuilt from source in seconds to minutes | No |
| AD-8 | Today's parser edges get `origin = parser`, `status = valid`, and a precision per kind from how the mapper resolves it `[agreed 2026-11-12]` (table below). The exact-call-edges feature fills `scip@<commit>` and `type-aware` | precision says how the target was found, so it follows the resolution, not the kind | No |
| AD-9 | The test fixture reuses a running test container and never starts one `[agreed 2026-11-12]`: on CI the service container (`SPECWEAVER_TEST_PG_URL`); locally `specweaver-test-pg`, started once by `python scripts/test_db.py up`, separate from the user's sidecar and its volume. With no server, every database test fails with that command, never a skip. Suite time before (146 s) and after is reported (NFR-3) | the commit gate runs locally, so a database test must never skip there; a container per run would cost its start on every run | No |

### Edge precision today (AD-8)

Read in `graph/core/builder/mapper.py` (2026-11-12). Precision says how the target was found.

| Kind | How the mapper resolves the target | Precision |
|---|---|---|
| `CONTAINS` | file → each declared node, from the AST nesting (`_map_child`, :326) | exact |
| `IMPORTS`, resolved | the module name through the module index to one file (`_map_imports`, `modules.resolve`, :178-183) | exact |
| `IMPORTS`, unresolved | a ghost module node (:184) | name-only |
| `EXTENDS`, `IMPLEMENTS`, resolved | the bare type name, when exactly one project type has it (`_supertype_target`, :229-235) | name-only: a library type of the same name would match the project's type; Kotlin also marks every supertype `extends` |
| `EXTENDS`, `IMPLEMENTS`, unresolved or ambiguous | a ghost type node | name-only |
| `CALLS` | the bare callee name, when exactly one procedure has it, else a ghost (`_callee_target`, :265-271) | name-only: the census found wrong unique matches (`logger.warning` → a project `warning`, 173) |

Nothing is `type-aware` today. `CONSUMES`, `FULFILLS`, `PUBLISHES`, `SUBSCRIBES` are declared in the
ontology and never emitted.

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| Remove the depth cap (SF-01) | small | low |
| Sidecar, roles, password file, fixture, CI (SF-02) | medium | medium: container start on CI and locally |
| Alembic over many schemas, one transaction (SF-03) | medium | medium: not a documented Alembic recipe |
| Store port and Postgres repository, 19 test files moved (SF-04) | medium | medium |
| DB traversal (SF-05) | small–medium | low: spiked |
| Vectors (SF-06) | small | low |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| `B-FLOW-04` | graph tools and hybrid search on one store | high |
| `A-SENS-04` | a contracts schema and per-service isolation to build the service graph on | high |
| Exact-call-edges feature | edge columns for origin, precision, status | medium |
| Agents on multi-service projects | Postgres-enforced service boundaries | high |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Alembic cannot loop schemas in one transaction | low | medium | FR-10's test is the first red of SF-03; fall back to raw SQL steps under Alembic's version tables |
| The test container slows the suite | medium | medium | one container per session, one database per worker, rollback per test; NFR-3 measures it |
| A password leaks into a log | low | high | NFR-6 test greps every captured output |
| The local machine has no Podman | low | medium | `sw db up` and the fixture fail with a clear reason, never a skip |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `B-SENS-02` builder | loads and rewrites the whole graph each build | a later delta write per file (exact-call-edges feature) | not here |
| The three SQLite files | single-user local stores | one backend (the later SQLite-move feature) | not here |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Working with the Postgres store | `sw db up`, the fixture, adding a migration, the one-transaction rule, adding a service, roles | ⬜ To be written during Pre-commit |
| `working_in_this_repo.md` §12 | add "the graph is on Postgres: migrations, not steps" | ⬜ |

## Sub-Feature Breakdown

### SF-01: No fixed traversal depth
- **Scope**: delete `MAX_NEIGHBOURHOOD_DEPTH`; the in-memory engines take `depth: int | None`.
- **FRs**: [FR-1, FR-2, FR-3, FR-4]
- **Inputs**: today's engines and selectors.
- **Outputs**: unbounded in-memory traversal and the shared traversal test cases, reused by SF-05.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/A-SENS-02/A-SENS-02_sf01_implementation_plan.md

### SF-02: The sidecar and the test database
- **Scope**: `sw db up/status/down`, the password file, the agent-read refusal, the test fixture and the CI service.
- **FRs**: [FR-5, FR-6, FR-7, FR-8]
- **Inputs**: the pinned image; `specweaver_root()`.
- **Outputs**: a running Postgres, credentials, a per-worker test database.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/A-SENS-02/A-SENS-02_sf02_implementation_plan.md

### SF-03: Schemas, roles and migrations
- **Scope**: Alembic over every service schema in one transaction, the contracts tree, roles and grants, libraries, the new-service flow.
- **FRs**: [FR-9, FR-10, FR-11, FR-12, FR-26]
- **Inputs**: SF-02's server and fixture.
- **Outputs**: versioned schemas and per-service roles.
- **Depends on**: SF-02
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/A-SENS-02/A-SENS-02_sf03_implementation_plan.md

### SF-04: Isolation
- **Scope**: the permission guarantees: hostile query at Postgres and at our filter, read-only agent roles with the statement timeout, library API views.
- **FRs**: [FR-13, FR-14, FR-15]
- **Inputs**: SF-03's schemas and roles.
- **Outputs**: proven service boundaries.
- **Depends on**: SF-03
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/A-SENS-02/A-SENS-02_sf04_implementation_plan.md

### SF-05: The graph on Postgres
- **Scope**: the store port, `PostgresGraphRepository`, edge columns, builder switch, SQLite graph store removed.
- **FRs**: [FR-16, FR-17, FR-18, FR-19, FR-28]
- **Inputs**: SF-03's schemas.
- **Outputs**: `sw graph build` on Postgres.
- **Depends on**: SF-03
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/A-SENS-02/A-SENS-02_sf05_implementation_plan.md

### SF-06: Traversal and vectors on Postgres
- **Scope**: `reach` / `path` with the time limit, BFS tree and summary; vector indexes and kNN; the storage half of `US-11` P-3.
- **FRs**: [FR-20, FR-21, FR-22, FR-23, FR-24, FR-25, FR-27]
- **Inputs**: SF-01's test cases, SF-04's roles, SF-05's tables.
- **Outputs**: the store surface `B-FLOW-04` builds its tools on.
- **Depends on**: SF-01, SF-04, SF-05
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/A-SENS-02/A-SENS-02_sf06_implementation_plan.md

SF-06 holds 7 FRs, above the heuristic of 5, but all of them sit in one module (`graph/core/store`)
on one surface; splitting traversal from vectors would split the hybrid query (FR-25) from the
traversal it joins.

## Execution Order

1. SF-01 and SF-02 in parallel (no dependencies).
2. SF-03 (after SF-02).
3. SF-04 and SF-05 in parallel (both after SF-03).
4. SF-06 (after SF-01, SF-04 and SF-05).

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | No fixed traversal depth | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-02 | The sidecar and the test database | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-03 | Schemas, roles and migrations | SF-02 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-04 | Isolation | SF-03 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-05 | The graph on Postgres | SF-03 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-06 | Traversal and vectors on Postgres | SF-01, SF-04, SF-05 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design APPROVED 2026-11-12.
**Next step**: trigger the implementation-plan skill for SF-01 (SF-02 may run in parallel).
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume
from there using the appropriate skill.
