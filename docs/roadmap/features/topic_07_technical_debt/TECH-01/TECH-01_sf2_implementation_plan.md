# Implementation Plan: Domain-Driven Design Unification [SF-2: Decentralize CLI Layer]
- **Feature ID**: TECH-01
- **Sub-Feature**: SF-2 — Decentralize CLI Layer
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-01/TECH-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-01/TECH-01_sf2_implementation_plan.md
- **Status**: COMPLETED

## Goal Description
Refactor the monolithic `interfaces/cli/` layer by decentralizing Typer CLI commands into their respective domain packages. To maintain strict archetype enforcement, domains will adopt a Hexagonal Architecture (Vertical Slicing), utilizing a neutral top-level folder containing `core/` (pure-logic) and `interfaces/` (orchestrators/adapters) sub-packages.

This eliminates the "Package by Layer" anti-pattern, ensuring that each domain is a self-contained microservice-ready slice.

## Proposed Changes

### 1. Core Config & Database Bootstrapping
Extract database initialization downward to prevent circular imports.
#### [NEW] `src/specweaver/core/config/interfaces/cli.py`
- Moves `config.py` and `config_routing.py` here.
- Add `context.yaml` (archetype: orchestrator).
#### [NEW] `src/specweaver/core/config/cli_db_utils.py`
- Extract `get_db` and `bootstrap_database` from `interfaces/cli/_core.py` and `_db_utils.py` into this pure leaf module. Do NOT extract `console` or `typer` here to preserve `pure-logic` compliance.

### 2. Graph Domain CLI & Hexagon Sealing (Red Team Mitigation 2)
#### [NEW] `src/specweaver/graph/interfaces/cli.py`
- Moves `graph.py` and `lineage.py` here.
- Refactor to define `graph_app = typer.Typer()` without importing `_core`.
- Add `context.yaml` (archetype: orchestrator).
#### [NEW] `src/specweaver/graph/core/context.yaml`
- Explicitly `forbid: specweaver/graph/interfaces` to seal the pure-logic hexagon.

### 3. Assurance Domains CLI & Hexagon Sealing
#### [NEW] `src/specweaver/assurance/validation/interfaces/cli.py`
- Moves `drift.py` and `validation.py` here.
- Add `context.yaml` (archetype: orchestrator).
#### [NEW] `src/specweaver/assurance/validation/core/context.yaml`
- Add to seal pure-logic boundary against `interfaces`.
#### [NEW] `src/specweaver/assurance/standards/interfaces/cli.py`
- Moves `standards.py` here.
- Add `context.yaml` (archetype: orchestrator).
#### [NEW] `src/specweaver/assurance/standards/core/context.yaml`
- Add to seal pure-logic boundary.

### 4. Infrastructure (LLM) CLI & Hexagon Sealing
#### [NEW] `src/specweaver/infrastructure/llm/interfaces/cli.py`
- Moves `cost_commands.py` and `usage_commands.py` here.
- Add `context.yaml` (archetype: orchestrator).
#### [NEW] `src/specweaver/infrastructure/llm/core/context.yaml`
- Add to seal pure-logic boundary.

### 5. Workflows (Implementation & Review) CLI & Hexagon Sealing
#### [NEW] `src/specweaver/workflows/implementation/interfaces/cli.py`
- Moves `implement.py` here.
- Add `context.yaml` (archetype: orchestrator).
#### [NEW] `src/specweaver/workflows/implementation/core/context.yaml`
- Add to seal pure-logic boundary.
#### [NEW] `src/specweaver/workflows/review/interfaces/cli.py`
- Moves `review.py` here.
- Add `context.yaml` (archetype: orchestrator).
#### [NEW] `src/specweaver/workflows/review/core/context.yaml`
- Add to seal pure-logic boundary.

### 6. Workspace (Project) CLI & Hexagon Sealing
#### [NEW] `src/specweaver/workspace/project/interfaces/cli.py`
- Moves `projects.py`, `constitution.py`, and `hooks.py` here.
- Add `context.yaml` (archetype: orchestrator).
#### [NEW] `src/specweaver/workspace/project/core/context.yaml`
- Add to seal pure-logic boundary.

### 7. Core Flow CLI & Hexagon Sealing
#### [NEW] `src/specweaver/core/flow/interfaces/cli.py`
- Moves `pipelines.py` here.
- Add `context.yaml` (archetype: orchestrator).
#### [NEW] `src/specweaver/core/flow/core/context.yaml`
- Add to seal pure-logic boundary.

### 8. API Serving CLI
#### [MODIFY] `src/specweaver/interfaces/cli/routers/serve_router.py`
- Retains `serve.py` locally within the global orchestration layer since it boots the L6 API.

### 9. Destroy the Junk Drawer (`_helpers.py`)
Rather than keeping global helpers that cause upward dependencies or polluting config with `rich.table`, distribute the helpers to their respective domain `interfaces/cli.py` files:
- Move `_display_results` and `_print_summary` to `assurance/validation/interfaces/cli.py`.
- Move `_load_topology` to `graph/interfaces/cli.py`.
- Move `_run_workspace_op` to `workspace/project/interfaces/cli.py`.

### 10. Root CLI Re-Registration & Top-Down Injection
#### [MODIFY] `src/specweaver/interfaces/cli/main.py`
- Import all newly decentralized domain `typer.Typer()` apps and `app.add_typer()` them.
- Resolve global state (like active project and console instantiations) centrally and pass them downward via `typer.Context.obj` ONLY for new commands. For existing commands, domain CLIs will instantiate their own local `rich.Console()`.

### 11. Boundary Enforcement (The Hexagon Seal)
#### [MODIFY] `tach.toml`
- Explicitly map every newly created `core` and `interfaces` sub-package to ensure the Rust static analyzer natively enforces the boundaries.

#### [DELETE] Legacy CLI Files
- Remove all migrated files from `src/specweaver/interfaces/cli/` including `_helpers.py` and `_db_utils.py`. The only files remaining in L6 should be `main.py`, `_core.py` (stripped down), and any internal CLI routers.

## Verification Plan

### Automated Tests
- Run `pytest --tach` to strictly verify that no Domain CLI introduces an upward dependency violation or breaks archetype pure-logic constraints.
- Run `pytest tests/e2e/test_cli_bootstrap_e2e.py` to ensure the entrypoint is stable.

### Manual Verification
- Execute `sw --help` to confirm all commands (`sw graph`, `sw lineage`, `sw config`, etc.) are successfully registered and visible in the root Typer app.
