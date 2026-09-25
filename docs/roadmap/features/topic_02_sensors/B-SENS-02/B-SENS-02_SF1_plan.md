# B-SENS-02 SF-01 — In-Memory Graph Engine & Enterprise Ontology

**Status**: APPROVED · **FRs owned**: FR-1, FR-2, FR-6, FR-7, EXP-1 (per the design) · **Depends on**:
none · Design: [B-SENS-02_design.md](B-SENS-02_design.md) §Sub-features → SF-01

## Goal

Build the pure-logic graph domain: the ontology, the `GraphNode` / `GraphEdge` models, and the
`InMemoryGraphEngine` NetworkX wrapper, inside one bounded context with enforced layer rules.

## Changes

### Directory structure (DDD)

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

Built under `src/specweaver/graph/core/` (`core/engine`, `core/store`, `core/builder`) — see the file
table.

### Ontology (`src/specweaver/graph/core/engine/ontology.py`)

| Enum | Group | Members |
|---|---|---|
| `NodeKind` | Macro Architecture | `SYSTEM`, `MICROSERVICE` |
| | Code Structure | `FILE`, `MODULE`, `NAMESPACE`, `DATA_STRUCTURE` |
| | Execution | `PROCEDURE`, `STATE` |
| | Boundaries & Events | `API_CONTRACT`, `MESSAGE_QUEUE` |
| | External | `GHOST` |
| `EdgeKind` | Structural | `CONTAINS` |
| | Code | `IMPORTS`, `CALLS`, `IMPLEMENTS`, `EXTENDS` |
| | Dataflow | `CONSUMES` / `FULFILLS`, `PUBLISHES` / `SUBSCRIBES` |

### Files (all done)

| Layer | File | Holds |
|---|---|---|
| Bounded context | `src/specweaver/graph/context.yaml` | |
| Pure logic | `src/specweaver/graph/core/engine/context.yaml` | |
| | `src/specweaver/graph/core/engine/ontology.py` | the enums above |
| | `src/specweaver/graph/core/engine/models.py` | `GraphNode` (with `embedding_id`) and `GraphEdge` |
| | `src/specweaver/graph/core/engine/core.py` | `InMemoryGraphEngine` (NetworkX wrapper) |
| Orchestrator | `src/specweaver/graph/core/builder/context.yaml` | |
| | `src/specweaver/graph/core/builder/orchestrator.py` | `GraphBuilder` |
