# Knowledge Graph Querying

The graph boundary is strictly governed by the `GraphEngineProtocol`. Whether you are backed by the
`InMemoryGraphEngine` (NetworkX) or the future `RustGraphEngine` (petgraph via PyO3), all operations
use **semantic hash strings** as native Node IDs. Integer IDs are strictly prohibited outside the
repository storage layer.

## GraphEngineProtocol
Any engine powering the platform must adhere to this standard contract:

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

## Every Edge Carries Its Kind

An edge's kind lives on the networkx edge attribute named by `EDGE_KIND_ATTR`, which the engine, the
store and the loader all import rather than spell. It is one of the nine `EdgeKind` members; the
store **refuses** an edge that carries no kind rather than supplying one.

```python
from specweaver.graph.core.engine.models import EDGE_KIND_ATTR
from specweaver.graph.core.engine.ontology import EdgeKind

graph = engine.export_semantic_digraph()
calls = [
    (u, v) for u, v, data in graph.edges(data=True)
    if data.get(EDGE_KIND_ATTR) == EdgeKind.CALLS.value
]
```

Never read the attribute by literal name. The `graph_edges` **column** is called `type` because it
is part of the primary key, and reading the column's name off a graph is what caused the two
`TECH-068` defects the anti-patterns list records.

A build of `src/specweaver` (358 files) produces roughly **9,100 `CALLS`, 2,700 `CONTAINS`, 2,270
`IMPORTS` and 340 `EXTENDS`** edges, plus about 990 ghosts.

## Ghost Targets Are Answers, Not Failures

An edge whose target is not something the build parsed still exists, pointing at a `GHOST` node. So
a traversal returning nothing means *nothing depends on this*, and never *what depends on it was
outside what we parsed*. Ambiguity ghosts too: a name declared in two files is not one thing, and a
reader following an invented dependency is worse served than one seeing a visible unknown.

Ghost namespaces are separate per kind — a module, a type and a procedure sharing a name are three
different unknowns. See `docs/dev_guides/ontology_mapping.md` for the resolution rules and for the
one known gap: the unresolved raw name does not yet reach the edge's metadata.

## Basic Subgraph Querying
The most common operation is extracting a localized subgraph around a specific node (e.g., a modified file or a newly discovered function) using its semantic hash.

```python
from specweaver.graph.core.engine.protocol import GraphEngineProtocol

# Query a 3-hop subgraph around a specific semantic hash string
# (Note: extract_subgraph now raises NodeNotFoundError if the hash does not exist)
semantic_digraph = engine.extract_subgraph(start_hash="default:a3f8c1e2...", depth=3)
```

## Naming Conventions
To maintain type safety and avoid ID confusion, strict naming rules apply:
1. `engine` ALWAYS means an implementation of `GraphEngineProtocol`.
2. Any variable holding a NetworkX graph with semantic hash keys MUST be named `semantic_digraph` (never `graph`, `nx_graph`, or `db_digraph`).

## GraphML Serialization
To pass graph data to LLM agents or external tools, serialize the subgraph to GraphML format.

```python
from specweaver.graph.core.builder.orchestrator import GraphBuilder

# Serializes the entire graph to disk with strict Path Traversal bounds
# Assumes 'engine' implements GraphEngineProtocol
builder = GraphBuilder(engine)
builder.export_graph_to_disk(workspace_root="/workspace", output_name="out")
```
