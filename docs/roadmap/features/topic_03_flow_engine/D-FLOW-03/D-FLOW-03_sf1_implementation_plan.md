# Implementation Plan: Static Model Routing — SF-1: ModelRouter + DB + Handler Integration

- **Feature ID**: feature_3_14
- **Sub-Feature**: SF-1 — ModelRouter + DB + Handler Integration
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/D-FLOW-03/D-FLOW-03_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/D-FLOW-03/D-FLOW-03_sf1_implementation_plan.md
- **Status**: COMPLETE

---

## Overview

This plan implements the routing engine for Feature 3.12b. When complete, every
pipeline LLM call resolves its adapter **and model** from the per-task-type DB
config rather than the single project default. All callers that don't configure
routing continue working identically (FR-3: transparent fallback).

SF-2 (CLI commands) depends on two new DB methods added here. SF-1 must be
committed before SF-2 planning begins.

---

## Research Notes (Phase 0 Findings)

**R1 — `RunContext` assembly points (two locations):**
- `cli/pipelines.py:229` — `_execute_run()`: assembles context for a fresh `sw run`.
  LLM is wired at lines 241–250. `ModelRouter` must be created here alongside the adapter.
- `cli/pipelines.py:379` — `resume()`: assembles context for `sw resume`. Note: the
  `resume` command does NOT wire up the LLM adapter at all (pre-existing gap).
  Add `ModelRouter` injection here too, inside a try/except to match the `run` pattern.

**R2 — `DraftSpecHandler` makes zero LLM calls** — no routing needed. Skip this handler.

**R3 — `_build_tool_dispatcher` in `_review.py:58`** checks
`hasattr(context.llm, 'generate_with_tools')`. Since `context.llm` remains the
default fallback adapter, this check is unaffected by routing. No change needed here.

**R4 — `load_settings` raises `ValueError` (not `KeyError`)** when the role has no
profile link (settings.py:104). The router catches this as "no entry — return None".

**R5 — No `unlink_project_profile` exists in `_db_llm_mixin.py`.** Must add it.
Existing `link_project_profile` uses `INSERT OR REPLACE` — so set is already idempotent.

**R6 — `_review_config_from_context` and `_gen_config_from_context`** are shared
private helpers per-file. Update each to accept an optional `RouterResult` argument
(keyword-only) and prefer it over `context.config` when provided.

**R7 — `TelemetryCollector` wrapping** is done inside `ModelRouter.get_for_task()`
at cache-fill time. The cache stores the already-wrapped adapter. No double-wrapping.

**R9 — `LintFixHandler._llm_fix()` calls `llm.generate(prompt)` with a raw string** — a pre-existing
bug. This bypasses `GenerationConfig` entirely, so model, temperature, and `task_type`
are never set. When `context.llm` is a `TelemetryCollector` (i.e., telemetry enabled),
this call **fails at runtime** with `TypeError: generate() missing 1 required positional
argument: 'config'`. SF-1 fixes this by refactoring `_llm_fix()` to use the standard
`generate(messages: list[Message], config: GenerationConfig)` interface.
After SF-1, every handler in the codebase uses the unified call — no raw string paths remain.

**R10 — `TaskType` docstring is stale**: `"Does not affect generation behavior"` is no longer
true after 3.12b — `TaskType` is now also the routing key. Docstring must be updated.

---

## Proposed Changes

### 1. `llm/router.py` [NEW]

New file in `llm/` (adapter archetype). Contains `RouterResult` and `ModelRouter`.

