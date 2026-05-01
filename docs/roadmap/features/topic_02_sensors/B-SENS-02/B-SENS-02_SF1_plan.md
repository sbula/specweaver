# Implementation Plan: B-SENS-02 [SF-1: In-Memory Graph Engine & Enterprise Ontology]
- **Feature ID**: B-SENS-02
- **Sub-Feature**: SF-1 — In-Memory Graph Engine & Enterprise Ontology
- **Design Document**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_design.md
- **Status**: APPROVED

## Proposed Architectural Changes

### Revised Directory Structure (True DDD)
```text
src/specweaver/graph/
├── context.yaml               (Defines the Bounded Context for the whole domain)
├── engine/                    (Pure Logic - NetworkX & Pydantic)
│   ├── context.yaml           (Forbids importing store/ or builder/)
│   ├── ontology.py            
│   ├── models.py              
│   └── core.py    
├── store/                     (Infrastructure - SQLite)
│   └── context.yaml           (Allows importing engine/)
└── builder/                   (Application/Orchestration)
    └── context.yaml           (Allows importing engine/ and store/)
```

### Revised Ontology (`src/specweaver/graph/engine/ontology.py`)

#### `NodeKind` Enum
*   **Macro Architecture:** `SYSTEM`, `MICROSERVICE`
*   **Code Structure:** `FILE`, `MODULE`, `NAMESPACE`, `DATA_STRUCTURE`
*   **Execution:** `PROCEDURE`, `STATE`
*   **Boundaries & Events:** `API_CONTRACT`, `MESSAGE_QUEUE`
*   **External:** `GHOST`

#### `EdgeKind` Enum
*   **Structural:** `CONTAINS`
*   **Code:** `IMPORTS`, `CALLS`, `IMPLEMENTS`, `EXTENDS`
*   **Dataflow:** `CONSUMES` / `FULFILLS`, `PUBLISHES` / `SUBSCRIBES`

---

## File Manifest for SF-1 Execution

### 1. `src/specweaver/graph/` (The Bounded Context)
*   `[x]` `src/specweaver/graph/context.yaml`

### 2. `src/specweaver/graph/engine/` (Pure Logic Layer)
*   `[x]` `src/specweaver/graph/engine/context.yaml` 
*   `[x]` `src/specweaver/graph/engine/ontology.py` 
*   `[x]` `src/specweaver/graph/engine/models.py` (Defines `GraphNode` with `embedding_id` and `GraphEdge`).
*   `[x]` `src/specweaver/graph/engine/core.py` (The `InMemoryGraphEngine` NetworkX wrapper).

### 3. `src/specweaver/graph/builder/` (Orchestrator Layer)
*   `[x]` `src/specweaver/graph/builder/context.yaml` 
*   `[x]` `src/specweaver/graph/builder/orchestrator.py` (The `GraphBuilder` class).
