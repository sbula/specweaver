# Phase 3: Feature Isolation & Incremental Expansion

> **Status**: Active (Phase 2 complete)
> **Goal**: Take each major capability from the architecture docs, isolate it as a self-contained feature, and implement it one by one. Each feature is proposed → approved → implemented → tested → merged.

> [!IMPORTANT]
> **Before starting any feature**: check [ORIGINS.md](../../ORIGINS.md) for blueprint references. Many features below are inspired by patterns in other open-source projects — those entries include direct links to source files, classes, and docs to study. Don't start from scratch when a working reference implementation exists.

Order will be based on value and dependencies. Likely sequence:

| Priority | Feature | Source Doc | Why This Order |
|:---|:---|:---|:---|
| **3.1** ✅ | Feature Spec layer (L2 decomposition) | `lifecycle_layers.md` | `SpecKind` enum (feature/component), kind-aware rule presets, `DecomposeHandler`, confidence-based review scoring, `feature_decomposition.yaml` pipeline. **Complete**: 8 components, 1886 tests. See [implementation plan](phase_3/feature_3_1_implementation_plan.md). |
| **3.2** ✅ | Constitution as first-class artifact | `constitution_template.md` | Project-wide governing doc (`CONSTITUTION.md`) injected into every LLM call. Walk-up resolution, configurable size limits, CLI management (`sw constitution show/check/init`). **Complete**: constitution loader, PromptBuilder integration, handler threading, CLI commands, 1974 tests. See [implementation plan](phase_3/feature_3_2_implementation_plan.md). _(inspired by [Spec Kit](https://github.com/github/spec-kit), [DMZ SOUL.md](https://github.com/TheMorpheus407/the-dmz))_ |
| **3.3** ✅ | Domain profiles for threshold calibration | `future_capabilities_reference.md` §19 | Named preset bundles (5 profiles: web-app, data-pipeline, library, microservice, ml-model). `config/profiles.py`, DB v5 migration (`domain_profile` column), 5 CLI commands. Bulk-writes to DB override layer. **Complete**: 3 components, 2038 tests. See [implementation plan](phase_3/feature_3_3_implementation_plan.md). |
| **3.4** ✅ | Custom rule paths (rules-as-pipeline architecture) | _(deferred from Step 8b)_ | Validation sub-pipeline: `ValidationPipeline` / `ValidationStep` models, YAML-defined pipelines with inheritance (extends/override/remove/add), circular-extends guard, `sw list-rules`, `--pipeline` override, custom D-prefix rule loader, `RuleAtom` adapter, profile-specific pipelines, project-local pipeline overrides, `apply_settings_to_pipeline()`. **Complete**: 10 components, 2181 tests. See [implementation plan](phase_3/feature_3_4_implementation_plan.md). |
| **3.5** ✅ | Auto-discover standards from codebase | _(new)_ | Extend `sw scan --standards` → extract naming, error handling, type hints, docstring style, test patterns, import patterns from code (Python + JS/TS). Store in DB (schema v6 `project_standards` table). Auto-inject via `PromptBuilder.add_standards()`. Bootstrap `CONSTITUTION.md` from conventions. **Complete**: 4 sub-phases (Python analyzer, scanner+CLI+DB, JS/TS analyzers, constitution bootstrap), 2774 tests. See [implementation plan](phase_3/feature_3_5_implementation_plan.md). _(inspired by [Agent OS v3](https://github.com/buildermethods/agent-os))_ |
| | | | ⚠️ **Post-3.5 cleanup required**: Consolidate validation override mechanisms. DB `validation_overrides` table (3.3) and validation sub-pipeline YAML inheritance (3.4) both configure per-project rule thresholds. Decide: sub-pipelines as single source of truth, or DB overrides as runtime layer on top? See discussion below. |
| **3.6** ✅ | Explicit plan phase (Spec → Plan → Tasks) | _(new)_ | New `PLAN+SPEC` handler between validate and implement. Captures architecture decisions, tech stack choices, constraint reasoning in a structured Plan artifact before code generation. Includes [Google Stitch](https://stitch.withgoogle.com/) via its SDK to auto-generate interactive UI mockups from the spec's Contract section. |
| **3.7** 🔧 | **`sw serve` — REST API server** | _(new)_ | FastAPI server exposing all CLI commands as REST endpoints. Foundation for **all** external UIs (web dashboard, VS Code extension, IntelliJ plugin, tablet). Endpoints: project management, validation, review triggers, pipeline status/control, config CRUD, gate decisions (approve/reject with remarks). JSON responses reuse existing Pydantic models. WebSocket channel for real-time pipeline progress. **In progress**: TDD phases 1–3 complete (57 API tests), 3128 total tests. |
| **3.8** ✅ | **Web dashboard** (minimal) | _(new)_ | Lightweight FastAPI + Jinja2/HTMX dashboard served by `sw serve`. Views: project list, pipeline status, pending HITL reviews with approve/reject buttons, review verdict display, remarks text area. Mobile-responsive — works on tablet (the "train" scenario). No heavy JS framework; server-rendered HTML. **Complete:** 3142 tests. |
| **3.9** ✅ | **Podman/Docker containerization** | _(new)_ | `Containerfile` bundling Python + `sw` CLI + SQLite + `sw serve`. Volume-mount `/projects` for host file access with strict path boundaries. Port: 8000 (unified). One-command deployment: `podman run --env-file .env -v ./myproject:/projects -p 8000:8000 ghcr.io/sbula/specweaver`. Centralized `config/paths.py` with `SPECWEAVER_DATA_DIR` env var. `CORS_ORIGINS` env var for remote dashboard access. CI/CD via GitHub Actions → GHCR. **Complete:** 3160 tests. |
| **3.10** ✅ | Agentic research tools (FileSearch, WebSearch) | `mvp_feature_definition.md` | LLM function-calling via provider-agnostic abstraction. 6 tools (4 filesystem + 2 web) in `loom/commons/research/`. `WorkspaceBoundary` enforcement, `ToolExecutor`, `generate_with_tools()` on adapter. Wired into Reviewer + Planner. **Complete**: boundaries, executor, tool definitions, adapter integration, 3353 tests. See [implementation plan](phase_3/feature_3_10_implementation_plan.md). |
| **3.11** ✅ | Auto spec-mention detection _(inspired by Aider)_ | _(new)_ | Scan LLM responses for spec/file names → auto-pull into context for follow-up calls. Pure-logic `llm/mention_scanner/` module + resolver with workspace boundary enforcement. Follow-up injection wired through `Reviewer.mentioned_files` param. **Complete**: scanner, resolver, PromptBuilder integration, follow-up injection, 3353 tests. See [implementation plan](phase_3/feature_3_11_implementation_plan.md). |
| **3.12** | Multi-model LLM support (dynamic routing) | `future_capabilities_reference.md` §9, §15 | Route prompts to best model per task by result/cost ratio (Gemini, Claude, Qwen, Mistral, OpenAI); interface already abstracted |
| **3.12a** | LLM cost & token tracking per task | _(new)_ | Track token counts (input/output) and compute costs per model per task type (draft/review/implement/check). Aggregate into cost reports. Enables data-driven model selection in 3.12 — find the best result/cost ratio per task. Uses existing `TokenBudget` + `LLMResponse` metadata. |
| **3.13** | Project metadata injection _(inspired by Aider)_ | _(new)_ | Inject project name, archetype, language target, date, active config into system prompt; similar to Aider's `get_platform_info()` |
| **3.14** | Spec-to-code traceability | `future_capabilities_reference.md` §17 | Bidirectional linking |
| **3.15** | Automated iterative decomposition (multi-level) | `future_capabilities_reference.md` §18 | Builds on 3.1's foundation: DMZ-style iterative loop, automated quality gates (Structure Tests 1-5 + Change Map coverage), recursive decomposition (feature → sub-features → components). Agent proposes, HITL approves |
| **3.16** | Smart scan exclusions (tiered) | _(inspired by PasteMax)_ | 3-tier file exclusion: binary exts, default patterns (.git, __pycache__), per-project overrides + `.specweaverignore` |
| **3.17** | File watcher (`sw watch`) | _(inspired by PasteMax)_ | Auto-re-validate specs on disk change; DX polish for iterative authoring |
| **3.18** | Router-based flow control | _(new)_ | Conditional branching in pipelines — route specs to different pipeline paths based on assessment (e.g., simple → fast track, complex → full decomposition, unclear → HITL). New `router` YAML key on steps. _(inspired by [CrewAI](https://github.com/crewAIInc/crewAI) `@router()`)_ |
| **3.19** ⏸ | Pipeline visualization (`sw graph`) | _(deferred)_ | Auto-generate Mermaid diagrams from pipeline YAML definitions. **Postponed** — most valuable after 3.18 (Router) and 3.21 (Fan-out) add non-linear flow. _(inspired by [CrewAI](https://github.com/crewAIInc/crewAI) `flow.plot()`)_ |
| **3.20** | **Scenario Testing — Independent Verification** | _(inspired by agent-system, NVIDIA HEPH, BDD renaissance)_ | Dual-pipeline architecture: coding + scenario pipelines run in parallel, meet at JOIN gate. Contract-first (Python Protocols), structured YAML scenarios, arbiter agent for error attribution. See [proposal](scenario_testing_proposal.md) and [ORIGINS.md](../../ORIGINS.md). |
| **3.21** | Multi-spec pipeline fan-out | _(from 3.1 analysis)_ | Sub-pipeline spawning: decomposition outputs N component specs, each runs its own L3 pipeline. Parent pipeline waits for all children. Sequential first, parallel later. Depends on 3.1. |
| **3.22** | Structured output schemas | _(new)_ | Declarative JSON schemas for pipeline results (validation, review, generation). Same data renders as Rich console (CLI), cards (Web UI), or inline decorations (IDE). Prerequisite for 3.8 dashboard and 3.23 VS Code extension. _(inspired by [Google A2UI](https://github.com/google/A2UI))_ |
| **3.23** | **VS Code extension** | _(new)_ | Thin extension that calls `sw serve` REST endpoints. Tree view for registered projects, inline review verdicts, "Approve/Reject" buttons in status bar, pipeline progress panel. Depends on 3.7 (API) and 3.22 (structured schemas). Later: IntelliJ/Eclipse adapters use the same REST API with different UI wrappers. |

## Process for Each Feature

1. Write an isolation proposal (what, inputs, outputs, interfaces, scope)
2. HITL approves the proposal
3. Implement with tests
4. Dogfood on SpecWeaver itself
5. Validate
6. Merge

---

## 3.20 Scenario Testing — Implementation Steps

> **Depends on**: Phase 2 Steps 11–12 (flow engine runner + gates), Phase 3.14 (spec-to-code traceability).
> **Full proposal**: [scenario_testing_proposal.md](scenario_testing_proposal.md)

| Sub-step | Component | Description |
|:---------|:----------|:------------|
| **3.20a** | Spec template enforcement | Require `## Scenarios` section in specs with structured inputs (preconditions, inputs, expected outputs) in YAML code blocks. Enhance S07 to validate. |
| **3.20b** | API contract generation | New handler: `generate+contract` — extract Python Protocol/ABC from spec Contract section. Output: `api_contract.py`. |
| **3.20c** | Scenario generation atom | New atom: spec + API contract → structured YAML scenarios (LLM). Multiple scenarios per public method: happy path, error paths, boundary, state transitions. |
| **3.20d** | Scenario → pytest conversion | New atom: structured YAML scenarios → executable parametrized pytest files. Mechanical conversion, no LLM needed. |
| **3.20e** | `scenario_agent` role | New role in loom/tools: sees `specs/` + `scenarios/` only. `FileSystemTool` path allowlist per role. |
| **3.20f** | `scenario_validation.yaml` | New pipeline definition: generate_contract → generate_scenarios → convert_to_pytest → signal READY. |
| **3.20g** | JOIN gate type | New `GateType.JOIN` in `models.py` — waits for two pipelines to both signal READY before proceeding. |
| **3.20h** | Pipeline orchestrator | Runs coding + scenario pipelines in parallel. Synchronizes at JOIN gate. |
| **3.20i** | Arbiter agent | Third agent with full read access. On scenario test failure: determines fault (code/scenario/spec), produces filtered feedback to each pipeline. |
| **3.20j** | Feedback loop & retry | Coding agent gets stack traces + spec references. Scenario agent gets expected vs actual + spec references. Neither sees other's code. Loop back if fixable, HITL escalation if spec ambiguity. |

---

## ⚠️ Post-3.5 Cleanup: Validation Override Consolidation

After Feature 3.5 is complete, we must consolidate two mechanisms that both configure per-project rule behavior:

| Mechanism | Feature | Where | What it does |
|---|---|---|---|
| `validation_overrides` table | 3.3 (Domain Profiles) | `~/.specweaver/specweaver.db` | Enable/disable rules, set warn/fail thresholds per project. Written by `sw config set-profile`. |
| Sub-pipeline YAML inheritance | 3.4 (Rules-as-Pipeline) | `.specweaver/pipelines/*.yaml` + built-in defaults | `extends`/`override`/`remove`/`add` operations define which rules run and in what order. Profile-specific pipeline files. |

**Problem**: Both mechanisms configure "which rules run with what thresholds" — creating duplication and ambiguity about which layer wins.

**Options to evaluate**:

1. **Sub-pipelines as single source of truth** — Remove `validation_overrides` from DB. Domain profiles become YAML pipeline definitions only. CLI commands (`sw config set-profile`) write YAML instead of DB rows.
   - ✅ Single mechanism, YAML is human-readable, versioned in git
   - ❌ Requires migration of existing DB overrides

2. **DB overrides as runtime layer on top of YAML** — Keep both. Pipeline YAML defines the base, DB overrides apply at runtime via `apply_settings_to_pipeline()`.
   - ✅ Clear precedence (YAML = structure, DB = runtime tuning)
   - ❌ Two places to look, debugging harder

3. **Merge into DB only** — Pipelines stored in DB, not YAML files.
   - ❌ Loses git versioning, harder to review
   - ❌ Against "no SpecWeaver in project folder" principle (already in DB, so OK), but YAML is more transparent

**Decision required after 3.5 is complete.** Track in Feature 3.5b or a dedicated cleanup task.
