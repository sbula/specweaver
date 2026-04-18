# Implementation Plan: Macro & Annotation Evaluator [SF-3: Tool Intent & Guide Publishing]
- **Feature ID**: 3.30
- **Sub-Feature**: SF-3 — Tool Intent & Guide Publishing
- **Design Document**: docs/roadmap/phase_3/feature_3.30/feature_3.30_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.30/feature_3.30_sf3_implementation_plan.md
- **Status**: APPROVED

## Goal
To properly publish the `read_unrolled_symbol` integration capabilities and formally document the underlying Macro/Annotation Unroll pattern via the internal SpecWeaver Developer Guides for cross-team scalability.

## Research Notes
- **`CodeStructureTool` Intents**: During SF-1 and SF-2 development, the `read_unrolled_symbol` AST intent was automatically swept into `src/specweaver/core/loom/tools/code_structure/tool.py` and its corresponding LLM JSON schema in `definitions.py` to facilitate iterative evaluation constraints. The codebase logic already accurately routes the evaluator requests!
- **Developer Guide Targets**: The existing `docs/dev_guides/adding_framework_guide.md` currently only describes mapping validation rules using predefined archetypes (the `spring-boot.yaml` pipeline structure). It completely lacks instructions for engineers on how to actually update or add the `frameworks/*.yaml` *Schema Evaluators* used by the `CodeStructureAtom` to unroll annotations. 

## Implementation Steps

### 1. Update `adding_framework_guide.md`
- Provide a new section "Step 1b: Defining Framework Schema Evaluators (Macro Unrolling)" explaining the LSP-bypass architecture.
- Document the schema mapping strategy for developers to translate things like `@RestController` (or their company's proprietary `@AuthBase` API classes) into explicit YAML abstractions, located sequentially inside `src/specweaver/workflows/evaluators/frameworks/<archetype>.yaml`.
- Cover the `metadata.supported_languages` binding constraint explicitly.

## Quality/Architecture Verification
- No Python code files require structural logic updates, bypassing strict boundary violations.
- Will verify Markdown format consistency statically natively via pre-commit standards.
