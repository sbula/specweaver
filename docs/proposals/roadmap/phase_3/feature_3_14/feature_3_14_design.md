# Design: Static Model Routing (Config-Driven)

- **Feature ID**: feature_3_14
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/proposals/roadmap/phase_3/feature_3_14/feature_3_14_design.md

## Feature Overview

Feature 3.12b adds config-driven static model routing to the SpecWeaver LLM layer.
It solves the problem that every pipeline step today uses the same single adapter
and model, preventing users from manually assigning better-suited or cheaper models
per task type (e.g., `review → claude-3-5-sonnet`, `draft → gemini-3-flash`,
`implement → gemini-3-1-pro`).

The system maps `TaskType` values to named DB LLM profiles. At generation time, each
handler resolves a `RouterResult` (adapter + model + temperature + max_tokens) for
its task type and builds `GenerationConfig` from that — not from the project default.
The default profile remains the fallback when no routing entry exists.

**Explicit**: It does NOT touch adapters, telemetry logic, validation, or pipeline YAML.
**Key constraint**: No AI, no dynamic learning — pure user configuration in SQLite.

### Multi-instance Provider Support

Multiple task types MAY map to the same provider with different models
(e.g., `draft → gemini-3-flash-preview`, `implement → gemini-3-1-pro`).
The `ModelRouter` handles this by caching the **adapter instance** at the
`(provider, api_key_hash)` level — one `GeminiAdapter` instance serves both tasks
because the model name is carried in `GenerationConfig.model`, not the adapter.
Different providers get separate adapter instances (e.g., one `GeminiAdapter`,
one `AnthropicAdapter`).

---

## Research Findings

### Codebase Patterns

- **`TaskType` enum** (`llm/models.py`): `DRAFT`, `REVIEW`, `PLAN`, `IMPLEMENT`,
  `VALIDATE`, `CHECK`, `UNKNOWN`. These string values are the routing keys.
  `TaskType.DRAFT.value == "draft"`, `TaskType.REVIEW.value == "review"`, etc.

