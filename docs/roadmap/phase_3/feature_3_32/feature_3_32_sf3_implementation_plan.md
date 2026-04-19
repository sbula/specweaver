# Implementation Plan: Deep Semantic Hashing [SF-3: Incremental Topology Crawler]
- **Feature ID**: 3.32
- **Sub-Feature**: SF-3 — Incremental Topology Crawler
- **Design Document**: docs/roadmap/phase_3/feature_3_32/feature_3_32_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_32/feature_3_32_sf3_implementation_plan.md
- **Status**: IMPLEMENTED

## 1. Sub-Feature Scope & Requirements
Modifies the `TopologyGraph` core engine to proactively evaluate Semantic Merkle trees. Rather than downstream execution plugins parsing OS boundaries repeatedly, the graph becomes contextually aware of mathematically "stale" components, enabling incremental loop bypassing across the ecosystem.
- **FR-3:** Detects mismatches between disk `mtime`/semantic hashes and the cache. Recursively invalidates upward consumers using `_reverse` adjacencies, explicitly tagging only stale nodes.

## 2. Resolving HITL Decisions & Implications (Phase 4 Merge)

During the Phase 4 HITL Gate, 3 critical architectural shifts were approved regarding how staleness interacts with the rest of the SpecWeaver ecosystem:

1. **Statefulness Injection (`stale_nodes`)**: Rather than making clients compute sub-graphs, `TopologyGraph` will explicitly surface a `self.stale_nodes: set[str]` property representing the temporal diff between the Merkle cache and the exact disk state. 
2. **Auto-Inference Injection**: `TopologyGraph.from_project(auto_infer=True)` will feed virtually inferred `context.yaml` boundaries directly into the `DependencyHasher` alongside static physical directories, generating Merkle roots that encompass 100% of the mapped codebase.
3. **Total Mismatch Fallback (Zero-Trust)**: If the `.specweaver/topology.cache.json` is missing or fully deleted, the crawler will safely default to a 100% stale state, flagging every node natively.

> [!CAUTION]
> **IMPLICATION: THE CACHE-FLUSH DILEMMA**
> **You MUST NOT auto-flush the cache within the Topology instantiation loop.**
> If `TopologyGraph.from_project()` instantly overwrites the semantic cache after checking for mismatches, the baseline is lost. The very next `QARunner` pipeline initializing the graph 1 millisecond later will see zero differences, flag everything as clean, and bypass the validation pipeline entirely.
> **Constraint:** The Topology engine ONLY calculates staleness. Writing the cache must remain explicitly externalized (deferred to the downstream orchestrator/runners upon successful pipeline culmination).

## 3. Technical Modifications

### A. Graph Invalidation Engine (`src/specweaver/assurance/graph/topology.py`)
[MODIFY] `src/specweaver/assurance/graph/topology.py`

**Purpose**: Augment the graph initialization sequence (`from_project()`) to internally compute semantic hashes via `DependencyHasher`, diff against the legacy cache, and expose the impact blast-radius as `graph.stale_nodes`.

**Key Additions:**
1. **Property Exposure**: Add `self.stale_nodes: set[str]` to the `TopologyGraph` `__init__`.
2. **Hasher Hooks**: Internally initialize `DependencyHasher(project_root)` in `from_project()`. Fetch the existing topological state via `load_cache()`.
3. **Manifest Compilation**: Gather all located (and auto-inferred) `context.yaml` directories as target manifests.
4. **Invalidation Algorithm (FR-3)**:
   - Call `hasher.compute_hashes(manifests)`.
   - Iterate over the new target hashes. If a module's `semantic_hash` differs from the `load_cache()` mapping (or does not exist), add the module to an internal `stale_seeds: set[str]`.
   - If the loaded cache was completely empty `{}` (no file exists), flag `stale_seeds = set(nodes.keys())`.
   - Construct the final `stale_nodes` property by passing `stale_seeds` through the existing recursive Tarjan reverse-adjacency lookup. For each seed module, trace `self.impact_of(seed)` and union the output to `stale_nodes`.

## 4. Verification Constraints
- **Test Matrix (`tests/unit/assurance/graph/test_topology.py` & `test_topology_staleness.py`)**:
  - Test exactly 1 missing cache fallback (all nodes flag stale).
  - Test exactly 1 mutated node cleanly flagging exactly its 3 direct/transitive upstream consumers via `impact_of` without crashing.
  - Test validation that the `TopologyGraph` actively *returns* cleanly without attempting to invoke `DependencyHasher.save_cache()`.
  
### HITL Test Matrix Revisions:
- Included **Edge Case Protection**: Tests confirming dynamic nodes injected without `yaml_path` safely skip the topology crawler checking.
- Included **Tombstone Protection**: Added logic parsing missing `nodes` mapping compared to `context.yaml#consumes` to successfully bubble up staleness when dependencies are deleted.
- Extracted staleness tests to `tests/unit/assurance/graph/test_topology_staleness.py` to adhere to maximum file size limits.
