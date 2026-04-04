# Implementation Plan: Internal Layer Enforcement (Tach) [SF-2: Resource & Core Capability Hardening]
- **Feature ID**: 3.20a
- **Sub-Feature**: SF-2 — Resource & Core Capability Hardening
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3_20a/feature_3_20a_design.md
- **Design Section**: §Sub-Feature Decomposition → SF-2
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_20a/feature_3_20a_sf2_implementation_plan.md
- **Status**: APPROVED

## Feature Scope Overview
This Sub-Feature formalizes the Resource and Core Capability modules (`project`, `context`, `graph`, `llm`) into the `tach.toml` registry.

## Proposed Changes

### 1. Architecture Linter Configuration
#### [MODIFY] `tach.toml`
- Append four new independent modules explicitly outlining their dependencies against the Base layers and each other.

```toml
[[modules]]
path = "src.specweaver.project"
depends_on = [
    { path = "src.specweaver.logging" },
    { path = "src.specweaver.standards" }
]
strict = true

[[modules]]
path = "src.specweaver.context"
depends_on = [
    { path = "src.specweaver.logging" }
]
strict = true

[[modules]]
path = "src.specweaver.graph"
depends_on = [
    { path = "src.specweaver.logging" },
    { path = "src.specweaver.context" }
]
strict = true

[[modules]]
path = "src.specweaver.llm"
depends_on = [
    { path = "src.specweaver.logging" },
    { path = "src.specweaver.config" },
    { path = "src.specweaver.graph" }
]
strict = true
```

### 2. Base Layer Boilerplate Cleanup
#### [DELETE] `src/specweaver/project/__init__.py`
#### [DELETE] `src/specweaver/context/__init__.py`
#### [DELETE] `src/specweaver/graph/__init__.py`
#### [DELETE] `src/specweaver/llm/__init__.py`
- *Context: Cleaning up the legacy `__all__` encapsulation since `tach` will map public boundaries.*

## User Review Required
> [!IMPORTANT]
> The DAG mapping has been determined via rigorous codebase inspection (`llm` imports `config` and `graph`; `graph` imports `context`). If any underlying code is using dynamic or hidden upstream imports (e.g. `llm` importing `cli`), it will break in runtime after Tach enforces this isolation.

## Open Questions
- None.

## Verification Plan
1. **Automated Validation**: `tach check` will verify the math of the bounded contexts.
2. **Pre-Commit Suite**: `python -m pytest tests/` and `ruff check` will operate naturally inside the gating sequence.
