# Implementation Plan: Internal Layer Enforcement (Tach) [SF-1: Initialization & Base Layer Isolation]
- **Feature ID**: 3.20a
- **Sub-Feature**: SF-1 — Initialization & Base Layer Isolation
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3_20a/feature_3_20a_design.md
- **Design Section**: §Sub-Feature Decomposition → SF-1
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_20a/feature_3_20a_sf1_implementation_plan.md
- **Status**: APPROVED

## Feature Scope Overview
This Sub-Feature initializes `Tach` into SpecWeaver and formally defines the bottom-most dependencies (the "Base Layer"). It guarantees that `config`, `standards`, and `logging.py` operate completely stateless and free from any upward dependency entanglements.

## Proposed Changes

### 1. Build and CI Dependencies
#### [MODIFY] `pyproject.toml`
- Add `"tach"` to the `[project.optional-dependencies] dev` array. 
- *Context: Aligns tightly with standard Python packaging constraints mapped in Phase 4.*

#### [MODIFY] `.agents/workflows/pre-commit/phase-2-code-quality.md`
- Inject a mandatory step forcing the AI agent to execute `tach check` alongside `ruff` and `mypy`. 
- *Context: As decided in Phase 4, we integrate this strictly into the internal workflow gate rather than relying on external developer git-hooks.*

### 2. Architecture Linter Configuration & Cleanup
#### [NEW] `tach.toml`
- Create the root layer-graph configuration file.
- Define three completely independent modules to guarantee stateless base behaviors. 
- **CRITICAL SYNTAX HINT:** An incoming agent must use exact syntax so it does not hallucinate configuration keys.
```toml
[modules]
[[modules.path]]
path = "src.specweaver.logging"
depends_on = []
strict = true

[[modules.path]]
path = "src.specweaver.config"
depends_on = [
    { path = "src.specweaver.logging" }
]
strict = true

[[modules.path]]
path = "src.specweaver.standards"
depends_on = [
    { path = "src.specweaver.logging" }
]
strict = true
```

#### [DELETE] Base Layer Boilerplate
- Delete `src/specweaver/config/__init__.py` and `src/specweaver/standards/__init__.py`. 
- *Context: As we formalize each layer into Tach, we must systematically clean up the legacy, manual `__all__ = [...]` export logic behind us. This prevents two conflicting architectural systems from existing simultaneously.*

> [!CAUTION]  
> If `tach check` throws any violation indicating that `config` or `standards` accidentally references a domain model from `src/specweaver/validation` or `src/specweaver/flow`, **the workflow must fail**. Those upstream references must be surgically severed and passed via arguments to maintain strict Base Layer statelessness.

## Verification Plan

### Automated Tests
1. Run `pip install -e ".[dev]"` to confirm `tach` installs successfully via `pyproject.toml`.
2. Run `tach sync` or manually author `tach.toml` root constraints.
3. Run `tach check` from the project root. Expect a zero exit code if the Base Layer isolates successfully.

### Quality Gates
- Proceed through `/pre-commit` workflow, confirming the new Phase 2 gate successfully enforces `tach check`.
