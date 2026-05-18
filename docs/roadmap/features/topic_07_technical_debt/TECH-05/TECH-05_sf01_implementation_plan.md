# Implementation Plan: Context Loading Pipeline Refactoring [SF-01: Delete All CLI Wrappers]

- **Feature ID**: TECH-05
- **Sub-Feature**: SF-01 — Delete All CLI Wrappers
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-05/TECH-05_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-05/TECH-05_sf01_implementation_plan.md
- **Status**: IMPLEMENTED

---

## Research Notes

### What Actually Exists (Phase 0 findings)

**FR-1: `_load_constitution_content` in `workspace/project/interfaces/cli.py`**
```python
def _load_constitution_content(project_path, spec_path=None):
    info = find_constitution(project_path, spec_path=spec_path)
    return info.content if info else None
```
Public API: `find_constitution(project_path, spec_path=None) -> ConstitutionInfo | None`. Replace pattern:
```python
_info = find_constitution(project_path, spec_path=spec_path)
constitution = _info.content if _info else None
```

**FR-2: `_load_standards_content` in `assurance/standards/interfaces/cli.py`**
```python
def _load_standards_content(project_path, target_path=None, *, max_chars=2000):
    db = _core.get_db()
    active = _run_workspace_op("get_active_project")
    if not active:
        return None
    return load_standards_content(db, active, project_path, target_path=target_path, max_chars=max_chars)
```
This internally calls `_run_workspace_op` — so FR-2 and FR-4 are entangled. `run_repo_op` must exist before standards callers are updated.

**FR-3: `_require_llm_adapter` in `infrastructure/llm/interfaces/cli.py`**
Complex wrapper with:
- `_run_workspace_op("get_active_project")` → `project_name`
- `load_settings(db, project, llm_role=llm_role)` → `SpecWeaverSettings`
- `create_llm_adapter(settings, telemetry_project=project)` → `(settings, adapter, gen_config)`
- Catches `LLMAdapterError` → `typer.Exit(1)` + `console.print`
- Catches `ValueError` → **hardcoded fallback** with `api_key="test-key"` (security risk, must die)

Public APIs: `load_settings(db, project_name)` in `core/config/settings_loader.py`, `create_llm_adapter(settings, telemetry_project)` in `infrastructure/llm/factory.py`.

**FR-4: `_run_workspace_op` — TWO copies**
- **Copy 1** `workspace/project/interfaces/cli.py`: string-dispatch via `getattr(repo, method_name)(*args)`
- **Copy 2** `core/config/interfaces/cli.py` lines 24-32: identical implementation

Replacement: typed `run_repo_op(fn)` in `interfaces/cli/_core.py`. `_core.py` already has: `get_db()`, `console`, `app`, `_require_active_project()` (but currently uses `_run_workspace_op` — must update too).

**FR-5: `_load_topology` + `_select_topology_contexts` in `graph/interfaces/cli.py`**
- `_load_topology`: calls `TopologyEngine()` + `TopologyGraph.from_project(project_path, engine, auto_infer=False)`, then `console.print()` for feedback
- `_select_topology_contexts`: string→selector class dispatch via `_SELECTOR_MAP` dict + `console.print()` for feedback

`TopologyGraph` and all selectors already live in `assurance/graph/`. New public facade in `assurance/graph/loader.py`.

### Test Impact (Phase 0 findings)

Tests that patch the OLD function paths (must update patch targets after move):
- `tests/unit/workspace/project/interfaces/test_cli_hooks.py` — patches `specweaver.workspace.project.interfaces.cli._run_workspace_op`
- `tests/unit/infrastructure/llm/interfaces/test_helpers_llm_fallback.py` — patches `specweaver.workspace.project.interfaces.cli._run_workspace_op` AND tests the hardcoded fallback
- `tests/unit/infrastructure/llm/interfaces/test_helpers_telemetry.py` — patches `specweaver.infrastructure.llm.interfaces.cli._run_workspace_op`
- `tests/unit/graph/interfaces/test_cli_lineage.py` — patches `specweaver.graph.interfaces.cli._run_workspace_op`
- `tests/unit/core/flow/interfaces/test_resolve_pipeline_name.py` — patches `_run_workspace_op`
- `tests/unit/interfaces/cli/test_cli_helpers.py` — imports `_load_constitution_content` directly, tests it
- `tests/unit/infrastructure/llm/interfaces/test_cli_telemetry_flush.py` — patches `_load_constitution_content`

