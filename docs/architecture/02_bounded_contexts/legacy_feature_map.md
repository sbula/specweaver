# Legacy Feature Map

Each feature was built incrementally across 3 phases. For each feature:
**Where** = specific files, **What** = their role, **Why there** = architectural reasoning.

## Phase 1 — MVP (Prove the Core Loop)

**Project scaffold** (`sw init`)
- `project/scaffold.py` — creates directory structure, seeds `CONSTITUTION.md` & `.specweaverignore` globally + registers in DB. Scaffolds native topological boundary maps (`src/context.yaml` and `tests/context.yaml`) dynamically to enforce isolated domains preventing Engine access hallucination. Lives in `project/` (adapter archetype) because it does filesystem I/O to discover/create project structures.
- `config/database.py` — SQLite schema + multi-project registry. Lives in `config/` (pure-logic, leaf) because every module needs settings — it's at the bottom.
- `cli/project_commands.py` — `sw init/use/projects/remove`. Lives in `cli/` (entry-point) — thin delegation to `project/`.

**Loom layer** (filesystem tools + atoms + interfaces)
- `sandbox/filesystem/executor.py` — `FileExecutor`: raw I/O with path validation, symlink blocking, `FolderGrant`. In `commons/` because it's shared infra consumed by both tools and atoms.
- `sandbox/filesystem/tool.py` — `FileSystemTool`: intent-based facade with `ROLE_INTENTS` gating. In `tools/` because it's the agent-facing layer.
- `sandbox/filesystem/interfaces.py` — `ReviewerFileInterface`, `ImplementerFileInterface`, etc. Each role sees only its allowed methods — physically absent, not just blocked.
- `sandbox/filesystem/atom.py` — `FileSystemAtom`: engine-internal ops (unrestricted). In `atoms/` because the engine is trusted.

**Validation engine** (19 rules)
- `validation/runner.py` — `ValidationRunner`: applies rule list to a spec. In `validation/` (pure-logic) because it's stateless computation — no I/O, no LLM.
- `validation/rules/spec/s01_one_sentence.py` through `s11_...py` — individual rule implementations. Each is a pure function: `(spec_text) → findings[]`.
- `validation/rules/code/c01_...py` through `c09_...py` — code quality rules.

**LLM adapter** (Multi-Provider)
- `llm/adapter.py` — `LLMAdapter` abstract base class (provider-agnostic contract). In `llm/` (adapter archetype) because it wraps an external service.
- `llm/adapters/registry.py` — Auto-discovery registry. Scans and registers adapters dynamically at import across the implicit namespace.
- `llm/adapters/gemini.py` — `GeminiAdapter`: Gemini API calls, error translation, response parsing.
- `llm/adapters/openai.py` — `OpenAIAdapter`: OpenAI SDK wrapper with full tool use.
- `llm/adapters/anthropic.py` — `AnthropicAdapter`: Anthropic SDK wrapper with full tool use.
- `llm/adapters/mistral.py` — `MistralAdapter`: Mistral SDK wrapper.
- `llm/adapters/qwen.py` — `QwenAdapter`: Qwen via OpenAI-compatible endpoint.
- `llm/prompt_builder.py` — `PromptBuilder`: XML-tagged block assembly with token budgets and metadata injection (`add_project_metadata`). In `llm/` because prompt construction is part of the LLM abstraction.
- `llm/models.py` — `LLMResponse`, `ToolDefinition`, `TaskType`, `GenerationConfig`. Data models for the LLM contract.
- `llm/telemetry.py` — `estimate_cost()`, `create_usage_record()`, `CostEntry`, `UsageRecord`. Pure-logic cost estimation with configurable pricing tables. In `llm/` because it's LLM-specific pricing logic. *(Feature 3.12)*
- `llm/collector.py` — `TelemetryCollector`: decorator wrapping `LLMAdapter`, captures token usage per call. In `llm/` because it's an adapter-level concern. *(Feature 3.12)*
- `cli/lineage.py` — Lineage tagging and tree exploration CLI commands (`sw lineage tag`, `sw lineage tree`). In `cli/` because it's an end-user presentation layer for artifact databases. *(Feature 3.14)*
- `llm/factory.py` — `create_llm_adapter()`: factory function that creates adapter + optional `TelemetryCollector` wrapping. Loads cost overrides from DB. *(Feature 3.12)*
- `config/_db_telemetry_mixin.py` — `TelemetryMixin`: DB persistence for `llm_usage_log` + `llm_cost_overrides` tables. In `config/` because it's a DB mixin. *(Feature 3.12)*