```python
# src/specweaver/llm/router.py

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from specweaver.core.config.database import Database
    from specweaver.infrastructure.llm.models import TaskType

logger = logging.getLogger(__name__)


class RouterResult(NamedTuple):
    """Resolved routing result for one LLM call."""
    adapter: Any           # LLMAdapter or TelemetryCollector proxy
    model: str
    temperature: float
    max_output_tokens: int
    provider: str          # for logging / diagnostics
    profile_name: str      # for logging / diagnostics


class ModelRouter:
    """Resolves the correct LLM adapter + settings per TaskType.

    Created once per pipeline run by the CLI layer. Injected into
    RunContext.llm_router. Caches adapter instances by (provider, api_key_hash)
    so that multiple task types sharing the same provider reuse one adapter.

    Multiple task types MAY use the same provider with different models
    (e.g. draft → gemini-flash, implement → gemini-pro). They share one
    GeminiAdapter instance; model differences are in RouterResult.model.
    """

    def __init__(
        self,
        db: "Database",
        project_name: str,
        telemetry_project: str | None = None,
    ) -> None:
        self._db = db
        self._project_name = project_name
        self._telemetry_project = telemetry_project
        self._cache: dict[str, Any] = {}  # key: f"{provider}:{hash(api_key)}"

    def get_for_task(self, task_type: "TaskType") -> RouterResult | None:
        """Return RouterResult for this task_type, or None if no routing configured.

        None → caller MUST fall back to context.llm + context.config.llm.model.
        Never raises — all exceptions are caught and logged as warnings.
        """
        import os
        from specweaver.core.config.settings import load_settings
        from specweaver.infrastructure.llm.adapters import get_adapter_class

        role_key = f"task:{task_type.value}"

        try:
            settings = load_settings(self._db, self._project_name, llm_role=role_key)
        except ValueError:
            # No routing entry for this task_type
            logger.debug(
                "[routing] no entry for task_type=%s, using default",
                task_type.value,
            )
            return None
        except Exception:
            logger.warning(
                "[routing] lookup failed for task_type=%s",
                task_type.value,
                exc_info=True,
            )
            return None

        cache_key = f"{settings.llm.provider}:{hash(settings.llm.api_key)}"
        if cache_key not in self._cache:
            try:
                adapter_cls = get_adapter_class(settings.llm.provider)
                api_key = settings.llm.api_key or os.environ.get(
                    getattr(adapter_cls, "api_key_env_var",
                            f"{settings.llm.provider.upper()}_API_KEY"), ""
                )
                adapter: Any = adapter_cls(api_key=api_key or None)
                if self._telemetry_project:
                    from specweaver.infrastructure.llm.collector import TelemetryCollector
                    from specweaver.infrastructure.llm.telemetry import CostEntry
                    try:
                        raw = self._db.get_cost_overrides()
                        overrides = {k: CostEntry(*v) for k, v in raw.items()} if raw else None
                    except Exception:
                        overrides = None
                    adapter = TelemetryCollector(adapter, self._telemetry_project, overrides)
                self._cache[cache_key] = adapter
            except Exception:
                logger.warning(
                    "[routing] adapter creation failed for provider=%s",
                    settings.llm.provider,
                    exc_info=True,
                )
                return None

        logger.debug(
            "[routing] task_type=%s → provider=%s, model=%s",
            task_type.value, settings.llm.provider, settings.llm.model,
        )
        return RouterResult(
            adapter=self._cache[cache_key],
            model=settings.llm.model,
            temperature=settings.llm.temperature,
            max_output_tokens=settings.llm.max_output_tokens,
            provider=settings.llm.provider,
            profile_name="",
        )
```

> [!NOTE]
> `llm/router.py` follows the `adapter` archetype: it wraps external services
> (adapter creation) and consumes only `config/` and `llm/adapters/` — both
> allowed by `llm/context.yaml`. No `loom/*` imports.

---

### 2. `flow/_base.py` [MODIFY]

Add `llm_router: Any = None` field to `RunContext`:

```python
# In RunContext — after the existing `db: Any = None` field:
llm_router: Any = None  # ModelRouter | None — per-task-type adapter resolution (3.12b)
```

This is a backward-compatible additive change. All existing `RunContext(...)` calls
continue to work unchanged. Handlers check `context.llm_router is not None`.

---

### 3. `flow/_generation.py` [MODIFY]

Update `_gen_config_from_context()` to accept and prefer `RouterResult`:

