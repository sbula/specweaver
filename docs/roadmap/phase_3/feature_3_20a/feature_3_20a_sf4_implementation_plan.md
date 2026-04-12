# Implementation Plan: Internal Layer Enforcement (Tach) [SF-4: Public Interface Enforcement]
- **Feature ID**: 3.20a
- **Sub-Feature**: SF-4 — Public Interface Enforcement
- **Design Document**: docs/roadmap/phase_3/feature_3_20a/feature_3_20a_design.md
- **Status**: APPROVED

## 1. Goal
Delete all remaining `__init__.py` proxy-export boilerplate files deep inside `src/specweaver` and enforce their replacement with native, computationally-evaluated Rust boundaries using Tach's `interfaces:` registry. With this, any new agent can systematically modify exactly what needs to be changed without any guesswork.

## 2. Proposed Changes

### Layer 1: Core Bounded Contexts Registry (`tach.toml`)
#### [MODIFY] `tach.toml`
The following components must have their `[[interfaces]]` blocks formally deployed to replace `__init__.py`. 
*Note: Any external import targeting a file not explicitly defined in these lists will trigger a static architectural failure.*

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

### Layer 2: LLM Adapter Registry Refactor
#### [NEW] `src/specweaver/llm/adapters/registry.py`
- Copy the dynamic plugin loader (`_ensure_discovered()`, `register_adapter()`) natively into this explicit file instead of burying it in an init module.
#### [DELETE] `src/specweaver/llm/adapters/__init__.py`
#### [MODIFY] Import Path Rewiring
- Rewrite `from specweaver.infrastructure.llm.adapters import ...` to `from specweaver.infrastructure.llm.adapters.registry import ...` inside `src/specweaver/llm/factory.py`, `src/specweaver/llm/telemetry.py`, `src/specweaver/llm/router.py`.

### Layer 3: Loom Boilerplate Extinction
#### [DELETE] The Loom Proxy Sub-Tree
The following arbitrary proxies must be physically deleted:
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

#### [MODIFY] Loom Path Rewiring
Consumers previously calling `from specweaver.core.loom.tools.git import GitTool` must explicitly call `from specweaver.core.loom.tools.git.tool import GitTool`. All boundary verification relies strictly on Tach.

## 3. Verification
1. Run `tach check` to prove interfaces block illegal imports.
2. Run `ruff run` to locate mis-linked internal imports following the `__init__.py` purge.
3. Run `pytest` to guarantee the dynamic LLM adapter factory functions stably internally.
