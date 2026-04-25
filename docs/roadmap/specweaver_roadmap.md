# SpecWeaver Roadmap

> **Status**: ACTIVE
> **Context**: SpecWeaver is a Spec-First Development platform orchestrating LLM agents via deterministic AST constraints. 

> [!IMPORTANT]
> **The Core Principle**: MVP first → Prove it works → Isolate & implement features incrementally.
> Every phase must produce something *runnable*. 

> [!NOTE]
> **Detailed phase roadmaps** and granular feature checklists are in [`docs/roadmap/`](roadmap/). This document serves solely as the high-level executive overview.

---

## Current Focus (Active)

We are deeply focused on **Phase 3 (Feature Expansion)**, specifically expanding the polyglot Tree-Sitter AST foundation. By building out robust parsing support for enterprise languages (C/C++, Markdown, Go), we are securing the physical "Sensors" required to power the downstream engine capabilities like Deep Semantic Hashing and the Persistent Knowledge Graph.

---

## The 6 Phases Overview

### [Phase 1: MVP — Prove the Concept](roadmap/phase_1_mvp.md) ✅
**Goal:** A runnable CLI that demonstrates the Core Loop end-to-end. Static validation works. LLM integration works.
*Status: Complete*

### [Phase 2: Flow Engine & Stabilize](roadmap/phase_2_flow_engine.md) 🔧
**Goal:** Agents use tools; the flow engine orchestrates atoms and subflows. MVP individual steps become composable. Agent has topology awareness.
*Status: Complete*

### [Phase 3: Feature Isolation & Incremental Expansion](roadmap/phase_3_feature_expansion.md) 🟢
**Goal:** Take each major capability from the architecture docs, isolate it as a self-contained feature, and implement incrementally. This includes expanding polyglot support, interfaces (Web Dashboard, VS Code), and assurance bounds.
*Status: Active*

### [Phase 4: Advanced Capabilities](roadmap/phase_4_advanced.md) 🔜
**Goal:** Complex engineering capabilities including RAG, tiered access, multi-agent review, LLM cost analytics, and Deterministic Friction Detection.
*Status: Upcoming*

### [Phase 5: Domain Brain — Hybrid Graph + Vector RAG](roadmap/phase_5_domain_brain.md) 🔮
**Goal:** Persistent domain knowledge system: cross-service impact analysis, SLA-aware spec authoring, and Socratic Drafting.
*Status: Future*

### [Phase 6: External Validation](roadmap/phase_6_external_validation.md) 🔮
**Goal:** SpecWeaver is used on a real project that isn't SpecWeaver itself (e.g., an automatic trading system). Full workflow validation.
*Status: Future*

---

## Success Criteria

**MVP is PROVEN when you can:**
1. ✅ `sw init my-app --path .` registers and scaffolds the project
2. ✅ `sw check some_spec.md` reports PASS/FAIL with findings
3. ✅ `sw draft greet_service` produces a real spec via HITL interaction
4. ✅ `sw implement greet_service_spec.md` generates code + tests
5. ✅ `sw check --level code greet_service.py` checks syntax, tests, coverage
6. ✅ `sw review code greet_service.py` provides LLM semantic judgment

**Product is USEFUL when additionally:**
7. ✅ You've used it on SpecWeaver itself (dogfooding)
8. 🔜 You've used it on an external project (trading system)
9. ✅ Features can be added without restructuring (interface extensibility confirmed)
10. 🔜 Topology-aware spec authoring catches cross-service issues before code generation
11. ✅ Multi-project management: `sw projects`, `sw use`, `sw remove`, `sw update`, `sw scan`
