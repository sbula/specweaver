# TECH-02: Structural Refactoring of Workspace AST Module

## Context & Motivation
During the implementation of SF-3 (Knowledge Graph Builder), we identified that the `specweaver.workspace.ast.parsers` directory contains both mechanical Tree-Sitter extraction logic (parsers) and translation layers (adapters) that map ASTs to other domains (like the Universal Graph Ontology).

To make the bounded context crystal clear, we want to introduce a dedicated `ast` boundary inside the workspace module. The target structure separates mechanical extraction from output mapping:
- `specweaver.workspace.ast.parsers`: Raw Tree-Sitter extractions.
- `specweaver.workspace.ast.adapters`: Translation layers mapping ASTs to foreign boundaries.

## Scope of Work
1. **Directory Migration:** Move `src/specweaver/workspace/ast/parsers/` to `src/specweaver/workspace/ast/parsers/`.
2. **Adapter Relocation:** Move any adapters (e.g., `graph_adapter.py`) into `src/specweaver/workspace/ast/adapters/`.
3. **Mass Import Refactoring:** Update all references to `specweaver.workspace.ast.parsers` across the ~85 files spanning `assurance`, `flow`, `loom`, `llm`, and `tests`.
4. **Context Update:** Update `src/specweaver/workspace/ast/context.yaml` to reflect the new `ast` sub-boundary.

## Risk Assessment
- **Risk Level:** High (Churn). Touching 85 files across 5 distinct domains creates a high risk for merge conflicts if other feature branches are in flight.
- **Mitigation:** Execute this refactoring in complete isolation on a fresh branch (`chore/tech-02-ast-restructure`) with absolutely no logic changes. Rely on the automated test suite (Unit, Integration, E2E) to verify 100% structural parity.

## Dependencies
- This story MUST be executed **after** B-SENS-02 (SF-3) is merged to `main` to avoid conflict thrashing on the `graph_adapter`.
