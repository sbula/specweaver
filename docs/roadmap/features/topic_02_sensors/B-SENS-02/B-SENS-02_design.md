# B-SENS-02 — Knowledge Graph Builder

**Status**: APPROVED · **COMPLETE** — SF-01, SF-02, SF-03 committed · **Phase**: 6 · **Feature ID**:
B-SENS-02

| | |
|---|---|
| Consumes | `D-SENS-02` (Tree-Sitter parsers: raw AST) · `A-SENS-01` (Deep Semantic Hashing) |
| Harmonizes | `D-SENS-01` (Topology Graph) · `B-SENS-01` (Lineage Graph) |
| Future | `A-SENS-02` (Postgres) · `A-SENS-04` (Graph Federation) · `C-SENS-05` (Embedded SQL Extraction) |
| Not touched | orchestration pipelines; remote cloud databases |

## What it does

A persistent, semantic Knowledge Graph for the Workspace Context system. Stores AST nodes (files,
classes, functions, variables) and their edges (imports, def-use chains, Control Flow) in a
project-local SQLite database (`.specweaver/specweaver.db`), wrapped in `NetworkX` for fast traversal.

Why: cuts LLM hallucination and avoids recalculating the graph on every query.

Constraints: language-agnostic; deduplicates nodes via Deep Semantic Hashing (`A-SENS-01`); fast to
query locally.

## Why a project-local DB

SQLite databases were global (`~/.specweaver/specweaver.db`, via
`src/specweaver/core/config/database.py`). A *local* project database (`.specweaver/specweaver.db`)
prevents lock contention during parallel agent execution across microservices (AD-1).

## Architecture

The graph domain is pure logic plus its own store, consuming `parsers` through an injected adapter.
Planned home: `src/specweaver/workspace/graph/`; built as `src/specweaver/graph/` (SF-01).

| Module | Does |
|---|---|
| `graph/core/engine` | `InMemoryGraphEngine` (`NetworkX`), ontology, `GraphNode` / `GraphEdge` — pure logic |
| `graph/core/store` | `SqliteGraphRepository` behind `AbstractGraphRepository` (SF-02) |
| `graph/core/builder` | `GraphBuilder` orchestrator + `OntologyMapper` (SF-01, SF-03) |
| `graph/topology`, `graph/lineage` | Topology (`D-SENS-01`) and Lineage (`B-SENS-01`) graphs, harmonized in SF-03 |

**Since moved** (noted 2026-09-25): `graph_store/` now lives at `src/specweaver/graph/core/store/`;
the lineage repository at `src/specweaver/graph/lineage/store/lineage_repository.py`.

Blueprint: the `tree-climber` repository — Kildall's iterative dataflow analysis framework
(`RoundRobinSolver`) and Visitor Pattern (see `docs/analysis/B-SENS-02_tree_climber_analysis.md`).

### External dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| NetworkX | 3.6.1 | `DiGraph`, `shortest_path`, subgraph extraction, traversal | Yes | `>=3.0` in `pyproject.toml`. Stable, pure Python, no C-extensions. |

## Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Local `.specweaver/specweaver.db` | Prevents global lock contention on `~/.specweaver/specweaver.db` during multi-agent workflows. | Yes — approved by User on 2026-04-28 |
| AD-2 | NetworkX wrapper | Fastest pure-Python graph library for extracting subgraphs before passing context to the LLM. | No |
| AD-3 | Interface Fallback Heuristic | Resolves IoC/Spring/Quarkus dependencies by drawing `IMPLEMENTS` edges and tracing back to concrete classes. | No |
| AD-4 | `API_CONTRACT` Nodes | Separates cross-language RPCs. TS `CONSUMES` the contract; Go `FULFILLS` it. APIs can evolve independently. | No |
| AD-5 | SCC Condensation (Tarjan's) | Prevents infinite loops in the Dataflow solver caused by circular imports. | No |
| AD-6 | Selective Ghost Nodes | Parses manifest files to create Ghost Nodes only for external libraries (CVE tracking), saving DB space. | No |
| AD-7 | `OntologyMapper` Layer | Translates native Tree-Sitter AST nodes to universal ontology (`PROCEDURE`, `DATA_STRUCTURE`, `STATE`). | No |
| AD-8 | Ignore Macros (with Safety Flag) | Avoids becoming a slow C/Rust compiler. Tags nodes with `contains_unexpanded_macros=True` for LLM safety. | No |
| AD-9 | Defer Embedded SQL Parsing | Too complex for MVS. Split into backlog feature `C-SENS-05: Embedded SQL Extraction`. | No |
| AD-10 | Accept Framework Blind Spots | Avoids becoming a compiler for Django/Spring. Semantic tags (`framework: django_orm`) let LLMs infer implicit methods. | No |
| AD-11 | Functional Paradigm Support | Scala/Clojure lambdas map to `PROCEDURE` and `PASSED_TO` dataflow edges. | No |
| AD-12 | Abstract Repository Pattern | DB access behind an interface (e.g., `GraphRepository`). SQLite syntax outside the adapter is forbidden, for future `A-SENS-02` (Postgres). | No |
| AD-13 | Soft Deletes (Tombstoning) | When a node's hash disappears (e.g., Git branch switch), set `is_active=FALSE` instead of hard `DELETE` to keep LLM-generated metadata if the branch returns. | No |
| AD-14 | Flattened Closures | Inner functions (e.g., Python nested `def`) are serialized inside their parent's body, not extracted as standalone nodes, to prevent graph pollution. | No |
| AD-15 | Overload Ambiguity Fallback | If an edge target is ambiguous in dynamic languages (e.g., overloaded `execute`), the `CALLS` edge links to the parent `DATA_STRUCTURE` rather than guessing the `PROCEDURE`. | No |
| AD-16 | KISS | Direct Python functions and `NetworkX`. PubSub event brokers or Observer patterns inside SF-01 are forbidden. | No |
| AD-17 | Federated GraphRAG | Graphs are bounded per-microservice. Cross-repo linkage happens at query-time via `API_CONTRACT` URI nodes (`service://...`), preventing global DB lock contention. | No |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Parse AST | Graph Builder | Parses AST dictionaries from `D-SENS-02` | In-memory `NetworkX` nodes are created |
| FR-2 | Deduplicate Nodes | Graph Builder | Applies `A-SENS-01` hashing | Exact structural duplicates are merged to a single Node ID |
| FR-3 | Persist Graph | Graph Builder | Writes Nodes and Edges to local SQLite | Data is saved to `.specweaver/specweaver.db` |
| FR-6 | Query Interface | System | Queries subgraph by symbol/file | Returns a `NetworkX` subgraph up to specified depth |
| FR-7 | Visualization Export | Graph Builder | Exports graph to `NetworkX` GraphML | Generates `.specweaver/graph.graphml` for external 3D visualizers like Gephi |
| [EXP-1] | Structural Hashing | Graph Builder | Computes a secondary hash ignoring variable names | Experimental: detects and flags code clones |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|---|----------------------|
| NFR-1 | Performance | Querying a subgraph of depth 3 MUST return within 50ms. |
| NFR-2 | Scale | Local SQLite schema MUST support graphs of up to 100,000 nodes without deadlocks. |
| NFR-3 | Concurrency | Parallel agent processes MUST NOT throw `database is locked` errors (solved via project-local DBs). |
| NFR-4 | PostgreSQL Trigger | Switch to PostgreSQL sidecar IF total graph exceeds 500,000 edges or multi-repo cross-queries are required. **[proof: none — unfalsifiable as written]** |

## Data model and ontology

Raw Tree-Sitter CST nodes are translated into this universal ontology before ingestion, so
implementation agents hand off context in one vocabulary. SF-01 expanded it; the full enums are in the
[SF-01 plan](B-SENS-02_SF1_plan.md).

**Node types**

- `FILE`: a physical source file.
- `DATA_STRUCTURE`: Class, Struct, Interface, Trait, or ORM Model.
- `PROCEDURE`: Function, Method, Lambda, or Receiver.
- `STATE`: global variables, Enums, class-level attributes (local variables go into procedure metadata).
- `API_CONTRACT`: cross-language endpoints (e.g., REST routes, gRPC definitions).
- `GHOST`: third-party external dependencies (parsed via package manifests).

**Edge types**

- `IMPORTS`: File A imports File B.
- `CALLS`: Procedure A invokes Procedure B.
- `IMPLEMENTS`: Data Structure A fulfills Data Structure B (resolves IoC).
- `CONSUMES` / `FULFILLS`: Service A consumes an `API_CONTRACT` that Service B fulfills.

### SQLite schema contract (SF-02)

The `GraphRepository` implements at least this baseline schema, to prevent B-Tree fragmentation:

- `nodes` table: `(id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, name TEXT, semantic_hash TEXT UNIQUE, clone_hash TEXT, file_id TEXT, metadata JSON)`
- `edges` table: `(source_id INTEGER, target_id INTEGER, type TEXT, metadata JSON, PRIMARY KEY (source_id, target_id, type))`

## Federation and monorepos

Graph Federation (`A-SENS-04`) supports multi-repo microservices (e.g., US-11 GraphRAG for Brownfield
Scale). Each microservice keeps its own local `.specweaver/specweaver.db` in its own repository — no
central monolithic `specweaver.db`.

- **System Architecture Graph (the "outside" layer).** One graph links all microservices
  *exclusively* via their interfaces (REST APIs, Kafka/RabbitMQ queues, shared file systems), with
  none of their internal logic. It lives outside any microservice's DB: in the central
  GitOps/Infrastructure repository's `.specweaver/specweaver.db`, or globally in
  `~/.specweaver/specweaver.db`.
- **Mandatory ID prefixing.** Every Node ID is prefixed with its microservice identifier (e.g.,
  `billing:ast:1a2b3c4d`, not `1a2b3c4d`), so the System Graph can fuse with local DBs without ID
  collisions.
- **Dynamic fusing** (future query pipelines). When GraphRAG hits an external URI in the System
  Graph, it mounts the remote SQLite database and fuses internal subgraphs only on explicit drill-down.

Monorepos and strongly modularized monoliths pick one of two patterns:

1. **Federation (multiple DBs).** Distinct deployable microservices (e.g., an Nx workspace): each
   microservice folder keeps its own `.specweaver/specweaver.db`, linked via `API_CONTRACT` nodes —
   same as polyrepo.
2. **Monolith (single DB).** A heavily coupled monolith: one `.specweaver/specweaver.db` at the
   repository root.
   - Internal borders are `TOPOLOGY_BOUNDARY` nodes (from `context.yaml` rules or module boundaries),
     not `API_CONTRACT` nodes.
   - Subgraphs are isolated at query-time by the `package_name` or `service_name` properties on
     `GraphNode`.
   - ID prefixing still applies (e.g., `monolith:billing:ast:123`), so IDs stay globally safe if the
     monolith is refactored or talks to an external microservice.

## Data lifecycle

The graph follows this lifecycle so refactors, deletions and moved functions leave no "Ghost Nodes"
and no duplicates.

1. **Cold start (boot).** When SpecWeaver initializes, SF-02 reads the SQLite backup and compares each file's stored
   `semantic_hash` with the filesystem (`A-SENS-01`).
   - Match: the file's subgraph loads into the in-memory NetworkX engine.
   - Mismatch / missing: the file is flagged `DIRTY` for re-ingestion.
2. **Update cycle (node-level semantic diffing)** for a `DIRTY` file — no full subgraph rebuild:
   1. Parse & map: fresh AST via `D-SENS-02` → `OntologyMapper` → new `GraphNode` objects.
   2. Hash diff: compare new `semantic_hash` values with the nodes stored in memory/SQLite for
      `file_id = X`.
   3. Insert (new): a new hash → INSERT the node, then calculate/insert its edges.
   4. Purge (deleted/ghost): a hash in the DB but not in the new AST (function deleted or renamed) →
      DELETE that node and sever only its attached edges.
   5. Preserve (unchanged): hash matches (e.g., a comment or blank line added elsewhere) → DO
      NOTHING. The node and its inbound/outbound edges stay intact.
3. **Synchronization (async flush).** After the NetworkX update, SF-02 pushes the new subgraphs to
   SQLite with an `UPSERT`, so disk matches memory.
4. **Refactoring (moving functions).** Identity is `semantic_hash` (A-SENS-01), not an arbitrary ID.
   Moving a function from `auth.py` to `utils.py` without changing its code keeps its hash: the
   update cycle purges it from `auth.py` and re-ingests it into `utils.py`, and external edges (like
   `CALLS`) pointing to that `semantic_hash` reconnect without manual graph patching.

## Security & Red Team Mitigations

| # | Vulnerability | Mitigation Strategy | Assigned Sub-Feature |
|---|---------------|---------------------|----------------------|
| RT-1 | **SQL Injection (AST Poisoning)** | 100% parameterized queries (`?` bindings) for all inserts. Raw AST string concatenation is forbidden. | SF-01 |
| RT-2 | **AST Bomb (Stack Overflow)** | Strict recursion depth bounds (e.g., `MAX_AST_DEPTH = 500`). Graceful failure with `is_partial=True` flag. | SF-03 & SF-04 |
| RT-3 | **Ghost Node Spoofing** | Prefer internal `D-SENS-01` topology resolution over package manifest resolution, so attackers cannot spoof internal RPCs. | SF-02 |
| RT-4 | **SQLite Lock Contention** | Enable `PRAGMA journal_mode=WAL;` for asynchronous background flushes to the database. | SF-02 |
| RT-5 | **GraphML Info Leak** | Append `*.graphml` to `.gitignore` on generation, to prevent proprietary architecture leaks. | SF-01 |
| RT-6 | **Structural Hash Collision** | The experimental Structural Hash MUST be confined to a `clone_hash` column. Semantic Hash stays the unique Primary Key. | SF-01 & SF-02 |
| RT-8 | **Ghost Edge Stagnation** | Edge invalidation MUST be bi-directional. When a node is UPSERTED, all incoming AND outgoing edges are wiped before recalculation. | SF-01 |
| RT-11 | **Stale Graph Boot Trap** | SF-03 MUST compare `A-SENS-01` file hashes against the DB on boot. Any mismatch triggers an immediate purge and re-parse of that file's subgraph. | SF-03 |
| RT-12 | **Orphaned Node Accumulation** | Updating a modified file MUST trigger a hard reset (`DELETE FROM nodes WHERE file_id = X`) before inserting the new AST nodes, wiping deleted functions/ghosts. | SF-01 |
| RT-13 | **Memory Bloat Eviction** | The in-memory `NetworkX` graph MUST be tied to the CLI process lifecycle. As a daemon it MUST support an explicit `clear_cache()` command. | SF-01 |
| RT-14 | **Declarative AST Crash** | The `OntologyMapper` MUST NOT assume files contain executable `PROCEDURE` nodes (e.g., TypeSpec/HCL2). It maps `API_CONTRACT` without throwing exceptions. | SF-01 |
| RT-15 | **Syntax Error Poisoning** | `D-SENS-02` ASTs contain `ERROR` nodes if code is half-written. The mapper MUST skip `ERROR` blocks rather than crash the ingestion pipeline. | SF-01 |
| RT-16 | **GraphML Path Traversal** | The `export_graph` path target MUST be sanitized and bounded inside `workspace_root`, preventing `../../../etc/passwd` overwrites. | SF-01 |
| RT-17 | **Centrality Math Collapse** | Internal NetworkX routing uses `INTEGER` node IDs for matrix math (Feature 3.38); the string `semantic_hash` stays in external lookup dictionaries. | SF-01 & SF-02 |
| RT-18 | **NetworkX Thread Contention** | NetworkX is not thread-safe. All in-memory `DiGraph` mutations (INSERT/DELETE) MUST be wrapped in a `threading.Lock()`, preventing process crashes during parallel agent execution. | SF-01 |
| RT-19 | **Auto-Generated Code Bloat** | Ingestion MUST skip files over 1MB or with known auto-generated headers (e.g., protobuf, minified JS), preventing graph bloat and slowdown. | SF-01 |
| RT-20 | **Symlink Infinite Recursion** | The file scanner MUST ignore OS symlinks (`os.path.islink()`), preventing `RecursionError` from recursive directory loops. | SF-01 |
| RT-21 | **Case-Insensitive Path Thrashing** | All `file_id` and import paths MUST be normalized (e.g., absolute and lowercased on Windows/Mac), so OS capitalization changes do not trigger mass ghost-deletions. | SF-01 |
| RT-22 | **Serialization Infinite Loops** | Functions that serialize NetworkX subgraphs into Markdown for the LLM MUST keep a `visited_nodes` set to break circular import cycles. | SF-01 |
| RT-23 | **AST Metadata Prompt Injection** | Data injected into `metadata JSON` from the AST MUST be sanitized to strip LLM hijack strings (e.g., `<|im_start|>`) hiding in developer comments. | SF-01 |
| RT-24 | **OOM Memory Bombing** | RT-19's size limit MUST use `os.path.getsize(path)` *before* opening the I/O stream, so a 5GB file cannot trigger an Out-Of-Memory crash. | SF-01 |
| RT-25 | **Metadata Black Hole Attack** | The `GraphNode` Pydantic model MUST enforce a 2KB limit on the dumped `metadata` JSON blob. Raw code or embeddings in metadata are forbidden. | SF-01 |
| RT-26 | **Namespace Prefix Spoofing** | ID prefixes MUST be prepended by the `GraphRepository` (reading `context.yaml`), NOT passed as an argument by the AST parser, so agents cannot spoof cross-service IDs. | SF-02 |
| RT-27 | **Infinite Depth OOM Crash** | The `InMemoryGraphEngine` MUST enforce a hard-coded maximum depth (e.g., `max(requested, 5)`) on all subgraph extraction queries, preventing enterprise-wide memory loads. | SF-01 |
| RT-28 | **Standard Library Ghost Swarm** | The `OntologyMapper` MUST silently drop `CALLS` edges to native standard libraries (e.g., `sys.stdlib_module_names`), preventing millions of useless nodes. | SF-01 |
| RT-29 | **Metadata Key Obfuscation** | `metadata` JSON MUST be validated via Pydantic Discriminated Unions per `NodeKind`. `Dict[str, Any]` is forbidden. Unrecognized keys are silently dropped (no data smuggling). | SF-01 |
| RT-30 | **Local Context YAML Poisoning** | On boot the Orchestrator MUST validate the local `context.yaml` `service_name` against the global `~/.specweaver/specweaver.db` registry before passing it to the GraphRepository. | SF-03 |
| RT-31 | **Parallel Query Exhaustion** | The `InMemoryGraphEngine` MUST use an async `Semaphore` to limit concurrent subgraph extractions (e.g., max 3), so LLM loops cannot OOM via parallel `NetworkX` instances. | SF-01 |
| RT-32 | **Polyglot Ghost Blindspot** | `D-SENS-02` parsers MUST provide standard library exclusion Regexes (e.g., `^java\..*`) to the `OntologyMapper`: the Python `sys` module cannot identify Java/Go/Rust built-ins. | SF-01 |

RT-30 exists to stop rogue agents hijacking other microservice namespaces.

## Developer guides

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Knowledge Graph Querying | How to extract context using the `NetworkX` wrapper | 🟩 Completed (`docs/dev_guides/knowledge_graph_querying.md`) |
| OntologyMapper Integration | How to map a new language's Tree-Sitter CST to the Universal Graph Ontology | 🟩 Completed (`docs/dev_guides/ontology_mapping.md`) |

## Sub-features

| SF | Does | FRs | Depends on | Plan |
|----|------|-----|-----------|------|
| SF-01 | In-memory engine + ontology (below) | FR-1, FR-2, FR-6, FR-7, EXP-1 | — | [SF1](B-SENS-02_SF1_plan.md) |
| SF-02 | SQLite storage adapter (below) | FR-3, FR-6 | SF-01 | [sf02](B-SENS-02_sf02_implementation_plan.md) |
| SF-03 | Builder orchestration + harmonization (below) | FR-1, FR-6 | SF-01, SF-02 | [sf03](B-SENS-02_sf03_implementation_plan.md) |

Order: SF-01 (no deps) → SF-02 → SF-03. The plans restate ownership: SF-02 owns FR-2, FR-3; SF-03
owns FR-1, FR-6, FR-7.

**SF-01 — In-Memory Knowledge Graph Engine & Enterprise Ontology.** Parses AST dictionaries via the
`OntologyMapper`, applies semantic hashes, builds the in-memory `NetworkX` graph. Lives entirely in
`src/specweaver/graph/` (pure logic): blind to the filesystem, the database and the AST parser; it
only accepts raw JSON dicts passed down from the orchestrator. Expands the ontology to capture
macro-architectural boundaries as Edges. Exposes the read query API.

- Inputs: raw JSON dictionaries (AST data, topology data) passed via orchestration.
- Outputs: expanded `GraphNode` schema, new Edge types, in-memory `NetworkX` graph, `.graphml` export.

**SF-02 — Persistent Storage Adapter (SQLite).** Creates the `src/specweaver/graph_store/` (adapter)
module, isolated from `config/` so structural graph data stays apart from application settings.
Implements the `GraphRepository` adapter. Promotes `service_name` and `package_name` to explicit,
indexed DB columns to prevent Context Window collapse. Handles asynchronous flush/load of the
`NetworkX` graph.

- Inputs: in-memory `NetworkX` graph.
- Outputs: `ProjectDatabase` SQLite connection object targeting `.specweaver/specweaver.db`.

**SF-03 — Graph Builder Orchestration & Harmonization.** Creates the
`src/specweaver/graph/core/builder/` (orchestrator) module to coordinate the sensor triad.

1. Extracts the AST via a generic AST-to-Dict adapter (wrapping `workspace.parsers`), injected into
   the `GraphBuilder` orchestrator at the CLI root to keep domain boundaries. The orchestrator
   enforces ID Prefixing (e.g., `monolith:billing:ast:<hash>`) across the `InMemoryGraphEngine` and
   `graph_store/`.
2. Refactors the existing legacy graphs onto the same triad, as feature-specific graph sub-modules:
   - **Topology Graph (`D-SENS-01`)**: pure graph math (Tarjan's, cycle detection) moves from
     `src/specweaver/assurance/graph/topology.py` into `specweaver.graph.topology`; `assurance`
     delegates computation to it.
   - **Lineage Graph (`B-SENS-01`)**: the SQLite `artifact_events` table schema moves out of
     `config/database.py`, and the tree-traversal math out of `cli/lineage.py`, into
     `specweaver.graph.lineage`. The CLI stays a thin router.

- Inputs: file system paths, legacy graph generators.
- Outputs: harmonized pipeline orchestrating AST/Topology extraction into the SQLite DB.
- Tech debt spawned: `TECH-003` — structural refactoring of the Workspace AST module (extract
  `workspace.parsers` to `workspace.ast.parsers`); `TECH-004` — analysis & refactoring of the
  `sw graph build` CLI (move orchestration to `GraphBuildAtom`).

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | In-Memory Graph Engine & Enterprise Ontology | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Persistent Storage Adapter | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Graph Builder Orchestration & Harmonization | SF-01, SF-02 | ✅ | ✅ | ✅ | ✅ | ✅ |
