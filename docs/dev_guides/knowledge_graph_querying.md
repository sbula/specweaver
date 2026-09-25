# Knowledge Graph Querying

Use when: code reads or writes the knowledge graph through an engine.

`GraphEngineProtocol` is the only graph boundary. Every engine, today `InMemoryGraphEngine`
(NetworkX), later `RustGraphEngine` (petgraph via PyO3), uses **semantic hash strings** as Node IDs.
Integer IDs are prohibited outside the repository storage layer.

## Rules

1. `engine` ALWAYS means an implementation of `GraphEngineProtocol`.
2. A variable holding a NetworkX graph with semantic hash keys MUST be named `semantic_digraph`
   (never `graph`, `nx_graph`, or `db_digraph`).
3. Read an edge's kind through `EDGE_KIND_ATTR`, never by literal name (see Edge kinds).

## The protocol

```python
from typing import Protocol
import networkx as nx

class GraphEngineProtocol(Protocol):
    def upsert_node(self, node: GraphNode) -> None: ...
    def upsert_edge(self, edge: GraphEdge) -> None: ...
    def remove_node(self, semantic_hash: str) -> None: ...
    def remove_edge(self, source_hash: str, target_hash: str) -> None: ...
    def get_nodes_for_file(self, file_id: str) -> set[str]: ...
    def get_edges_involving(self, semantic_hashes: set[str]) -> set[tuple[str, str]]: ...
    def export_semantic_digraph(self) -> nx.DiGraph: ...
    def load_semantic_digraph(self, semantic_digraph: nx.DiGraph) -> None: ...
    def extract_subgraph(self, start_hash: str, depth: int) -> nx.DiGraph: ...
    def to_graphml_string(self) -> str: ...
    def clear_cache(self) -> None: ...
```

## Edge kinds

The kind is on the networkx edge attribute named by `EDGE_KIND_ATTR`, imported (never spelled) by
engine, store and loader. It is one of the nine `EdgeKind` members. The store **refuses** an edge
without a kind; it never supplies one.

```python
from specweaver.graph.core.engine.models import EDGE_KIND_ATTR
from specweaver.graph.core.engine.ontology import EdgeKind

graph = engine.export_semantic_digraph()
calls = [
    (u, v) for u, v, data in graph.edges(data=True)
    if data.get(EDGE_KIND_ATTR) == EdgeKind.CALLS.value
]
```

Trap: the `graph_edges` **column** is called `type` (it is part of the primary key). Reading the
column's name off a graph caused the two `TECH-068` defects in the anti-patterns list.

Scale: a build of `src/specweaver` (358 files) yields roughly **9,100 `CALLS`, 2,700 `CONTAINS`,
2,270 `IMPORTS` and 340 `EXTENDS`** edges, plus about 990 ghosts.

## Ghost targets are answers

An edge to something the build did not parse still exists and points at a `GHOST` node. An empty
traversal therefore means *nothing depends on this*, never *what depends on it was outside what we
parsed*.

- Ambiguous names ghost too: a name declared in two files is not one thing, and a visible unknown
  serves a reader better than an invented dependency.
- One ghost namespace per kind: a module, a type and a procedure sharing a name are three unknowns.

Resolution rules and the one known gap (the unresolved raw name does not yet reach the edge's
metadata): `docs/dev_guides/ontology_mapping.md`.

## Subgraph query

The common case: a localized subgraph around one node (e.g. a modified file or a newly discovered
function), by semantic hash.

```python
from specweaver.graph.core.engine.protocol import GraphEngineProtocol

# Query a 3-hop subgraph around a specific semantic hash string
# (Note: extract_subgraph now raises NodeNotFoundError if the hash does not exist)
semantic_digraph = engine.extract_subgraph(start_hash="default:a3f8c1e2...", depth=3)
```

## GraphML export

To hand graph data to LLM agents or external tools, serialize to GraphML.

```python
from specweaver.graph.core.builder.orchestrator import GraphBuilder

# Serializes the entire graph to disk with strict Path Traversal bounds
# Assumes 'engine' implements GraphEngineProtocol
builder = GraphBuilder(engine)
builder.export_graph_to_disk(workspace_root="/workspace", output_name="out")
```
