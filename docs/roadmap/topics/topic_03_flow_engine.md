# Topic 03: Flow Orchestration (Nervous System)

This document tracks all capabilities related to the pipeline runner, routing, state management, and telemetry.

## DAL-E: Prototyping
* **`E-FLOW-01` ✅: Config DB** (Legacy: Step 8)<br>
  > _(new)_ | SQLite database at `~/.specweaver/` for multi-project management. Configurable thresholds per validation rule, stored in the project config DB.
* **`E-FLOW-02` ✅: YAML Pipelines** (Legacy: Step 10)<br>
  > _(new)_ | Define what a pipeline IS — YAML schema, step model (action + target), gate definitions, parser. No execution yet, just the data model and parsing.
* **`E-FLOW-03` ✅: Multi-Provider Registry** (Legacy: 3.13)<br>
  > _(split from original 3.12)_ | Auto-discovery registry: each adapter is self-describing (`provider_name`, `api_key_env_var`, `default_costs`). System scans `llm/adapters/` at import → builds registry automatically. Adding a new provider = one file, zero other changes. **Complete**: Registry auto-discovery, schemas V10, 5 adapters (Gemini, OpenAI, Anthropic, Mistral, Qwen), factory integration, and `sw config set-provider`. 3531 tests.

## DAL-D: Internal Tooling
* **`D-FLOW-01` ✅: Pipeline Runner** (Legacy: Step 11)<br>
  > SQLite Pipeline Runner & State Persistence
* **`D-FLOW-02` ✅: sw run CLI** (Legacy: Step 13)<br>
  > _(new)_ | `sw run` command to invoke pipelines from CLI. Rich step-by-step progress. `--verbose` / `--json` output. Robust error handling with friendly one-liners. Structured file-based logging across all SpecWeaver modules.
* **`D-FLOW-03` ✅: Static Model Routing** (Legacy: 3.14)<br>
  > _(split from original 3.12)_ | Map task types to models in config: `review → claude`, `implement → gemini-pro`. Uses registry to resolve provider+model. No AI, no learning — pure user configuration. **Complete:** 3568 tests total.
* **`D-FLOW-04` ✅: Unified Runner Architecture** (Legacy: 3.16)<br>
  > _(new)_ | Refactor single-shot CLI commands (`sw review`, `sw draft`, etc.) to use dynamic 1-step pipelines via `PipelineRunner`. Standardizes execution, telemetry, and state tracking. Includes project-wide logging reform. **Complete**: 3589 tests.

## DAL-C: Enterprise Standard
* **`C-FLOW-01` ✅: Cost Telemetry** (Legacy: 3.12)<br>
  > _(split from original 3.12)_ | Log `model_id`, `prompt_tokens`, `completion_tokens`, `estimated_cost` on every LLM call. `TelemetryCollector` (decorator), `UsageRecord`/`estimate_cost()`, `TelemetryMixin` (DB persistence), schema v9, factory telemetry wrapping, task_type attribution in flow handlers. CLI: `sw usage` (summary table with `--all`/`--since`), `sw costs` (view/set/reset overrides). Runner + CLI + API flush integration via `context.db`. **Complete**: 3451 tests.
* **`C-FLOW-02` ✅: Router-Based Control** (Legacy: 3.25)<br>
  > _(new)_ | Conditional branching in pipelines — route specs to different pipeline paths based on assessment (e.g., simple → fast track, complex → full decomposition). New `router` YAML key on steps. **Complete**: 3877 tests.
* **`C-FLOW-03` ✅: Multi-Spec Fan-Out** (Legacy: 3.27)<br>
  > _(from 3.1 analysis)_ | Sub-pipeline spawning: decomposition outputs N component specs, each runs its own L3 pipeline. Parent pipeline waits for all children. **Critically:** Uses the Topology Graph to mathematically predict file blast radius. Safely runs disjoint components fully in parallel mapped to separate isolated sandboxes, injecting dynamic `SW_PORT_OFFSET` hashes to prevent test collision (port bounds, SQLite locks) without incurring git merge conflicts. **Complete**: 3986 tests.
