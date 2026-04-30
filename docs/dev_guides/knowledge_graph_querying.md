# Knowledge Graph Querying

The `InMemoryGraphEngine` provides a thread-safe, mathematically isolated `NetworkX` graph representation of the workspace.

## Basic Subgraph Querying
The most common operation is extracting a localized subgraph around a specific node (e.g., a modified file or a newly discovered function).

```python
from specweaver.graph.engine import InMemoryGraphEngine

# Query a 3-hop subgraph around a specific integer node ID
subgraph = engine.query_subgraph(target_node_id=142, depth=3)
```

## The Microservice Firewall
When building polyglot microservices, you want to prevent contextual pollution. The engine provides a `whitelist_namespaces` capability that automatically prunes `APPLICATION` and `IMPLEMENTATION` details belonging to foreign microservices, while preserving `API_CONTRACT` edges.

```python
# Returns a subgraph that drops implementation details from other services
clean_graph = engine.query_subgraph(
    target_node_id=142, 
    depth=5, 
    whitelist_namespaces=["src/services/billing"]
)
```

## GraphML Serialization
To pass graph data to LLM agents or external tools, serialize the subgraph to GraphML format.

```python
from specweaver.graph.export import export_to_graphml

# Serializes the entire graph to disk with strict Path Traversal bounds
export_to_graphml(engine, target_path="out/graph.graphml", workspace_root="/workspace")
```