```python
def _gen_config_from_context(
    context: RunContext,
    *,
    temperature: float = 0.2,
    task_type: TaskType | None = None,
    routed: "RouterResult | None" = None,   # NEW parameter
) -> GenerationConfig:
    from specweaver.infrastructure.llm.models import GenerationConfig
    from specweaver.infrastructure.llm.models import TaskType as _TaskType

    resolved_type = task_type if task_type is not None else _TaskType.IMPLEMENT

    if routed is not None:
        return GenerationConfig(
            model=routed.model,
            temperature=routed.temperature,   # profile-wins: per-task-type intent
            max_output_tokens=routed.max_output_tokens,
            task_type=resolved_type,
        )
    if context.config is not None:
        return GenerationConfig(
            model=context.config.llm.model,
            temperature=temperature,          # fallback: handler default
            max_output_tokens=context.config.llm.max_output_tokens,
            task_type=resolved_type,
        )
    return GenerationConfig(
        model="gemini-3-flash-preview",
        temperature=temperature,
        max_output_tokens=4096,
        task_type=resolved_type,
    )
```

> [!NOTE]
> **Temperature resolution — profile-wins:** When a routing entry is active,
> `routed.temperature` is used verbatim from the profile. This allows the same
> model (e.g. `gemini-3.1-pro`) to be used at `temperature=0.5` for spec writing
> and `temperature=0.2` for review within the same pipeline run, simply by
> configuring two routing entries with matched profiles.
> Handler-default temperatures (e.g., 0.2, 0.3) apply **only** in the fallback
> path (no routing entry configured for that task type).

**`GenerateCodeHandler.execute`** — add routing resolution:

```python
async def execute(self, step, context):
    started = _now_iso()
    if context.llm is None:
        return _error_result("LLM adapter required for generate steps", started)
    try:
        from specweaver.infrastructure.llm.models import TaskType
        routed = (
            context.llm_router.get_for_task(TaskType.IMPLEMENT)
            if context.llm_router else None
        )
        adapter = routed.adapter if routed else context.llm
        config = _gen_config_from_context(context, temperature=0.2,
                                          task_type=TaskType.IMPLEMENT, routed=routed)
        from specweaver.workflows.implementation.generator import Generator
        generator = Generator(llm=adapter, config=config)
        # ... rest unchanged
```

**`GenerateTestsHandler.execute`** — same pattern, `TaskType.IMPLEMENT`.

**`PlanSpecHandler._build_config`** — update signature and prefer routed:

```python
def _build_config(self, context: RunContext, routed: "RouterResult | None" = None):
    from specweaver.infrastructure.llm.models import GenerationConfig, TaskType
    if routed is not None:
        return GenerationConfig(
            model=routed.model,
            temperature=routed.temperature,   # profile-wins
            max_output_tokens=routed.max_output_tokens,
            task_type=TaskType.PLAN,
        )
    if context.config is not None:
        return GenerationConfig(model=context.config.llm.model, temperature=0.3,
                                max_output_tokens=context.config.llm.max_output_tokens,
                                task_type=TaskType.PLAN)
    return GenerationConfig(model="gemini-3-flash-preview", temperature=0.3,
                            max_output_tokens=4096, task_type=TaskType.PLAN)
```

**`PlanSpecHandler.execute`** — resolve routing and pass to `_build_config`:

```python
routed = (
    context.llm_router.get_for_task(TaskType.PLAN)
    if context.llm_router else None
)
adapter = routed.adapter if routed else context.llm
config = self._build_config(context, routed=routed)
planner = Planner(llm=adapter, config=config, ...)
```

---

### 4. `flow/_review.py` [MODIFY]

Update `_review_config_from_context()`:

```python
def _review_config_from_context(
    context: RunContext,
    routed: "RouterResult | None" = None,   # NEW
) -> GenerationConfig:
    from specweaver.infrastructure.llm.models import GenerationConfig, TaskType

    if routed is not None:
        return GenerationConfig(
            model=routed.model,
            temperature=routed.temperature,   # profile-wins
            max_output_tokens=routed.max_output_tokens,
            task_type=TaskType.REVIEW,
        )
    if context.config is not None:
        return GenerationConfig(model=context.config.llm.model, temperature=0.3,
                                max_output_tokens=context.config.llm.max_output_tokens,
                                task_type=TaskType.REVIEW)
    return GenerationConfig(model="gemini-3-flash-preview", temperature=0.3,
                            max_output_tokens=4096, task_type=TaskType.REVIEW)
```

**`ReviewSpecHandler.execute`** — add routing and pass routed adapter + config:

