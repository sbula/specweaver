# A-SENS-01 SF-03 — Incremental Topology Crawler

**Status**: IMPLEMENTED · **Feature ID**: 3.32 · **FRs owned**: FR-3 · **Depends on**: SF-02 ·
Design: [A-SENS-01_design.md](A-SENS-01_design.md) §Sub-features → SF-03

## Goal

`TopologyGraph` evaluates the semantic Merkle tree itself and knows which components are "stale",
so downstream plugins can skip clean ones instead of each re-parsing the tree.

- **FR-3:** detect mismatches between disk `mtime`/semantic hashes and the cache; invalidate upward
  consumers via `_reverse` adjacencies; tag only stale nodes.

## Where it plugs in

`src/specweaver/assurance/graph/topology.py` — `from_project()` computes hashes via
`DependencyHasher`, diffs against the previous cache, and exposes the blast radius as
`graph.stale_nodes`.

## Changes

1. **Property**: `self.stale_nodes: set[str]` on `TopologyGraph` `__init__`.
2. **Hasher hook**: `from_project()` creates `DependencyHasher(project_root)` and reads the previous
   state via `load_cache()`.
3. **Manifests**: all located (and auto-inferred) `context.yaml` directories.
4. **Invalidation (FR-3)**:
   - call `hasher.compute_hashes(manifests)`;
   - a module whose `semantic_hash` differs from the `load_cache()` mapping, or is absent, goes into
     `stale_seeds: set[str]`;
   - loaded cache empty `{}` (no file) → `stale_seeds = set(nodes.keys())`;
   - `stale_nodes` = union of `self.impact_of(seed)` for each seed (the existing recursive Tarjan
     reverse-adjacency lookup).

> [!CAUTION]
> **Never flush the cache inside `TopologyGraph.from_project()`.** If it overwrote the cache after
> diffing, the next `QARunner` building the graph 1 millisecond later would see no difference, flag
> everything clean and skip validation. The topology engine ONLY calculates staleness; writing the
> cache belongs to the downstream orchestrator, after a successful pipeline (SF-04).

## Tests

`tests/unit/assurance/graph/test_topology.py` and `test_topology_staleness.py`:

| Case | Proves |
|---|---|
| missing cache | all nodes flagged stale |
| exactly 1 mutated node | exactly its 3 direct/transitive upstream consumers flagged via `impact_of` |
| `from_project` returns | `DependencyHasher.save_cache()` is never invoked |
| dynamic node without `yaml_path` | skipped by the crawler, no crash |
| dependency deleted (tombstone) | missing `nodes` entry vs `context.yaml#consumes` bubbles staleness up |

Staleness tests live in `tests/unit/assurance/graph/test_topology_staleness.py` to respect the
maximum file size.

## Decisions (audit)

1. **`stale_nodes` on the graph**: `TopologyGraph` exposes `self.stale_nodes: set[str]` — the diff
   between the Merkle cache and disk — instead of clients computing sub-graphs.
2. **Auto-inference included**: `TopologyGraph.from_project(auto_infer=True)` feeds inferred
   `context.yaml` boundaries into `DependencyHasher` alongside static directories, so the Merkle
   roots cover 100% of the mapped codebase.
3. **Total mismatch fallback (zero-trust)**: `.specweaver/topology.cache.json` missing or deleted →
   100% stale; every node flagged.
