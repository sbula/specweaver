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
| **5.5a** | HITL root-cause tagging on pipeline failure | _(split from original 3.12)_ — When pipeline fails or human rejects, prompt: "Where did the root cause originate?" `[Flawed Spec / Short-sighted Plan / Bad Code / Requirements Changed]`. Builds labeled ground truth dataset for future routing optimization. See [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md). |
| **5.6** | Socratic drafting flow — topology-aware questioning during `sw draft` | Phase A+B (seeds in Phase 2) |
| **5.7** | **Memory consolidation** — LLM-powered knowledge deduplication | _(new)_ When new knowledge overlaps with existing, LLM decides: keep, update, delete, or insert_new. Prevents infinite knowledge growth. _(Blueprint: CrewAI's `consolidation_threshold` and merge logic — ORIGINS.md § CrewAI)_ |
| **5.8** | 🔬 **Dynamic routing engine + AI Arbiter** | _(split from original 3.12)_ — Automatic model selection using Attributed Lifecycle Score (ALS). AI-powered fault attribution across multi-model, cross-lifecycle pipelines. **Science fiction today** — depends on persistent knowledge graph (5.1-5.5), labeled training data (5.5a), and solving the credit assignment problem. See [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md). |

---

## Ideas to Consider

### Prompt-enforced priority resolution as final fusion layer (5.4 + 5.5)

_Source: "Beyond Vector Search: Building a Deterministic 3-Tiered Graph-RAG System" (Matthew Mayo, Machine Learning Mastery, April 2026)_

Feature 5.4 currently specifies composite **scoring** (semantic × similarity + recency × decay + importance × weight) as the mechanism for ranking retrieved knowledge. This is a **pre-context algorithmic filter** — it decides what enters the prompt. The article demonstrates a complementary **post-selection** technique: after scoring selects the top-K results, label each result by its provenance tier (e.g., `[PRIORITY 1 - AST FACTS]`, `[PRIORITY 2 - TOPOLOGY]`, `[PRIORITY 3 - VECTOR DOCUMENTS]`) and embed explicit conflict-resolution rules in the system prompt forcing the LM to deterministically prefer higher-trust sources when conflicts exist.

This maps cleanly onto our existing trust levels table in the [Domain Brain proposal](../domain_brain_hybrid_rag.md) §4 (AST=1.0, context.yaml=0.95, architect=0.9, agent-generated=0.7, internet=0.5). Rather than relying solely on algorithmic scoring to filter conflicts before they reach the LM, we could **also** present the hierarchy inside the prompt so the LM itself adjudicates transparently. The two mechanisms are complementary, not competing: scoring controls the **volume** of context, prompt labels control the **authority** weighting.

> [!NOTE]
> Phases A (context-enriched prompts) and B (in-memory topology graph) are already completed in Phase 2. Phase 5 covers the persistent, event-driven extensions that add value only when managing large multi-service architectures (20+ services).