**Spec drafting** (`sw draft`)
- `drafting/drafter.py` — `Drafter`: multi-turn LLM interaction for spec authoring. In `drafting/` (orchestrator) because it coordinates LLM + HITL context.
- `context/providers.py` — `ContextProvider`, `HITLProvider`: supply project context to the drafter. In `context/` (contract archetype) — pure interfaces, no implementation.

**Spec/Code review** (`sw review`)
- `review/reviewer.py` — `Reviewer`: sends spec/code to LLM, parses structured verdict. In `review/` (orchestrator) — coordinates LLM calls + verdict parsing.
- `review/models.py` — `ReviewResult`, `ReviewVerdict`, `ReviewFinding`. Pure data models.

**Code generation** (`sw implement`)
- `implementation/generator.py` — `CodeGenerator`: spec → code + tests via LLM. In `implementation/` (orchestrator) — coordinates LLM + validation.

## Phase 2 — Flow Engine (Orchestration)

**Topology graph** (`sw context`)
- `graph/topology.py` — `TopologyGraph`: builds dep graph from `context.yaml` files, provides impact analysis, cycle detection. In `graph/` (pure-logic) — stateless computation over context data.
- `graph/selectors.py` — cross-cutting queries ("all modules with archetype=adapter"). Pure functions.

**Config store** (`sw config`, `sw projects`)
- `config/settings.py` — `SpecWeaverSettings`, `ValidationSettings`, `LLMSettings`: Pydantic models with env-var loading + TOML overrides. In `config/` because it's the root of the settings hierarchy.
- `config/database.py` — `Database`: Core SQLite connection provider and CQRS async engine. Stores active state and base project tables. (Lineage, Telemetry, and Flow State are decentralized to bounded context repositories).

**Pipeline models + runner**
- `flow/models.py` — `PipelineDefinition`, `PipelineStep`, `GateDefinition`, `StepAction`, `StepTarget`: pure data model (no execution). In `flow/` because it defines what a pipeline *is*.
- `flow/parser.py` — YAML → `PipelineDefinition` deserialization.
- `flow/runner.py` — `PipelineRunner`: walks steps, dispatches to handlers, evaluates gates. The core execution loop.
- `flow/gates.py` — `GateEvaluator`: auto/hitl/loop_back/retry/abort logic. Extracted from runner for testability.
- `flow/handlers.py` — `StepHandlerRegistry`: maps `(action, target)` → handler class. Each handler (`_draft.py`, `_review.py`, `_validation.py`, `_generation.py`, `_lint_fix.py`, `_decompose.py`) adapts a step to the corresponding domain module.
- `flow/state.py` — `PipelineRun`, `StepRecord`, `StepResult`: mutable run state.
- `flow/store.py` — `StateStore`: SQLite persistence for run state + audit log.
- `pipelines/*.yaml` — declarative pipeline definitions (data, not code).

**Git tools** (sandbox) — same 4-layer pattern as filesystem:
- `sandbox/git/executor.py` — `GitExecutor`: whitelisted git commands, `_BLOCKED_ALWAYS` list.
- `sandbox/git/tool.py` — `GitTool`: conventional commit enforcement, role gating.
- `sandbox/git/interfaces.py` — `ReviewerGitInterface` (read-only), `ImplementerGitInterface` (commit allowed).
- `sandbox/git/atom.py` — `EngineGitExecutor`: unrestricted for engine use.

