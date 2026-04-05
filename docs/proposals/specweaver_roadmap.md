# SpecWeaver Roadmap

> **Date**: 2026-03-08 | **Updated**: 2026-03-27
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
- ✅ Validation config: `sw config list` and `--pipeline` cascade overrides
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
**Phase 3 (Features)**: Features 3.1 through 3.6 ✅ | Feature 3.7 🔧 | Features 3.8 through 3.20b ✅ (3785 total tests)

**What we're building next** (see [mvp_feature_definition.md](mvp_feature_definition.md)):
- ✅ Feature 3.5: Auto-discover standards from codebase — multi-language (Py/JS/TS)
- ✅ **Post-3.5 cleanup**: Consolidate DB `validation_overrides` vs YAML inheritance (Completed in 3.20b)
- ✅ Feature 3.6: Explicit plan phase (Spec → Plan → Tasks) (Including Stitch Mockups)
- 🔧 Feature 3.7: REST API server (`sw serve`) — TDD phases 1–3 complete
- ✅ Feature 3.8: Web Dashboard (`sw serve`) — HTMX, Jinja2
- ✅ Feature 3.9: Podman/Docker containerization — Volume mounts, remote access
- ✅ Feature 3.10: Agentic research tools (FileSearch, WebSearch)
- ✅ Feature 3.11: Auto spec-mention detection — Scanner + injection algorithms
- ✅ Feature 3.12: Token & cost telemetry — Usage tracking, costs CLI, runner flush
- ✅ Feature 3.13: Multi-provider adapter registry — Auto-discovery (OpenAI, Anthropic, Qwen)
- ✅ Feature 3.14: Static model routing — Task-type to provider+model routing override
- ✅ Feature 3.15: Project metadata injection — Archetype context scaling
- ✅ Feature 3.16: Unified Runner Architecture & Universal Logging
- ✅ Feature 3.17: Spec-to-code traceability — Artifact Lineage Graph
- ✅ Feature 3.18: AST Drift Detection & AI Root-Cause Analysis — Parser-backed drift gating
- ✅ Feature 3.19: Polyglot QARunner Interface — Black Box execution wrapping
- ✅ Feature 3.20a: Internal Layer Enforcement (Tach) — Strict Domain-Driven isolation
- ✅ Feature 3.20b: Dynamic Risk-Based Rulesets (DAL) — Contextual baseline risk enforcement

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

**Features**: 3.1 (L2 Decomposition ✅) → 3.2 (Constitution ✅) → 3.3 (Domain Profiles ✅) → 3.4 (Custom Rules ✅) → 3.5 (Standards Auto-Discover ✅) → 3.6 (Plan Phase ✅) → 3.7 (REST API 🔧) → 3.8 (Web Dashboard ✅) → 3.9 (Container ✅) → 3.10 (Research Tools ✅) → 3.11 (Auto-Mention ✅) → 3.12 (Telemetry ✅) → 3.13 (Multi-Provider Registry ✅) → 3.14 (Static Routing ✅) → 3.15 (Metadata Injection ✅) → 3.16 (Unified Runner ✅) → 3.17 (Artifact Lineage ✅) → 3.18 (AST Drift Detection ✅) → 3.19 (Polyglot Runner ✅) → 3.20a (Internal Layer Enforcement 🚧) → 3.20b (Dynamic Rulesets ✅) → 3.21+ (Upcoming)

---

### [Phase 4: Advanced Capabilities](roadmap/phase_4_advanced.md)

Features from `future_capabilities_reference.md` that require significant engineering: symbol index, AST chunking, RAG, tiered access, multi-agent review, conversation summarization, mutation testing, Web UI. Also includes LLM cost analytics sub-features that build on 3.13's telemetry data.

**Features**: 4.1 (Symbol Index) → 4.2 (AST Chunking) → 4.3 (RAG) → 4.4 (Access Rights) → 4.5 (Multi-Agent) → 4.5a (Task-Type Cost Analytics — spending dashboards, model comparison) → 4.5b (Artifact Lineage Graph — merges with 3.17) → 4.5c (Deterministic Friction Detection — diff-based upstream attribution) → 4.5d (Data-Driven Routing Recommendations — suggest model swaps) → 4.6–4.10

---

### [Phase 5: Domain Brain — Hybrid Graph + Vector RAG](roadmap/phase_5_domain_brain.md)

Persistent domain knowledge system: cross-service impact analysis, SLA-aware spec authoring, automated architectural consistency. Extends the in-memory topology graph (Phase 2) into a persistent, event-driven knowledge graph. Enhanced with hierarchical memory scoping, composite scoring (semantic + recency + importance), and LLM-powered memory consolidation (keep/update/delete/insert_new). _(informed by [CrewAI](https://github.com/crewAIInc/crewAI) memory architecture)_

**Features**: 5.1 (Persistent Graph) → 5.2 (EDKG) → 5.3 (GC) → 5.4 (Hybrid RAG + Composite Scoring) → 5.5 (Provenance) → 5.5a (HITL Root-Cause Tagging — label failures for routing data) → 5.6 (Socratic Drafting) → 5.7 (Memory Consolidation) → 5.8 (🔬 Dynamic Routing + AI Arbiter — ALS scoring, auto model selection)

---

### [Phase 6: External Validation](roadmap/phase_6_external_validation.md)

SpecWeaver is used on a real project that isn't SpecWeaver itself (e.g., the automatic trading system — 20 microservices). Full workflow validation and experience documentation.

---

## Timeline Estimate (Spare-Time + AI Agents)

```
Phase 1: MVP (Steps 1-6)     ████████████████████████████     (~8-12 sessions)  [Steps 1-5 ✅, Step 6 ⏸]
Phase 2: Flow Engine (7-14)   ████████████████████████████████ (~10-14 sessions) [Steps 7-12 ✅]
Phase 3: Feature Expansion    ████████████████████████████████ (~open-ended, feature by feature) [Feature 3.7 🔧]
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
