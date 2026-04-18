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
- **Available Tooling:** `LanguageAnalyzer.extract_imports()` already natively exists inside `specweaver/workspace/context/analyzers.py` and is fully competent at extracting structural AST imports across bounds.
- **Architectural Rules:** Because `assurance/graph/context.yaml` explicitly consumes `specweaver/context` (which represents `workspace/context`), we can legally use the `LanguageAnalyzer` inside the graph module without violating the `pure-logic` or `loom/*` isolation boundaries!

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
| AD-3 | Rocket Mode Backlog (Feature 3.33) | Hardcoded strictly to "Bicycle Mode" (flat-files). Massive Monorepo topologies (100+ services) will utilize Feature 3.33 later to swap this layer out for 'Rocket Mode' Sidecar databases (Falkor/Vector). | No |
| AD-4 | Leverage `LanguageAnalyzers` | Reuses existing AST parsing logic inside `workspace/context` to map semantic dependencies, preventing code duplication natively. | No |

## Sub-Feature Breakdown

### SF-1: Semantic State caching (DependencyHasher)
- **Scope**: Implements a dedicated utility for computing and persisting shallow and structural Merkle dependencies targetting `<project_root>/.specweaver/topology.cache.json`. **MUST** securely inject `/.specweaver/` into the `.gitignore` to prevent tracking pollution!
- **FRs**: [FR-1, FR-2]
- **Inputs**: OS file chunks, extracted string imports.
- **Outputs**: Serialized pure-data cache map.
- **Depends on**: none

### SF-2: Incremental Topology Crawler
- **Scope**: Modifies `topology.py` `TopologyGraph.from_project()` to actively diff against the Semantic Cache, applying subtree invalidations natively instead of global recursive parsing.
- **FRs**: [FR-3]
- **Inputs**: Semantic Cache map.
- **Outputs**: Instantiated TopologyGraph.
- **Depends on**: [SF-1]

## Execution Order
1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Semantic State Caching | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-2 | Incremental Topology | SF-1 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design completed and officially APPROVED by HITL.
**Next step**: Run `/implementation-plan docs/roadmap/phase_3/feature_3_32/feature_3_32_design.md`
