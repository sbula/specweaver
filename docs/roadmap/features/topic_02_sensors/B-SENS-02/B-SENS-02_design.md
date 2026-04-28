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
| FR-4 | Dataflow Chains | Graph Builder | Executes Round-Robin solver | Def-Use edges are calculated and stored |
| FR-5 | Control Flow | Graph Builder | Executes Visitor Pattern | Execution branches (True/False edges) are stored |
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

## Security & Red Team Mitigations

| # | Vulnerability | Mitigation Strategy | Assigned Sub-Feature |
|---|---------------|---------------------|----------------------|
| RT-1 | **SQL Injection (AST Poisoning)** | 100% parameterized queries (`?` bindings) required for all inserts. Raw AST string concatenation is forbidden. | SF-1 |
| RT-2 | **AST Bomb (Stack Overflow)** | Strict recursion depth bounds (e.g., `MAX_AST_DEPTH = 500`). Graceful failure with `is_partial=True` flag. | SF-3 & SF-4 |
| RT-3 | **Ghost Node Spoofing** | Prioritize internal `D-SENS-01` topology resolution over package manifest resolution to prevent attackers from spoofing internal RPCs. | SF-2 |
| RT-4 | **SQLite Lock Contention** | Enable `PRAGMA journal_mode=WAL;` and exponential backoff retries for concurrent multi-agent graph updates. | SF-1 |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Knowledge Graph Querying | How to extract context using the `NetworkX` wrapper | ⬜ To be written during Pre-commit |
| OntologyMapper Integration | Documentation on how to map a new language's Tree-Sitter CST to the Universal Graph Ontology | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: Local Project Database Engine
- **Scope**: Implements the SQLite schema and connection manager for `.specweaver/graph.db`.
- **FRs**: [FR-3]
- **Inputs**: File system paths from workspace root.
- **Outputs**: `ProjectDatabase` connection object.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_sf1_implementation_plan.md

### SF-2: NetworkX Integration & Node Deduplication
- **Scope**: Parses AST dictionaries, applies semantic hashes (and experimental structural hashes), and exposes the read query and GraphML export APIs.
- **FRs**: [FR-1, FR-2, FR-6, FR-7, EXP-1]
- **Inputs**: AST output from `D-SENS-02`.
- **Outputs**: `NetworkX` `DiGraph` instance and `.graphml` export.
- **Depends on**: [SF-1]
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_sf2_implementation_plan.md

### SF-3: Control Flow Visitor Pattern
- **Scope**: Maps the explicit execution branches (True/False edges) between nodes.
- **FRs**: [FR-5]
- **Inputs**: Raw AST control flow structures (if/else/while).
- **Outputs**: Directed edges in the SQLite database.
- **Depends on**: [SF-2]
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_sf3_implementation_plan.md

### SF-4: Round-Robin Dataflow Solver
- **Scope**: Computes the variable Def-Use chains across scope boundaries using Kildall's iterative framework.
- **FRs**: [FR-4]
- **Inputs**: Variable declarations and usage nodes.
- **Outputs**: Dataflow edges in the SQLite database.
- **Depends on**: [SF-2]
- **Impl Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_sf4_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)
3. SF-3 and SF-4 in parallel (both depend only on SF-2)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Local Project DB | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-2 | NetworkX Integration | SF-1 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-3 | Control Flow Visitor | SF-2 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-4 | Dataflow Solver | SF-2 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design APPROVED.
**Next step**: Start implementation planning by running:
`/implementation-plan docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_design.md SF-1`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
