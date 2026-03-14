# Phase 4: Advanced Capabilities

> **Status**: Pending
> **Goal**: The features from `future_capabilities_reference.md` that require significant engineering.

| Priority | Feature | Source |
|:---|:---|:---|
| **4.1** | Symbol index + anti-hallucination gate | `future_capabilities_reference.md` §11 |
| **4.2** | AST-based semantic chunking (RAG foundation) | `future_capabilities_reference.md` §3 |
| **4.3** | RAG context provider + rich Qdrant payloads | `rag_architecture.md` §1/§5, [Domain Brain proposal](../domain_brain_hybrid_rag.md) Phase C |
| **4.4** | Tiered access rights (zero-trust knowledge) | `future_capabilities_reference.md` §1 |
| **4.5** | Agent isolation patterns (multi-agent review) | `future_capabilities_reference.md` §6 |
| **4.6** | Conversation summarization _(inspired by Aider)_ | _(new)_ — Compress old multi-turn drafting/review messages when context fills up; keep recent turns + summary of history. Enables long sessions without manual context reset. |
| **4.7** | Verification gates (mutation testing, assertion density) | `future_capabilities_reference.md` §13, §14 |
| **4.8** | Blast radius / locality enforcement | `future_capabilities_reference.md` §16 |
| **4.9** | Containerized deployment (Podman) | `mvp_feature_definition.md` |
| **4.10** | **Web UI + server mode** | _(new)_ — SpecWeaver as a daemon with REST/WebSocket API and browser-based UI for remote operation (tablet/mobile). Enables directing SpecWeaver from any device while it runs on a home/cloud server. |
