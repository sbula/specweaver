# Design: Deep Semantic Hashing

- **Feature ID**: 3.32
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3_32/feature_3_32_design.md

## Feature Overview

Feature 3.32 introduces "Deep Semantic Hashing" via Merkle-trees to keep SpecWeaver's internal Topology Graph explicitly in sync without performing full project crawls on every initialization.
Instead of relying strictly on full tree parsing, the topology tracks "Dependency Hashes"—meaning a module's hash changes mechanically if and only if its own content changes *or* any of its imported dependencies change. This provides massive speed improvements by isolating AST computations strictly to invalidated branches (incremental crawling).

## Research Findings

### Codebase Patterns
- **Current State:** `TopologyGraph.from_project()` directly executes `rglob` over all bounds recursively building the entire `DependencyGraph` into memory. 
- **Legacy Technical Debt:** `LanguageAnalyzer.extract_imports()` exists in `specweaver/workspace/context/analyzers.py`, but it is heavily tethered to legacy Python `ast` and leaves Java/Kotlin/Rust commented out. To fulfill polyglot semantic hashing, we must adapt the `tree-sitter` pure-logic parsing proven in `core/loom`.
- **Architectural Rules:** Because `assurance/graph/context.yaml` explicitly consumes `specweaver/context` (which represents `workspace/context`), placing hashing logic in `assurance/graph/hasher.py` fully obeys `dmz` L2-L1 topology downward consumption without violating `pure-logic` or `loom/*` isolation boundaries!

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| hashlib | stdlib | `sha256()` | Python |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Merkle Root Generation | DependencyHasher | Combines `sha256` of file contents + Merkle roots of all extracted imports. | Returns a deterministic `semantic_hash` spanning the dependency tree. |
| FR-2 | Cached Adjacency State | TopologyGraph | Reads/Writes `.specweaver/topology.cache.json` containing previously mapped hashes. | Prevents redundant parsing overhead during sequential Agent tasks. |
| FR-3 | Incremental Crawler | TopologyGraph | Detects mismatches between disk `mtime` / semantic hashes and the Cache. | Recursively invalidates upward consumers utilizing `self._reverse` adjacencies, strictly rebuilding only stale nodes. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Speed / Overhead | Graph verification from Cache must complete in under 50ms for a 1,000-module codebase natively. |
| NFR-2 | Architectural Purity | The hashing logic MUST reside natively inside the Topology engine or Workspace layers without bleeding OS boundaries. |

## External Dependencies
None required. Uses native `hashlib` and `json`.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Project-Local Persistence (Bicycle Mode) | Store cache in `.specweaver/topology.cache.json` at the target `project_root`. Inherently survives Docker/Podman transient teardowns because the root is volume-mounted. Perfect native scaling to microservices without polluting the laptop's global environments. | No |
| AD-2 | Automated `.gitignore` Injection | Because AD-1 drops an artifact into legacy projects, SpecWeaver must auto-inject `.specweaver/` into the Gitignore to prevent repository pollution. | No |
| AD-3 | External Semantic Backends (Feature 3.48) | Hardcoded strictly to "Bicycle Mode" (flat-files). A newly postponed feature (3.48) has been explicitly added to the backlog to swap this layer out for 'Rocket Mode' Sidecar databases (Falkor/Neo4j). | No |
| AD-4 | Leverage `LanguageAnalyzers` | Reuses AST parsing logic inside `workspace/context` to map semantic dependencies, preventing code duplication natively. | No |
| AD-5 | Polyglot Tree-Sitter Decoupling | Decouple pure-logic Tree-Sitter models out of the restricted `loom/commons/language` sandbox and into `workspace/parsers/`. This cures massive parallel AST dependencies, enabling 5 languages natively without breaking the rigid L0/L3 architecture bounds. | Yes |

## Sub-Feature Breakdown

### SF-1: Polyglot Parser Decoupling
- **Scope**: Resolves legacy AST technical debt. Extracts `CodeStructureInterface` and language `codestructure.py` out of `loom/commons/language` and moves them downward into `workspace/parsers/`. Upgrades `workspace/context/analyzers.py` to natively utilize these Tree-Sitter engines instead of raw Python `ast`. Updates all imports across `assurance`, `loom`, and `workspace`.
- **FRs**: [NFR-2]
- **Inputs**: Existing tree-sitter bindings.
- **Outputs**: Centralized `workspace/parsers/` domain.
- **Depends on**: none

### SF-2: Semantic State caching (DependencyHasher)
- **Scope**: Implements a dedicated utility for computing and persisting shallow and structural Merkle dependencies targetting `<project_root>/.specweaver/topology.cache.json`. **MUST** securely inject `/.specweaver/` into the `.gitignore` using a tracked comment block to prevent tracking pollution!
- **FRs**: [FR-1, FR-2]
- **Inputs**: OS file chunks, Tree-Sitter extracted dotted imports.
- **Outputs**: Serialized pure-data cache map (with versions and mtime signatures to support NFR-1 incremental speeds).
- **Depends on**: [SF-1]

### SF-3: Incremental Topology Crawler
- **Scope**: Modifies `topology.py` `TopologyGraph.from_project()` to actively diff against the Semantic Cache, applying subtree invalidations natively via Tarjan's SCC cycle-loop breaking instead of global recursive parsing.
- **FRs**: [FR-3]
- **Inputs**: Semantic Cache map.
- **Outputs**: Instantiated TopologyGraph.
- **Depends on**: [SF-2]

## Execution Order
1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)
3. SF-3 (depends on SF-2)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Polyglot Parser Decoupling | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Semantic State Caching | SF-1 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-3 | Incremental Topology | SF-2 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: SF-1 is fully refactored, tests are 100% green, and `tach check` passed natively confirming clean boundary separation. Ready for SF-2.
**Next step**: Research and plan SF-2 (The Dependency Hasher).