- **`GenerationConfig.task_type`** (`llm/models.py`): every handler already stamps
  `task_type` on the config before calling `generate()`. The routing key is present.
  Currently the `model` field is always taken from `context.config.llm.model`
  (the project's default profile). 3.12b changes this so the handler uses
  the model from the routed profile instead.

- **`create_llm_adapter(db, llm_role=...)`** (`llm/factory.py`): accepts a role string,
  loads the matching profile from `project_llm_links`, returns
  `(SpecWeaverSettings, adapter, GenerationConfig)`.
  The routing DB lookup uses this same function with `llm_role="task:<task_type>"`.

- **`load_settings(db, project_name, llm_role=...)`** (`config/settings.py`): resolves
  a profile from `project_llm_links` for `(project_name, llm_role)`. Returns
  `SpecWeaverSettings` with the profile's model, temperature, max_tokens, provider.
  Falls back to `system-default` if no project-specific link exists.
  **3.12b lookup pattern**: `load_settings(db, project, llm_role=f"task:{task_type}")`
  If no row exists for `"task:review"` → `ValueError` is raised by `load_settings`,
  which the router catches and treats as "no routing configured → return None".

- **`project_llm_links`** (DB schema V10): `(project_name TEXT, role TEXT, profile_id INT)`.
  Routing entries use role key `"task:<TaskType.value>"` (e.g., `"task:review"`,
  `"task:implement"`). These are distinct from existing entries `"review"`, `"draft"`,
  `"search"` — no collision.

- **`RunContext`** (`flow/_base.py`): carries `llm: Any` and `config: Any`.
  Adding `llm_router: Any = None` is additive and backward-compatible.
  Handlers check `context.llm_router is not None` and prefer it.

- **Handlers that need updating** (3 files):
  - `flow/_generation.py` — `_gen_config_from_context()`, `GenerateCodeHandler`,
    `GenerateTestsHandler`, `PlanSpecHandler._build_config()`
  - `flow/_review.py` — `ReviewSpecHandler`, `ReviewCodeHandler`
  - `flow/_draft.py` — `DraftSpecHandler`

- **`TelemetryCollector`** (`llm/collector.py`): wraps an adapter to capture usage.
  The `ModelRouter` wraps each newly-created adapter in a `TelemetryCollector`
  at cache-fill time if `telemetry_project` is set. Cached adapter instances are
  already wrapped — no re-wrapping on subsequent calls.

- **DB schema unchanged** — No migration needed. Routing uses existing
  `project_llm_links` table with namespaced role keys.

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| None — pure internal | — | — | — |

### Blueprint References

- `llm_routing_and_cost_analysis.md` §4.3.12b: "Config schema + router lookup in handlers"
- `llm/factory.py` (3.12): telemetry-wrapped adapter creation pattern to reuse
- `project_llm_links` + `load_settings()` pattern (settings.py)

---

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Config mapping | User | Links a named LLM profile to a `TaskType` via CLI or API | Row inserted in `project_llm_links` with `role = "task:<task_type>"` |
| FR-2 | Per-step resolution | System | At LLM call time, resolves adapter **and model** using the step's `task_type` | Returns `RouterResult(adapter, model, temperature, max_tokens)` matching the linked profile; handler builds `GenerationConfig` from this |
| FR-3 | Transparent fallback | System | `task_type` has no routing entry in DB | `ModelRouter` returns `None`; handler falls back to `context.llm` + `context.config.llm.model` (pre-3.12b behavior) |
| FR-4 | CLI surface | User | `sw config routing set <task_type> <profile_name>` / `show` / `clear [task_type]` | DB updated; table displayed; confirmation printed |
| FR-5 | DB persistence | System | Routing config survives restarts | `project_llm_links` rows with `"task:"` prefix survive; readable on next `ModelRouter` call |
| FR-6 | Telemetry preserved | System | Routed adapter is wrapped in `TelemetryCollector` when telemetry is active | `UsageRecord.task_type` correctly set; `flush()` called at pipeline end |
| FR-7 | Same-provider multi-model | System | Two task types use same provider, different models (e.g. gemini-flash + gemini-pro) | One shared adapter instance per `(provider, api_key)` used for both; `GenerationConfig.model` differs between calls |

---

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Backward compatibility | Zero behavior change for projects with no routing config in DB |
| NFR-2 | Adapter caching | `ModelRouter` caches adapter instances by `f"{provider}:{hash(api_key)}"`. No new adapter creation on second call for same provider+key |
| NFR-2b | Temperature resolution | **Profile-wins**: when a routing entry is active, `RouterResult.temperature` is used verbatim. Same model at different temperatures per task type (e.g. `gemini-3.1-pro` at `0.5` for spec writing, `0.2` for review) is explicitly supported. Handler-default temperatures apply only in the no-routing fallback path. |
| NFR-3 | Error handling | Profile not found in DB → log `WARNING "[routing] no entry for task_type=review, using default"` → return `None`. No exception propagated. |
| NFR-4 | Observability | Routing resolution logged at `DEBUG`: `"[routing] task_type=review → profile=claude-profile (provider=anthropic, model=claude-3-5-sonnet)"` |
| NFR-5 | DB compatibility | No schema migration required |

---

## Architectural Decisions

### AD-1: New `llm/router.py` (adapter archetype)

Place the `ModelRouter` class in `llm/`. The `llm/` module's archetype is `adapter`
(wraps external services). `ModelRouter` wraps the factory + adapter creation logic.
It consumes `config/` (DB + settings) which `llm/` is already allowed to do.
It forbids `loom/*` — the router never touches tools or atoms.

### AD-2: `RouterResult` NamedTuple

The handler needs adapter **and** model/temperature/max_tokens to build the correct
`GenerationConfig`. Returning just the adapter is insufficient because `GenerationConfig.model`
would still be the default project model.

```python
# llm/router.py
from typing import NamedTuple

class RouterResult(NamedTuple):
    adapter: Any          # LLMAdapter or TelemetryCollector
    model: str
    temperature: float
    max_output_tokens: int
    provider: str         # for logging / diagnostics
    profile_name: str     # for logging / diagnostics
```

### AD-3: `ModelRouter` class contract

```python
# llm/router.py
class ModelRouter:
    """Resolves the correct LLM adapter + settings per TaskType.

    Created once per pipeline run by the CLI/API layer.
    Injected into RunContext.llm_router.
    Caches adapter instances by (provider, api_key_hash).
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

    def get_for_task(self, task_type: "TaskType") -> "RouterResult | None":
        """Return RouterResult for the given task_type, or None if no routing configured.

        Returns None → caller falls back to context.llm + context.config.llm.model.
        Never raises — all exceptions are caught and logged.
        """
        ...
```

**Internal logic of `get_for_task`:**

```python
role_key = f"task:{task_type.value}"  # e.g. "task:review"

try:
    settings = load_settings(self._db, self._project_name, llm_role=role_key)
except ValueError:
    # No routing entry for this task_type → return None (caller uses default)
    logger.debug("[routing] no entry for task_type=%s, using default", task_type.value)
    return None
except Exception:
    logger.warning("[routing] lookup failed for task_type=%s", task_type.value, exc_info=True)
    return None

cache_key = f"{settings.llm.provider}:{hash(settings.llm.api_key)}"
if cache_key not in self._cache:
    adapter_cls = get_adapter_class(settings.llm.provider)
    adapter = adapter_cls(api_key=settings.llm.api_key or None)
    if self._telemetry_project:
        adapter = TelemetryCollector(adapter, self._telemetry_project)
    self._cache[cache_key] = adapter

adapter = self._cache[cache_key]
logger.debug(
    "[routing] task_type=%s → profile (provider=%s, model=%s)",
    task_type.value, settings.llm.provider, settings.llm.model,
)
return RouterResult(
    adapter=adapter,
    model=settings.llm.model,
    temperature=settings.llm.temperature,
    max_output_tokens=settings.llm.max_output_tokens,
    provider=settings.llm.provider,
    profile_name="",  # populated from DB row name if needed
)
```

### AD-4: Handler integration pattern

Each handler that calls `context.llm` for generation is updated to:

```python
# Resolve routing (new pattern, same for all 3 handler files)
routed = context.llm_router.get_for_task(task_type) if context.llm_router else None
adapter = routed.adapter if routed else context.llm
config = GenerationConfig(
    model=routed.model if routed else context.config.llm.model,
    temperature=routed.temperature if routed else <handler_default_temperature>,
    max_output_tokens=routed.max_output_tokens if routed else context.config.llm.max_output_tokens,
    task_type=task_type,
)
```

The existing helpers `_gen_config_from_context()` (in `_generation.py`) and
`_build_config()` (in `PlanSpecHandler`) are updated to accept an optional
`RouterResult` and prefer it over `context.config`.

### AD-5: `ModelRouter` creation in CLI layer

`ModelRouter` is created in the CLI where `RunContext` is assembled, alongside
`create_llm_adapter()`. It receives the same `db`, `project_name`, and
`telemetry_project` parameters. It is injected into `RunContext.llm_router`.

```python
# cli/_helpers.py (or equivalent, wherever RunContext is built)
router = ModelRouter(db, active_project, telemetry_project=project_name)
context = RunContext(
    ...,
    llm=adapter,          # existing default adapter (fallback)
    llm_router=router,    # new: per-task routing
)
```

### AD-6: Reuse `project_llm_links` with `"task:"` namespace

Role key format: `f"task:{task_type_value}"` where `task_type_value` is
the `.value` of `TaskType` enum (lowercase string: `"draft"`, `"review"`, etc.).
Examples: `"task:review"`, `"task:implement"`, `"task:plan"`.
These are lexicographically distinct from existing roles `"draft"`, `"review"`,
`"search"` — no collision. No DB migration needed.

**DB query agent must write** (in `_db_llm_mixin.py` or by calling `load_settings`):
```python
# To store a routing entry:
db.link_project_profile(project_name, f"task:{task_type}", profile_id)
# To read a routing entry (via existing load_settings):
settings = load_settings(db, project_name, llm_role=f"task:{task_type}")
# To delete a routing entry:
db.unlink_project_profile(project_name, f"task:{task_type}")  # NEW method needed
# To list all routing entries:
db.get_project_routing_entries(project_name)  # NEW method needed — SELECT WHERE role LIKE "task:%"
```

Note: `unlink_project_profile` and `get_project_routing_entries` are new DB methods
to be added to `_db_llm_mixin.py` as part of SF-1.

### AD-7: Unified LLM call interface — `generate(messages, config)` everywhere

Prior to 3.12b, `LintFixHandler._llm_fix()` called `llm.generate(prompt)` with a raw
string — bypassing `GenerationConfig` entirely. This is a **latent bug**: it fails at
runtime when telemetry is active (`TelemetryCollector.generate()` requires both
`messages: list[Message]` and `config: GenerationConfig`).

SF-1 refactors `_llm_fix()` to use the standard interface:
```
generate(messages: list[Message], config: GenerationConfig) → LLMResponse
```

**After SF-1, this is the single unified LLM call interface for all handlers.**
No handler passes a raw string to `generate()`. The interface is defined in
`LLMAdapter` (abstract base) and respected by all adapters and `TelemetryCollector`.
This unification is a pre-condition for routing to work uniformly across all task types.

---

## CLI Command Specification (SF-2)

All commands operate on the **active project**.

```
sw config routing set <task_type> <profile_name>
```
- `<task_type>`: one of `draft`, `review`, `plan`, `implement`, `validate`, `check`
- `<profile_name>`: name of an existing LLM profile in DB
- Effect: insert/replace `project_llm_links` row `(active_project, "task:<task_type>", profile_id)`
- Error if profile name not found: print error, exit non-zero

```
sw config routing show
```
- Print table of all routing entries for active project
- Columns: `Task Type | Profile | Provider | Model | Temperature`
- If no routing configured: print "No routing configured. All tasks use the default profile."

```
sw config routing clear [<task_type>]
```
- Without `<task_type>`: clears all `"task:*"` routing entries for active project
- With `<task_type>`: clears only that one entry
- Confirmation: "Cleared routing for review." / "Cleared all routing entries."

Command group: `sw config routing <subcommand>` — implement as a Typer sub-application
added to `cli/config_commands.py`, following the pattern of existing command groups.

---

## Sub-Feature Breakdown

### SF-1: ModelRouter + DB + Handler Integration

**Scope**: The data model and routing engine.
- New file: `llm/router.py` — `RouterResult` NamedTuple + `ModelRouter` class
- Modified: `flow/_base.py` — add `llm_router: Any = None` to `RunContext`
- Modified: `flow/_generation.py` — update `_gen_config_from_context()` +
  `PlanSpecHandler._build_config()` to accept and prefer `RouterResult`
- Modified: `flow/_review.py` — update `ReviewSpecHandler`, `ReviewCodeHandler`
- Modified: `flow/_draft.py` — update `DraftSpecHandler`
- Modified: `config/_db_llm_mixin.py` — add `unlink_project_profile()` and
  `get_project_routing_entries()` methods
- Modified: CLI entry point (wherever `RunContext` is assembled) — create
  `ModelRouter` and inject into `RunContext.llm_router`

**FRs**: FR-1 (DB write), FR-2 (resolution + RouterResult), FR-3 (fallback),
FR-5 (persistence), FR-6 (telemetry), FR-7 (multi-model)

**Inputs**:
- `Database` instance with `project_llm_links` rows (written by CLI or test fixtures)
- Active project name
- `RunContext` (standard pipeline context)
- `task_type: TaskType` passed by each handler

**Outputs**:
- `RouterResult | None` per `get_for_task()` call
- All existing tests pass unchanged (fallback path exercised when `llm_router=None`)
- New unit tests: `tests/unit/llm/test_router.py`

**Depends on**: none
**Impl Plan**: `docs/proposals/roadmap/phase_3/feature_3_14/feature_3_14_sf1_implementation_plan.md`

---

### SF-2: CLI Routing Commands

**Scope**: The user-facing `sw config routing` command group.
- Modified: `cli/config_commands.py` — add `routing_app` Typer sub-application with
  `set`, `show`, `clear` subcommands

**FRs**: FR-4

**Inputs**: SF-1's `unlink_project_profile()` and `get_project_routing_entries()` DB methods

**Outputs**:
- `sw config routing set implement claude-profile` → inserts DB row, prints confirmation
- `sw config routing show` → prints routing table for active project
- `sw config routing clear [task_type]` → removes row(s), prints confirmation
- New unit tests: `tests/unit/cli/test_config_routing_commands.py`

**Depends on**: SF-1 (needs the two new DB methods)
**Impl Plan**: `docs/proposals/roadmap/phase_3/feature_3_14/feature_3_14_sf2_implementation_plan.md`

---

## Dependency Graph

```
SF-1 (ModelRouter + DB + handlers)
  └──▶ SF-2 (CLI commands)
```

Topological execution order: SF-1, then SF-2. Linear — no parallelism.

---

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | ModelRouter + DB + handler integration | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | CLI routing commands | SF-1 | ✅ | ✅ | ✅ | ✅ | ⬜ |

---

## Session Handoff

**Current status**: SF-2 Pre-Commit complete. Ready for Commit Boundary.
**Next step**: Run `/dev docs/proposals/roadmap/phase_3/feature_3_14/feature_3_14_sf2_implementation_plan.md`
**If resuming mid-feature**: Read Progress Tracker. Find first ⬜ in the Dev/Pre-Commit/Committed columns.
