# Design: Dynamic Tool Gating via Archetypes

- **Feature ID**: 3.30a
- **Phase**: 3
- **Status**: DRAFT
- **Design Doc**: docs/roadmap/phase_3/feature_3.30a/feature_3.30a_design.md

## Feature Overview

Feature 3.30a adds Framework Plugin Composition and Targeted AST Searching to the CodeStructure Engine, alongside Dynamic Tool Gating. It solves three critical modularity risks: First, it allows `context.yaml` to define a list of `plugins` (e.g., `["spring-security", "spring-ai"]`) to merge multiple framework schemas concurrently instead of relying on a single monolithic archetype. Second, it expands the `list_symbols` tool intent with a `decorator_filter` argument, empowering Agents to explicitly search for security boundaries like `@PreAuthorize`. Third, it aggregates `intents.hide` blocks across all loaded plugins to mathematically restrict LLM tool capabilities at runtime.

## Research Findings

### Codebase Patterns
- **Reuse opportunities**: `loader.py` already natively uses `deep_merge_dict`. Passing an array of schema names dynamically concatenates them perfectly without logic rewrites. `CodeStructureTool.list_symbols` delegates down to the AST Parser, which inherently extracts `framework_markers` dictionaries natively. Translating a string filter parameter directly into the array comprehension exposes the search natively.
- **Touched modules**: `src/specweaver/core/loom/dispatcher.py`, `src/specweaver/core/loom/tools/code_structure/tool.py`.
- **Architecture rules**: `ToolDispatcher` dynamically wraps tools. Adding an intercept pattern where the schema YAML exposes `intents.hide` lists and forces `CodeStructureTool` to drop them from `definitions()` fits perfectly within the domain boundaries. `CodeStructureAtom` executes, `CodeStructureTool` routes.
- **Constraints**: We must ensure no circular imports occur between the AST Atom execution layers and the LLM Tool wrapper interfaces.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| None | N/A     | Python Native  | N/A    |

### Blueprint References
Feature 3.30 (Macro Unrolling) - Using the identical flat `<archetype>.yaml` parser engine to configure tool JSON responses.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Plugin Schema Composition | System | Parses `plugins` array from `context.yaml` and injects them as an active schema list into `CodeStructureAtom`. | Extracts evaluating coverage across multiple siloed repositories (e.g., Boot + Security) natively without version explosion. |
| FR-2 | Targeted Decorator Filtering | Agent | Invokes `list_symbols(decorator_filter="PreAuthorize")` intent target. | AST parses file, checks all `framework_markers["decorator"]` arrays, and returns exclusively the matches. |
| FR-3 | Hide Unsupported Schema Tools | System | Aggregates `intents.hide` configuration blocks across all dynamically loaded Framework YAML Plugins. | System automatically deletes the matching definitions from the JSON schema generation prompt. |
| FR-4 | Dispatcher Injection | System | Exposes the aggregated hidden intent list into the `CodeStructureTool` securely during `ToolDispatcher` build time. | Tool retains secure encapsulation without needing IO knowledge of schemas. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | Filtering tool schemas and parsing versions must complete via standard O(1) dictionary lookups with `< 5ms` latency. |
| NFR-2 | Reliability | Hiding a tool schema mathematically guarantees the LLM adapter never sends it, invoking absolute zero-trust restriction. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| None | N/A | N/A | Y | Pure architectural extension of existing tools. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Native Gating via schema evaluator YAMLs | Centralizing configurations (both Macro unrolling AND Agent intent capabilities) into a single flat `frameworks/<plugin>.yaml` file enforces total Domain Knowledge boundaries without fragmenting config definitions. | No |
| AD-2 | Modular Composition over Versioning | Replacing `spring-boot@3` hardcoding with `plugins: [spring-security]` treats schemas as pure mathematical supersets to prevent O(N) factorial explosion of physical configuration files. | Yes — approved functionally. |

## Developer Guides Required

Evaluate if this feature introduces a new sub-system, paradigm, or extension layer that requires a Developer Guide for onboarding engineers.

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Dynamic Intent Hiding | Documentation on configuring `intents: hide:` in `adding_framework_guide.md`. | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: Plugin Composition & AST Search
- **Scope**: Update `ArchetypeResolver` and `dispatcher.py` to parse an expandable `plugins` array. Update `list_symbols` in Tool Definitions and AST parsers to support an optional string `decorator_filter` that reads from the `framework_markers` payload.
- **FRs**: [FR-1, FR-2]
- **Inputs**: `context.yaml` definitions and LLM Tool Calls.
- **Outputs**: Agent can successfully retrieve target code blocks exclusively possessing specific Framework properties.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/phase_3/feature_3.30a/feature_3.30a_sf1_implementation_plan.md

### SF-2: Dynamic Tool Gating Intercept
- **Scope**: Aggregate `intents.hide` properties from `CodeStructureAtom`'s loaded schema cluster into the `CodeStructureTool` JSON defintions via `dispatcher.py`.
- **FRs**: [FR-3, FR-4]
- **Inputs**: Properly composited schema dict from SF-1.
- **Outputs**: Properly restricted list of `ToolDefinition`s sent to LLM prompt.
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/phase_3/feature_3.30a/feature_3.30a_sf2_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Plugin Composition & AST Search | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Dynamic Tool Gating Intercept | SF-1 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design DRAFT — awaiting HITL approval.
**Next step**: After approval, run:
`/implementation-plan docs/roadmap/phase_3/feature_3.30a/feature_3.30a_design.md SF-2`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.
