# Phase 5: Domain Brain — Hybrid Graph + Vector RAG

> **Status**: Pending
> **Goal**: Persistent domain knowledge system that enables cross-service impact analysis, SLA-aware spec authoring, and automated architectural consistency enforcement.
> **Full proposal**: [Domain Brain — Hybrid Graph + Vector RAG Architecture](../domain_brain_hybrid_rag.md)

> [!IMPORTANT]
> **Before starting any feature**: check [ORIGINS.md](../../ORIGINS.md) for blueprint references. Features 5.4 and 5.7 are directly informed by CrewAI's memory architecture — study [`crewai/memory/`](https://github.com/crewAIInc/crewAI/tree/main/src/crewai/memory) and the [Memory docs](https://docs.crewai.com/concepts/memory) first.

| Priority | Feature | Proposal Phase |
|:---|:---|:---|
| **5.1** | Persistent topology graph (serialized JSON → FalkorDB) | Phase D.1 → D.2 |
| **5.2** | Event-driven knowledge graph (EDKG) — file/commit triggers update nodes/edges | Phase D |
| **5.3** | Hash-based garbage collection for graph nodes | Phase D |
| **5.4** | Hybrid RAG orchestration — graph-guided vector search + **composite scoring** | Phase C + D. _(Enhanced with CrewAI's scoring formula: `semantic × similarity + recency × decay + importance × weight`, configurable half-life profiles per knowledge type — ORIGINS.md § CrewAI)_ |
| **5.5** | Provenance tracking + trust levels for knowledge sources | Phase D |
| **5.6** | Socratic drafting flow — topology-aware questioning during `sw draft` | Phase A+B (seeds in Phase 2) |
| **5.7** | **Memory consolidation** — LLM-powered knowledge deduplication | _(new)_ When new knowledge overlaps with existing, LLM decides: keep, update, delete, or insert_new. Prevents infinite knowledge growth. _(Blueprint: CrewAI's `consolidation_threshold` and merge logic — ORIGINS.md § CrewAI)_ |

> [!NOTE]
> Phases A (context-enriched prompts) and B (in-memory topology graph) are already completed in Phase 2. Phase 5 covers the persistent, event-driven extensions that add value only when managing large multi-service architectures (20+ services).
