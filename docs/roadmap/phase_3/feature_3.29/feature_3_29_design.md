# Design: Archetype-Based Rule Sets

- **Feature ID**: 3.29
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3.29/feature_3.29_design.md

## Feature Overview

Feature 3.29 introduces Archetype-Based Rule Sets, executing isolated framework bounds checking for multi-language monorepos.
By reading the `context.yaml`'s `archetype` field (e.g., `spring-boot`, `rust-axum`), SpecWeaver seamlessly hot-swaps pipeline profiles to grade both the Design (Spec) and Implementation (AST) phases without custom Python wrappers.
Crucially, this design heavily relies on **Dependency Injection**: The `flow` engine orchestrates `loom/atoms` for heavy OS/C-binding AST extraction, injecting purely memory-safe, parsed payloads down into the `assurance/` DMZ. This perfectly isolates pure-logic validation from side-effect Execution.

## Research Findings

### Codebase Patterns
- **Layer Isolation:** `docs/dev_guides/layer_isolation_and_di.md` explicitly forbids `assurance/` from using C-bindings (`tree-sitter`) directly. Dependency Injection orchestrated by `flow/` is the absolute rule.
- **Language Commons:** Framework AST `.scm` extraction logic MUST reside exclusively in `loom/commons/language/<lang>/codestructure.py`.
- **Overlay with 3.30:** Feature 3.30 adds macro/annotation unrolling to `CodeStructure`. 3.29 focuses purely on the Pipeline orchestration and boolean constraint checks, leaving structural AST unrolling upgrades to 3.30 seamlessly.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| None | N/A | Exclusively bounded to internal engines. | N/A |

### Blueprint References
- ArchUnit (Java) and native Linter Profiles (ESLint cascade).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Profile Orchestration | PipelineRunner | Dynamically parses `context.yaml` archetype | Sets `validation_[spec|code]_[archetype].yaml` implicitly, gracefully defaulting upon failure. |
| FR-2 | Framework AST Querying | Loom Commons / Atoms | Expands polyglot schemas | Extracts specific node markers (macros, annotations, inheritance) from frameworks safely into Dict/Json payloads. |
| FR-3 | Code Archetype Bounds | Validation Engine | Executes `C12_ArchetypeCodeBounds` via DI payload | Evaluates generated code framework mechanics against YAML `PARAM_MAP` configs. |
| FR-4 | Spec Archetype Bounds | Validation Engine | Executes `S12_ArchetypeSpecBounds` via text | Evaluates generated `Spec.md` schemas against required architecture (e.g., Ports, Adapters). |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Architectural Purity | `assurance/` MUST NOT import `tree_sitter` or `loom/*`. AST logic executes as pure matching against injected payloads. |
| NFR-2 | Open Source Lineage | Baseline Framework profiles (Spring, Django) are maintained inside Native SpecWeaver yaml templates; Proprietary profiles reside in user sub-folders. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| None | N/A | N/A | Y | Pure architectural extension. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Dependency Injected AST | Violating `pure-logic` constraints causes cyclic dependency crashes. The `flow` orchestration layer extracts via Loom and injects payloads to Validation. | No |
| AD-2 | Rule Agnosticism | A unified `C12` rule prevents the codebase from scaling out to hundreds of framework-specific wrapper scripts. | No |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| adding_framework_guide.md | Explains the threshold boundary between native OS tooling (QARunner) versus SpecWeaver structural archetype configs, and how users define parameter structures. | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: Dependency Injection & Orchestrator Routing
- **Scope**: Modifies `flow/runner.py` and `flow/_validation.py` to route YAML archetypes and inject memory-safe `CodeStructureAtom` payloads into the rule parameter checks.
- **FRs**: [FR-1]
- **Inputs**: `context.yaml` topology bounds.
- **Outputs**: Activated Pipelines & DI AST variables.
- **Depends on**: none

### SF-2: Language Commons Framework Schemas
- **Scope**: Modifies `loom/commons/language/` to add specific Framework `.scm` queries (Annotations, Decorators, Traits) for polyglot structural payloads.
- **FRs**: [FR-2]
- **Inputs**: OS file handles.
- **Outputs**: Serialized pure-data Structural Payloads.
- **Depends on**: [SF-1]

### SF-3: Pure Logic Archetype Validators
- **Scope**: Creates the `C12` and `S12` pure logic wrappers inside `assurance/validation/rules/` matching parameters to DI payloads.
- **FRs**: [FR-3, FR-4]
- **Inputs**: Payload dictionaries, YAML `PARAM_MAP` overrides.
- **Outputs**: Gate `RuleResult` findings.
- **Depends on**: [SF-1, SF-2]

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)
3. SF-3 (depends on SF-2)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Injection & Orchestrator | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Commons Framework Schema | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-3 | Archetype Validators     | SF-2 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Feature 3.29 SF-1, SF-2, and SF-3 are all completed and committed.
**Next step**: Proceed to subsequent Phase 3 features.
**If resuming mid-feature**: Feature 3.29 is complete.
