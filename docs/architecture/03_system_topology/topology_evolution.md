# Architecture Concept: Hybrid GraphRAG and Topological Evolution

**Status:** concept, April 2026. Evolution of Feature 3.33, inspired by structural analysis models
(e.g., Graphify). As of 2026-09-25 only the NetworkX graph engine exists in code
(`graph/core/engine/`); centrality, God Nodes, Leiden, Rocket Mode and inferred edges are not built.

## The idea

SpecWeaver captures code structure as an explicit graph, not as vector embeddings. Graph traversal (BFS) is
the primary lookup; vectors are a secondary semantic fallback.

**Why not vector-only Code-RAG** (Chroma, pgvector): chunking destroys exact logical boundaries
(e.g., AST bounds), so retrieval breaks on large codebases.

## 1. Feature 3.32f: Knowledge Graph Builder & Persistence

- Extract AST logic (classes/functions) and build the graph.
- **Persist** the graph to local specweaver.db (SQLite) at extraction.
- On boot, deserialize the edges into a NetworkX in-memory object for traversal — no rebuild from
  source on every startup.

This must exist before database providers can be abstracted.

## 2. Feature 3.33 Framework: Topology Provider Abstraction (Bicycle vs Rocket Mode)

| Mode | Mechanism | Strength | Limit |
|---|---|---|---|
| **Bicycle** (SQLite/BM25 local persistence) | Persistent `SQLite/BM25` baseline plus an **in-memory graph** (`NetworkX` or `rustworkx`) populated per query bounds | Local ASTs in RAM: instant BFS, community clustering, network-flow math, no disk I/O | Fails across large polyglot microservice boundaries spread over separate repositories |
| **Rocket** (PostgreSQL + Apache AGE + pgvector) | Persistent server database | `Apache AGE` (Cypher on Postgres) for cross-service cluster analysis and edge walking; `pgvector` only as supplemental lookup for fuzzy logic the AST does not map | — |

## 3. Degree Centrality and "God Nodes" (Feature 3.38)

- **Metric:** Degree Centrality of a node = incoming call edges + outgoing dependency edges. Replaces
  the AI guessing which context files weigh most.
- **"God Nodes":** the top-ranked nodes, flagged explicitly. Changing them causes large ripple effects.
- **Visualization:** `sw graph` renders a standalone `.html` graph (PyVis/D3.js). Engineers drag,
  zoom and spot community clusters and God Nodes locally, without the Heavy Dashboard API.

## 4. Leiden Community Clustering

Picking the right set of `context_files` for a prompt is hard. BFS expansion enables clustering
(e.g., Leiden detection) on topological dependencies, so the LLM gets `context_files` that share a
"neighborhood" of real dependencies, not just similar names.

## 5. Multi-Modal Edges & Reverse-Weaving (Feature 3.43)

Tree-sitter gives precise extracted edges between code files. Architecture knowledge outside code
needs a second edge kind.

- **Inputs:** whiteboard diagrams, PDFs and Markdown docs, through Vision/LLM extractors.
- **Inferred edges:** LLM evaluations inject these concepts into the Postgres/NetworkX graph, with
  edges tagged `[semantically_similar]` or `[inferred]`. Humans and agents can tell AST fact from
  AI inference.
- **Application:** Feature 3.43 (Reverse-Weaving) — drop legacy diagrams into the CLI to bootstrap
  raw implementations.
