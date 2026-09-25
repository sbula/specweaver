# C-EXEC-01 SF-02 — Resource & Core Capability Hardening

**Status**: APPROVED · **FRs owned**: none · **Feature ID**: 3.20a · Design:
[C-EXEC-01_design.md](C-EXEC-01_design.md) §Sub-features → SF-02

No FR of its own: SF-02 extends FR-1's declaration to the resource and capability layers. Recorded
2026-08-17 from `INT-US-01-SF02-MIG` so the silence is deliberate.

## Goal

Register the resource and core capability modules (`project`, `context`, `graph`, `llm`) in
`tach.toml`.

## Changes

1. **`tach.toml`** — four modules with their dependencies on the base layer and each other:

```toml
[[modules]]
path = "src.specweaver.workspace.project"
depends_on = [
    { path = "src.specweaver.logging" },
    { path = "src.specweaver.assurance.standards" }
]
strict = true

[[modules]]
path = "src.specweaver.workspace.context"
depends_on = [
    { path = "src.specweaver.logging" }
]
strict = true

[[modules]]
path = "src.specweaver.assurance.graph"
depends_on = [
    { path = "src.specweaver.logging" },
    { path = "src.specweaver.workspace.context" }
]
strict = true

[[modules]]
path = "src.specweaver.infrastructure.llm"
depends_on = [
    { path = "src.specweaver.logging" },
    { path = "src.specweaver.core.config" },
    { path = "src.specweaver.assurance.graph" }
]
strict = true
```

2. **Delete** the legacy `__all__` encapsulation — `tach` maps the public boundaries:
   `src/specweaver/project/__init__.py`, `src/specweaver/context/__init__.py`,
   `src/specweaver/graph/__init__.py`, `src/specweaver/llm/__init__.py`.

> [!IMPORTANT]
> The DAG comes from codebase inspection (`llm` imports `config` and `graph`; `graph` imports
> `context`). A dynamic or hidden upstream import (e.g. `llm` importing `cli`) breaks at runtime
> once Tach enforces this.

## Tests

1. `tach check` verifies the bounded contexts.
2. `python -m pytest tests/` and `ruff check` in the gate.
