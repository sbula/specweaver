# Implementation Plan: The Knowledge Graph Emits One of Its Nine Declared Edge Kinds [SF-01: Close the edge-write traps]

- **Feature ID**: TECH-068
- **Sub-Feature**: SF-01 — Close the edge-write traps
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-068/TECH-068_sf01_implementation_plan.md
- **Status**: APPROVED (2026-08-21)

## Scope

`FR-14` (every edge carries its kind explicitly) and `FR-16` (an edge the rebuilt graph no longer
holds is deleted). No dependencies. Both must close before any sub-feature writes a new edge kind.

## Research Notes

### The design understates `FR-14`. It is not a latent trap — it is firing now.

`InMemoryGraphEngine.add_edge` stores the kind under **`kind`**:

```python
self._nx_graph.add_edge(edge.source_hash, edge.target_hash, kind=edge.kind.value)   # core.py:40
```

`persist_semantic_digraph` reads **`type`**:

```python
edge_batch.append((source_id, target_id, data.get("type", "CALLS"), meta_str))       # repository.py:165
```

Different keys, so the fallback fires on every edge. **Measured**: a real build of
`src/specweaver/graph` persisted **108 edges, all typed `CALLS`** — and every one of them is a
`CONTAINS` edge. The persisted graph today claims a call graph it does not have and holds zero
`CONTAINS` rows.

This corrects the design's Problem Statement, which says the mapper "emits `CONTAINS` and nothing
else". That is true in memory and false in the database.

### Why no test caught it

Every test in `tests/unit/graph/core/store/test_repository_flush.py` hand-builds its `nx.DiGraph`
with `type="CALLS"` — the store's own key — rather than going through the engine. The tests assert
the store's convention against itself and cannot observe the mismatch. `test_repository_flush.py`
lines 28, 81, 144, 175 all do this.

**Consequence for the test plan**: the `FR-14` proof must construct edges through
`InMemoryGraphEngine.add_edge` with a real `GraphEdge`, never by hand. A hand-built graph reproduces
the blind spot.

### `FR-16` is also `FR-14`'s migration path

`graph_edges` has `PRIMARY KEY (source_id, target_id, type)`. Fixing the key mismatch alone does not
repair an existing database: a corrected `CONTAINS` row is a *new* primary key, so the wrong `CALLS`
row survives beside it. `FR-16` deleting edges the rebuilt graph no longer holds is what removes
them on the next build. The two FRs are ordered within the boundary for that reason.

### Surfaces this plan touches

| Symbol | Signature as it exists | File |
|---|---|---|
| `persist_semantic_digraph` | `(self, semantic_digraph: nx.DiGraph) -> None` | `graph/core/store/repository.py` |
| `_extract_nodes` | `(self, nx_graph: nx.DiGraph) -> tuple[list[Any], list[Any]]` | same |
| `add_edge` | writes `kind=edge.kind.value` onto the nx edge | `graph/core/engine/core.py:40` |
| `GraphEdge` | `{source_hash: str, target_hash: str, kind: EdgeKind}` | `graph/core/engine/models.py:44` |
| `graph_edges` | `(source_id, target_id, type, metadata)`, PK on the first three | `repository.py:81` |

### Constraints carried in

- `graph/core/store` `context.yaml` allows `sqlite3`; the engine forbids it. Deletion logic belongs
  in the store, never in the engine.
- Chunk every write at 5,000 rows (RT-4). The existing loops already do; a new `DELETE` must too.
- Nodes are tombstoned, never deleted (RT-13). **Edges are not nodes** — `FR-16` deletes rows,
  because an edge has no identity to resurrect and a tombstoned edge column does not exist.

## Commit Boundaries

### CB-1 — The persisted edge kind is the edge's kind

**Proves**: `FR-14`
**Tier**: integration. The claim spans the engine and the store — the two disagree, and a unit test
on either alone is what hid the defect for the life of the feature.

1. Write the failing test first: build a graph through `InMemoryGraphEngine.add_edge` with a
   `GraphEdge` whose kind is `CONTAINS`, persist it, read `graph_edges.type` back. It reports
   `CALLS` today. **That red is the evidence this boundary exists.**
2. Make the store read the key the engine writes, and **remove the fallback** so an edge with no
   kind raises rather than inventing one. Pseudocode, in order:
   - read the kind from the edge's attributes;
   - if absent → raise, naming the edge, rather than substituting a default;
   - write it into the existing `type` column.
3. The column name does not change. `type` is part of the primary key, so renaming it means a
   migration this boundary does not need.

**Done when**: the test is green **and** this mutant is killed —
`--old 'data.get("kind")' --new 'data.get("kind", "CALLS")'` restores the fallback and the test must
go red.

### CB-2 — An edge the graph no longer holds is gone

**Proves**: `FR-16`
**Tier**: integration. The claim is about what survives a persist cycle, which only the store and a
real database can answer.

1. Write the failing test first: persist a graph containing `a→b`, persist the same graph without
   that edge, assert the row is gone. It survives today. **Red before green.**
2. Clear the outgoing edges of the nodes being written, then insert. Pseudocode, in order:
   - for the nodes in this write, delete their edge rows, chunked against SQLite's variable limit;
   - then insert, as now.

   **Corrected during development.** This step originally specified a diff — read what the database
   holds, delete only what the incoming graph has dropped. A mutation pass showed the difference is
   not observable: the insert that follows restores everything still held, so ignoring the diff
   entirely changed no test. Two mutants survived against it. Clear-then-insert is the same
   behaviour with a branch removed, and all three mutants against it are killed.
3. Scope the deletion to the nodes in this write. A global diff would delete another service's
   edges, because `graph_edges` carries no `service_name` of its own.

**Done when**: the test is green **and** this mutant is killed — neutralise the delete so it removes
nothing, and the test must go red.

### CB-3 — The blind spot cannot regrow

**Proves**: `FR-14` (guard)
**Tier**: unit.

1. A test asserting that the store reads the same attribute key the engine writes, so the two cannot
   drift apart again silently. This is the guardrail the ticket ships with its fix.

**Done when**: the test is green **and** changing either side's key makes it red.

## Test Plan

| Test | Tier | Proves | Goes red because |
|---|---|---|---|
| edge kind survives engine → store | integration | FR-14 | the store reads `type`, the engine writes `kind` |
| an edge with no kind is refused | unit | FR-14 | today a missing kind silently becomes `CALLS` |
| a removed edge does not survive a re-persist | integration | FR-16 | nothing deletes edges |
| deletion does not cross service boundaries | integration | FR-16 | the new delete could over-reach |
| engine and store agree on the attribute key | unit | FR-14 | the guard against regrowth |

Four buckets: happy path (kind round-trips), boundary (empty edge set, an edge with no kind),
graceful degradation (a database with pre-existing wrong rows is corrected by the next build),
hostile input (an edge whose kind is not a member of `EdgeKind`).

## Non-Goals

- Any new edge kind. `SF-02` onwards owns those.
- Renaming the `type` column, which is part of the primary key.
- Tombstoning edges. Nodes are tombstoned by RT-13; an edge has no identity to resurrect.
- Repairing existing databases by migration. `FR-16` corrects them on the next build.