```python
from specweaver.infrastructure.llm.models import TaskType
routed = (
    context.llm_router.get_for_task(TaskType.REVIEW)
    if context.llm_router else None
)
adapter = routed.adapter if routed else context.llm
reviewer = Reviewer(
    llm=adapter,
    config=_review_config_from_context(context, routed=routed),
    tool_dispatcher=_build_tool_dispatcher(context, role="reviewer"),
)
```

**`ReviewCodeHandler.execute`** — same pattern.

> [!NOTE]
> `_build_tool_dispatcher(context, ...)` still checks `hasattr(context.llm, ...)`.
> `context.llm` remains the default fallback adapter and is always set when the
> pipeline is LLM-enabled — this check is unaffected by routing.

---

### 5. `config/_db_llm_mixin.py` [MODIFY]

Add two methods to `LlmProfilesMixin`:

```python
def unlink_project_profile(self, project_name: str, role: str) -> bool:
    """Remove a project-role → profile link.

    Returns True if a row was deleted, False if no such link existed.
    """
    with self.connect() as conn:
        cursor = conn.execute(
            "DELETE FROM project_llm_links WHERE project_name = ? AND role = ?",
            (project_name, role),
        )
        return cursor.rowcount > 0

def get_project_routing_entries(
    self, project_name: str,
) -> list[dict[str, object]]:
    """Return all routing entries (role LIKE 'task:%') for a project.

    Each dict has keys: role, profile_id, and all llm_profiles columns
    (name, model, provider, temperature, max_output_tokens, response_format).
    Returns empty list if no routing is configured.
    """
    with self.connect() as conn:
        rows = conn.execute(
            """
            SELECT pll.role, p.*
            FROM project_llm_links pll
            JOIN llm_profiles p ON p.id = pll.profile_id
            WHERE pll.project_name = ? AND pll.role LIKE 'task:%'
            ORDER BY pll.role
            """,
            (project_name,),
        ).fetchall()
        return [dict(r) for r in rows]
```

---

### 6. `cli/pipelines.py` [MODIFY]

**In `_execute_run()` — after the LLM wiring block (lines 241–250), add routing:**

```python
# Wire up ModelRouter if LLM was successfully configured
if context.llm is not None:
    try:
        from specweaver.infrastructure.llm.router import ModelRouter
        db = _core.get_db()
        active = db.get_active_project()
        if active:
            context.llm_router = ModelRouter(
                db, active, telemetry_project=active,
            )
    except Exception:
        pass  # Routing is optional — never block pipeline startup
```

**In `resume()` — after the `RunContext(...)` block (line 379), add the same pattern:**

```python
# Wire up LLM + router for resume (mirrors _execute_run)
try:
    _, adapter, _ = _helpers._require_llm_adapter(project_path)
    context.llm = adapter
    from specweaver.infrastructure.llm.router import ModelRouter
    db = _core.get_db()
    active = db.get_active_project()
    if active:
        context.llm_router = ModelRouter(db, active, telemetry_project=active)
except Exception:
    _core.console.print(
        "[yellow]Warning:[/yellow] No LLM configured. LLM-dependent steps will fail.",
    )
```

> [!NOTE]
> The `resume` command currently doesn't wire up the LLM at all (pre-existing gap).
> We fix this as part of SF-1 because adding routing without the LLM would be
> meaningless in resumed runs.

---

### 7. `flow/_lint_fix.py` [MODIFY]

**Architectural outcome: after this change, every handler in the codebase uses the
unified `generate(messages: list[Message], config: GenerationConfig)` interface.
No raw string paths remain.**

Two changes:

**A — Add `context: RunContext` parameter to `_llm_fix()`** (propagated from `execute()`):

```python
# In execute(), change call site:
await self._llm_fix(
    context.llm,
    code_files[0],
    lint_result.exports.get("errors", []) if lint_result.exports else [],
    context=context,   # NEW
)
```

**B — Rewrite `_llm_fix()` to use the standard interface + routing:**

