# C-EXEC-01 SF-04 — Public Interface Enforcement

**Status**: APPROVED · **FRs owned**: FR-3 · **Feature ID**: 3.20a · Design:
[C-EXEC-01_design.md](C-EXEC-01_design.md) §Sub-features → SF-04

FR-3 (public surfaces declared through `interfaces:`, not `__init__.py` re-export hacks) recorded
2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-01-SF02-MIG`. Its soft-deprecation guard now
asserts the block was found (it had matched a module prefix `tach.toml` does not use).

**Since moved:** `loom/` now lives under `sandbox/` (e.g. `sandbox/qa_runner/core/`). Paths below
are as of the plan's date.

## Goal

Delete the remaining `__init__.py` proxy-export files inside `src/specweaver` and replace them with
Tach's `interfaces:` registry, so the public surface of each module is explicit.

## Changes

1. **`tach.toml`** — `[[interfaces]]` blocks replace `__init__.py`. An external import of a file
   not listed here is an architecture failure.

```toml
[[interfaces]]
from = ["src.specweaver.workspace.project"]
expose = ["constitution", "scaffold", "discovery", "settings", "models"]

[[interfaces]]
from = ["src.specweaver.workspace.context"]
expose = ["analyzers", "provider", "hitl_provider", "inferrer", "recency", "models"]

[[interfaces]]
from = ["src.specweaver.assurance.graph"]
expose = ["topology", "selectors", "builder", "models"]

[[interfaces]]
from = ["src.specweaver.infrastructure.llm"]
expose = ["models", "adapters.base", "adapters.registry", "prompt_builder", "mention_scanner.models", "mention_scanner.scanner", "telemetry", "router", "collector", "factory", "lineage"]

[[interfaces]]
from = ["src.specweaver.core.loom"]
expose = ["atoms", "commons", "dispatcher", "security", "tools"]
```

2. **LLM adapter registry**
   - NEW `src/specweaver/llm/adapters/registry.py` — the dynamic plugin loader
     (`_ensure_discovered()`, `register_adapter()`) moves here from the init module.
   - DELETE `src/specweaver/llm/adapters/__init__.py`.
   - Rewrite `from specweaver.infrastructure.llm.adapters import ...` to
     `from specweaver.infrastructure.llm.adapters.registry import ...` in
     `src/specweaver/llm/factory.py`, `src/specweaver/llm/telemetry.py`,
     `src/specweaver/llm/router.py`.
3. **Loom proxies — DELETE:**
   - `src/specweaver/loom/atoms/__init__.py`
   - `src/specweaver/loom/atoms/filesystem/__init__.py`
   - `src/specweaver/loom/atoms/git/__init__.py`
   - `src/specweaver/loom/atoms/qa_runner/__init__.py`
   - `src/specweaver/loom/commons/__init__.py`
   - `src/specweaver/loom/commons/filesystem/__init__.py`
   - `src/specweaver/loom/commons/git/__init__.py`
   - `src/specweaver/loom/commons/qa_runner/__init__.py`
   - `src/specweaver/loom/commons/qa_runner/java/__init__.py`
   - `src/specweaver/loom/commons/qa_runner/kotlin/__init__.py`
   - `src/specweaver/loom/commons/qa_runner/python/__init__.py`
   - `src/specweaver/loom/commons/qa_runner/rust/__init__.py`
   - `src/specweaver/loom/commons/qa_runner/typescript/__init__.py`
   - `src/specweaver/loom/tools/__init__.py`
   - `src/specweaver/loom/tools/filesystem/__init__.py`
   - `src/specweaver/loom/tools/git/__init__.py`
   - `src/specweaver/loom/tools/qa_runner/__init__.py`
   - `src/specweaver/loom/tools/web/__init__.py`
4. **Loom import rewiring** — `from specweaver.core.loom.tools.git import GitTool` becomes
   `from specweaver.core.loom.tools.git.tool import GitTool`. Boundary checks rely on Tach alone.

## Tests

1. `tach check` — interfaces block illegal imports.
2. `ruff run` — finds mis-linked internal imports after the `__init__.py` purge.
3. `pytest` — the dynamic LLM adapter factory still works.
