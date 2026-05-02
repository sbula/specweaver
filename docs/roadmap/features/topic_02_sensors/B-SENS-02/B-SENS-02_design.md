# Design: Knowledge Graph Builder

- **Feature ID**: B-SENS-02
- **Phase**: 6
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_design.md

## Feature Overview

Feature B-SENS-02 adds a persistent, semantic Knowledge Graph to the Workspace Context system.
It solves the problem of LLM hallucination and expensive graph recalculation by persistently storing AST nodes (files, classes, functions, variables) and their edges (imports, def-use chains, Control Flow) in a project-local SQLite database (`.specweaver/graph.db`), wrapped in `NetworkX` for fast traversal.
It interacts with `D-SENS-02` (Tree-Sitter Parsers) to ingest the raw AST, and does NOT touch orchestration pipelines or remote cloud databases.
Key constraints: Must be language-agnostic, must deduplicate nodes via Deep Semantic Hashing (`A-SENS-01`), and must be extremely fast to query locally.

## Research Findings

### Codebase Patterns
- `D-SENS-02` already provides the raw Tree-Sitter AST dictionaries.
- Currently, SQLite databases are global (`~/.specweaver/specweaver.db`) via `src/specweaver/core/config/database.py`.
- We are introducing a *local* project database pattern (`.specweaver/graph.db`) to prevent lock contention during parallel agent execution across microservices.
- The new logic belongs in a pure-logic module: `src/specweaver/workspace/graph/` consuming `parsers`.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| NetworkX | >=3.0 | `DiGraph`, `shortest_path`, traversal | `pyproject.toml` |