```python
async def _llm_fix(
    self,
    llm: Any,
    code_path: Path,
    lint_errors: list[dict[str, object]],
    *,
    context: RunContext,         # NEW
) -> None:
    """Ask the LLM to fix lint errors in the given file."""
    from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role, TaskType

    code = code_path.read_text(encoding="utf-8")
    error_summary = "\n".join(
        f"- {e.get('file', '?')}:{e.get('line', '?')} [{e.get('code', '?')}] {e.get('message', '')}"
        for e in lint_errors
    )
    prompt = (
        f"Fix the following lint errors in this Python file.\n\n"
        f"## Lint Errors\n{error_summary}\n\n"
        f"## Current Code\n```python\n{code}\n```\n\n"
        f"Return ONLY the fixed Python code, no explanations."
    )

    messages = [Message(role=Role.USER, content=prompt)]

    # Base config from project default (fallback)
    if context.config is not None:
        base_config = GenerationConfig(
            model=context.config.llm.model,
            temperature=0.1,    # low creativity — fix, not invent
            max_output_tokens=context.config.llm.max_output_tokens,
            task_type=TaskType.CHECK,
        )
    else:
        base_config = GenerationConfig(
            model="gemini-3-flash-preview",
            temperature=0.1,
            max_output_tokens=4096,
            task_type=TaskType.CHECK,
        )

    # Routing resolution — same pattern as all other handlers
    routed = (
        context.llm_router.get_for_task(TaskType.CHECK)
        if context.llm_router else None
    )
    adapter = routed.adapter if routed else llm
    config = GenerationConfig(
        model=routed.model,
        temperature=routed.temperature,
        max_output_tokens=routed.max_output_tokens,
        task_type=TaskType.CHECK,
    ) if routed else base_config

    response = await adapter.generate(messages, config)   # unified interface
    fixed_code = response.text.strip()
    if fixed_code.startswith("```"):
        lines = fixed_code.split("\n")
        lines = [line for line in lines if not line.startswith("```")]
        fixed_code = "\n".join(lines)
    code_path.write_text(fixed_code + "\n", encoding="utf-8")
```

> [!NOTE]
> `temperature=0.1` is the handler default for lint fixing (**profile-wins** applies:
> if a routing entry for `TaskType.CHECK` is configured, `routed.temperature` is
> used instead). This is the same profile-wins rule as all other handlers.

> [!CAUTION]
> The existing `LintFixHandler` tests that mock `context.llm.generate()` will need
> updating: they must pass `(messages, config)` not a raw string. Check
> `tests/unit/flow/` for existing `LintFixHandler` tests before writing new ones.

---

### 8. `llm/models.py` [MODIFY]

Update `TaskType` docstring — it is now both a telemetry label **and** a routing key:

```python
class TaskType(enum.StrEnum):
    """Classification of an LLM call's purpose.

    Used by:
    - ``TelemetryCollector``: labels each UsageRecord with the call's task type.
    - ``ModelRouter`` (3.12b): serves as the routing key for per-task LLM profile
      resolution. Configure a routing entry for a task type to use a different
      model or temperature than the project default.

    Does NOT affect generation behavior directly — adapters do not inspect this
    field. It is read by the router and telemetry layers only.
    """
```

---

## `llm/context.yaml` [MODIFY]

Add `ModelRouter` and `RouterResult` to the `exposes` list:

```yaml
exposes:
  - LLMAdapter
  - GeminiAdapter
  - LLMResponse
  - LLMError
  - PromptBuilder
  - TaskType
  - TelemetryCollector
  - UsageRecord
  - ModelRouter      # NEW (3.12b)
  - RouterResult     # NEW (3.12b)
```

---

## Tests

New test file: `tests/unit/llm/test_router.py`

### Test scenarios:

```
TestRouterResult
  test_is_namedtuple            — RouterResult has required fields
  test_adapter_field            — adapter is accessible

TestModelRouterGetForTask
  test_returns_none_when_no_entry          — no "task:review" in DB → None
  test_returns_router_result_when_entry    — entry exists → RouterResult with correct model
  test_caches_adapter_by_provider_key      — two calls, same provider → same adapter instance
  test_different_models_same_provider      — gemini-flash + gemini-pro → same adapter, different models
  test_different_providers_different_adapters — gemini + anthropic → different instances
  test_fallback_on_load_settings_value_error — ValueError from load_settings → None, no raise
  test_fallback_on_adapter_creation_error  — adapter_cls raises → None, no raise
  test_telemetry_wrapping                  — telemetry_project set → CollectorWrapper around adapter
  test_no_telemetry_wrapping               — telemetry_project=None → raw adapter

