# SpecWeaver Roadmap

> **Date**: 2026-03-08 | **Updated**: 2026-03-20
> **Status**: ACTIVE
> **Context**: Step-by-step plan for SpecWeaver development. Fresh start from scratch, informed by [flowManager](https://github.com/sbula/flowManager) learnings. MVP-first approach: prove the concept, then expand feature by feature.

> [!IMPORTANT]
> **The Core Principle**: MVP first → Prove it works → Isolate & implement features one by one → Full functionality.
> Every phase must produce something *runnable*. No phase is "just spec work."

> [!NOTE]
> **Detailed phase roadmaps** are in [`docs/proposals/roadmap/`](roadmap/). This document is the high-level overview only.

---

## Current State (updated 2026-03-20)

**What exists:**
- ✅ Repo: `sbula/specweaver` — fresh, clean
- ✅ Documentation: MVP feature definition, methodology, architecture, lifecycle layers
- ✅ Decision log: Python, Typer CLI, Gemini API, deployment isolation
- ✅ Project scaffold: `pyproject.toml`, CLI shell, `sw init`
- ✅ Loom layer: Filesystem tools, atoms, and interfaces (**183 tests**, fully linted + type-checked)
- ✅ Validation engine: 19 rules (S01-S11, C01-C08), configurable thresholds, per-project overrides
- ✅ LLM adapter: Gemini API adapter with interface abstraction
- ✅ Spec drafting: Interactive `sw draft` with HITL context
- ✅ Spec/Code review: LLM-powered `sw review` with ACCEPTED/DENIED verdicts
- ✅ Code generation: `sw implement` generates code + tests from spec
- ✅ Topology graph: In-memory dep graph, impact analysis, cycle detection, auto-infer
- ✅ Project registry: SQLite config store, multi-project, `sw use/projects/remove/update`
- ✅ Validation config: `sw config set/get/list/reset`, `--strict`, `--set` CLI overrides
- ✅ Context-enriched prompts: PromptBuilder, token budgets, topology injection, trust signals, dynamic scaling
- ✅ Flow engine: Pipeline models, runner, state tracking, gates, retry, loop-back, HITL parking
- ✅ Loom test runner: Atom + tool with role gating, lint-fix reflection loop
- ✅ Integration test suite: 54 tests across 5 files with shared sample project fixture
- ✅ Feature 3.1: Kind-aware validation (`--level feature`), feature drafting, decomposition pipeline, confidence-scored review
- ✅ Feature 3.2: Constitution as first-class artifact — `CONSTITUTION.md` injected into all LLM calls, walk-up resolution, CLI management (`sw constitution show/check/init`), configurable size limits
- ✅ Feature 3.3: Domain profiles for threshold calibration — 5 built-in profiles (web-app, data-pipeline, library, microservice, ml-model), `config/profiles.py`, DB v5 migration, 5 CLI commands (`sw config profiles/show-profile/set-profile/get-profile/reset-profile`)
- ✅ Feature 3.4: Rules-as-pipeline architecture — validation sub-pipeline (YAML definitions with inheritance), `sw list-rules`, `--pipeline` override, custom D-prefix rule loader, `RuleAtom` adapter, profile-specific pipelines, circular-extends guard, project-local pipeline overrides, 2181 tests
- ✅ CLI refactoring: Split `cli.py` into `cli/` package (11 submodules), 65 new unit tests, reviewer ERROR verdict bug fix, 2411 tests

**Phase 1 (MVP)**: Steps 1–5 ✅ | Step 6 ⏸ (deferred)
**Phase 2 (Flow Engine)**: Steps 7–14 ✅
**Phase 3 (Features)**: Feature 3.1 ✅ | Feature 3.2 ✅ | Feature 3.3 ✅ | Feature 3.4 ✅

**What we're building next** (see [mvp_feature_definition.md](mvp_feature_definition.md)):
- ✅ Feature 3.5: Auto-discover standards from codebase _(Agent OS v3)_ — multi-language (Py/JS/TS), multi-scope, conditional LLM comparison
- ⚠️ **Post-3.5 cleanup**: Consolidate DB `validation_overrides` (3.3) vs sub-pipeline YAML inheritance (3.4) — decide single source of truth
- ✅ Feature 3.6: Explicit plan phase (Spec → Plan → Tasks) (Including Stitch UI Mockups)
- Feature 3.7: Pipeline visualization _(CrewAI)_

---

## Phases

### [Phase 1: MVP — Prove the Concept](roadmap/phase_1_mvp.md) ✅

A runnable CLI that demonstrates the Core Loop end-to-end. Static validation works. LLM integration works. Steps 1–5 complete (scaffold, loom, validation, LLM adapter, drafting, review, implementation). Step 6 (dogfooding) deferred until Phase 2 complete.

**Steps**: 1 (Scaffold) → 1b (Loom) → 2 (Validation) → 3 (LLM Adapter) → 4 (Drafting + Review) → 5 (Implementation) → 6 (Dogfooding ⏸)

---

### [Phase 2: Flow Engine & Stabilize](roadmap/phase_2_flow_engine.md) 🔧

Agents use tools; the flow engine orchestrates atoms and subflows. MVP individual steps become composable. Agent has topology awareness. Ready for external use.

**Steps**: 7 (Topology ✅) → 8a (Config Store ✅) → 8b (Validation Config ✅) → 9 (Context-Enriched Prompts ✅) → 10 (Pipeline Models ✅) → 11 (Runner ✅) → 12 (Gates/Retry ✅) → 13a (CLI `sw run` ✅) → 13b (Logging ✅) → 14 (Docs ✅)

---

### [Phase 3: Feature Isolation & Incremental Expansion](roadmap/phase_3_feature_expansion.md)

Take each major capability from the architecture docs, isolate it as a self-contained feature, implement one by one. Each feature is proposed → approved → implemented → tested → validated → merged.

**Features**: 3.1 (L2 Decomposition ✅) → 3.2 (Constitution ✅) → 3.3 (Domain Profiles ✅) → 3.4 (Custom Rules ✅) → 3.5 (Standards Auto-Discover ✅) → 3.6 (Plan Phase ✅) → 3.7 (Pipeline Viz) → 3.7a (REST API) → 3.7b (Web Dashboard) → 3.7c (Container) → 3.8–3.19 → 3.20 (VS Code Extension)

---

### [Phase 4: Advanced Capabilities](roadmap/phase_4_advanced.md)

Features from `future_capabilities_reference.md` that require significant engineering: symbol index, AST chunking, RAG, tiered access, multi-agent review, conversation summarization, mutation testing, Web UI.

**Features**: 4.1 (Symbol Index) → 4.2 (AST Chunking) → 4.3 (RAG) → 4.4 (Access Rights) → 4.5 (Multi-Agent) → 4.6–4.10

---

### [Phase 5: Domain Brain — Hybrid Graph + Vector RAG](roadmap/phase_5_domain_brain.md)

Persistent domain knowledge system: cross-service impact analysis, SLA-aware spec authoring, automated architectural consistency. Extends the in-memory topology graph (Phase 2) into a persistent, event-driven knowledge graph. Enhanced with hierarchical memory scoping, composite scoring (semantic + recency + importance), and LLM-powered memory consolidation (keep/update/delete/insert_new). _(informed by [CrewAI](https://github.com/crewAIInc/crewAI) memory architecture)_

**Features**: 5.1 (Persistent Graph) → 5.2 (EDKG) → 5.3 (GC) → 5.4 (Hybrid RAG + Composite Scoring) → 5.5 (Provenance) → 5.6 (Socratic Drafting) → 5.7 (Memory Consolidation)

---

### [Phase 6: External Validation](roadmap/phase_6_external_validation.md)

SpecWeaver is used on a real project that isn't SpecWeaver itself (e.g., the automatic trading system — 20 microservices). Full workflow validation and experience documentation.

---

## Timeline Estimate (Spare-Time + AI Agents)

```
Phase 1: MVP (Steps 1-6)     ████████████████████████████     (~8-12 sessions)  [Steps 1-5 ✅, Step 6 ⏸]
Phase 2: Flow Engine (7-14)   ████████████████████████████████ (~10-14 sessions) [Steps 7-12 ✅]
Phase 3: Feature Expansion    ████████████████████████████████ (~open-ended, feature by feature) [Feature 3.6 ✅]
Phase 4: Advanced             ████████████████████████████████ (~open-ended)
Phase 5: Domain Brain         ████████████████             (~when in-memory graph proves insufficient)
Phase 6: External             ████████                         (~2-3 sessions)
                              ─────────────────────────────────────────────
                              S1        S5        S10       S15        ...
```

> [!TIP]
> **Agent leverage**: Steps 2-3 (validation rules) are prime candidates for AI-assisted implementation — each rule is a small, self-contained function with clear inputs/outputs. Steps 4-5 (LLM features) require more human judgment on prompt design.

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
8. ✅ You've used it on an external project (trading system)
9. ✅ Features can be added without restructuring (interface extensibility confirmed)
10. ✅ Topology-aware spec authoring catches cross-service issues before code generation
11. ✅ Multi-project management: `sw projects`, `sw use`, `sw remove`, `sw update`, `sw scan`

---

## Superseded Document

This roadmap replaces the original `specweaver_roadmap.md` from flowManager, which described evolving the flowManager engine (recursive flow execution, atoms, sub-flows, state persistence, crash recovery). That approach was abandoned in favor of a fresh start — see [ORIGINS.md](../ORIGINS.md) for the full history.