Tests with LOCAL `_run_workspace_op` helper (defined in-file, not imported — NOT affected by the delete):
- `test_cli_constitution.py`, `test_usage_commands.py`, `test_cli_config.py`, `test_config_routing.py`, `test_cli_standards.py`

### Key Constraint

**`_load_standards_content` callers pass only `(project_path, target_path=spec_path)`** — no `db`, no `project_name`. The wrapper resolves both internally. After deletion, each caller must:
1. Acquire `db` via `_core.get_db()` (already done in each command)
2. Acquire `project_name` via `_core.run_repo_op(lambda r: r.get_active_project())`
3. Call `load_standards_content(db, project_name, project_path, target_path=...)`

---

## Implementation Steps

> **Mandatory step order**: add `run_repo_op` first (Step 1), then all deletions (Steps 2-6), then test updates (Step 7).

### Step 1 — Add `run_repo_op()` to `interfaces/cli/_core.py`

Add after the existing `_require_active_project` function:

```python
from collections.abc import Awaitable, Callable
from typing import TypeVar

from specweaver.workspace.store import WorkspaceRepository

_T = TypeVar("_T")


def run_repo_op(fn: Callable[[WorkspaceRepository], Awaitable[_T]]) -> _T:
    """Run a typed WorkspaceRepository operation synchronously (CLI only).

    Replaces the string-dispatched ``_run_workspace_op`` anti-pattern.
    Each caller passes a typed lambda, giving IDE autocomplete and
    grep-ability.

    Example::

        active = _core.run_repo_op(lambda r: r.get_active_project())
        proj = _core.run_repo_op(lambda r: r.get_project(name))

    Warning: This is CLI-only. API handlers must use async sessions directly.
    """
    import anyio

    db = get_db()

    async def _action() -> _T:
        async with db.async_session_scope() as session:
            return await fn(WorkspaceRepository(session))

    return anyio.run(_action)
```

Also update `_require_active_project` to use `run_repo_op` instead of importing `_run_workspace_op`:
```python
def _require_active_project() -> str:
    get_db()
    name_raw = run_repo_op(lambda r: r.get_active_project())
    if not name_raw:
        console.print(
            "[red]Error:[/red] No active project. "
            "Run [bold]sw init <name>[/bold] or [bold]sw use <name>[/bold].",
        )
        raise typer.Exit(code=1)
    return str(name_raw)
```

Update `__all__`: add `"run_repo_op"`.

### Step 2 — Delete `_load_constitution_content` from `workspace/project/interfaces/cli.py`

Delete the function body (2 lines). Update all 5 import sites:

| File | Change |
|---|---|
| `core/flow/interfaces/cli.py` | Remove import; replace `_load_constitution_content(project_path, spec_path=spec_path)` with `find_constitution(project_path, spec_path=spec_path)` (add `from specweaver.workspace.project.constitution import find_constitution`) |
| `workflows/review/interfaces/cli.py` | Same |
| `workflows/implementation/interfaces/cli.py` | Same |
| `interfaces/api/v1/review.py` | Remove import; inline 2 lines |
| `interfaces/api/v1/implement.py` | Remove import; inline 2 lines |

### Step 3 — Delete `_load_standards_content` from `assurance/standards/interfaces/cli.py`

Delete the function body. Update all 3 import sites (note: these also need `project_name`, acquired via `run_repo_op`):

| File | Change |
|---|---|
| `core/flow/interfaces/cli.py` | Remove import; inline 3-step fetch (db, project_name via `run_repo_op`, then `load_standards_content`) |
| `workflows/review/interfaces/cli.py` | Same |
| `workflows/implementation/interfaces/cli.py` | Same (was: `_load_standards_content(project_path, target_path=spec_path)` → now explicit) |

