# Implementation Plan: Internal Layer Enforcement (Tach) [SF-3: Presentation Layer Sterilization]
- **Feature ID**: 3.20a
- **Sub-Feature**: SF-3 — Presentation Layer Sterilization
- **Design Document**: docs/roadmap/phase_3/feature_3_20a/feature_3_20a_design.md
- **Design Section**: §Sub-Feature Decomposition → SF-3
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_20a/feature_3_20a_sf3_implementation_plan.md
- **Status**: APPROVED

## 1. Goal
Enforce that no domain logic inside `src/specweaver` is mathematically allowed to depend on `api` or `cli`.

## 2. Proposed Changes

### Configuration Binding
#### [MODIFY] `tach.toml`
- Declare `src.specweaver.interfaces.api` and `src.specweaver.interfaces.cli` as tracked modules.
- Run `tach sync` to auto-populate the massive `depends_on` graphs for these layers (which consume almost all underlying components). Because they are registered at the physical ceiling of the module stack, no other module will have them in its dependency list, mathematically sterilizing the presentation layer.

### Boilerplate Cleanup
#### [MODIFY] `src/specweaver/cli/__init__.py`
- Unlike the resource capabilities, the CLI `__init__.py` houses the core Typer `@app.callback()` lifecycle and cannot be deleted.
- I will prune lines 78-95 which contain legacy backward-compatible re-exports (`from specweaver.interfaces.cli._helpers import...`) since this violates Python clean architecture when `tach` defines the interface bounds. 

#### [NO CHANGE] `src/specweaver/api/__init__.py`
- Contains no domain logic hacking or `__all__` blockages. Retained as-is for package compliance.

## Verification
1. `tach sync` explicitly establishes the DAG.
2. `tach check` ensures `api` and `cli` sit explicitly at the top of the dependency funnel.
3. `ruff` and `pytest` confirm no broken CLI integrations.
