# Design: Macro & Annotation Evaluator

- **Feature ID**: 3.30
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3.30/feature_3.30_design.md

## Feature Overview

Feature 3.30 adds a specialized indexer capability to the Polyglot AST Extractor. It solves the problem of the LLM receiving only raw signatures (e.g., `#[derive(Clone)]` or `@RestController`) by unrolling Rust Procedural Macros, Kotlin Compiler Plugins, and backend annotations so the LLM understands the true runtime reality. 
Instead of relying on slow, OS-level compiler invocations (like KSP or `cargo expand`), it adopts the highly successful Architecture pattern from Feature 3.29 (Archetype Rule Sets). It evaluates the AST markers (already natively extracted by `extract_framework_markers`) against modular, declarative YAML framework schemas (e.g., Spring Boot, Quarkus, NestJS) to translate raw annotations into concrete, unrolled runtime behaviors.

## Research Findings

### Codebase Patterns
- **AST Marker Extraction**: The existing `CodeStructureTool` and `CodeStructureAtom` already possess a highly robust `extract_framework_markers` function across Java, Kotlin, Typescript, Rust, and Python. It correctly strips `@RestController`, `@PostMapping`, `impl Trait`, etc.
- **Archetype Parallels**: Feature 3.29 loads framework rules dynamically from `workflows/pipelines/frameworks/`. We can use the exact same declarative pattern to define "unroll maps" (e.g., "If `@GetMapping(X)` is found, output `HTTP GET X`").

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| tree-sitter | latest | Core CST extraction (already implemented). | N/A |

### Blueprint References
Feature 3.29 (Archetype-Based Rule Sets) - Loading declarative YAML bounds from the ecosystem plugins.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Evaluate Framework Macros | System | Evaluates AST markers against declarative YAML framework schemas. | Translates raw decorators/bases into unrolled text representations mathematically. |
| FR-2 | Multi-Language Support | System | Natively supports major framework libraries across Java, Kotlin, TS, Python, and Rust. | Schemas for Spring Boot, Quarkus, NestJS, FastAPI, and Actix are evaluated correctly. |
| FR-3 | CodeStructureTool Integration | Agent | Calls `read_unrolled_symbol` intent | The tool delegates to the schema evaluator, appending the unrolled logic to the symbol. |
| FR-4 | Directory Hot-Loading | System | Discovers custom `.yaml` schema overrides residing in arbitrary ecosystem directories. | Natively evaluates against user-supplied definitions without recompilation. |
| FR-5 | Cascading Unrolling | System | Resolves compounded schema definitions iteratively. | Prevents LLMs from missing nested meaning during recursive framework behaviors. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | Evaluation runs via purely in-memory dictionary lookups off the tree-sitter AST, executing in < 10ms. No OS shell-outs. |
| NFR-2 | Graceful Degradation | If an annotation is not mapped in the schema, it smoothly falls back to just exposing the raw signature. |
| NFR-3 | Extensibility | Framework schemas MUST be modular YAML files so engineers can add custom internal frameworks easily. |
| NFR-4 | Schema Security Boundaries | The YAML evaluation engine MUST remain tightly data-declarative. | It MUST NOT parse or `eval()` any dynamic execution bindings from untrusted definitions. |
| NFR-5 | Recursion Protection | The engine MUST enforce algorithmic bounds against cyclic parsing (e.g. `A` unrolls to `B`, `B` unrolls to `A`). | Implements a strict hard-cap (max depth 5) preventing zero-day OOM Infinite loop vulnerabilities. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| None | N/A | N/A | Y | Pure architectural extension of existing tools. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Declarative YAML Unrolling vs Compiler API | Native Compiler interactions (KSP, `cargo expand`) violate NFR-1 (Performance) inside quick agent loops. Static mapping through YAML is exactly how Feature 3.29 built isolated, fast Archetype rules. | No |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Adding Custom Frameworks | Instructions for developers to map their own proprietary ORM or APIs into YAML Unroll Schemas. | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: Core Schema Evaluator Engine
- **Scope**: Implement the parser logic inside `commons/language/evaluator.py` to ingest YAML maps and transform AST `extract_framework_markers()` output into readable runtime strings.
- **FRs**: [FR-1]
- **Inputs**: AST Framework dict, YAML mapping.
- **Outputs**: Evaluated text (e.g., `Endpoint: GET /api`).
- **Depends on**: none
- **Impl Plan**: docs/roadmap/phase_3/feature_3.30/feature_3.30_sf1_implementation_plan.md

### SF-2: Native Core Framework Libraries
- **Scope**: Write the default YAML Evaluation schemas for major ecosystem lifecycles explicitly covering Java/Kotlin (Spring Boot, Quarkus), TS (NestJS), Python (FastAPI, Django), and Rust (Actix).
- **FRs**: [FR-2]
- **Inputs**: Framework API Docs.
- **Outputs**: Declarative YAML Maps.
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/phase_3/feature_3.30/feature_3.30_sf2_implementation_plan.md

### SF-3: Tool Intent & Guide Publishing
- **Scope**: Extend `CodeStructureTool` with the `read_unrolled_symbol` integration. Write the comprehensive Developer Guide ensuring the platform can easily onboard new frameworks.
- **FRs**: [FR-3]
- **Inputs**: Evaluator Engine, Documentation.
- **Outputs**: JSON Schema update to agents, Published MD.
- **Depends on**: SF-2
- **Impl Plan**: docs/roadmap/phase_3/feature_3.30/feature_3.30_sf3_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends only on SF-1)
3. SF-3 (depends dynamically on SF-2 completion)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Core Schema Evaluator Engine | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Native Core Framework Libraries | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-3 | Tool Intent & Guide Publishing | SF-2 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Feature 3.30 is FULLY CLOSED.
**Next step**: Feature 3.30a initialization.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.
