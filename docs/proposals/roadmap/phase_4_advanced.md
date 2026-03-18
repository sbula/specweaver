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
| **4.6** | Conversation summarization | _(inspired by Aider)_ — Compress old multi-turn drafting/review messages when context fills up; keep recent turns + summary of history. _(Blueprint: [`aider/history.py`](https://github.com/Aider-AI/aider/blob/main/aider/history.py) `summarize_end()` — ORIGINS.md § Aider)_ |
| **4.7** | Verification gates (mutation testing, assertion density) | `future_capabilities_reference.md` §13, §14 |
| **4.8** | Blast radius / locality enforcement | `future_capabilities_reference.md` §16 |
| **4.9** | Containerized deployment (Podman) | `mvp_feature_definition.md` |
| **4.10** | **Web UI + server mode** | SpecWeaver as a daemon with REST/WebSocket API and browser-based UI. Includes **per-project pipeline storage** (layer 2): SQLite `pipelines` table, CRUD via `sw pipeline` CLI + REST API. _(See also: [A2UI](https://github.com/google/A2UI) declarative component catalog for agent-generated UI, Phase 3.19 structured output schemas as foundation — ORIGINS.md § A2UI)_ |
