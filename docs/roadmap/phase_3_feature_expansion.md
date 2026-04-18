# Phase 3: Feature Isolation & Incremental Expansion

> **Status**: Active (Phase 2 complete)
> **Goal**: Take each major capability from the architecture docs, isolate it as a self-contained feature, and implement it one by one. Each feature is proposed → approved → implemented → tested → merged.

> [!IMPORTANT]
> **Before starting any feature**: check [ORIGINS.md](../../ORIGINS.md) for blueprint references. Many features below are inspired by patterns in other open-source projects — those entries include direct links to source files, classes, and docs to study. Don't start from scratch when a working reference implementation exists.

Order will be based on value and dependencies. Likely sequence:

| Priority | Feature | Source Doc | Why This Order |
|:---|:---|:---|:---|
| **3.1** ✅ | Feature Spec layer (L2 decomposition) | `lifecycle_layers.md` | `SpecKind` enum (feature/component), kind-aware rule presets, `DecomposeHandler`, confidence-based review scoring, `feature_decomposition.yaml` pipeline. **Complete**: 8 components, 1886 tests. See [implementation plan](phase_3/feature_3_01/feature_3_01_implementation_plan.md). |
| **3.2** ✅ | Constitution as first-class artifact | `constitution_template.md` | Project-wide governing doc (`CONSTITUTION.md`) injected into every LLM call. Walk-up resolution, configurable size limits, CLI management (`sw constitution show/check/init`). **Complete**: constitution loader, PromptBuilder integration, handler threading, CLI commands, 1974 tests. See [implementation plan](phase_3/feature_3_02/feature_3_02_implementation_plan.md). _(inspired by [Spec Kit](https://github.com/github/spec-kit), [DMZ SOUL.md](https://github.com/TheMorpheus407/the-dmz))_ |
| **3.3** ✅ | Domain profiles for threshold calibration | `future_capabilities_reference.md` §19 | Named preset bundles (5 profiles: web-app, data-pipeline, library, microservice, ml-model). `config/profiles.py`, DB v5 migration (`domain_profile` column), 5 CLI commands. Bulk-writes to DB override layer. **Complete**: 3 components, 2038 tests. See [implementation plan](phase_3/feature_3_03/feature_3_03_implementation_plan.md). |
| **3.4** ✅ | Custom rule paths (rules-as-pipeline architecture) | _(deferred from Step 8b)_ | Validation sub-pipeline: `ValidationPipeline` / `ValidationStep` models, YAML-defined pipelines with inheritance (extends/override/remove/add), circular-extends guard, `sw list-rules`, `--pipeline` override, custom D-prefix rule loader, `RuleAtom` adapter, profile-specific pipelines, project-local pipeline overrides, `apply_settings_to_pipeline()`. **Complete**: 10 components, 2181 tests. See [implementation plan](phase_3/feature_3_04/feature_3_04_implementation_plan.md). |
| **3.5** ✅ | Auto-discover standards from codebase | _(new)_ | Extend `sw scan --standards` → extract naming, error handling, type hints, docstring style, test patterns, import patterns from code (Python + JS/TS). Store in DB (schema v6 `project_standards` table). Auto-inject via `PromptBuilder.add_standards()`. Bootstrap `CONSTITUTION.md` from conventions. **Complete**: 4 sub-phases (Python analyzer, scanner+CLI+DB, JS/TS analyzers, constitution bootstrap), 2774 tests. See [implementation plan](phase_3/feature_3_05/feature_3_05_implementation_plan.md). _(inspired by [Agent OS v3](https://github.com/buildermethods/agent-os))_ |
| **3.6** ✅ | Explicit plan phase (Spec → Plan → Tasks) | _(new)_ | New `PLAN+SPEC` handler between validate and implement. Captures architecture decisions, tech stack choices, constraint reasoning in a structured Plan artifact before code generation. Includes [Google Stitch](https://stitch.withgoogle.com/) via its SDK to auto-generate interactive UI mockups from the spec's Contract section. |
| **3.7** 🔧 | **`sw serve` — REST API server** | _(new)_ | FastAPI server exposing all CLI commands as REST endpoints. Foundation for **all** external UIs (web dashboard, VS Code extension, IntelliJ plugin, tablet). Endpoints: project management, validation, review triggers, pipeline status/control, config CRUD, gate decisions (approve/reject with remarks). JSON responses reuse existing Pydantic models. WebSocket channel for real-time pipeline progress. **In progress**: TDD phases 1–3 complete (57 API tests), 3128 total tests. |
| **3.8** ✅ | **Web dashboard** (minimal) | _(new)_ | Lightweight FastAPI + Jinja2/HTMX dashboard served by `sw serve`. Views: project list, pipeline status, pending HITL reviews with approve/reject buttons, review verdict display, remarks text area. Mobile-responsive — works on tablet (the "train" scenario). No heavy JS framework; server-rendered HTML. **Complete:** 3142 tests. _Future: after 3.12a, dashboard gains cost-override editing via existing REST endpoints — zero new backend code._ |
| **3.9** ✅ | **Podman/Docker containerization** | _(new)_ | `Containerfile` bundling Python + `sw` CLI + SQLite + `sw serve`. Volume-mount `/projects` for host file access with strict path boundaries. Port: 8000 (unified). One-command deployment: `podman run --env-file .env -v ./myproject:/projects -p 8000:8000 ghcr.io/sbula/specweaver`. Centralized `config/paths.py` with `SPECWEAVER_DATA_DIR` env var. `CORS_ORIGINS` env var for remote dashboard access. CI/CD via GitHub Actions → GHCR. **Complete:** 3160 tests. |
| **3.10** ✅ | Agentic research tools (FileSearch, WebSearch) | `mvp_feature_definition.md` | LLM function-calling via provider-agnostic abstraction. 6 tools (4 filesystem + 2 web) in `loom/commons/research/`. `WorkspaceBoundary` enforcement, `ToolExecutor`, `generate_with_tools()` on adapter. Wired into Reviewer + Planner. **Complete**: boundaries, executor, tool definitions, adapter integration, 3353 tests. See [implementation plan](phase_3/feature_3_10/feature_3_10_implementation_plan.md). |
| **3.11** ✅ | Auto spec-mention detection _(inspired by Aider)_ | _(new)_ | Scan LLM responses for spec/file names → auto-pull into context for follow-up calls. Pure-logic `llm/mention_scanner/` module + resolver with workspace boundary enforcement. Follow-up injection wired through `Reviewer.mentioned_files` param. **Complete**: scanner, resolver, PromptBuilder integration, follow-up injection, 3353 tests. See [implementation plan](phase_3/feature_3_11/feature_3_11_implementation_plan.md). |
| **3.11a** ✅ | Architectural debt clean-up (3.10 & 3.11) | `architecture_reference.md` | Address accumulated tech debt: refactor Planner to use `PromptBuilder`, extract LLM tool-use loop from adapters to allow mid-loop injection callbacks, delete `loom/commons/research/` moving dispatcher to `loom/` root, merge `WorkspaceBoundary` into `FolderGrant`, and decentralize `ToolDefinition`s. |
| **3.11b** ✅ | Post-3.5 validation override consolidation | _(deferred from 3.5)_ | **Resolved — no code change needed.** Audit confirmed the dual-layer design is intentional and already well-documented: YAML pipelines (3.4) define structure, DB overrides (3.3) provide runtime tuning, `--set` flags give ephemeral CLI overrides. Cascade: `YAML → DB → --set`. Bridge: `apply_settings_to_pipeline()`. |
| **3.12** ✅ | Token & cost telemetry | _(split from original 3.12)_ | Log `model_id`, `prompt_tokens`, `completion_tokens`, `estimated_cost` on every LLM call. `TelemetryCollector` (decorator), `UsageRecord`/`estimate_cost()`, `TelemetryMixin` (DB persistence), schema v9, factory telemetry wrapping, task_type attribution in flow handlers. CLI: `sw usage` (summary table with `--all`/`--since`), `sw costs` (view/set/reset overrides). Runner + CLI + API flush integration via `context.db`. **Complete**: 3451 tests. |
| **3.13** ✅ | Multi-provider adapter registry | _(split from original 3.12)_ | Auto-discovery registry: each adapter is self-describing (`provider_name`, `api_key_env_var`, `default_costs`). System scans `llm/adapters/` at import → builds registry automatically. Adding a new provider = one file, zero other changes. **Complete**: Registry auto-discovery, schemas V10, 5 adapters (Gemini, OpenAI, Anthropic, Mistral, Qwen), factory integration, and `sw config set-provider`. 3531 tests. |
| **3.14** ✅ | Static model routing (config-driven) | _(split from original 3.12)_ | Map task types to models in config: `review → claude`, `implement → gemini-pro`. Uses registry to resolve provider+model. No AI, no learning — pure user configuration. **Complete:** 3568 tests total. |
| **3.15** ✅ | Project metadata injection _(inspired by Aider)_ | _(new)_ | Inject project name, archetype, language target, date, active config into system prompt; similar to Aider's `get_platform_info()`. **Complete**: 3587 tests. |
| **3.16** ✅ | **Unified Runner Architecture & Universal Logging** | _(new)_ | Refactor single-shot CLI commands (`sw review`, `sw draft`, etc.) to use dynamic 1-step pipelines via `PipelineRunner`. Standardizes execution, telemetry, and state tracking. Includes project-wide logging reform. **Complete**: 3589 tests. |
| **3.17** ✅ | Spec-to-code traceability (Artifact Lineage Graph) | `future_capabilities_reference.md` §17 | Core database-backed lineage tracking and #sw-artifact tagging. Enables exact LLM provenance attribution and cost-per-feature analysis while remaining orthogonal to AST dependencies. **Complete**: 3591 tests. |
| **3.18** ✅ | AST Drift Detection & AI Root-Cause Analysis | _(deferred from 3.14)_ | Builds on UUIDs to provide deep, parser-backed drift detection. **Complete**: SF-1 and SF-2 integrated into Flow engine and CLI. Tests passing. |
| **3.19** ✅ | Polyglot QARunner Interface | _(new)_ | Wraps target-language CLI commands (`cargo`, `gradlew`, `pytest`) into a unified `LanguageRunnerInterface`. Treats execution as a Black Box (validating exit codes/stderr) to prevent Python AST hardcoding. **Complete.** |
| **3.20a** ✅ | Internal Layer Enforcement (Tach) | _(split from 3.20)_ | Installed and configured Tach to enforce strict Domain-Driven layer isolation inside SpecWeaver's internal architecture, deleting `__init__.py` boilerplate and stopping L3 capabilities from importing L1 CLI dependencies. **Complete**: Replaced Ruff TID252, globally enforced implicitly bound namespaces, and subsumed legacy C05 rules to use Tach. |
| **3.20b** ✅ | Dynamic Risk-Based Rulesets (DAL) | _(split from 3.20)_ | Injects strict constraints or relaxed defaults into the fixed 10-test battery based on the target module's domain risk (DAL) via "Fractal Resolution," outsourcing FFI boundary checks to native tools (Tach, ArchUnit, ESLint). Replaced legacy Database Validation Overrides with Pipeline YAML Inheritance. **Complete**: 3684 tests. |
| **3.21** ✅ | Automated Traceability Matrix (`@traces`) | _(new)_ | Mathematically counts FRs/NFRs in the L3 spec and asserts exact matching `@traces(req_id)` tags in the AST of generated test files. Hard-fails pipeline if coverage is incomplete, preventing "Correlated Hallucinations." |
| **3.22** ✅ | Polyglot AST Skeleton Extractor | _(new)_ | _Pivoted from Context Ledger (304 Caching) to prevent LLM memory hallucination._ Provides `read_skeleton`, `read_symbol`, and AST mutation capabilities via Tree-Sitter. **Complete**: SF-1 (Read) and SF-2 (Write) across 5 languages fully completed and bound to Engine with 90%+ coverage. |
| **3.23** ✅ | Bi-Directional Spec Rot Interceptor | _(new)_ | The "2nd-Day Problem" solver. Blocks builds/commits if the implementation AST diverges from the `Spec.md` markdown, forcing developers to reconcile documentation with hot-fixes. **Complete:** SF-1 and SF-2 integrated into Flow engine and CLI. Tests passing. |
| **3.24** ✅ | Automated iterative decomposition (multi-level) | `future_capabilities_reference.md` §18 | Builds on basic foundation: DMZ-style iterative loop, automated quality gates, recursive decomposition (feature → sub-features → components). |
| **3.25** ✅ | Router-based flow control | _(new)_ | Conditional branching in pipelines — route specs to different pipeline paths based on assessment (e.g., simple → fast track, complex → full decomposition). New `router` YAML key on steps. **Complete**: 3877 tests. |
| **3.26** ✅ | Git Worktree Bouncer (Sandbox) | [Design ✅](phase_3/feature_3.26/feature_3.26_design.md) | Provides dictatorial validation while fully supporting native IDEs. Clones current target to a `git worktree` for the Agentic IDE. Mathematical diff striping auto-rejects and deletes LLM hallucinations to forbidden files before merge. **Complete**: 3884 tests. |
| **3.26a** ✅ | **Domain-Driven Module Consolidation** | _(from 3.26 discussion)_ | Massive architectural refactoring of flat directories into strict DDD boundaries. Moves L1-L5 phases to `workflows/` (drafting, review, implementation, planning), pure-logic discovery to `assurance/` (standards, validation), physical state to `workspace/` (project, context), and external endpoints to `interfaces/` (api, cli). Fixes all absolute Python imports across 3800 tests. |
| **3.26c** ✅ | **Interactive Gate Variables (HITL)** | _(new)_ | Immediately actionable. Updates `PromptBuilder` to explicitly isolate human `GateType.HITL` rejections into a mathematically bound `<dictator-overrides>` XML section, granting them strict promotional weight above standard linter error findings in loop-back generation sequences. **Complete**: 3934 tests. |
| **3.27** ✅ | Multi-spec pipeline fan-out | _(from 3.1 analysis)_ | Sub-pipeline spawning: decomposition outputs N component specs, each runs its own L3 pipeline. Parent pipeline waits for all children. **Critically:** Uses the Topology Graph to mathematically predict file blast radius. Safely runs disjoint components fully in parallel mapped to separate isolated sandboxes, injecting dynamic `SW_PORT_OFFSET` hashes to prevent test collision (port bounds, SQLite locks) without incurring git merge conflicts. **Complete**: 3986 tests. |
| **3.28** ✅ | Scenario Testing — Independent Verification | _(inspired by agent-system)_ | Dual-pipeline architecture: coding + scenario pipelines run in parallel, meet at JOIN gate. Contract-first (Python Protocols), structured YAML scenarios, arbiter agent for error attribution. **Complete:** 4168 tests. |
| **3.28a** ✅ | ↳ Spec template enforcement | _(subfeature)_ | Require `## Scenarios` section in specs with structured inputs (preconditions, inputs, expected outputs) in YAML code blocks. Enhance S07 to validate. |
| **3.28b** ✅ | ↳ API contract generation | _(subfeature)_ | New handler: `generate+contract` — extract Python Protocol/ABC from spec Contract section. Output: `api_contract.py`. |
| **3.28c** ✅ | ↳ Scenario generation atom | _(subfeature)_ | New atom: spec + API contract → structured YAML scenarios (LLM). Multiple scenarios per public method. **Must explicitly map to Spec `req_id`s in the YAML schema.** **Complete:** 4012 tests. |
| **3.28d** ✅ | ↳ Scenario → pytest conversion | _(subfeature)_ | New atom: structured YAML scenarios → executable parametrized pytest files. Mechanical conversion **must inject zero-dependency `# @trace(FR-X)` tags** for C09. **Complete.** |
| **3.28e** ✅ | ↳ `scenario_agent` role | _(subfeature)_ | New role in loom/tools: sees `specs/` + `scenarios/` only. `FileSystemTool` path allowlist per role. **Complete.** |
| **3.28f** ✅ | ↳ `scenario_validation.yaml` | _(subfeature)_ | New pipeline definition: generate_contract → generate_scenarios → convert_to_pytest → signal READY. **Complete.** |
| **3.28g** ✅ | ↳ JOIN gate type | _(subfeature)_ | New `GateType.JOIN` in `models.py` — waits for two pipelines to both signal READY before proceeding. **Complete.** |
| **3.28h** ✅ | ↳ Pipeline orchestrator | _(subfeature)_ | Runs coding + scenario pipelines in parallel. Synchronizes at JOIN gate. **Complete.** |
| **3.28i** ✅ | ↳ Arbiter agent | _(subfeature)_ | Third agent with full read access. On scenario test failure: determines fault (code/scenario/spec), produces filtered feedback to each pipeline. **Complete.** |
| **3.28j** ✅ | ↳ Feedback loop & retry | _(subfeature)_ | Coding agent gets stack traces + spec references. Scenario agent gets expected vs actual + spec references. Neither sees other's code. Loop back if fixable, HITL escalation if spec ambiguity. **Complete.** |
| **3.29** ✅ | Archetype-Based Rule Sets | _(new)_ | Auto-provisioned rules for specific architectural profiles (`kotlin-service`, `rust-worker`) to enforce framework-specific standards inherently. **Complete**: SF-1 (Injection), SF-2 (Language Commons Framework Schemas), and SF-3 (Archetype Rule Bounds + Plugins). |
| **3.30** ✅ | Macro & Annotation Evaluator | _(new)_ | Specialized indexer capable of unrolling Rust Procedural Macros (`#[derive]`) and Kotlin Compiler Plugins (Spring Boot annotations) so the LLM understands the true runtime reality, not just the raw signature. **Complete:** SF-1, SF-2, and SF-3 implemented. 4241 tests natively passing. |
| **3.30a** ✅ | Dynamic Tool Gating via Archetypes | _(new)_ | Branch off from 3.30. Intercepts the `context.yaml` active archetype to mathematically remove or inject specific JSON Schema Tool Definitions (`list_symbols`) to the Agent at generation runtime, strictly enforcing framework-specific capabilities. |
| **3.31** ✅ | Protocol & Schema Analyzers | _(new)_ | Native parsing of `.proto` (gRPC), `openapi.yaml`, and AsyncAPI files to catch contract drift across polyglot microservices. **Complete**: Implementation of native YAML/Proto extractors, Atom/Tool orchestrator bindings, and C13 Contract Drift Rule natively mapped against AST validation. |
| **3.32** | Deep Semantic Hashing | _(new)_ | Replaces shallow file hashing with "Dependency Hashing" (hash changes if imported modules change). Uses Merkle-trees to keep the Topology Graph explicitly in sync without full project crawls. |
| **3.33** | Topology Provider Abstraction | _(new)_ | Toggle between local `SQLite/BM25` (Bicycle mode) and heavy Sidecars like `FalkorDB + VectorDB` (Rocket mode) to map cross-service topologies based on project size. |
| **3.34** | Structured output schemas | _(new)_ | Declarative JSON schemas for pipeline results (validation, review, generation). Same data renders as Rich console (CLI), cards (Web UI), or inline decorations (IDE). Prerequisite for dashboard and VS Code ext. |
| **3.34b** | REST API Synchronization with CLI | _(shifted from 3.48)_ | Update REST API capabilities to achieve full parity with the expanded CLI (e.g., constitution bootstrapping, interactive gate variables, DAL configurations, scenario pipelines). Prerequisite for the VS Code Extension. |
| **3.35** | **VS Code extension** | _(new)_ | Thin extension that calls `sw serve` REST endpoints. Tree view for registered projects, inline review verdicts, "Approve/Reject" buttons in status bar, pipeline progress panel. |
| **3.36** | Smart scan exclusions (tiered) | _(inspired by PasteMax)_ | 3-tier file exclusion: binary exts, default patterns (.git, __pycache__), per-project overrides + `.specweaverignore` |
| **3.37** | File watcher (`sw watch`) | _(inspired by PasteMax)_ | Auto-re-validate specs on disk change; DX polish for iterative authoring |
| **3.38** ⏸ | Pipeline visualization (`sw graph`) | _(deferred)_ | Auto-generate Mermaid diagrams from pipeline YAML definitions. **Postponed** — most valuable after router logic added. |
| **3.39** | Symbolic Math Validation | _(new)_ | Specialized rules to formally verify mathematical/ML calculations (e.g., FinBERT, trading algorithms) generated in execution code. |
| **3.40** | External Context Providers | _(new)_ | Arbitrary script injections (e.g., `dump_db_schema.py`) via `context/providers.py` to pipe live environment schema (like a 900-table DB) into LLM prompts without polluting the core. |
| **3.40b** | **Native CLI Action Nodes** | _(inspired by Archon)_ | Augments 3.40 to introduce declarative `action: bash` pipeline steps. Mandates that all referenced hooks physically reside in the `FolderGrant`-protected `.specweaver/scripts/` directory to prevent Agent RCE. Pipes deterministic `stdout` cleanly into downstream pipeline states, enabling robust terminal orchestration between AI loops. |
| **3.41** | Industry Standard Bridges | _(new)_ | Adapters to interface seamlessly with massive open-source protocols: Pact.io (Consumer contract testing), Glean (Internal Fact Graphs), and ArchCodex (Drift Prevention). |
| **3.42** | Semantic Test Completeness Review (AI Validator) | _(new)_ | An LLM-backed Code Validation Rule (`C10_test_completeness.py`) that analyzes the agent's generated test suite against the target spec to assert whether all unhappy paths, error bounds, and expected outcomes are semantically verified. Emits ERRORs for missing branch coverage to ensure thorough completeness. |
| **3.43** | Reverse-Weaving (`sw capture`) | _(new)_ | Archaeology tool for brownfield adoption. Uses AST "Skeleton Extraction" (signatures + Javadocs) to draft baseline `Spec.md` contracts from legacy DB/Java code. all supported languages |
| **3.44** | OpenTelemetry Agent Tracing | _(new)_ | Directly tracing hierarchical LLM workflow logic out of the `PipelineRunner` using the `OpenTelemetry (OTel)` standard to emit Spans into enterprise endpoints (Jaeger/Datadog) for comprehensive thought observability. |
| **3.45** | Ephemeral Execution Containers (Zero-Trust QA) | _(new)_ | Resolves Agent RCE vulnerabilities. When `QARunner` executes LLM-generated tests (`pytest`), execution routes natively into ephemeral, headless Podman/Docker sub-containers instead of the host machine. |
| **3.46** | **Functional Agent Sandboxing (Black Box Ledgers)** | _(new)_ | Completely disables continuous chat context. Hand-offs managed explicitly via disk ledger: `Request in` → `Context boots` → `Result out` → mechanically valid before next hydration. Prioritizes state determinism over execution speed. |
| **3.47** | Agent Platform Benchmarking (`sw eval`) | _(new)_ | Built-in command to run SpecWeaver's internal pipelines against a deterministic suite of synthetic SWE-bench bugs to mathematically prove that platform extensions haven't degraded the internal token costs or success rate. |

## Process for Each Feature

The full lifecycle is orchestrated by `/feature`. Individual stages can be invoked
standalone for targeted work. The Design Document's Progress Tracker is the single
source of truth for what is done and what remains across all sessions.

### Full lifecycle (recommended)
```
/feature <feature_id>
```

### Individual stages (targeted use)
```
/design <feature_id>
/implementation-plan <design_doc_path> [<sf_id>]
/dev <impl_plan_path>
/pre-commit
```

### Steps

1. **`/design`** — Intake + research + FR/NFR + API validation + arch alignment + decompose
   → Output: `docs/architecture/<feature_id>_design.md` (Status: APPROVED)

2. **`/implementation-plan`** (one run per sub-feature, in dependency order)
   → Technical research + audit (16 categories) + arch check + HITL review + HITL approval
   → Output: `docs/roadmap/phase_3/<feature_id>[_sf<N>]_implementation_plan.md`
   → Updates: Progress Tracker in the Design Document

3. **`/dev`** (one run per implementation plan)
   → TDD (red → green → refactor) per task; `/pre-commit` + HITL gate at every commit boundary
   → Updates: Progress Tracker in the Design Document

4. **Commit** (HITL boundary — mandatory stop after each `/pre-commit` within `/dev`)

5. **Dogfood + validate** (after all sub-features committed)

6. **Merge**

> [!NOTE]
> Sub-features with no shared dependencies may run in parallel sessions.
> Check the Progress Tracker in the Design Document before starting any session.

---

## ⚠️ Post-3.5 Cleanup: Validation Override Consolidation

After Feature 3.5 is complete, we must consolidate two mechanisms that both configure per-project rule behavior:

| Mechanism | Feature | Where | What it does |
|---|---|---|---|
| `validation_overrides` table | 3.3 (Domain Profiles) | `~/.specweaver/specweaver.db` | Enable/disable rules, set warn/fail thresholds per project. Written by `sw config set-profile`. |
| Sub-pipeline YAML inheritance | 3.4 (Rules-as-Pipeline) | `.specweaver/pipelines/*.yaml` + built-in defaults | `extends`/`override`/`remove`/`add` operations define which rules run and in what order. Profile-specific pipeline files. |

**Problem**: Both mechanisms configure "which rules run with what thresholds" — creating duplication and ambiguity about which layer wins.

**Options to evaluate**:

1. **Sub-pipelines as single source of truth** [✅ SELECTED IN FEATURE 3.20b] — Removed `validation_overrides` from DB. Domain profiles became YAML pipeline definitions only.
   - ✅ Single mechanism, YAML is human-readable, versioned in git
   - ✅ Completed in 3.20b via Database Schema V14 migration

2. **DB overrides as runtime layer on top of YAML** [❌ REJECTED]
   - ❌ Two places to look, debugging harder

3. **Merge into DB only** [❌ REJECTED]
   - ❌ Loses git versioning, harder to review

**Status:** Completed in Phase 3.20b. Validation rules and domain profiles completely transitioned to declarative YAML pipelines.
