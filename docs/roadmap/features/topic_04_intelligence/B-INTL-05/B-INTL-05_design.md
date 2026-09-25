# B-INTL-05 — Dynamic Tool Gating via Archetypes

**Status**: DRAFT · **Feature ID**: 3.30a · **Phase**: 3 · SF-01 committed; SF-02 passed Pre-Commit,
awaiting the user's commit.

| | |
|---|---|
| Extends | Feature 3.30 (Macro Unrolling) — same flat `<archetype>.yaml` parser engine, here configuring tool JSON responses |
| Touches | `src/specweaver/core/loom/dispatcher.py`, `src/specweaver/core/loom/tools/code_structure/tool.py` |
| External deps | None — Python only, a pure extension of existing tools |

## What it does

Three additions to the CodeStructure engine:

1. **Plugin composition** — `context.yaml` lists `plugins` (e.g., `["spring-security", "spring-ai"]`);
   their framework schemas merge, instead of one monolithic archetype.
2. **Targeted AST search** — the `list_symbols` intent takes a `decorator_filter`, so an agent can
   search for security boundaries such as `@PreAuthorize`.
3. **Dynamic tool gating** — `intents.hide` blocks from all loaded plugins are aggregated, and those
   tools are removed from what the LLM can call at runtime.

## How it fits

- `loader.py` already uses `deep_merge_dict`: passing a list of schema names merges them with no
  logic rewrite.
- `CodeStructureTool.list_symbols` delegates to the AST parser, which already extracts
  `framework_markers` dictionaries. The string filter goes straight into that array comprehension.
- `ToolDispatcher` wraps tools. The schema YAML exposes `intents.hide`, and `CodeStructureTool`
  drops those names from `definitions()`. `CodeStructureAtom` executes; `CodeStructureTool` routes.
- Constraint: no circular imports between the AST Atom execution layers and the LLM Tool wrapper
  interfaces.

## Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Gating via schema evaluator YAMLs | One flat `frameworks/<plugin>.yaml` holds both Macro unrolling AND Agent intent capabilities, keeping Domain Knowledge boundaries without fragmenting config definitions. | No |
| AD-2 | Modular Composition over Versioning | Replacing `spring-boot@3` hardcoding with `plugins: [spring-security]` treats schemas as supersets and avoids an O(N) factorial explosion of configuration files. | Yes — approved functionally. |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Plugin Schema Composition | System | Parses `plugins` array from `context.yaml` and injects them as an active schema list into `CodeStructureAtom`. | Evaluates coverage across multiple siloed repositories (e.g., Boot + Security) without version explosion. |
| FR-2 | Targeted Decorator Filtering | Agent | Invokes `list_symbols(decorator_filter="PreAuthorize")` intent target. | AST parses file, checks all `framework_markers["decorator"]` arrays, and returns exclusively the matches. |
| FR-3 | Hide Unsupported Schema Tools | System | Aggregates `intents.hide` configuration blocks across all dynamically loaded Framework YAML Plugins. | System deletes the matching definitions from the JSON schema generation prompt. |
| FR-4 | Dispatcher Injection | System | Exposes the aggregated hidden intent list into the `CodeStructureTool` during `ToolDispatcher` build time. | Tool keeps its encapsulation without needing IO knowledge of schemas. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | Filtering tool schemas and parsing versions must complete via standard O(1) dictionary lookups with `< 5ms` latency. |
| NFR-2 | Reliability | A hidden tool schema is never sent by the LLM adapter — zero-trust restriction. |

## Guides owed

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Dynamic Intent Hiding | Documentation on configuring `intents: hide:` in `adding_framework_guide.md`. | ⬜ To be written during Pre-commit |

## Sub-features

| SF | Does | FRs | Inputs → Outputs | Depends on | Plan |
|----|------|-----|------------------|-----------|------|
| SF-01 | `ArchetypeResolver` and `dispatcher.py` parse a `plugins` array; `list_symbols` (tool definitions + AST parsers) takes an optional string `decorator_filter` read against `framework_markers` | FR-1, FR-2 | `context.yaml` definitions, LLM tool calls → the agent retrieves only code blocks with the given framework properties | none | [sf01](B-INTL-05_sf01_implementation_plan.md) |
| SF-02 | `intents.hide` from `CodeStructureAtom`'s loaded schema cluster reaches the `CodeStructureTool` JSON definitions via `dispatcher.py` | FR-3, FR-4 | composited schema dict from SF-01 → restricted list of `ToolDefinition`s in the LLM prompt | SF-01 | [sf02](B-INTL-05_sf02_implementation_plan.md) |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Plugin Composition & AST Search | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Dynamic Tool Gating Intercept | SF-01 | ✅ | ✅ | ✅ | ✅ | ⬜ |

**Next**: the user commits SF-02.
