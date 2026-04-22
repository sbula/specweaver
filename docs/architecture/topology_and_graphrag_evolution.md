# Architecture Concept: Hybrid GraphRAG and Topological Evolution

> **Date**: April 2026
> **Context**: Evolution of Feature 3.33 inspired by structural analysis models (e.g., Graphify).
> **Objective**: Definitively establish the SpecWeaver methodology for capturing codebase relationships, proving that explicit Graph Topology surpasses Vector Embeddings for code structures, and outline the multi-modal integration patterns.

## Concept Overview
Traditional Code-RAG relies heavily on Vector Embeddings stored in databases (Chroma, pgvector). This approach fundamentally breaks on large codebases because chunking destroys exact logical boundaries (e.g., AST bounds). 

By leaning into rigorous Graph Theory methodologies, SpecWeaver shifts the anchor from Nearest-Neighbor search to Breadth-First-Search (BFS) structural traversals, only leveraging vectors as a secondary semantic fallback.

## 1. Feature 3.33 Framework: Bicycle vs Rocket Mode
To ensure SpecWeaver's topology operations remain scalable, the backend abstraction is split:

### Bicycle Mode (In-Memory Graphs)
- **Mechanism:** Drops complex recursive SQLite CTE graph queries in favor of an **In-Memory Graph object** (`NetworkX` or `rustworkx`) populated locally per query bounds.
- **Why it matters:** Local ASTs are parsed and piped into RAM, allowing instantaneous BFS traversal, community clustering, and network flow math without hitting disk I/O.
- **Limitation:** Fails when spanning massive, polyglot microservice boundaries distributed across separated repositories. 

### Rocket Mode (PostgreSQL + Apache AGE + pgvector)
- **Mechanism:** Persistent, enterprise-grade architecture.
- **Why it matters:** Utilizes `Apache AGE` (Cypher queries on Postgres) to perform cross-service cluster analysis and edge walking. Uses `pgvector` purely as a supplemental lookup for fuzzy logic unmapped by native AST trees.

## 2. Degree Centrality and "God Nodes" (Feature 3.38)
Instead of forcing AI to guess which context files map highest weight, SpecWeaver will introduce local centrality math against AST graphs.

- **The Metric:** By calculating the **Degree Centrality** of a node (counting incoming call edges and outgoing dependency edges), the system can mathematically classify architectural pillars.
- **"God Nodes":** The top-ranked centralized nodes are flagged explicitly as "God Nodes". These signify dangerous classes where changes yield massive ripple effects.
- **Visualization:** `sw graph` will render a completely standalone `.html` web graph (using PyVis/D3.js). Engineers can drag, zoom, and visually identify community clusters and "God Nodes" locally, eliminating the need to wait for the Heavy Dashboard API.

## 3. Leiden Community Clustering
When constructing Prompt boundaries, finding optimal combinations of `context_files` is difficult. BFS expansion allows us to use clustering algorithms (like Leiden detection). 

- **Execution:** Applying these math bounds on topological dependencies allows SpecWeaver to feed LLMs dense, logically intertwined `context_files` that share a "neighborhood" rather than just similar naming schemas.

## 4. Multi-Modal Edges & Reverse-Weaving (Feature 3.43)
While Tree-sitter enforces precise Extracted Edges between code files, we must map arbitrary architecture knowledge.

- **Expanding Inputs:** Pipelining Whiteboard diagrams, PDFs, and Markdown documentation through Vision/LLM extractors.
- **Inferred Edges:** The system will dynamically inject these unstructured concepts into the Postgres/NetworkX graph using specialized LLM evaluations, explicitly tagging the relationship edges as `[semantically_similar]` or `[inferred]`. This allows humans or agents to confidently distinguish between strict AST realities and AI-inferred logic. 
- **Application:** Powering Feature 3.43 (Reverse-Weaving), allowing developers to drop legacy diagrams into the CLI to bootstrap raw implementations dynamically.