TestModelRouterIntegration (with real in-memory DB)
  test_route_set_and_resolved    — link_project_profile + get_for_task round-trip

TestHandlerRouting (uses MockRouter)
  test_generate_code_uses_routed_adapter        — GenerateCodeHandler uses routed adapter/model
  test_generate_code_uses_routed_temperature     — GenerateCodeHandler uses routed.temperature (not handler default)
  test_generate_code_falls_back_no_router        — no llm_router → context.llm + default temp used
  test_plan_spec_uses_routed_adapter             — PlanSpecHandler uses routed adapter/model
  test_plan_spec_uses_routed_temperature         — PlanSpecHandler uses routed.temperature
  test_review_spec_uses_routed_adapter           — ReviewSpecHandler uses routed adapter/model
  test_review_spec_uses_routed_temperature       — ReviewSpecHandler uses routed.temperature
  test_review_code_uses_routed_adapter           — ReviewCodeHandler uses routed adapter/model
  test_same_model_different_temps_per_task_type  — gemini-pro at 0.5 (plan) and 0.2 (review) in same pipeline
  test_lint_fix_uses_routed_adapter              — LintFixHandler uses routed adapter/model for CHECK
  test_lint_fix_uses_routed_temperature          — LintFixHandler uses routed.temperature (not 0.1 default)
  test_lint_fix_falls_back_no_router             — no llm_router → context.llm + default temp
  test_lint_fix_calls_generate_with_messages     — generate() receives list[Message] not raw str (regression guard)

TestLintFixHandlerInterface (existing or new file tests/unit/flow/test_lint_fix.py)
  test_llm_fix_uses_generate_with_messages_config  — generate(messages, config) called, not generate(str)
  test_llm_fix_task_type_is_check                  — config.task_type == TaskType.CHECK
  test_llm_fix_temperature_default                 — no routing → temperature=0.1

TestDbLlmMixin (existing file — add cases)
  test_unlink_project_profile_existing     — returns True, row deleted
  test_unlink_project_profile_nonexistent  — returns False, no error
  test_get_project_routing_entries_empty   — no task: rows → []
  test_get_project_routing_entries_returns — two task: rows → correct dicts
  test_get_project_routing_entries_excludes_non_task — "review" row not included
```

> [!CAUTION]
> Do NOT use real LLM calls in any test. All adapters must be mocked via
> `unittest.mock.MagicMock` or `AsyncMock`. The router tests use a real
> in-memory SQLite DB (following the pattern in `test_factory.py`).

---

## Verification Plan

All commands run from `c:\development\pitbula\specweaver`.

```bash
# Run new router tests
python -m pytest tests/unit/llm/test_router.py -v --tb=short

# Run full test suite to confirm no regressions
python -m pytest --tb=short -q

# Lint
ruff check src/ tests/

# Type-check (mypy or pyright — check pyproject.toml for which is used)
python -m mypy src/specweaver/llm/router.py src/specweaver/flow/_base.py
```

Expected outcome: all tests pass, no new lint errors, no circular imports introduced.

---

## Dependency Graph

```
llm/router.py
  ├── consumes: config/ (load_settings, Database)  ✅ allowed
  ├── consumes: llm/adapters/ (get_adapter_class)  ✅ same module group
  ├── consumes: llm/collector.py (TelemetryCollector) ✅ same module
  └── forbids: loom/*  ✅ not imported

flow/_base.py (RunContext + llm_router field)
  └── no new imports — `Any` type annotation

flow/_generation.py, flow/_review.py
  ├── consumes: llm/router.py (RouterResult) — TYPE_CHECKING only ✅
  └── no new runtime imports

cli/pipelines.py
  └── consumes: llm/router.py (ModelRouter) — lazy import ✅
```

**No circular imports.** `llm/router.py` does not import from `flow/`.
Handlers import `RouterResult` under `TYPE_CHECKING` only (no runtime cost).

---

## Backlog (not in this SF)

- `profile_name` field of `RouterResult` is always `""` — populate it from the DB
  profile name for richer logging (low priority, SF-2 can add it)
- `sw resume` LLM wiring was missing before this SF — document the fix in release notes
