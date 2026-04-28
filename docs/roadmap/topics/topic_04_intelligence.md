# Topic 04: Master Brain (Intelligence)

This document tracks all capabilities related to LLM integration, specification logic, and AI decision-making.

## DAL-E: Prototyping
* **`E-INTL-01` ✅: LLM Adapter** (Legacy: Step 3)<br>
  > _(new)_ | LLM adapter works. The 2 LLM-dependent spec rules (S03, S07) are implemented. The dependency-direction rule (S04) is wired.
* **`E-INTL-02` ✅: Spec Drafting** (Legacy: Step 4)<br>
  > Spec Drafting (`sw draft`) & HITL Provider

## DAL-D: Internal Tooling
* **`D-INTL-01` ✅: Implementation Generator** (Legacy: Step 5)<br>
  > _(new)_ | The full loop works. Spec -> code -> tests -> validation -> review.
* **`D-INTL-02` ✅: Feature Decomposition** (Legacy: 3.1)<br>
  > `lifecycle_layers.md` | `SpecKind` enum (feature/component), kind-aware rule presets, `DecomposeHandler`, confidence-based review scoring, `feature_decomposition.yaml` pipeline. **Complete**: 8 components, 1886 tests. See [implementation plan](features/topic_04_intelligence/D-INTL-02/D-INTL-02_implementation_plan.md).
