# Domain Brain — Hybrid Graph + Vector RAG Architecture

> **Status**: VISION — Long-term architectural direction. Not scheduled for immediate implementation.
> **Date**: 2026-03-12
> **Origin**: Architecture brainstorm exploring how to augment SpecWeaver's spec-authoring and code-generation with a persistent, structured domain knowledge system.
> **Related**:
> - [Context YAML Spec](../architecture/context_yaml_spec.md) — the existing boundary manifest system (foundation layer)
> - [SpecWeaver Roadmap](specweaver_roadmap.md) — phased delivery plan
> - [Future Capabilities Reference](../analysis/future_capabilities_reference.md) — §3 AST chunking, §11 symbol index, §17 traceability

---

## 1. Problem Statement

As SpecWeaver-managed projects grow in complexity (20+ microservices, multi-tenant, cross-domain dependencies), two problems emerge:

1. **Spec quality degrades** — Agents writing specs for Service B don't know that Service A has a latency constraint that makes their design infeasible.
2. **Impact blindness** — Changing a spec or interface in one module silently breaks assumptions in downstream consumers.

A flat vector database (Qdrant) finds *similar* code but cannot traverse *causal chains*. A graph database finds *dependencies* but cannot understand *semantics*. The solution is a hybrid architecture.

---

## 2. Architecture Vision

```
┌─────────────────────────────────────────────────────────┐
│                    SpecWeaver Agent                     │
│                                                         │
│  "Write a spec for a circuit breaker on the Feed"       │
│                                                         │
│  ┌──────────────────┐    ┌────────────────────────┐     │
│  │  Topology Graph   │    │    Qdrant (Vectors)     │     │
│  │  (Structure)      │    │    (Semantics)          │     │
│  │                   │    │                         │     │
│  │  Feed ──→ Risk    │    │  get_price(): "Returns  │     │
│  │  Feed ──→ Order   │    │   latest spot price     │     │
│  │  Risk ──→ Audit   │    │   from Binance WS"      │     │
│  │                   │    │                         │     │
│  │  "What depends    │    │  "Show me similar       │     │
│  │   on Feed?"       │    │   circuit breakers"     │     │
│  └──────────────────┘    └────────────────────────┘     │
│           │                         │                    │
│           └─────────┬───────────────┘                    │
│                     ▼                                    │
│           Enriched Prompt Context                        │
│  "Downstream consumers: [Risk, Order].                   │
│   Constraint: Risk needs realtime data.                  │
│   Pattern: Coinbase feed uses graceful warmup."           │
└─────────────────────────────────────────────────────────┘
```

### Two distinct "brains"

| Brain | Technology | Scope | Purpose |
|---|---|---|---|
| **Code Memory** (Local) | Qdrant | Per-service: public signatures + 1-line descriptions | Code generation: "what APIs exist?" |
| **Architecture Memory** (Global) | Graph (in-memory → DB) | Cross-service: topology, constraints, SLAs | Spec authoring: "what breaks if I change this?" |

---

## 3. Phased Implementation

### Phase A: Context-Enriched Prompts (Now — Phase 2 roadmap)

**What**: Feed `context.yaml` topology + constraints into `sw draft` and `sw review spec` prompts.

**How**: At `sw draft` startup, scan all `context.yaml` files in the target project. Extract `consumes`, `constraints`, and `purpose` fields. Inject a "System Context" block into the LLM prompt:

```
You are writing a spec for module: PriceFeedCircuitBreaker
This module consumes: [BinancePriceFeed, TenantConfigService]
The following modules consume PriceFeedCircuitBreaker: [RiskEngine, OrderManager]
Active constraints:
  - RiskEngine: "Data must be realtime for delta-neutrality calculations"
  - OrderManager: "All failover must be logged via AuditLog API"
```

**Effort**: Low. YAML scanning + string formatting. No new dependencies.

**Value**: The "Socratic partner" effect — the agent asks the right questions because it knows the neighbourhood.

---

### Phase B: In-Memory Topology Graph (Phase 2 roadmap)

**What**: Build an adjacency graph from `context.yaml` at startup. Enable impact analysis and cycle detection.

**How**: A `TopologyGraph` class (~50-100 lines):

