# Phase 4: Advanced Capabilities

> **Status**: Pending
> **Goal**: The features from `future_capabilities_reference.md` that require significant engineering.

> [!IMPORTANT]
> **Before starting any feature**: check [ORIGINS.md](../../ORIGINS.md) for blueprint references. Several features below build on patterns from Aider, CrewAI, and A2UI — study those implementations first.

| Priority | Feature | Source |
|:---|:---|:---|
| **4.1** | Symbol index + anti-hallucination gate | `future_capabilities_reference.md` §11 |
| **4.2** | AST-based semantic chunking (RAG foundation) | `future_capabilities_reference.md` §3. _(See also: [CrewAI Knowledge](https://docs.crewai.com/concepts/knowledge) for RAG source patterns, embedder config, query rewriting — ORIGINS.md § CrewAI)_ |
| **4.3** | RAG context provider + rich Qdrant payloads | `rag_architecture.md` §1/§5, [Domain Brain proposal](../domain_brain_hybrid_rag.md) Phase C. _(See also: CrewAI's knowledge sources and custom embedder configuration — ORIGINS.md § CrewAI)_ |
| **4.4** | Tiered access rights (zero-trust knowledge) | `future_capabilities_reference.md` §1 |
| **4.5** | Agent isolation patterns (multi-agent review) | `future_capabilities_reference.md` §6 |
| **4.5a** | Task-type cost analytics dashboard | _(split from original 3.12)_ — Aggregate telemetry from 3.12 into cost breakdown by task type (draft/review/plan/implement) across models. Data-driven model selection insights. See [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md). |
| **4.5b** | Artifact lineage graph | _(split from original 3.12, merges with 3.14)_ — Tag every artifact with `artifact_uuid`, `parent_uuid`, `model_id`. Build directed lineage graph: spec → plan → code → tests. Foundation for friction detection and provenance. See [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md). |
| **4.5c** | Deterministic friction detection | _(split from original 3.12)_ — When downstream agent modifies >20% of upstream scaffolding (measured by `git diff`), flag "friction event" and attribute to upstream model. No LLM needed — pure diff math. See [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md). |
| **4.5d** | Data-driven routing recommendations | _(split from original 3.12)_ — Analyze telemetry + friction data to **suggest** (not auto-apply) model swaps. "Model X has 3× more friction on planning tasks than Model Y." See [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md). |
| **4.6** | Conversation summarization | _(inspired by Aider)_ — Compress old multi-turn drafting/review messages when context fills up; keep recent turns + summary of history. _(Blueprint: [`aider/history.py`](https://github.com/Aider-AI/aider/blob/main/aider/history.py) `summarize_end()` — ORIGINS.md § Aider)_ |
| **4.7** | Verification gates (mutation testing, assertion density) | `future_capabilities_reference.md` §13, §14 |
| **4.8** | Blast radius / locality enforcement | `future_capabilities_reference.md` §16 |
| **4.9** | Containerized deployment (Podman) | `mvp_feature_definition.md` |
| **4.10** | **Web UI + server mode** | SpecWeaver as a daemon with REST/WebSocket API and browser-based UI. Includes **per-project pipeline storage** (layer 2): SQLite `pipelines` table, CRUD via `sw pipeline` CLI + REST API. _(See also: [A2UI](https://github.com/google/A2UI) declarative component catalog for agent-generated UI, Phase 3.19 structured output schemas as foundation — ORIGINS.md § A2UI)_ |
| **4.11** | Multi-Modal Visual Quality Gates (V-Series) | _(new)_ | Expanding the validation engine battery with `V-Series` rules using VLM (Vision LLMs) + Headless Browsers (Playwright) via internal Docker rendering, calculating visual UI drift perfectly against the UI component specifications. |

---

## Ideas to Consider

### Entity-bridged multi-index query fanout (4.2 + 4.3)

_Source: "Beyond Vector Search: Building a Deterministic 3-Tiered Graph-RAG System" (Matthew Mayo, Machine Learning Mastery, April 2026)_

When 4.2 (AST chunking) and 4.3 (Qdrant payloads) are implemented alongside the existing topology graph, the **query bridge mechanism** needs to be specified — i.e., how a user prompt fans out to both the graph and the vector store simultaneously. The article demonstrates a concrete pattern: extract named entities from the prompt via NER (spaCy), use those entities as **strict graph lookups** against the topology/knowledge graph, while running the full prompt as a **semantic similarity search** against Qdrant. This produces two distinct result streams that are then merged into the context window. This aligns with our Phase C (Rich Qdrant Payloads) + Phase B (Topology Graph) architecture and provides a concrete answer to the "graph-guided vector search" mechanism described in 5.4.