* **`D-INTL-03` ✅: Explicit Plan Phase** (Legacy: 3.6)<br>
  > _(new)_ | New `PLAN+SPEC` handler between validate and implement. Captures architecture decisions, tech stack choices, constraint reasoning in a structured Plan artifact before code generation. Includes [Google Stitch](https://stitch.withgoogle.com/) via its SDK to auto-generate interactive UI mockups from the spec's Contract section.
* **`D-INTL-04` 🔜: Design Questionnaire** (Legacy: 3.52)<br>
  > [Arch Doc](../architecture/synthetic_commons_and_questionnaire_design.md) | Eliminates "Blank Canvas" LLM hallucinations during greenfield bootstrap. Injects an interactive CLI wizard (persistence, authentication, archetype choices) bounding the LLM's solution space securely into a localized `context.yaml` before `sw plan` or `sw draft` engages.

* **`D-INTL-05` ✅: Project Metadata Injection** (Legacy: 3.15)<br>
  > _(new)_ | Inject project name, archetype, language target, date, active config into system prompt; similar to Aider's `get_platform_info()`. **Complete**: 3587 tests.
## DAL-C: Enterprise Standard
* **`C-INTL-01` ✅: Iterative Decomposition** (Legacy: 3.24)<br>
  > `future_capabilities_reference.md` §18 | Builds on basic foundation: DMZ-style iterative loop, automated quality gates, recursive decomposition (feature → sub-features → components).
* **`C-INTL-02` ✅: MCP Client Architecture** (Legacy: 3.32c)<br>
  > [Arch Doc](../architecture/mcp_architecture_design.md) | Restructuring `context/providers.py` to natively support the Model Context Protocol (MCP). Implements the core Context Harness (JSON-RPC over stdio, Proxy Agents, Lazy Resource URIs) standardizing external integrations for future tools (Jira, Confluence). **Complete**: SF-1, SF-2, SF-3, and SF-4 (MCP Explorer Tool).
* **`C-INTL-03` 🔜: Reverse-Weaving** (Legacy: 3.43)<br>
  > _(new)_ | Archaeology tool for brownfield adoption. Uses AST Skeleton Extraction combined with Multi-Modal extraction loops from PDFs/Diagrams mapped as [semantically_similar] to draft baseline Spec.md contracts from legacy DB/Java code.
* **`C-INTL-04` 🔜: Conversation Summarization** (Legacy: 4.6)<br>
  > _(inspired by Aider)_ — Compress old multi-turn drafting/review messages when context fills up; keep recent turns + summary of history. _(Blueprint: [`aider/history.py`](https://github.com/Aider-AI/aider/blob/main/aider/history.py) `summarize_end()` — ORIGINS.md § Aider)_

## DAL-B: High-Assurance
* **`B-INTL-01` ✅: Archetype Rule Sets** (Legacy: 3.29)<br>
  > _(new)_ | Auto-provisioned rules for specific architectural profiles (`kotlin-service`, `rust-worker`) to enforce framework-specific standards inherently. **Complete**: SF-1 (Injection), SF-2 (Language Commons Framework Schemas), and SF-3 (Archetype Rule Bounds + Plugins).
* **`B-INTL-02` ✅: Macro Evaluator** (Legacy: 3.30)<br>
  > _(new)_ | Specialized indexer capable of unrolling Rust Procedural Macros (`#[derive]`) and Kotlin Compiler Plugins (Spring Boot annotations) so the LLM understands the true runtime reality, not just the raw signature. **Complete:** SF-1, SF-2, and SF-3 implemented. 4241 tests natively passing.
* **`B-INTL-03` 🔜: Synthetic Commons** (Legacy: 3.51)<br>
  > [Arch Doc](../architecture/synthetic_commons_and_questionnaire_design.md) | Pre-emptive architectural de-duplication. Scans drafted subfeatures in `DecomposeHandler` for cross-cutting overlaps (e.g. shared schemas/utils) and extracts them into a synthetic "Tier 0" feature, forcing subfeatures to share logic rather than parallelizing duplicate implementations.
* **`B-INTL-04` 🔮: Dynamic AI Arbiter** (Legacy: 5.8)<br>
  > _(split from original 3.12)_ — Automatic model selection using Attributed Lifecycle Score (ALS). AI-powered fault attribution across multi-model, cross-lifecycle pipelines. **Science fiction today** — depends on persistent knowledge graph (5.1-5.5), labeled training data (5.5a), and solving the credit assignment problem. See [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md).

* **`B-INTL-05` 🔜: Dynamic Tool Gating via Archetypes** (Legacy: 3.30a)<br>
  > _(new)_ | Branch off from 3.30. Intercepts the `context.yaml` active archetype to mathematically remove or inject specific JSON Schema Tool Definitions (`list_symbols`) to the Agent at generation runtime, strictly enforcing framework-specific capabilities.
* **`B-INTL-06` 🔜: Multi-Agent Isolation Patterns** (Legacy: 4.5)<br>
  > _(new)_ | Agent isolation patterns (multi-agent review). Ensures that multiple agents reviewing the same architecture operate in secure, independent sandboxes to prevent contextual contamination or collective hallucinations.
* **`B-INTL-07` 🔜: Error Attribution Arbiter**<br>
  > _(new)_ | A specialized LLM reviewer that sits at the JOIN gate of the Scenario Testing Pipeline. It reads the test failure, the code, and the YAML scenario, and mathematically determines whether the code failed the scenario, or if the scenario was written incorrectly.

* **`B-INTL-08` 🔮: Semantic Code Review**<br>
  > _(new)_ | Replaces text-based PR diffs with mathematical Graph Diffs. Explains exactly how a pull request alters dataflow chains across the system.

## DAL-A: Mission-Critical
* **`A-INTL-01` 🔜: Adversarial Spec Review** (Legacy: 3.50)<br>
  > _(inspired by Cavekit)_ | Branches the Arbiter Agent into the `sw draft` phase to run a Red Team adversarial challenge on the Spec. Mathematically disproves/attacks the L3 Spec for contradictions and edge-cases *before* generation, minimizing downstream rollout failures.
* **`A-INTL-02` 🔜: LLM Symbolic Execution** (Legacy: 4.14)<br>
  > _(new)_ | Using heuristics to actively guide strict symbolic compilers (like KLEE) by aggressively pruning execution trees to natively discover 0-days.
* **`A-INTL-03` 🔜: Socratic Drafting** (Legacy: 5.6)<br>
  > Phase A+B (seeds in Phase 2) | Socratic drafting flow — topology-aware questioning during `sw draft`
* **`A-INTL-04` 🔜: Memory Consolidation** (Legacy: 5.7)<br>
  > _(new)_ When new knowledge overlaps with existing, LLM decides: keep, update, delete, or insert_new. Prevents infinite knowledge growth. _(Blueprint: CrewAI's `consolidation_threshold` and merge logic — ORIGINS.md § CrewAI)_