```python
class TopologyGraph:
    """In-memory directed graph from context.yaml consumes/exposes."""

    def __init__(self, project_root: Path):
        self._adj: dict[str, set[str]] = {}   # module → set of modules it consumes
        self._rev: dict[str, set[str]] = {}   # module → set of modules that consume it
        self._constraints: dict[str, list[str]] = {}
        self._load(project_root)

    def impact_of(self, module: str) -> set[str]:
        """All modules transitively affected if `module` changes."""
        ...  # BFS/DFS on reverse adjacency

    def dependencies_of(self, module: str) -> set[str]:
        """All modules `module` transitively depends on."""
        ...  # BFS/DFS on forward adjacency

    def cycles(self) -> list[list[str]]:
        """Detect circular dependency chains."""
        ...  # Tarjan's or simple DFS

    def constraints_for(self, module: str) -> list[str]:
        """Aggregate constraints from module + all its consumers."""
        ...
```

**No external dependencies** needed. Plain `dict` + DFS. NetworkX is overkill for <500 nodes.

**Integration points**:
- `sw draft` — inject impact analysis into prompt context
- `sw review spec` — warn if spec touches high-impact modules
- `sw check` — new rule candidate: S12 (topology cycle detection)

---

### Phase C: Rich Qdrant Payloads (Phase 4 roadmap — RAG foundation)

**What**: Enrich Qdrant vector entries with structured metadata from `context.yaml` + AST-extracted code signatures.

**How**: Combined payload schema per code entity:

```json
{
  "entity_type": "function",
  "name": "check_margin_limit",
  "signature": "check_margin_limit(tenant_id: str, amount: Decimal) -> bool",
  "docstring": "Validates available margin for the given tenant.",
  "file_hash": "a3f8c2...",

  "parent_module": "risk-margin-engine",
  "module_domain": "risk-management",
  "module_depends_on": ["binance-price-feed", "tenant-config"],
  "multi_tenant_ready": true,
  "latency_critical": true,
  "max_latency_ms": 50,
  "data_freshness": "realtime"
}
```

**Data sources** (all deterministic, no LLM needed):
- **Code** → AST parser extracts public symbols, signatures, docstrings
- **context.yaml** → Provides module-level metadata (consumes, constraints, operational fields)
- **File hash** → Enables staleness detection without re-parsing

**Qdrant filter queries** this enables:
- `WHERE multi_tenant_ready = true AND latency_critical = true` → "Find all fast, tenant-aware APIs"
- `WHERE module_depends_on CONTAINS 'binance-price-feed'` → "Find all consumers of the feed"

---

### Phase D: Persistent Graph DB — Event-Driven Knowledge Graph (Phase 5+ roadmap)

**What**: Replace the in-memory topology graph with a persistent graph database. Enable event-driven updates, temporal queries, and multi-hop reasoning.

**Why wait**: The in-memory graph is sufficient for <200 services. Persistent graph adds value when:
- Runtime metrics (actual latencies, error rates) need to be stored alongside design-time topology
- Historical queries are needed ("how did the topology look before the refactoring?")
- The project exceeds what fits in a single `context.yaml` scan

#### Technology Options

| Option | Pros | Cons | Best For |
|---|---|---|---|
| **FalkorDB** | Redis-compatible, fast, graph+vector native | Newer project, smaller community | Teams already using Redis |
| **Neo4j** | Mature, Cypher query language, huge ecosystem | Heavy, Java-based, licensing | Large teams, complex queries |
| **Memgraph** | Cypher-compatible, in-memory, fast writes | Less mature than Neo4j | Real-time use cases |
| **NetworkX (persisted)** | No infrastructure, pickle/JSON serialization | Not a real DB, no concurrent access | Solo/small teams |

**Recommendation**: Start with **NetworkX serialized to JSON** (Phase D.1). Migrate to **FalkorDB** only if concurrent access or runtime metrics are needed (Phase D.2).

#### Data Model (Abstract)

```
Nodes:
  ├── Intent (Spec)          — "What should this module do?"
  ├── Implementation (Code)  — "How does it do it?"
  ├── Constraint (Rule)      — "What must not be violated?"
  └── Source (Provenance)     — "Where does this knowledge come from?"

Edges:
  ├── SATISFIES              — Implementation → Intent (code fulfills spec)
  ├── DEPENDS_ON             — Module → Module (consumes relationship)
  ├── CONSTRAINS             — Constraint → Intent (rule applies to spec)
  ├── CONTRADICTS            — Intent → Intent (conflicting requirements)
  ├── EVOLVED_FROM           — Intent v2 → Intent v1 (spec history)
  └── ORIGIN_OF              — Source → any node (provenance tracking)
```

#### Event-Driven Updates

```
Trigger              →  Action
─────────────────────────────────────────────────
File saved           →  Hash check. If changed: re-parse, update node.
Git commit           →  Batch update: re-scan changed files only.
Spec finalized       →  Create/update Intent node + SATISFIES edges.
context.yaml changed →  Rebuild topology edges for that module.
Manual entry (HITL)  →  Create Constraint node with source: "architect".
```