* **`C-FLOW-04` 🔜: Work Packet Bundling** (Legacy: 3.49)<br>
  > _(inspired by Cavekit)_ | Optimizes the Dynamic DAG Topology Dispatcher (3.27) by bundling tiny, independent components into aggregated "Work Packets" assigned to a single Git Worktree. Reduces Git I/O overhead and LLM context initialization tokens drastically.

* **`C-FLOW-05` ✅: Interactive Gate Variables (HITL)** (Legacy: 3.26c)<br>
  > _(new)_ | Immediately actionable. Updates `PromptBuilder` to explicitly isolate human `GateType.HITL` rejections into a mathematically bound `<dictator-overrides>` XML section, granting them strict promotional weight above standard linter error findings in loop-back generation sequences. **Complete**: 3934 tests.
* **`C-FLOW-06` ✅: Refactoring Phase 3 Optimizations** (Legacy: 3.32d)<br>
  > _(new)_ | Execute High-ROI adaptations immediately: Context Condensation (AST Skeletons), Impact-Aware Test Limiting, DAL CI/CD Risk Evaluation, Standards Scaffolding, and Dynamic Context Routing. See [design doc](features/topic_03_flow_engine/C-FLOW-06/C-FLOW-06_design.md). **Complete:** All refactorings, Impact-Aware gates, and DI boundaries successfully validated.
* **`C-FLOW-07` 🔜: HITL Root-Cause Tagging** (Legacy: 5.5a)<br>
  > _(new)_ | Direct integration with the Friction Analytics dashboard. When the Agent encounters friction, a human steps in (HITL) and actively tags *why* the pipeline failed (e.g., "Bad Spec", "Hallucination"), feeding the attribution engine.
## DAL-B: High-Assurance
* **`B-FLOW-01` ✅: Scenario Testing Pipeline** (Legacy: 3.28)<br>
  > _(inspired by agent-system)_ | Dual-pipeline architecture: coding + scenario pipelines run in parallel, meet at JOIN gate. Contract-first (Python Protocols), structured YAML scenarios, arbiter agent for error attribution. **Complete:** 4168 tests.
* **`B-FLOW-02` 🔜: OpenTelemetry Agent Tracing** (Legacy: 3.44)<br>
  > _(new)_ | Directly tracing hierarchical LLM workflow logic out of the `PipelineRunner` using the `OpenTelemetry (OTel)` standard to emit Spans into enterprise endpoints (Jaeger/Datadog) for comprehensive thought observability.
* **`B-FLOW-03` 🔜: Friction Detection** (Legacy: 4.5c)<br>
  > _(split from original 3.12)_ — When downstream agent modifies >20% of upstream scaffolding (measured by `git diff`), flag "friction event" and attribute to upstream model. No LLM needed — pure diff math. See [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md).
* **`B-FLOW-04` 🔜: Hybrid RAG Orchestration** (Legacy: 5.4)<br>
  > Phase C + D. _(Enhanced with CrewAI's scoring formula: `semantic × similarity + recency × decay + importance × weight`, configurable half-life profiles per knowledge type — ORIGINS.md § CrewAI)_

## DAL-A: Mission-Critical
* **`A-FLOW-01` 🔜: Data-Driven Routing** (Legacy: 4.5d)<br>
  > _(split from original 3.12)_ — Analyze telemetry + friction data to **suggest** (not auto-apply) model swaps. "Model X has 3× more friction on planning tasks than Model Y." See [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md).
* **`A-FLOW-02` 🔜: Hash GC** (Legacy: 5.3)<br>
  > Phase D | Hash-based garbage collection for graph nodes
* **`A-FLOW-03` 🔜: Entropy GC** (Legacy: 5.9)<br>
  > _(new)_ | An offline cron-agent utilizing the `PostgreSQL` persistent topology graph to mathematically detect and automatically delete completely unreferenced AST nodes/dead code modules across the monolithic repository.
