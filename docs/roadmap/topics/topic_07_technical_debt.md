# Topic 07: Technical Debt & Architecture (TECH)

This document tracks all massive refactoring efforts, technical debt removal, and underlying architectural epics required to ensure the platform remains stable, secure, and mathematically sound as it scales to enterprise levels. These stories do not add new user-facing features but are critical for long-term project viability.

## Domain-Driven Design (DDD)
* **`TECH-01` 🔜: Domain-Driven Design Unification**
  > [Description](../features/topic_07_technical_debt/TECH-01/TECH-01_ddd_refactor.md) | SpecWeaver's internal architecture is perfectly cohesive and microservice-ready, preventing "Dumping Ground" anti-patterns and circular dependencies as the team scales. The massive refactoring effort to align the legacy `config/`, `cli/`, and `loom/` layers with the pure Domain-Driven Design (Package by Feature) principles established by the B-SENS-02 Graph Triad.

## Architecture & Restructuring
* **`TECH-02` 🟢: Structural Refactoring of Workspace AST Module**
  > [Description](../features/topic_07_technical_debt/TECH-02/TECH-02_ast_restructuring.md) | To make the bounded context crystal clear, we want to introduce a dedicated `ast` boundary inside the workspace module. This separates mechanical Tree-Sitter extraction (`parsers`) from output mapping (`adapters`).
* **`TECH-03` 🔴: Architectural Analysis & Refactoring of `sw graph build` CLI**
  > [Description](../features/topic_07_technical_debt/TECH-03/TECH-03_graph_cli_analysis.md) | Analyzing whether a standalone CLI command for graph building is an architectural violation (leaky abstraction/duplicated orchestration). Proposes either migrating the orchestration logic into a centralized `GraphBuildAtom` or deprecating the CLI entirely in favor of an autonomous `spinUp` workflow.

## Schema & Data Layer
* **`TECH-04` 🔴: Database Table Prefix Harmonization**
  > [Description](../features/topic_07_technical_debt/TECH-04/TECH-04_design.md) | Refactor all existing database tables to use a strict domain-prefix naming convention (e.g., `workspace_projects`, `flow_artifact_events`). Established during B-INTL-09 with the `memory_` prefix pattern. Prevents naming collisions as domain count grows.

## Context Loading & RunContext Anti-Patterns
* **`TECH-05` 🔴: Context Loading Pipeline Refactoring**
  > [Description](../features/topic_07_technical_debt/TECH-05/TECH-05_design.md) | Three interrelated anti-patterns discovered during D-INTL-06 Red Team analysis that compound as new context sources are added:
  >
  > **Finding 1 — Business Logic in Interface/CLI Layers:** `_load_constitution_content()` is defined in `workspace/project/interfaces/cli.py` and `_load_standards_content()` in `assurance/standards/interfaces/cli.py`. These are data loading utilities, not CLI commands. They should live in their respective domain modules (`workspace/project/constitution.py`, `assurance/standards/loader.py`). The standards loader additionally couples to the CLI singleton via `_core.get_db()`.
  >
  > **Finding 2 — Cross-Interface Spider Web (10+ violations):** The private helpers `_load_constitution_content`, `_load_standards_content`, and `_run_workspace_op` are imported by 10+ other `interfaces/cli.py` modules (including `flow/interfaces/cli.py`, `review/interfaces/cli.py`, `implementation/interfaces/cli.py`, `api/v1/implement.py`, `api/v1/review.py`). These functions are not in any module's `exposes` list — they are private (`_` prefixed) helpers shared across unrelated interface modules, creating a spider web of cross-boundary imports.
  >
  > **Finding 3 — RunContext God Object (23 fields):** `RunContext` in `core/flow/handlers/base.py` has 23 fields and a 67-line `model_post_init` with side-effect-heavy initialization. Every new feature adds a field (`constitution`, `standards`, `plan`, `project_metadata`, `workspace_roots`, `api_contract_paths`, `db`, `llm_router`...). This is a classic God Object / grab-bag anti-pattern.
  >
  > **Highest-ROI Refactoring:** After D-INTL-06 SF-2 lands the shared `build_base_prompt()` factory in `workflows/commons/`, move constitution and standards loading INSIDE the factory (same pattern as memory hydration). This eliminates 2 RunContext fields, 10+ cross-interface imports, and makes the factory the single source of truth for all prompt context injection. Estimated effort: ~4h. Unblocks clean integration of all future context sources (conversation history, knowledge graph snippets).
  >
  > | Sub-Refactoring | What it fixes | Effort | ROI | Dependency |
  > |---|---|---|---|---|
  > | Move `_load_constitution_content` to `workspace/project/constitution.py` | Finding 1 | Low (~30 min) | Medium | None |
  > | Move `_load_standards_content` to `assurance/standards/loader.py` | Finding 1 | Low (~30 min) | Medium | None |
  > | Extract `_run_workspace_op` to a shared utility | Finding 2 | Medium (~2h) | Medium | Requires careful planning |
  > | Load constitution/standards inside factory | Findings 1+2+3 | High (~4h) | **Very High** | After D-INTL-06 SF-2 |