#### Garbage Collection

Every node carries:
- `origin_file`: the file path it was extracted from
- `origin_hash`: SHA-256 of the source content at extraction time
- `last_seen_commit`: the git commit where this node was last confirmed

**Cleanup rule**: If `origin_file` no longer exists OR its current hash ≠ `origin_hash`, mark the node as `stale`. Stale nodes are:
1. Flagged in impact analysis ("Warning: this dependency may be outdated")
2. Deleted after N commits without re-confirmation

---

## 4. Provenance & Trust Levels

Not all knowledge is equally trustworthy. The system must distinguish:

| Source | Trust | Can Agent Override? | Example |
|---|---|---|---|
| **Code (AST-extracted)** | 1.0 | No | `check_margin_limit()` exists |
| **context.yaml (HITL-approved)** | 0.95 | No | `consumes: [BinancePriceFeed]` |
| **Architect decision (manual)** | 0.9 | Never | "No Kafka in the hot path" |
| **Agent-generated metadata** | 0.7 | Yes, with review | "This function has O(n²) complexity" |
| **Internet research** | 0.5 | Yes | "Polars recommends lazy evaluation" |

Architect decisions stored as `constraints` in `context.yaml` are **hard invariants** — the agent must never override them, only flag conflicts for HITL resolution.

---

## 5. The Socratic Drafting Flow (Target Experience)

**Input**: User types a few keywords: *"circuit breaker, binance feed, latency failover"*

**Agent's internal process**:
1. Query topology graph: "What modules depend on BinancePriceFeed?"
   → `[RiskEngine, OrderManager, PortfolioService]`
2. Query constraints: "What rules apply to these consumers?"
   → `RiskEngine: realtime data required`, `OrderManager: all failover logged`
3. Query Qdrant: "How did we implement the Coinbase circuit breaker?"
   → Returns existing pattern with graceful warmup

**Agent asks HITL**:
> "I found 3 downstream consumers of BinancePriceFeed. RiskEngine requires realtime data — when the circuit breaker activates and switches to cache, how should RiskEngine behave? Options:
> 1. Pause trading (safest)
> 2. Widen margin requirements by factor X (conservative)
> 3. Continue with stale data (risky)"

**Result**: A spec that addresses cross-cutting concerns *before the first line of code is written*.

---

## 6. Cost/Benefit Summary

| Phase | Effort | Value for Specs | Value for Code | When |
|---|---|---|---|---|
| **A: Context-enriched prompts** | Low | High | Low | Now (Phase 2) |
| **B: In-memory topology graph** | Medium | Very High | Medium | Phase 2 |
| **C: Rich Qdrant payloads** | Medium | Medium | Very High | Phase 4 |
| **D: Persistent Graph DB (EDKG)** | Very High | Maximum | High | Phase 5+ |

---

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Engineering inception** — building a brain to feed the tool to write the specs to build the system | Schedule slip, never ships | Strict phasing. Phase A+B are zero-infrastructure. Don't start D until B proves insufficient |
| **YAML drift** — `context.yaml` falls out of sync with code | Corrupted topology, wrong constraints | CI check: validate `consumes` against actual imports (AST scan). Already designed in `context.lock` concept |
| **Graph entropy** — stale nodes accumulate | Agent reasons about dead code | Hash-based GC + `last_seen_commit` aging. Periodic full-scan reconciliation |
| **Over-reliance on LLM for extraction** | Hallucinated metadata | Zero LLM for extraction in Phases A-C. All data from deterministic sources (AST + YAML) |
| **Qdrant context pollution** — agents see irrelevant code from other services | Cross-service leakage | Strict `context.yaml` boundary enforcement: agents only query Qdrant within their `consumes` scope |

---

## 8. Design Decisions to Preserve Now

Even without building Phases C-D today, these decisions keep the path open:

1. **Keep `context.yaml` as the single source of truth** for module topology. Don't create parallel dependency files.
2. **Add operational metadata fields** to `context.yaml` schema (see [context_yaml_spec.md](../architecture/context_yaml_spec.md)):  `multi_tenant_ready`, `latency_critical`, `max_latency_ms`, `data_freshness`, `reliability_target`.
3. **Keep AST extraction patterns** in code rules (C05, C06, C08). These are the future Qdrant payload extractors.
4. **Keep specs technology-agnostic** (the "what", not the "how"). This enables the graph to reason about business logic without parsing implementation details.
5. **Maintain `consumes` validation** — `validate_boundaries()` atom already checks consumes references. This is the seed of graph integrity checking.