**Test runner** (sandbox) — same pattern:
- `sandbox/qa_runner/executor.py` — `QARunnerExecutor`: subprocess pytest with output capture.
- `sandbox/qa_runner/tool.py` — `QARunnerTool`: role-gated test execution.
- `sandbox/qa_runner/core/atom.py` — `QARunnerAtom`: engine-internal test runs + lint-fix reflection.

## Phase 3

**Common MCP Client Architecture (3.32c)**
- `flow/handlers/mcp_assembler.py` and `sandbox/mcp/` - establishes Pre-Fetched Context Envelope pattern to natively query and serialize Model Context Protocol (MCP) data for prompt environments safely.

**3.1 Kind-aware validation** — Added `--level feature` thresholds to `validation/`. Created `feature_decomposition.yaml` pipeline in `pipelines/`. Added `DecomposeHandler` to `flow/`. Each lives where its archetype dictates: rules in pure-logic, pipeline in data, handler in orchestrator.

**3.2 Constitution** — `project/constitution.py` handles discovery/validation of `CONSTITUTION.md` (in `project/` because it's filesystem discovery). `llm/prompt_builder.py` got `add_constitution()` (in `llm/` because it's prompt assembly). `cli/constitution_commands.py` added CLI surface.

**3.3 Domain profiles** — `config/profiles.py` defines 5 built-in profiles with threshold presets. Lives in `config/` because profiles are configuration data. DB v5 migration added profile storage. `cli/config_commands.py` added 5 profile CLI commands.

**3.4 Rules-as-pipeline** — `validation/` extended with sub-pipeline YAML definitions using inheritance (`extends: base`). `pipelines/validation_spec_*.yaml` files define domain-specific rule ordering. Custom D-prefix rules loaded from project dirs. `RuleAtom` adapter bridges rules→pipeline execution.

**3.5 Standards auto-discovery** — `standards/analyzer.py` (`StandardsAnalyzer`), `standards/python_analyzer.py` (`PythonStandardsAnalyzer`): single-pass AST extraction for 6 categories. In its own module `standards/` (orchestrator) because it's a self-contained capability that only needs `config/` for DB storage.

**3.6 Plan phase** — `planning/planner.py` (`Planner`): generates structured Plan artifacts from specs. `flow/_generation.py` got `PlanSpecHandler`. Planning is a separate module from implementation because it produces *plans* (architecture decisions, file layout), not *code*.

**3.7 REST API** — `api/` (adapter archetype): FastAPI server wrapping domain modules as HTTP endpoints. Forbidden from importing `cli/` or `sandbox/*` — it's a parallel entry point to CLI, not a wrapper around it.

**3.8 Web dashboard** — Extends `api/` with HTMX+Jinja2 templates for browser UI. Same module because it's the same HTTP server, just with HTML rendering alongside JSON endpoints.

**3.12 Token & Cost Telemetry** — `llm/telemetry.py` (`CostEntry`, `UsageRecord`), `llm/collector.py` (`TelemetryCollector`), `config/_db_telemetry_mixin.py` (`llm_cost_overrides`). Lives in `llm/` because it's LLM usage, and `config/` for SQLite persistence.

**3.12a Multi-Provider Adapter Registry** — `llm/adapters/registry.py` (auto-discovery registry scanning package at import), `llm/adapters/base.py` (self-describing adapter ABC), `config/settings.py` (`provider` field). Lives in `llm/adapters/` (adapter archetype) to support dynamic provider creation across implicit namespaces without central maps.

**3.13 Project Metadata Injection** — `llm/prompt_builder.py` updated to inject system data (project name, OS, archetype) ensuring robust reasoning references across LLM boundaries.

**3.13a Unified Runner Architecture** — The `PipelineRunner` (`flow/runner.py`) is now universally used to execute not just full YAML workflows but simple single-shot tasks (`sw review`, `sw draft`, `sw standards scan`) through dynamically constructed 1-step `PipelineDefinition` objects via `create_single_step()`. This removed disjoint telemetry-flushing and state management logic out of `cli/` and into the robust `flow/` engine.