### Blueprint References
- `tree-climber` repository: Kildall's iterative dataflow analysis framework (`RoundRobinSolver`) and Visitor Pattern (see `docs/analysis/B-SENS-02_tree_climber_analysis.md`).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Parse AST | Graph Builder | Parses AST dictionaries from `D-SENS-02` | In-memory `NetworkX` nodes are created |
| FR-2 | Deduplicate Nodes | Graph Builder | Applies `A-SENS-01` hashing | Exact structural duplicates are merged to a single Node ID |
| FR-3 | Persist Graph | Graph Builder | Writes Nodes and Edges to local SQLite | Data is saved to `.specweaver/graph.db` |
| FR-6 | Query Interface | System | Queries subgraph by symbol/file | Returns a `NetworkX` subgraph up to specified depth |
| FR-7 | Visualization Export | Graph Builder | Exports graph to `NetworkX` GraphML | Generates `.specweaver/graph.graphml` for external 3D visualizers like Gephi |
| [EXP-1] | Structural Hashing | Graph Builder | Computes a secondary hash ignoring variable names | Experimental: Detects and flags code clones mathematically |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | Querying a subgraph of depth 3 MUST return within 50ms. |
| NFR-2 | Scale | Local SQLite schema MUST support graphs of up to 100,000 nodes without deadlocks. |
| NFR-3 | Concurrency | Parallel agent processes MUST NOT throw `database is locked` errors (solved via project-local DBs). |
| NFR-4 | PostgreSQL Trigger | Switch to PostgreSQL sidecar IF total graph exceeds 500,000 edges or multi-repo cross-queries are required. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| NetworkX | 3.6.1 | `DiGraph`, subgraph extraction | Yes | Stable, pure Python, no C-extensions. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Local `.specweaver/graph.db` | Prevents global lock contention on `~/.specweaver/specweaver.db` during multi-agent workflows. | Yes — approved by User on 2026-04-28 |
| AD-2 | NetworkX wrapper | Fastest pure-Python graph math library for extracting subgraphs before passing context to LLM. | No |
| AD-3 | Interface Fallback Heuristic | Resolves IoC/Spring/Quarkus dependencies by drawing `IMPLEMENTS` edges and tracing back to concrete classes. | No |
| AD-4 | `API_CONTRACT` Nodes | Separates cross-language RPCs. TS `CONSUMES` the contract; Go `FULFILLS` it. APIs can evolve independently. | No |
| AD-5 | SCC Condensation (Tarjan's) | Prevents infinite loops in the Dataflow solver caused by circular imports. | No |
| AD-6 | Selective Ghost Nodes | Parses manifest files to only create Ghost Nodes for external libraries (CVE tracking), saving massive DB space. | No |
| AD-7 | `OntologyMapper` Layer | Translates native Tree-Sitter AST nodes to universal ontology (`PROCEDURE`, `DATA_STRUCTURE`, `STATE`). | No |
| AD-8 | Ignore Macros (with Safety Flag) | Prevents becoming a slow C/Rust compiler. Tags nodes with `contains_unexpanded_macros=True` for LLM safety. | No |
| AD-9 | Defer Embedded SQL Parsing | Too complex for MVS. Split into new backlog feature `C-SENS-05: Embedded SQL Extraction`. | No |
| AD-10 | Accept Framework Blind Spots | Prevents becoming a compiler for Django/Spring. Uses semantic tags (`framework: django_orm`) to let LLMs infer implicit methods. | No |
| AD-11 | Functional Paradigm Support | Scala/Clojure lambdas map perfectly to `PROCEDURE` and `PASSED_TO` dataflow edges. | No |
| AD-12 | Abstract Repository Pattern | DB interactions must be abstracted behind an interface (e.g., `GraphRepository`). Hardcoding SQLite syntax outside the adapter is forbidden to ensure future compatibility with `A-SENS-02` (Postgres). | No |
| AD-13 | Soft Deletes (Tombstoning) | When a node's hash disappears (e.g., during Git branch switching), use `is_active=FALSE` instead of hard `DELETE` to preserve LLM-generated metadata if the branch returns. | No |
| AD-14 | Flattened Closures | Inner functions (e.g., Python nested `def`) must be serialized inside their parent's body, not extracted as standalone nodes, to prevent graph pollution. | No |
| AD-15 | Overload Ambiguity Fallback | If an edge target is ambiguous in dynamic languages (e.g., overloaded `execute`), the `CALLS` edge must link to the parent `DATA_STRUCTURE` rather than guessing the wrong `PROCEDURE`. | No |
| AD-16 | KISS Principle Enforcement | The engine must use direct Python functions and `NetworkX`. Building complex PubSub event brokers or Observer patterns inside SF-1 is explicitly forbidden. | No |
| AD-17 | Federated GraphRAG | Graphs are bounded per-microservice. Cross-repo linkage is achieved dynamically at query-time via `API_CONTRACT` URI nodes (`service://...`), preventing global DB lock contention. | No |

## Security & Red Team Mitigations

| # | Vulnerability | Mitigation Strategy | Assigned Sub-Feature |
|---|---------------|---------------------|----------------------|
| RT-1 | **SQL Injection (AST Poisoning)** | 100% parameterized queries (`?` bindings) required for all inserts. Raw AST string concatenation is forbidden. | SF-1 |
| RT-2 | **AST Bomb (Stack Overflow)** | Strict recursion depth bounds (e.g., `MAX_AST_DEPTH = 500`). Graceful failure with `is_partial=True` flag. | SF-3 & SF-4 |
| RT-3 | **Ghost Node Spoofing** | Prioritize internal `D-SENS-01` topology resolution over package manifest resolution to prevent attackers from spoofing internal RPCs. | SF-2 |
| RT-4 | **SQLite Lock Contention** | Enable `PRAGMA journal_mode=WAL;` to allow smooth asynchronous background flushes to the database. | SF-2 |
| RT-5 | **GraphML Info Leak** | Automatically append `*.graphml` to `.gitignore` upon generation to prevent proprietary architecture leaks. | SF-1 |
| RT-6 | **Structural Hash Collision** | The experimental Structural Hash MUST be confined to a `clone_hash` column. Semantic Hash must remain the unique Primary Key. | SF-1 & SF-2 |
| RT-8 | **Ghost Edge Stagnation** | Edge invalidation MUST be explicitly bi-directional. When a node is UPSERTED, all incoming AND outgoing edges must be wiped before recalculation. | SF-1 |
| RT-11 | **Stale Graph Boot Trap** | SF-3 MUST compare `A-SENS-01` file hashes against the DB on boot. Any mismatch triggers an immediate purge and re-parse of that file's subgraph. | SF-3 |
| RT-12 | **Orphaned Node Accumulation** | Updating a modified file MUST trigger a hard reset (`DELETE FROM nodes WHERE file_id = X`) before inserting the new AST nodes to wipe deleted functions/ghosts. | SF-1 |
| RT-13 | **Memory Bloat Eviction** | The in-memory `NetworkX` graph MUST be tied to the CLI process lifecycle. If running as a daemon, it MUST support an explicit `clear_cache()` command. | SF-1 |
| RT-14 | **Declarative AST Crash** | The `OntologyMapper` MUST NOT assume files contain executable `PROCEDURE` nodes (e.g., TypeSpec/HCL2). It must map `API_CONTRACT` gracefully without throwing exceptions. | SF-1 |
| RT-15 | **Syntax Error Poisoning** | `D-SENS-02` ASTs will contain `ERROR` nodes if code is half-written. The mapper MUST gracefully skip `ERROR` blocks rather than crashing the ingestion pipeline. | SF-1 |
| RT-16 | **GraphML Path Traversal** | The `export_graph` path target MUST be explicitly sanitized and bounded strictly inside `workspace_root` to prevent `../../../etc/passwd` overwrites. | SF-1 |
| RT-17 | **Centrality Math Collapse** | Internal NetworkX routing should use fast `INTEGER` node IDs for matrix math (Feature 3.38), restricting the massive string `semantic_hash` to external lookup dictionaries. | SF-1 & SF-2 |
| RT-18 | **NetworkX Thread Contention** | NetworkX is not thread-safe. All in-memory `DiGraph` mutations (INSERT/DELETE) MUST be wrapped in a `threading.Lock()` to prevent fatal process crashes during parallel agent execution. | SF-1 |
| RT-19 | **Auto-Generated Code Bloat** | The ingestion engine MUST skip files exceeding 1MB or containing known auto-generated headers (e.g., protobuf, minified JS) to prevent severe graph bloating and performance degradation. | SF-1 |
| RT-20 | **Symlink Infinite Recursion** | The file scanner MUST explicitly ignore OS symlinks (`os.path.islink()`) to prevent `RecursionError` crashes caused by recursive directory loops. | SF-1 |
| RT-21 | **Case-Insensitive Path Thrashing** | All `file_id` and import paths MUST be normalized (e.g., absolute and lowercased on Windows/Mac) to prevent OS capitalization changes from triggering massive ghost-deletions. | SF-1 |
| RT-22 | **Serialization Infinite Loops** | Functions that serialize NetworkX subgraphs into Markdown strings for the LLM MUST maintain a `visited_nodes` set to break circular import cycles and prevent stringifier crashes. | SF-1 |
| RT-23 | **AST Metadata Prompt Injection** | Data injected into `metadata JSON` from the AST MUST be sanitized to strip potential LLM hijack strings (e.g., `<|im_start|>`) hiding in developer comments. | SF-1 |
| RT-24 | **OOM Memory Bombing** | Implementation of RT-19 (File size limits) MUST use `os.path.getsize(path)` to check the file size *before* opening the I/O stream, preventing massive 5GB files from triggering an Out-Of-Memory crash. | SF-1 |
| RT-25 | **Metadata Black Hole Attack** | The `GraphNode` Pydantic model MUST enforce a strict 2KB limit on the dumped `metadata` JSON blob. Storing raw code or embeddings in metadata is strictly forbidden. | SF-1 |
| RT-26 | **Namespace Prefix Spoofing** | ID prefixes MUST be deterministically prepended by the `GraphRepository` (reading `context.yaml`), NOT passed as a flexible argument by the AST parser, preventing agents from spoofing cross-service IDs. | SF-2 |
| RT-27 | **Infinite Depth OOM Crash** | The `InMemoryGraphEngine` MUST enforce a hard-coded maximum depth (e.g., `max(requested, 5)`) on all subgraph extraction queries to prevent catastrophic enterprise-wide memory loads. | SF-1 |
| RT-28 | **Standard Library Ghost Swarm** | The `OntologyMapper` MUST detect and silently drop `CALLS` edges pointing to native language standard libraries (e.g., `sys.stdlib_module_names`) to prevent millions of useless nodes. | SF-1 |
| RT-29 | **Metadata Key Obfuscation** | The `metadata` JSON blob MUST be strictly validated via Pydantic Discriminated Unions per `NodeKind`. Unstructured `Dict[str, Any]` is forbidden. Unrecognized keys must be silently dropped to prevent data smuggling. | SF-1 |
| RT-30 | **Local Context YAML Poisoning** | The Orchestrator MUST validate the local `context.yaml` `service_name` against the global `~/.specweaver/specweaver.db` registry on boot to prevent rogue agents from hijacking other microservice namespaces, before passing the validated name to the GraphRepository. | SF-3 |
| RT-31 | **Parallel Query Exhaustion** | The `InMemoryGraphEngine` MUST use an async `Semaphore` to limit concurrent subgraph extractions (e.g., max 3) to prevent LLM loops from triggering an OOM crash via parallel `NetworkX` instances. | SF-1 |
| RT-32 | **Polyglot Ghost Blindspot** | Language-specific AST parsers (`D-SENS-02`) MUST provide standard library exclusion Regexes (e.g., `^java\..*`) to the `OntologyMapper` because the Python `sys` module cannot identify Java/Go/Rust built-ins. | SF-1 |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Knowledge Graph Querying | How to extract context using the `NetworkX` wrapper | 🟩 Completed (`docs/dev_guides/knowledge_graph_querying.md`) |
| OntologyMapper Integration | Documentation on how to map a new language's Tree-Sitter CST to the Universal Graph Ontology | 🟩 Completed (`docs/dev_guides/ontology_mapping.md`) |

## Core Data Model & Ontology

To prevent contextual handoff failures between implementation agents, the Knowledge Graph MUST strictly adhere to this universal ontology. Raw Tree-Sitter CST nodes must be translated into these constraints before ingestion.

### Allowed Node Types
*   `FILE`: A physical source code file.
*   `DATA_STRUCTURE`: A Class, Struct, Interface, Trait, or ORM Model.
*   `PROCEDURE`: A Function, Method, Lambda, or Receiver.
*   `STATE`: Global variables, Enums, or Class-level attributes (local variables are serialized into procedure metadata).
*   `API_CONTRACT`: Cross-language endpoints (e.g., REST routes, gRPC definitions).
*   `GHOST`: Third-party external dependencies (parsed via package manifests).

### Allowed Edge Types
*   `IMPORTS`: File A imports File B.
*   `CALLS`: Procedure A invokes Procedure B.
*   `IMPLEMENTS`: Data Structure A fulfills Data Structure B (resolves IoC).
*   `CONSUMES` / `FULFILLS`: Service A consumes an `API_CONTRACT` that Service B fulfills.

### Microservice Graph Federation (Future-Proofing)
To support infinite enterprise scaling across massive multi-repo microservices (e.g., US-11 GraphRAG for Brownfield Scale), the Universal Graph must natively support **Graph Federation** (`A-SENS-04`).
Instead of building a single centralized monolithic `graph.db`, each microservice maintains its own local `.specweaver/graph.db` within its own repository.
*   **The System Architecture Graph (The "Outside" Layer)**: There must be one overarching graph layer that links all microservices together *exclusively* via their interfaces (REST APIs, Kafka/RabbitMQ queues, shared file systems) without including *any* of the microservices' internal logic.
    *   **Storage Location**: Because this graph exists "outside" any single microservice, it is NOT stored in a microservice's local DB. It is housed either in the company's central GitOps/Infrastructure repository's `.specweaver/graph.db`, or managed globally in `~/.specweaver/specweaver.db`.
*   **Mandatory ID Prefixing:** To ensure this high-level System Graph can dynamically fuse with local databases without global ID collisions, every single Node ID MUST be prefixed with its microservice identifier (e.g., `billing:ast:1a2b3c4d` instead of just `1a2b3c4d`).
*   **Dynamic Fusing:** In future query pipelines, when the GraphRAG engine hits an external URI in the System Graph, it will dynamically mount the remote SQLite database and fuse the internal subgraphs only when explicit drill-down is requested.

### Monorepo & Strongly Modularized Application Support
For Monorepos (containing multiple microservices) or strongly modularized monoliths, the architecture offers two deployment patterns:
1.  **The Federation Pattern (Multiple DBs):** If the monorepo contains distinct, deployable microservices (e.g., an Nx workspace), best practice is for each microservice folder to maintain its own `.specweaver/graph.db`. This behaves identically to the polyrepo Federation model above, linking via `API_CONTRACT` nodes.
2.  **The Monolith Pattern (Single DB):** For a heavily coupled monolith, the entire codebase is stored within a single `.specweaver/graph.db` at the repository root.
    *   **Internal Boundaries**: Instead of external `API_CONTRACT` nodes, SpecWeaver uses `TOPOLOGY_BOUNDARY` nodes (derived from `context.yaml` rules or module boundaries) to define internal architectural borders.
    *   **Internal Routing**: Subgraphs are isolated at query-time using the `package_name` or `service_name` properties on the `GraphNode`.
    *   **ID Prefixing Still Applies**: Even in a single-DB monolith, the ID prefixing rule (e.g., `monolith:billing:ast:123`) is strictly enforced to ensure the IDs are globally safe if the monolith is ever refactored or communicates with an external microservice.

### SQLite Schema Contract (SF-2)
The `GraphRepository` MUST implement at least this baseline schema to prevent B-Tree fragmentation:
*   `nodes` table: `(id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, name TEXT, semantic_hash TEXT UNIQUE, clone_hash TEXT, file_id TEXT, metadata JSON)`
*   `edges` table: `(source_id INTEGER, target_id INTEGER, type TEXT, metadata JSON, PRIMARY KEY (source_id, target_id, type))`

## Data Lifecycle & Ingestion Flow

To handle continuous codebase evolution (refactoring, file deletions, moving functions) without accumulating "Ghost Nodes" or duplicating data, the graph MUST adhere to this strict lifecycle:

### 1. The Cold Start (Boot)
When SpecWeaver initializes, SF-2 reads the SQLite backup. It cross-references the stored `semantic_hash` of each file against the current filesystem (`A-SENS-01`). 
*   **Match:** The file's subgraph is safely loaded into the in-memory NetworkX engine.
*   **Mismatch / Missing:** The file is flagged as `DIRTY` for re-ingestion.

### 2. The Update Cycle (Node-Level Semantic Diffing)
When a file is flagged as `DIRTY`, the engine avoids rebuilding the entire file's subgraph by using strict semantic diffing:
1.  **Parse & Map:** Extract the fresh AST via `D-SENS-02` and pass it through the `OntologyMapper` to generate the new `GraphNode` objects.
2.  **Hash Diffing:** Compare the `semantic_hash` of the new nodes against the existing nodes stored in memory/SQLite for `file_id = X`.
3.  **Insert (New):** If a new hash appears, INSERT the new node and calculate/insert its edges.
4.  **Purge (Deleted/Ghost):** If a hash exists in the DB but is missing from the new AST (e.g., function was deleted or renamed), DELETE that specific node and sever only its attached edges.
5.  **Preserve (Unchanged):** If the hash matches (e.g., you just added a comment or a blank line elsewhere in the file), DO NOTHING. The existing node and all its inbound/outbound edges remain perfectly intact.

### 3. The Synchronization Cycle (Async Flush)
Once the NetworkX graph is updated, SF-2 asynchronously pushes the new subgraphs to SQLite via an `UPSERT` operation, ensuring the persistent save-state matches memory.

### 4. Handling Refactoring (Moving Functions)
Because the Knowledge Graph relies on `semantic_hash` (A-SENS-01) as the unique identifier rather than arbitrary IDs, moving a function from `auth.py` to `utils.py` without changing its code preserves its hash. 
The Update Cycle will purge it from `auth.py` and re-ingest it into `utils.py`. Any external edges (like `CALLS`) pointing to that `semantic_hash` will seamlessly reconnect without manual graph patching.

## Sub-Feature Breakdown

### SF-1: In-Memory Knowledge Graph Engine & Enterprise Ontology
- **Scope**: Parses AST dictionaries via the `OntologyMapper`, applies semantic hashes, and builds the primary in-memory `NetworkX` graph. Resides entirely in `src/specweaver/graph/` (pure-logic). It is blind to the filesystem, the database, and the AST parser. It only accepts raw JSON dicts passed down from the orchestrator. Expands the ontology to capture macro-architectural boundaries as Edges. Exposes the read query API.
- **FRs**: [FR-1, FR-2, FR-6, FR-7, EXP-1]
- **Inputs**: Raw JSON dictionaries (AST data, topology data) passed via orchestration.
- **Outputs**: Expanded `GraphNode` schema, new Edge types, in-memory `NetworkX` graph, and `.graphml` export.
- **Depends on**: none
- **Impl Plan**: ⬜

### SF-2: Persistent Storage Adapter (SQLite)
- **Scope**: Creates the new `src/specweaver/graph_store/` (adapter) module. This is completely isolated from `config/` to keep structural graph data separate from application settings. Implements the `GraphRepository` adapter. Promotes `service_name` and `package_name` to explicit, indexed DB columns to prevent Context Window collapse. Handles asynchronous flush/load of the `NetworkX` graph.
- **FRs**: [FR-3, FR-6]
- **Inputs**: In-memory `NetworkX` graph.
- **Outputs**: `ProjectDatabase` SQLite connection object targeting `.specweaver/graph.db`.
- **Depends on**: [SF-1]
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_sf2_implementation_plan.md

### SF-3: Graph Builder Orchestration & Harmonization
- **Scope**: Creates the new `src/specweaver/graph/core/builder/` (orchestrator) module to coordinate the new sensor triad. First, it implements the pipeline to extract the AST via a generic AST-to-Dict adapter (wrapping `workspace.parsers`), injecting this adapter into the `GraphBuilder` orchestrator at the CLI root to maintain strict domain boundaries. The orchestrator enforces ID Prefixing (e.g., `monolith:billing:ast:<hash>`) across the `InMemoryGraphEngine` and `graph_store/`.
  Second, it aggressively refactors the project's existing legacy graphs to use this exact same triad by establishing feature-specific graph sub-modules:
  1. **Topology Graph (`D-SENS-01`)**: Migrates pure graph math (Tarjan's, cycle detection) from `src/specweaver/assurance/graph/topology.py` into a new `specweaver.graph.topology` module. `assurance` delegates to this module for computation.
  2. **Lineage Graph (`B-SENS-01`)**: Migrates the SQLite `artifact_events` table schema out of `config/database.py` and the tree-traversal math out of `cli/lineage.py` into a new `specweaver.graph.lineage` module. The CLI remains a thin router.
- **FRs**: [FR-1, FR-6]
- **Inputs**: File system paths, legacy graph generators.
- **Outputs**: Harmonized pipeline orchestrating AST/Topology extraction into the SQLite DB.
- **Depends on**: [SF-1, SF-2]
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_sf3_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)
3. SF-3 (depends on SF-1, SF-2)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | In-Memory Graph Engine & Enterprise Ontology | — | ✅ | ✅ | ✅ | ✅ | ✅ |
### Blueprint References
- `tree-climber` repository: Kildall's iterative dataflow analysis framework (`RoundRobinSolver`) and Visitor Pattern (see `docs/analysis/B-SENS-02_tree_climber_analysis.md`).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Parse AST | Graph Builder | Parses AST dictionaries from `D-SENS-02` | In-memory `NetworkX` nodes are created |
| FR-2 | Deduplicate Nodes | Graph Builder | Applies `A-SENS-01` hashing | Exact structural duplicates are merged to a single Node ID |
| FR-3 | Persist Graph | Graph Builder | Writes Nodes and Edges to local SQLite | Data is saved to `.specweaver/graph.db` |
| FR-6 | Query Interface | System | Queries subgraph by symbol/file | Returns a `NetworkX` subgraph up to specified depth |
| FR-7 | Visualization Export | Graph Builder | Exports graph to `NetworkX` GraphML | Generates `.specweaver/graph.graphml` for external 3D visualizers like Gephi |
| [EXP-1] | Structural Hashing | Graph Builder | Computes a secondary hash ignoring variable names | Experimental: Detects and flags code clones mathematically |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|---|----------------------|
| NFR-1 | Performance | Querying a subgraph of depth 3 MUST return within 50ms. |
| NFR-2 | Scale | Local SQLite schema MUST support graphs of up to 100,000 nodes without deadlocks. |
| NFR-3 | Concurrency | Parallel agent processes MUST NOT throw `database is locked` errors (solved via project-local DBs). |
| NFR-4 | PostgreSQL Trigger | Switch to PostgreSQL sidecar IF total graph exceeds 500,000 edges or multi-repo cross-queries are required. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| NetworkX | 3.6.1 | `DiGraph`, subgraph extraction | Yes | Stable, pure Python, no C-extensions. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Local `.specweaver/graph.db` | Prevents global lock contention on `~/.specweaver/specweaver.db` during multi-agent workflows. | Yes — approved by User on 2026-04-28 |
| AD-2 | NetworkX wrapper | Fastest pure-Python graph math library for extracting subgraphs before passing context to LLM. | No |
| AD-3 | Interface Fallback Heuristic | Resolves IoC/Spring/Quarkus dependencies by drawing `IMPLEMENTS` edges and tracing back to concrete classes. | No |
| AD-4 | `API_CONTRACT` Nodes | Separates cross-language RPCs. TS `CONSUMES` the contract; Go `FULFILLS` it. APIs can evolve independently. | No |
| AD-5 | SCC Condensation (Tarjan's) | Prevents infinite loops in the Dataflow solver caused by circular imports. | No |
| AD-6 | Selective Ghost Nodes | Parses manifest files to only create Ghost Nodes for external libraries (CVE tracking), saving massive DB space. | No |
| AD-7 | `OntologyMapper` Layer | Translates native Tree-Sitter AST nodes to universal ontology (`PROCEDURE`, `DATA_STRUCTURE`, `STATE`). | No |
| AD-8 | Ignore Macros (with Safety Flag) | Prevents becoming a slow C/Rust compiler. Tags nodes with `contains_unexpanded_macros=True` for LLM safety. | No |
| AD-9 | Defer Embedded SQL Parsing | Too complex for MVS. Split into new backlog feature `C-SENS-05: Embedded SQL Extraction`. | No |
| AD-10 | Accept Framework Blind Spots | Prevents becoming a compiler for Django/Spring. Uses semantic tags (`framework: django_orm`) to let LLMs infer implicit methods. | No |
| AD-11 | Functional Paradigm Support | Scala/Clojure lambdas map perfectly to `PROCEDURE` and `PASSED_TO` dataflow edges. | No |
| AD-12 | Abstract Repository Pattern | DB interactions must be abstracted behind an interface (e.g., `GraphRepository`). Hardcoding SQLite syntax outside the adapter is forbidden to ensure future compatibility with `A-SENS-02` (Postgres). | No |
| AD-13 | Soft Deletes (Tombstoning) | When a node's hash disappears (e.g., during Git branch switching), use `is_active=FALSE` instead of hard `DELETE` to preserve LLM-generated metadata if the branch returns. | No |
| AD-14 | Flattened Closures | Inner functions (e.g., Python nested `def`) must be serialized inside their parent's body, not extracted as standalone nodes, to prevent graph pollution. | No |
| AD-15 | Overload Ambiguity Fallback | If an edge target is ambiguous in dynamic languages (e.g., overloaded `execute`), the `CALLS` edge must link to the parent `DATA_STRUCTURE` rather than guessing the wrong `PROCEDURE`. | No |
| AD-16 | KISS Principle Enforcement | The engine must use direct Python functions and `NetworkX`. Building complex PubSub event brokers or Observer patterns inside SF-1 is explicitly forbidden. | No |
| AD-17 | Federated GraphRAG | Graphs are bounded per-microservice. Cross-repo linkage is achieved dynamically at query-time via `API_CONTRACT` URI nodes (`service://...`), preventing global DB lock contention. | No |

## Security & Red Team Mitigations

| # | Vulnerability | Mitigation Strategy | Assigned Sub-Feature |
|---|---------------|---------------------|----------------------|
| RT-1 | **SQL Injection (AST Poisoning)** | 100% parameterized queries (`?` bindings) required for all inserts. Raw AST string concatenation is forbidden. | SF-1 |
| RT-2 | **AST Bomb (Stack Overflow)** | Strict recursion depth bounds (e.g., `MAX_AST_DEPTH = 500`). Graceful failure with `is_partial=True` flag. | SF-3 & SF-4 |
| RT-3 | **Ghost Node Spoofing** | Prioritize internal `D-SENS-01` topology resolution over package manifest resolution to prevent attackers from spoofing internal RPCs. | SF-2 |
| RT-4 | **SQLite Lock Contention** | Enable `PRAGMA journal_mode=WAL;` to allow smooth asynchronous background flushes to the database. | SF-2 |
| RT-5 | **GraphML Info Leak** | Automatically append `*.graphml` to `.gitignore` upon generation to prevent proprietary architecture leaks. | SF-1 |
| RT-6 | **Structural Hash Collision** | The experimental Structural Hash MUST be confined to a `clone_hash` column. Semantic Hash must remain the unique Primary Key. | SF-1 & SF-2 |
| RT-8 | **Ghost Edge Stagnation** | Edge invalidation MUST be explicitly bi-directional. When a node is UPSERTED, all incoming AND outgoing edges must be wiped before recalculation. | SF-1 |
| RT-11 | **Stale Graph Boot Trap** | SF-3 MUST compare `A-SENS-01` file hashes against the DB on boot. Any mismatch triggers an immediate purge and re-parse of that file's subgraph. | SF-3 |
| RT-12 | **Orphaned Node Accumulation** | Updating a modified file MUST trigger a hard reset (`DELETE FROM nodes WHERE file_id = X`) before inserting the new AST nodes to wipe deleted functions/ghosts. | SF-1 |
| RT-13 | **Memory Bloat Eviction** | The in-memory `NetworkX` graph MUST be tied to the CLI process lifecycle. If running as a daemon, it MUST support an explicit `clear_cache()` command. | SF-1 |
| RT-14 | **Declarative AST Crash** | The `OntologyMapper` MUST NOT assume files contain executable `PROCEDURE` nodes (e.g., TypeSpec/HCL2). It must map `API_CONTRACT` gracefully without throwing exceptions. | SF-1 |
| RT-15 | **Syntax Error Poisoning** | `D-SENS-02` ASTs will contain `ERROR` nodes if code is half-written. The mapper MUST gracefully skip `ERROR` blocks rather than crashing the ingestion pipeline. | SF-1 |
| RT-16 | **GraphML Path Traversal** | The `export_graph` path target MUST be explicitly sanitized and bounded strictly inside `workspace_root` to prevent `../../../etc/passwd` overwrites. | SF-1 |
| RT-17 | **Centrality Math Collapse** | Internal NetworkX routing should use fast `INTEGER` node IDs for matrix math (Feature 3.38), restricting the massive string `semantic_hash` to external lookup dictionaries. | SF-1 & SF-2 |
| RT-18 | **NetworkX Thread Contention** | NetworkX is not thread-safe. All in-memory `DiGraph` mutations (INSERT/DELETE) MUST be wrapped in a `threading.Lock()` to prevent fatal process crashes during parallel agent execution. | SF-1 |
| RT-19 | **Auto-Generated Code Bloat** | The ingestion engine MUST skip files exceeding 1MB or containing known auto-generated headers (e.g., protobuf, minified JS) to prevent severe graph bloating and performance degradation. | SF-1 |
| RT-20 | **Symlink Infinite Recursion** | The file scanner MUST explicitly ignore OS symlinks (`os.path.islink()`) to prevent `RecursionError` crashes caused by recursive directory loops. | SF-1 |
| RT-21 | **Case-Insensitive Path Thrashing** | All `file_id` and import paths MUST be normalized (e.g., absolute and lowercased on Windows/Mac) to prevent OS capitalization changes from triggering massive ghost-deletions. | SF-1 |
| RT-22 | **Serialization Infinite Loops** | Functions that serialize NetworkX subgraphs into Markdown strings for the LLM MUST maintain a `visited_nodes` set to break circular import cycles and prevent stringifier crashes. | SF-1 |
| RT-23 | **AST Metadata Prompt Injection** | Data injected into `metadata JSON` from the AST MUST be sanitized to strip potential LLM hijack strings (e.g., `<|im_start|>`) hiding in developer comments. | SF-1 |
| RT-24 | **OOM Memory Bombing** | Implementation of RT-19 (File size limits) MUST use `os.path.getsize(path)` to check the file size *before* opening the I/O stream, preventing massive 5GB files from triggering an Out-Of-Memory crash. | SF-1 |
| RT-25 | **Metadata Black Hole Attack** | The `GraphNode` Pydantic model MUST enforce a strict 2KB limit on the dumped `metadata` JSON blob. Storing raw code or embeddings in metadata is strictly forbidden. | SF-1 |
| RT-26 | **Namespace Prefix Spoofing** | ID prefixes MUST be deterministically prepended by the `GraphRepository` (reading `context.yaml`), NOT passed as a flexible argument by the AST parser, preventing agents from spoofing cross-service IDs. | SF-2 |
| RT-27 | **Infinite Depth OOM Crash** | The `InMemoryGraphEngine` MUST enforce a hard-coded maximum depth (e.g., `max(requested, 5)`) on all subgraph extraction queries to prevent catastrophic enterprise-wide memory loads. | SF-1 |
| RT-28 | **Standard Library Ghost Swarm** | The `OntologyMapper` MUST detect and silently drop `CALLS` edges pointing to native language standard libraries (e.g., `sys.stdlib_module_names`) to prevent millions of useless nodes. | SF-1 |
| RT-29 | **Metadata Key Obfuscation** | The `metadata` JSON blob MUST be strictly validated via Pydantic Discriminated Unions per `NodeKind`. Unstructured `Dict[str, Any]` is forbidden. Unrecognized keys must be silently dropped to prevent data smuggling. | SF-1 |
| RT-30 | **Local Context YAML Poisoning** | The Orchestrator MUST validate the local `context.yaml` `service_name` against the global `~/.specweaver/specweaver.db` registry on boot to prevent rogue agents from hijacking other microservice namespaces, before passing the validated name to the GraphRepository. | SF-3 |
| RT-31 | **Parallel Query Exhaustion** | The `InMemoryGraphEngine` MUST use an async `Semaphore` to limit concurrent subgraph extractions (e.g., max 3) to prevent LLM loops from triggering an OOM crash via parallel `NetworkX` instances. | SF-1 |
| RT-32 | **Polyglot Ghost Blindspot** | Language-specific AST parsers (`D-SENS-02`) MUST provide standard library exclusion Regexes (e.g., `^java\..*`) to the `OntologyMapper` because the Python `sys` module cannot identify Java/Go/Rust built-ins. | SF-1 |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Knowledge Graph Querying | How to extract context using the `NetworkX` wrapper | 🟩 Completed (`docs/dev_guides/knowledge_graph_querying.md`) |
| OntologyMapper Integration | Documentation on how to map a new language's Tree-Sitter CST to the Universal Graph Ontology | 🟩 Completed (`docs/dev_guides/ontology_mapping.md`) |

## Core Data Model & Ontology

To prevent contextual handoff failures between implementation agents, the Knowledge Graph MUST strictly adhere to this universal ontology. Raw Tree-Sitter CST nodes must be translated into these constraints before ingestion.

### Allowed Node Types
*   `FILE`: A physical source code file.
*   `DATA_STRUCTURE`: A Class, Struct, Interface, Trait, or ORM Model.
*   `PROCEDURE`: A Function, Method, Lambda, or Receiver.
*   `STATE`: Global variables, Enums, or Class-level attributes (local variables are serialized into procedure metadata).
*   `API_CONTRACT`: Cross-language endpoints (e.g., REST routes, gRPC definitions).
*   `GHOST`: Third-party external dependencies (parsed via package manifests).

### Allowed Edge Types
*   `IMPORTS`: File A imports File B.
*   `CALLS`: Procedure A invokes Procedure B.
*   `IMPLEMENTS`: Data Structure A fulfills Data Structure B (resolves IoC).
*   `CONSUMES` / `FULFILLS`: Service A consumes an `API_CONTRACT` that Service B fulfills.

### Microservice Graph Federation (Future-Proofing)
To support infinite enterprise scaling across massive multi-repo microservices (e.g., US-11 GraphRAG for Brownfield Scale), the Universal Graph must natively support **Graph Federation** (`A-SENS-04`).
Instead of building a single centralized monolithic `graph.db`, each microservice maintains its own local `.specweaver/graph.db` within its own repository.
*   **The System Architecture Graph (The "Outside" Layer)**: There must be one overarching graph layer that links all microservices together *exclusively* via their interfaces (REST APIs, Kafka/RabbitMQ queues, shared file systems) without including *any* of the microservices' internal logic.
    *   **Storage Location**: Because this graph exists "outside" any single microservice, it is NOT stored in a microservice's local DB. It is housed either in the company's central GitOps/Infrastructure repository's `.specweaver/graph.db`, or managed globally in `~/.specweaver/specweaver.db`.
*   **Mandatory ID Prefixing:** To ensure this high-level System Graph can dynamically fuse with local databases without global ID collisions, every single Node ID MUST be prefixed with its microservice identifier (e.g., `billing:ast:1a2b3c4d` instead of just `1a2b3c4d`).
*   **Dynamic Fusing:** In future query pipelines, when the GraphRAG engine hits an external URI in the System Graph, it will dynamically mount the remote SQLite database and fuse the internal subgraphs only when explicit drill-down is requested.

### Monorepo & Strongly Modularized Application Support
For Monorepos (containing multiple microservices) or strongly modularized monoliths, the architecture offers two deployment patterns:
1.  **The Federation Pattern (Multiple DBs):** If the monorepo contains distinct, deployable microservices (e.g., an Nx workspace), best practice is for each microservice folder to maintain its own `.specweaver/graph.db`. This behaves identically to the polyrepo Federation model above, linking via `API_CONTRACT` nodes.
2.  **The Monolith Pattern (Single DB):** For a heavily coupled monolith, the entire codebase is stored within a single `.specweaver/graph.db` at the repository root.
    *   **Internal Boundaries**: Instead of external `API_CONTRACT` nodes, SpecWeaver uses `TOPOLOGY_BOUNDARY` nodes (derived from `context.yaml` rules or module boundaries) to define internal architectural borders.
    *   **Internal Routing**: Subgraphs are isolated at query-time using the `package_name` or `service_name` properties on the `GraphNode`.
    *   **ID Prefixing Still Applies**: Even in a single-DB monolith, the ID prefixing rule (e.g., `monolith:billing:ast:123`) is strictly enforced to ensure the IDs are globally safe if the monolith is ever refactored or communicates with an external microservice.

### SQLite Schema Contract (SF-2)
The `GraphRepository` MUST implement at least this baseline schema to prevent B-Tree fragmentation:
*   `nodes` table: `(id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, name TEXT, semantic_hash TEXT UNIQUE, clone_hash TEXT, file_id TEXT, metadata JSON)`
*   `edges` table: `(source_id INTEGER, target_id INTEGER, type TEXT, metadata JSON, PRIMARY KEY (source_id, target_id, type))`

## Data Lifecycle & Ingestion Flow

To handle continuous codebase evolution (refactoring, file deletions, moving functions) without accumulating "Ghost Nodes" or duplicating data, the graph MUST adhere to this strict lifecycle:

### 1. The Cold Start (Boot)
When SpecWeaver initializes, SF-2 reads the SQLite backup. It cross-references the stored `semantic_hash` of each file against the current filesystem (`A-SENS-01`). 
*   **Match:** The file's subgraph is safely loaded into the in-memory NetworkX engine.
*   **Mismatch / Missing:** The file is flagged as `DIRTY` for re-ingestion.

### 2. The Update Cycle (Node-Level Semantic Diffing)
When a file is flagged as `DIRTY`, the engine avoids rebuilding the entire file's subgraph by using strict semantic diffing:
1.  **Parse & Map:** Extract the fresh AST via `D-SENS-02` and pass it through the `OntologyMapper` to generate the new `GraphNode` objects.
2.  **Hash Diffing:** Compare the `semantic_hash` of the new nodes against the existing nodes stored in memory/SQLite for `file_id = X`.
3.  **Insert (New):** If a new hash appears, INSERT the new node and calculate/insert its edges.
4.  **Purge (Deleted/Ghost):** If a hash exists in the DB but is missing from the new AST (e.g., function was deleted or renamed), DELETE that specific node and sever only its attached edges.
5.  **Preserve (Unchanged):** If the hash matches (e.g., you just added a comment or a blank line elsewhere in the file), DO NOTHING. The existing node and all its inbound/outbound edges remain perfectly intact.

### 3. The Synchronization Cycle (Async Flush)
Once the NetworkX graph is updated, SF-2 asynchronously pushes the new subgraphs to SQLite via an `UPSERT` operation, ensuring the persistent save-state matches memory.

### 4. Handling Refactoring (Moving Functions)
Because the Knowledge Graph relies on `semantic_hash` (A-SENS-01) as the unique identifier rather than arbitrary IDs, moving a function from `auth.py` to `utils.py` without changing its code preserves its hash. 
The Update Cycle will purge it from `auth.py` and re-ingest it into `utils.py`. Any external edges (like `CALLS`) pointing to that `semantic_hash` will seamlessly reconnect without manual graph patching.

## Sub-Feature Breakdown

### SF-1: In-Memory Knowledge Graph Engine & Enterprise Ontology
- **Scope**: Parses AST dictionaries via the `OntologyMapper`, applies semantic hashes, and builds the primary in-memory `NetworkX` graph. Resides entirely in `src/specweaver/graph/` (pure-logic). It is blind to the filesystem, the database, and the AST parser. It only accepts raw JSON dicts passed down from the orchestrator. Expands the ontology to capture macro-architectural boundaries as Edges. Exposes the read query API.
- **FRs**: [FR-1, FR-2, FR-6, FR-7, EXP-1]
- **Inputs**: Raw JSON dictionaries (AST data, topology data) passed via orchestration.
- **Outputs**: Expanded `GraphNode` schema, new Edge types, in-memory `NetworkX` graph, and `.graphml` export.
- **Depends on**: none
- **Impl Plan**: ⬜

### SF-2: Persistent Storage Adapter (SQLite)
- **Scope**: Creates the new `src/specweaver/graph_store/` (adapter) module. This is completely isolated from `config/` to keep structural graph data separate from application settings. Implements the `GraphRepository` adapter. Promotes `service_name` and `package_name` to explicit, indexed DB columns to prevent Context Window collapse. Handles asynchronous flush/load of the `NetworkX` graph.
- **FRs**: [FR-3, FR-6]
- **Inputs**: In-memory `NetworkX` graph.
- **Outputs**: `ProjectDatabase` SQLite connection object targeting `.specweaver/graph.db`.
- **Depends on**: [SF-1]
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_sf2_implementation_plan.md

### SF-3: Graph Builder Orchestration & Harmonization
- **Scope**: Creates the new `src/specweaver/graph/core/builder/` (orchestrator) module to coordinate the new sensor triad. First, it implements the pipeline to extract the AST via a generic AST-to-Dict adapter (wrapping `workspace.parsers`), injecting this adapter into the `GraphBuilder` orchestrator at the CLI root to maintain strict domain boundaries. The orchestrator enforces ID Prefixing (e.g., `monolith:billing:ast:<hash>`) across the `InMemoryGraphEngine` and `graph_store/`.
  Second, it aggressively refactors the project's existing legacy graphs to use this exact same triad by establishing feature-specific graph sub-modules:
  1. **Topology Graph (`D-SENS-01`)**: Migrates pure graph math (Tarjan's, cycle detection) from `src/specweaver/assurance/graph/topology.py` into a new `specweaver.graph.topology` module. `assurance` delegates to this module for computation.
  2. **Lineage Graph (`B-SENS-01`)**: Migrates the SQLite `artifact_events` table schema out of `config/database.py` and the tree-traversal math out of `cli/lineage.py` into a new `specweaver.graph.lineage` module. The CLI remains a thin router.
- **FRs**: [FR-1, FR-6]
- **Inputs**: File system paths, legacy graph generators.
- **Outputs**: Harmonized pipeline orchestrating AST/Topology extraction into the SQLite DB.
- **Depends on**: [SF-1, SF-2]
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_sf3_implementation_plan.md
- **Technical Debt Spawns**:
  - `TECH-02`: Structural Refactoring of Workspace AST Module (Extracting `workspace.parsers` to `workspace.ast.parsers`).
  - `TECH-03`: Architectural Analysis & Refactoring of `sw graph build` CLI (Moving orchestration to `GraphBuildAtom`).

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)
3. SF-3 (depends on SF-1, SF-2)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | In-Memory Graph Engine & Enterprise Ontology | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Persistent Storage Adapter | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-3 | Graph Builder Orchestration & Harmonization | SF-1, SF-2 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: SF-3 Commit Boundary 3 and Commit Boundary 4 are **COMPLETED**.
**Next step**: 
1. Proceed to the next feature in the active routing queue.