### Step 4 — Delete `_require_llm_adapter` from `infrastructure/llm/interfaces/cli.py`

Delete the function body. Update all 4 import sites. Each CLI caller replaces with:
```python
db = _core.get_db()
project_name = _core.run_repo_op(lambda r: r.get_active_project())
from specweaver.core.config.settings_loader import load_settings
from specweaver.infrastructure.llm.factory import LLMAdapterError, create_llm_adapter
try:
    settings = load_settings(db, project_name, llm_role="draft")
    _, adapter, gen_config = create_llm_adapter(settings, telemetry_project=project_name)
except (LLMAdapterError, ValueError) as exc:
    _core.console.print(f"[red]Error:[/red] {exc}")
    raise typer.Exit(code=1) from exc
```
Note: The hardcoded fallback (`api_key="test-key"`) is deliberately killed. `ValueError` is now surfaced as a user error.

| File | Change |
|---|---|
| `core/flow/interfaces/cli.py` | Remove import; inline the pattern above |
| `workflows/review/interfaces/cli.py` | Same |
| `workflows/implementation/interfaces/cli.py` | Same |
| `assurance/validation/interfaces/cli_drift.py` | Same (lazy import → inline in the function where it's used) |

### Step 5 — Delete both copies of `_run_workspace_op`

**Copy 1** (`workspace/project/interfaces/cli.py`): Delete function. Update all 6 cross-domain call sites to use `_core.run_repo_op()`:

| File | Old call | New call |
|---|---|---|
| `interfaces/cli/main.py` | `_run_workspace_op("get_active_project")` | `_core.run_repo_op(lambda r: r.get_active_project())` |
| `infrastructure/llm/interfaces/cli.py` | `_run_workspace_op("get_active_project")` in `usage()` | `_core.run_repo_op(lambda r: r.get_active_project())` |
| `graph/interfaces/cli.py` | `_run_workspace_op("get_active_project")`, `_run_workspace_op("get_project", active)` | `run_repo_op` equivalents |
| `assurance/validation/interfaces/cli.py` | multiple calls | `run_repo_op` equivalents |
| `assurance/standards/interfaces/cli.py` | multiple calls | `run_repo_op` equivalents |

Also remove `from specweaver.workspace.project.interfaces.cli import _run_workspace_op` from each.

**Copy 2** (`core/config/interfaces/cli.py`): Delete local `_run_workspace_op` definition. Replace internal call sites with `_core.run_repo_op()`.

### Step 6 — Add Topology Facade + Delete `_load_topology` / `_select_topology_contexts`

**6a. Create `assurance/graph/loader.py`**:

```python
"""Public facade for topology loading and context selection.

Extracted from ``graph/interfaces/cli.py`` so that CLI and API can
load topology without importing from a CLI module.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.assurance.graph.topology import TopologyContext, TopologyGraph

logger = logging.getLogger(__name__)

_SELECTOR_MAP: dict[str, type] = {}


def _get_selector_map() -> dict[str, type]:
    if not _SELECTOR_MAP:
        from specweaver.assurance.graph.selectors import (
            ConstraintOnlySelector,
            DirectNeighborSelector,
            ImpactWeightedSelector,
            NHopConstraintSelector,
        )
        _SELECTOR_MAP.update({
            "direct": DirectNeighborSelector,
            "nhop": NHopConstraintSelector,
            "constraint": ConstraintOnlySelector,
            "impact": ImpactWeightedSelector,
        })
    return _SELECTOR_MAP


def load_topology(project_path: Path) -> TopologyGraph | None:
    """Load the project topology graph from context.yaml files.

    Returns None if no context.yaml files are found.
    Callers are responsible for any user-facing console output.
    """
    from specweaver.assurance.graph.topology import TopologyGraph
    from specweaver.graph.topology.engine import TopologyEngine

    engine = TopologyEngine()
    graph = TopologyGraph.from_project(project_path, engine, auto_infer=False)
    if not graph.nodes:
        logger.debug("No context.yaml files found — topology context disabled.")
        return None
    logger.debug("Loaded topology: %d modules.", len(graph.nodes))
    return graph


def select_topology_contexts(
    graph: TopologyGraph | None,
    module_name: str,
    *,
    selector_name: str = "direct",
) -> list[TopologyContext] | None:
    """Run a selector and return topology contexts, or None.

    Callers are responsible for any user-facing console output.
    """
    if graph is None:
        return None

    selector_map = _get_selector_map()
    selector_cls = selector_map.get(selector_name)
    if selector_cls is None:
        logger.warning("Unknown selector '%s', falling back to 'direct'.", selector_name)
        from specweaver.assurance.graph.selectors import DirectNeighborSelector
        selector_cls = DirectNeighborSelector

    selector = selector_cls()
    related = selector.select(graph, module_name)
    if not related:
        return None

    contexts = graph.format_context_summary(module_name, related)
    logger.debug("Topology: %d related module(s) via %s selector.", len(contexts), selector_name)
    return contexts
```

**6b. Delete `_load_topology`, `_select_topology_contexts`, and `_SELECTOR_MAP` from `graph/interfaces/cli.py`**.

**6c. Update 4 import sites** to use `assurance.graph.loader`:

| File | Old imports | New imports |
|---|---|---|
| `core/flow/interfaces/cli.py` | `from specweaver.graph.interfaces.cli import _load_topology, _select_topology_contexts` | `from specweaver.assurance.graph.loader import load_topology, select_topology_contexts` |
| `workflows/review/interfaces/cli.py` | Same | Same |
| `workflows/implementation/interfaces/cli.py` | Same | Same |
| `interfaces/api/v1/implement.py` | Same | Same |

**6d. Add `console.print` feedback** at each CLI call site (since it was stripped from the facade):
```python
topo_graph = load_topology(project_path)
if topo_graph is None:
    _core.console.print("[dim]No context.yaml files found -- topology context disabled.[/dim]")
```

### Step 7 — Update Tests

**Tests with broken patch paths** (must update monkeypatch targets):

| Test file | Old patch | New patch |
|---|---|---|
| `test_cli_hooks.py` | `specweaver.workspace.project.interfaces.cli._run_workspace_op` | `specweaver.interfaces.cli._core.run_repo_op` |
| `test_helpers_llm_fallback.py` | `specweaver.workspace.project.interfaces.cli._run_workspace_op` | `specweaver.interfaces.cli._core.run_repo_op`. Also delete tests for hardcoded fallback (function is gone). |
| `test_helpers_telemetry.py` | `specweaver.infrastructure.llm.interfaces.cli._run_workspace_op` | `specweaver.interfaces.cli._core.run_repo_op` |
| `test_cli_lineage.py` | `specweaver.graph.interfaces.cli._run_workspace_op` | `specweaver.interfaces.cli._core.run_repo_op` |
| `test_resolve_pipeline_name.py` | inline string `"_run_workspace_op"` | `"run_repo_op"` |
| `test_cli_telemetry_flush.py` | patches `_load_constitution_content` | patches `find_constitution` from `workspace.project.constitution` |

**Test file to rewrite/delete**:
- `tests/unit/interfaces/cli/test_cli_helpers.py` — directly imports and tests `_load_constitution_content`. The function is deleted; its behaviour is now tested in `test_constitution.py` (domain layer). Delete this test or convert to test `find_constitution` directly.

---

## Verification Plan

### Automated
1. `tach check` — zero boundary violations
2. `pytest tests/` — full suite passes
3. Manual smoke: `sw run <pipeline>`, `sw implement <spec>`, `sw review <file>` all succeed
4. `grep -r "_load_constitution_content\|_load_standards_content\|_require_llm_adapter\|_run_workspace_op\|_load_topology\|_select_topology_contexts" src/` — zero matches
5. `grep -r "graph.interfaces.cli import" src/` — zero matches (API no longer imports from CLI)

### Manual
- Run `sw implement` against a real spec: verify constitution + standards + topology all load
- Run `POST /implement` via API: verify no `console.print` noise in server logs
- Run `sw costs`, `sw usage` — verify LLM telemetry commands still work
