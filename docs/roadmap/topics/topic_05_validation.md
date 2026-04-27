# Topic 05: Validation Engine (Reflexes)

This document tracks all capabilities related to static analysis, linting, rulesets, and automated verification.

## DAL-E: Prototyping
* **`E-VAL-01` ✅: Core Validation Engine** (Legacy: Step 2)<br>
  > _(new)_ | `sw check path/to/spec.md` runs rules and reports results. This is the highest-leverage MVP feature — it proves the core concept without LLM cost.
* **`E-VAL-02` ✅: Auto-Discover Standards** (Legacy: 3.5)<br>
  > _(new)_ | Extend `sw scan --standards` → extract naming, error handling, type hints, docstring style, test patterns, import patterns from code (Python + JS/TS). Store in DB (schema v6 `project_standards` table). Auto-inject via `PromptBuilder.add_standards()`. Bootstrap `CONSTITUTION.md` from conventions. **Complete**: 4 sub-phases (Python analyzer, scanner+CLI+DB, JS/TS analyzers, constitution bootstrap), 2774 tests. See [implementation plan](features/topic_05_validation/E-VAL-02/E-VAL-02_implementation_plan.md). _(inspired by [Agent OS v3](https://github.com/buildermethods/agent-os))_

## DAL-D: Internal Tooling
* **`D-VAL-01` ✅: QA Runner Tool** (Legacy: Step 12)<br>
  > QA Runner Tool & Lint-Fix Reflection Loop
* **`D-VAL-02` ✅: Custom Rule Paths** (Legacy: 3.4)<br>
  > _(deferred from Step 8b)_ | Validation sub-pipeline: `ValidationPipeline` / `ValidationStep` models, YAML-defined pipelines with inheritance (extends/override/remove/add), circular-extends guard, `sw list-rules`, `--pipeline` override, custom D-prefix rule loader, `RuleAtom` adapter, profile-specific pipelines, project-local pipeline overrides, `apply_settings_to_pipeline()`. **Complete**: 10 components, 2181 tests. See [implementation plan](features/topic_05_validation/D-VAL-02/D-VAL-02_implementation_plan.md).
* **`D-VAL-03` ✅: Polyglot QARunner** (Legacy: 3.19)<br>
  > _(new)_ | Wraps target-language CLI commands (`cargo`, `gradlew`, `pytest`) into a unified `LanguageRunnerInterface`. Treats execution as a Black Box (validating exit codes/stderr) to prevent Python AST hardcoding. **Complete.**

* **`D-VAL-04` ✅: Adaptive Assurance Standards** (Legacy: 3.32a)<br>
  > _(new)_ | Toggles `StandardsAnalyzer` behavior between mining legacy styles ("Mimicry") vs injecting built-in idiomatic targets ("Best Practice"). Configured via `specweaver.toml`. Prevents the "Empty Repository" context vacuum for greenfield builds. **Complete:** SF-1 (Adaptive standard targeting) and SF-2 (Context Condensation Skeletons) fully integrated and heavily optimized.
## DAL-C: Enterprise Standard
* **`C-VAL-01` ✅: Constitution Artifact** (Legacy: 3.2)<br>
  > `constitution_template.md` | Project-wide governing doc (`CONSTITUTION.md`) injected into every LLM call. Walk-up resolution, configurable size limits, CLI management (`sw constitution show/check/init`). **Complete**: constitution loader, PromptBuilder integration, handler threading, CLI commands, 1974 tests. See [implementation plan](features/topic_05_validation/C-VAL-01/C-VAL-01_implementation_plan.md). _(inspired by [Spec Kit](https://github.com/github/spec-kit), [DMZ SOUL.md](https://github.com/TheMorpheus407/the-dmz))_
* **`C-VAL-02` ✅: Domain Profiles** (Legacy: 3.3)<br>
  > `future_capabilities_reference.md` §19 | Named preset bundles (5 profiles: web-app, data-pipeline, library, microservice, ml-model). `config/profiles.py`, DB v5 migration (`domain_profile` column), 5 CLI commands. Bulk-writes to DB override layer. **Complete**: 3 components, 2038 tests. See [implementation plan](features/topic_05_validation/C-VAL-02/C-VAL-02_implementation_plan.md).
* **`C-VAL-03` ✅: Dynamic Risk Rulesets** (Legacy: 3.20b)<br>
  > _(split from 3.20)_ | Injects strict constraints or relaxed defaults into the fixed 10-test battery based on the target module's domain risk (DAL) via "Fractal Resolution," outsourcing FFI boundary checks to native tools (Tach, ArchUnit, ESLint). Replaced legacy Database Validation Overrides with Pipeline YAML Inheritance. **Complete**: 3684 tests.
* **`C-VAL-04` ✅: Traceability Matrix Check** (Legacy: 3.21)<br>
  > _(new)_ | Mathematically counts FRs/NFRs in the L3 spec and asserts exact matching `@traces(req_id)` tags in the AST of generated test files. Hard-fails pipeline if coverage is incomplete, preventing "Correlated Hallucinations."

## DAL-B: High-Assurance
* **`B-VAL-01` ✅: AST Drift Detection** (Legacy: 3.18)<br>
  > _(deferred from 3.14)_ | Builds on UUIDs to provide deep, parser-backed drift detection. **Complete**: SF-1 and SF-2 integrated into Flow engine and CLI. Tests passing.
* **`B-VAL-02` ✅: Spec Rot Interceptor** (Legacy: 3.23)<br>
  > _(new)_ | The "2nd-Day Problem" solver. Blocks builds/commits if the implementation AST diverges from the `Spec.md` markdown, forcing developers to reconcile documentation with hot-fixes. **Complete:** SF-1 and SF-2 integrated into Flow engine and CLI. Tests passing.
* **`B-VAL-03` 🔜: Semantic Completeness Review** (Legacy: 3.42)<br>
  > _(new)_ | An LLM-backed Code Validation Rule (`C10_test_completeness.py`) that analyzes the agent's generated test suite against the target spec to assert whether all unhappy paths, error bounds, and expected outcomes are semantically verified. Emits ERRORs for missing branch coverage to ensure thorough completeness.
* **`B-VAL-04` 🔜: SWE-Bench QA Gates** (Legacy: 3.47)<br>
  > _(new)_ | Built-in command to run SpecWeaver's internal pipelines against a deterministic suite of synthetic SWE-bench bugs to mathematically prove that platform extensions haven't degraded the internal token costs or success rate.
* **`B-VAL-05` 🔜: DAL Architecture Gate**<br>
  > _(new)_ | A new `sw check` Validation Engine rule that asserts a package's dependencies do not violate DAL boundaries (e.g., ensuring a DAL-A component never imports a DAL-C component). Enforces architectural testing intensity requirements using the Persistent Knowledge Graph.

## DAL-A: Mission-Critical
* **`A-VAL-01` ✅: Protocol/Schema Analyzers** (Legacy: 3.31)<br>
  > _(new)_ | Native parsing of `.proto` (gRPC), `openapi.yaml`, and AsyncAPI files to catch contract drift across polyglot microservices. **Complete**: Implementation of native YAML/Proto extractors, Atom/Tool orchestrator bindings, and C13 Contract Drift Rule natively mapped against AST validation.
* **`A-VAL-02` 🔜: Symbolic Math Validation** (Legacy: 3.39)<br>
  > _(new)_ | Specialized rules to formally verify mathematical/ML calculations (e.g., FinBERT, trading algorithms) generated in execution code.
* **`A-VAL-03` 🔜: Mutation Testing Gates** (Legacy: 4.7)<br>
  > `future_capabilities_reference.md` §13, §14 | Verification gates (mutation testing, assertion density)
* **`A-VAL-04` 🔜: Rust PyO3 Validations** (Legacy: Backlog)<br>
  > _(new)_ | To mathematically unlock 10x-50x performance scaling and guarantee absolute memory-safe LLM sandboxing. Static Validation Rule Pipelines: Rewrite regex-heavy mathematical validation tasks natively in compiled Rust engine cores to instantly evaluate multi-thousand line specs.
* **`A-VAL-05` 🔜: Multi-Modal Visual Quality Gates (V-Series)** (Legacy: 4.11)<br>
  > _(new)_ | Expanding the validation engine battery with `V-Series` rules using VLM (Vision LLMs) + Headless Browsers (Playwright) via internal Docker rendering, calculating visual UI drift perfectly against the UI component specifications.
* **`A-VAL-06` 🔜: Industry Standard Bridges** (Legacy: 3.41)<br>
  > _(new)_ | Adapters to interface seamlessly with massive open-source protocols: Pact.io (Consumer contract testing), Glean (Internal Fact Graphs), and ArchCodex (Drift Prevention).