**3.14a AST Drift Engine (SF-1)** — Built on native `tree-sitter`, the Validation engine now structurally inspects the workspace against Plan expectations, performing drift detection by natively extracting AST signatures. Located in `validation/drift_detector.py` since it is a pure validation module used by code check rules to prevent agent drift.

**3.20b Dynamic Risk-Based Rulesets (DAL)** — Fractal Resolution Engine (SF-2) dynamically resolves Design Assurance Level constraints by scanning upwards from any target file to locate the nearest `context.yaml`, deep-merging local and global overrides through Pydantic into the pipeline stream. Lives in `config/dal_resolver.py` to prevent cyclic dependencies.

**3.22 Polyglot AST Skeleton Extractor** — High-performance tree-sitter bindings dynamically map into `commons/language/ast_parser.py`, powering the robust `CodeStructureTool` and `CodeStructureAtom` APIs. It parses Rust, Python, Java, Kotlin, TS, C++, Go, SQL, and Markdown into JSON structure payloads, stripping away monolithic "Context Window Bloat" to ensure agents only manipulate surgically exact signatures.

**3.23 Bi-Directional Spec Rot Interceptor** — Solves the "2nd-Day Problem" by executing native AST Drift checks directly via the `.git/hooks/pre-commit` phase. It leverages the Pipeline engine's `DriftCheckHandler` deterministically against `--staged` files, aborting commit streams (Exit 42) upon any undocumented divergence between the `Spec.md` and the active code syntax layer.

**3.24 Automated Iterative Decomposition** — Deep recursive decomposition (Feature → Sub-Features → Components) using dynamic sub-pipelines via `PipelineRunner.fan_out()`. Parent execution safely blocks via `asyncio.gather` while children pipelines run fully isolated.

**3.25 Router-Based Flow Control** — Extends Pipeline YAML schemas via `router` routing logic (`RouterDefinition`, `RouterEvaluator`). Eliminates strict linear execution in favor of declarative conditional branching. Limits backward routes to prevent OS memory exhaustion via predefined `max_total_loops` structural guards.

**3.26 Git Worktree Bouncer (Sandbox)** — Dictatorial validation executing pipeline generations logically into separated physical Git Sandboxes. Strips mathematical patch diffs to forcefully preserve `context.yaml` topological bounds, dropping LLM hallucinations prior to integration. Includes SF-3.26c Interactive Gate Variables for weighted dictator override injection.

**B-SENS-02 Lineage Harmonization** — Extracted generic graph operations into `graph.topology.engine` and `graph.lineage.engine`. Migrated artifact event logging from the global `config.database.Database` interface directly to a dedicated `graph_store.lineage_repository.LineageRepository` which strictly targets the project-local `.specweaver/specweaver.db` storage. This decoupled the core orchestration handlers (`generation`, `draft`, `lint_fix`) from legacy state managers.

**3.27 Multi-Spec Pipeline Fan-Out** — Sub-pipeline spawning mapped to separate isolated sandboxes via `SW_PORT_OFFSET` hashes to prevent SQLite lock collision. Safely coordinates components fully in parallel mapped to Topological dependencies, blocking execution through standard `JOIN` gates.

**3.28 Interactive Sandbox Execution (Arbiter Feedback)** — Dual-pipeline verification resolving correlated hallucinations by physically isolating the Scenario Generator from the Code Generator. A 3rd read-only Arbiter acts as the final decision mechanism to route filtered vocabulary error traces backwards safely without polluting the code agent's system prompt with scenario schemas.

**D-INTL-06 Context Hydration & Handover (SF-2 Inversion of Control)** — Centralizes agent memory hydration into `core.flow.handlers.base._build_base_prompt()`. Replaces a DRY violation across all 5 workflow modules by executing Inversion of Control (IoC). Handlers dynamically assemble `PromptBuilder` objects with system state, rules, and sqlite-backed memory context before delegating to pure Domain Layer workflows, preserving DDD boundaries while granting LLMs seamless contextual awareness of active/blocked tasks and handover constraints.
