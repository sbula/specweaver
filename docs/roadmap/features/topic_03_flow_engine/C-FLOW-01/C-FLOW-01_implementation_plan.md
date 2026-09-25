# C-FLOW-01 — Token & Cost Telemetry (implementation plan)

**Feature**: 3.12 · **Audit**: completed 2026-03-27 — all questions resolved across 2 audit passes ·
Analysis: [LLM Routing & Cost Optimization](../../analysis/llm_routing_and_cost_analysis.md)

## Goal

Log token usage and estimated cost for **every** LLM call (pipeline, CLI, API), persist it in the
project database, and show it in the CLI. Foundation for the cost features downstream: 3.12a
multi-provider, 3.12b static routing, 4.5a cost analytics.

**Since moved** (checked 2026-09-25): `llm/` now lives at `src/specweaver/infrastructure/llm/`
(`collector.py`, `telemetry.py`, `factory.py`; the usage table in `store.py`), `flow/` at
`src/specweaver/core/flow/`; usage commands are registered in `interfaces/cli/main.py`. Paths below
are as of the plan's date.

## Design: `TelemetryCollector` is a decorator

A **decorator** wraps any `LLMAdapter`, so every LLM call — pipeline, direct CLI, REST API — passes
one collection point. It is **not** a subclass of `LLMAdapter`; it delegates every call to the
wrapped adapter. This works because `RunContext.llm` is typed `Any` (duck typing).

Each `generate()`, `generate_with_tools()` or `generate_stream()` call produces one `UsageRecord`,
one DB row. A draft → review → implement pipeline produces 3 records, each with its `task_type`
read from `config.task_type`.

```
                  ┌─────────────────────────┐
                  │  TelemetryCollector      │  ← decorator, wraps ANY adapter
                  │  ┌───────────────────┐   │
caller ──────────►│  │  LLMAdapter impl   │   │──── LLM API
(handler/CLI/API) │  │  (Gemini/Claude/..)│   │
                  │  └───────────────────┘   │
                  │                           │
                  │  records: [UsageRecord]    │  ← one per call, accumulates in memory
                  └─────────────────────────┘
                            │
                            ▼ caller calls collector.flush(db)
                         SQLite (one row per record)
```

## Changes

### 1. `llm/` — models, telemetry, collector

1. **`src/specweaver/llm/models.py`** [MODIFY] — `TaskType` enum and a `task_type` field on
   `GenerationConfig`. Metadata only; does not affect generation. Each handler's config helper sets
   it (§1a).

```python
class TaskType(enum.StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    PLAN = "plan"
    IMPLEMENT = "implement"
    VALIDATE = "validate"
    CHECK = "check"
    UNKNOWN = "unknown"

class GenerationConfig(BaseModel):
    ...
    task_type: TaskType = TaskType.UNKNOWN
```

2. **`src/specweaver/llm/telemetry.py`** [NEW] — pure logic, no I/O, no DB access:
   - `CostEntry` — `NamedTuple(input_cost_per_1k: float, output_cost_per_1k: float)`
   - `DEFAULT_COST_TABLE: dict[str, CostEntry]` — built-in fallback prices.
   - `estimate_cost(model: str, usage: TokenUsage, overrides: dict[str, CostEntry] | None = None) -> float`
     — looks in `overrides` first, then `DEFAULT_COST_TABLE`; `0.0` for unknown models. The caller
     loads `overrides` from the DB, which keeps this module pure.
   - `UsageRecord` Pydantic model: `timestamp`, `project_name`, `task_type`, `model`, `provider`,
     `prompt_tokens`, `completion_tokens`, `total_tokens`, `estimated_cost_usd`, `duration_ms`
   - `create_usage_record(config: GenerationConfig, response: LLMResponse, provider: str, project: str, duration_ms: int, cost_overrides: dict | None = None) -> UsageRecord`
3. **`src/specweaver/llm/context.yaml`** [MODIFY] — add `TelemetryCollector`, `UsageRecord` and
   `TaskType` to `exposes`; `flow/` and `cli/` consume them.
4. **`src/specweaver/llm/collector.py`** [NEW] — `TelemetryCollector`:

```python
class TelemetryCollector:
    """Decorator that wraps an LLMAdapter and captures usage telemetry.

    NOT a subclass of LLMAdapter — uses duck typing (RunContext.llm is Any).
    Each generate/generate_with_tools/generate_stream call creates one
    UsageRecord. Records accumulate in memory until flush(db) is called.
    """

    def __init__(self, adapter: LLMAdapter, project: str, cost_overrides: dict | None = None):
        self._adapter = adapter
        self._project = project
        self._cost_overrides = cost_overrides
        self._records: list[UsageRecord] = []

    # --- Generation proxies (telemetry captured per call) ---

    async def generate(self, messages, config) -> LLMResponse:
        start = time.monotonic()
        response = await self._adapter.generate(messages, config)
        self._capture(config, response, time.monotonic() - start)
        return response

    async def generate_with_tools(self, messages, config, tool_executor, on_tool_round=None) -> LLMResponse:
        start = time.monotonic()
        response = await self._adapter.generate_with_tools(
            messages, config, tool_executor, on_tool_round
        )
        self._capture(config, response, time.monotonic() - start)
        return response

    async def generate_stream(self, messages, config) -> AsyncIterator[str]:
        """Proxy streaming — yields chunks, captures telemetry from final chunk metadata."""
        start = time.monotonic()
        total_text = []
        async for chunk in self._adapter.generate_stream(messages, config):
            total_text.append(chunk)
            yield chunk
        # After stream is fully consumed, build a synthetic LLMResponse for telemetry.
        # Token estimate from accumulated text (adapters may provide exact counts
        # in final chunk metadata — adapter-specific enhancement for later).
        elapsed = time.monotonic() - start
        estimated_output_tokens = self._adapter.estimate_tokens("".join(total_text))
        synthetic_usage = TokenUsage(
            prompt_tokens=0,  # Not available from streaming without adapter support
            completion_tokens=estimated_output_tokens,
            total_tokens=estimated_output_tokens,
        )
        synthetic_response = LLMResponse(
            text="", model=config.model, usage=synthetic_usage
        )
        self._capture(config, synthetic_response, elapsed)

    # --- Record capture ---

    def _capture(self, config, response, elapsed):
        """Create a UsageRecord from the config and response.
        task_type is read from config.task_type (set per call by each handler),
        NOT from the constructor."""
        self._records.append(create_usage_record(
            config, response, self._adapter.provider_name,
            self._project, int(elapsed * 1000),
            cost_overrides=self._cost_overrides,
        ))

    # --- Persistence ---

    @property
    def records(self) -> list[UsageRecord]:
        return list(self._records)

    def flush(self, db) -> int:
        """Persist all records to DB. Returns count.
        Never raises — telemetry failures are logged, not propagated."""
        count = len(self._records)
        try:
            for r in self._records:
                db.log_usage(r.model_dump())
            self._records.clear()
        except Exception:
            logger.warning("Failed to flush %d telemetry records", count, exc_info=True)
        return count

    # --- Delegate remaining LLMAdapter interface ---

    @property
    def provider_name(self) -> str:
        return self._adapter.provider_name

    def available(self) -> bool:
        return self._adapter.available()

    async def count_tokens(self, text, model) -> int:
        return await self._adapter.count_tokens(text, model)

    def estimate_tokens(self, text) -> int:
        return self._adapter.estimate_tokens(text)
```

Rules:

- **task_type** comes from `config.task_type` per call, not from the constructor. Each handler sets
  `config.task_type` when it builds its `GenerationConfig`, so multi-step pipelines label records
  correctly.
- **Streaming**: `generate_stream` captures timing and estimates output tokens from the concatenated
  text. `prompt_tokens` is `0` for streaming — a known gap; exact counts need adapter support
  (backlog).
- **Duration** is wall-clock, including tool execution for `generate_with_tools`. API-only timing is
  backlog.

### 1a. `flow/` — config helpers set `task_type`

The existing helpers build `GenerationConfig` without `task_type`. One-line additions only; no
telemetry logic in handlers — the collector captures everything.

- `src/specweaver/flow/_review.py` — `_review_config_from_context()` → `task_type=TaskType.REVIEW`:

```python
def _review_config_from_context(context: RunContext) -> GenerationConfig:
    from specweaver.infrastructure.llm.models import GenerationConfig, TaskType
    ...
    return GenerationConfig(
        model=..., temperature=0.3, max_output_tokens=...,
        task_type=TaskType.REVIEW,  # ← NEW
    )
```

- `src/specweaver/flow/_generation.py`:
  - `_gen_config_from_context()` takes a `task_type` param, default `TaskType.IMPLEMENT`
  - `GenerateCodeHandler` passes `task_type=TaskType.IMPLEMENT`
  - `GenerateTestsHandler` passes `task_type=TaskType.IMPLEMENT`
  - `PlanSpecHandler._build_config()` → `task_type=TaskType.PLAN`
- `src/specweaver/flow/_draft.py` — if a config helper exists, `task_type=TaskType.DRAFT`.
- `src/specweaver/cli/standards.py` (line 91) — the direct `GenerationConfig()` → add
  `task_type=TaskType.CHECK`.

### 2. `config/` — DB schema and persistence

1. **`src/specweaver/config/_schema.py`** [MODIFY] — `SCHEMA_V9`: tables `llm_usage_log` and
   `llm_cost_overrides`.

```sql
-- Usage telemetry log (one row per LLM call)
CREATE TABLE IF NOT EXISTS llm_usage_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT    NOT NULL,
    project_name      TEXT    NOT NULL,
    task_type         TEXT    NOT NULL,
    model             TEXT    NOT NULL,
    provider          TEXT    NOT NULL DEFAULT '',
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    estimated_cost    REAL    NOT NULL DEFAULT 0.0,
    duration_ms       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_usage_project ON llm_usage_log(project_name);
CREATE INDEX IF NOT EXISTS idx_usage_task_type ON llm_usage_log(task_type);

-- User-configurable cost overrides (overrides built-in DEFAULT_COST_TABLE)
CREATE TABLE IF NOT EXISTS llm_cost_overrides (
    model_pattern      TEXT PRIMARY KEY,
    input_cost_per_1k  REAL NOT NULL,
    output_cost_per_1k REAL NOT NULL,
    updated_at         TEXT NOT NULL
);
```

   No foreign key to `projects`: usage records survive project deletion, for historical analysis.
2. **`src/specweaver/config/database.py`** [MODIFY] — import `SCHEMA_V9`, add the v9 migration in
   `_ensure_schema()`. New methods:
   - `log_usage(record: dict)` — insert one row into `llm_usage_log`
   - `get_usage_summary(project: str | None, since: str | None) -> list[dict]` — aggregation
   - `get_usage_by_task_type(project: str) -> list[dict]` — grouping
   - `get_cost_overrides() -> dict[str, CostEntry]` — load all overrides
   - `set_cost_override(model_pattern, input_cost, output_cost)` — upsert
   - `delete_cost_override(model_pattern)` — remove one override

### 3. Where the collector is created

No change to `RunContext`. The only handler-side change is `task_type` (§1a). The collector wraps
the adapter where the adapter is created.

1. **`src/specweaver/llm/factory.py`** [MODIFY] — return type annotation `GeminiAdapter` → `Any`
   (the collector is a decorator, not a subclass). Add the wrapping:

```python
def create_llm_adapter(
    db, *, llm_role="draft", telemetry_project: str | None = None
) -> tuple[SpecWeaverSettings, Any, GenerationConfig]:
    settings, adapter, gen_config = _create_raw_adapter(db, llm_role=llm_role)
    if telemetry_project:
        cost_overrides = db.get_cost_overrides()
        adapter = TelemetryCollector(adapter, telemetry_project, cost_overrides)
    return settings, adapter, gen_config
```

   Callers that pass `telemetry_project` (CLI commands, pipeline runner, API endpoints) opt in.
   Callers that don't get the raw adapter — zero behavioral change.
2. **`src/specweaver/flow/runner.py`** [MODIFY] — after the pipeline ends (success or failure),
   flush:

```python
if isinstance(context.llm, TelemetryCollector):
    context.llm.flush(db)
```

3. **`src/specweaver/cli/_helpers.py`** [MODIFY] — `get_llm_adapter()` wraps `create_llm_adapter()`
   and passes the active project as `telemetry_project`, so every CLI-created adapter is wrapped.

```python
def get_llm_adapter(db, *, llm_role="draft"):
    project = db.get_active_project()  # already available
    return create_llm_adapter(db, llm_role=llm_role, telemetry_project=project)
```

4. **CLI command files** (`review_commands.py`, `draft_commands.py`, etc.) [MODIFY] — after a
   direct (non-pipeline) LLM operation, call `flush()` in a `finally` block:

```python
try:
    result = await reviewer.review_spec(...)
finally:
    if isinstance(adapter, TelemetryCollector):
        adapter.flush(db)
```

### 4. `cli/` — usage reporting

1. **`src/specweaver/cli/usage_commands.py`** [NEW]
   - `sw usage` — summary for the current project (total tokens, cost, by task type)
   - `sw usage --all` — across all projects
   - `sw usage --since 7d` — time window
   - `sw usage --by-model` — group by model instead of task type

   Output: Rich table — Task Type | Model | Calls | Tokens (In/Out) | Est. Cost
2. **`src/specweaver/cli/cost_commands.py`** [NEW]
   - `sw costs` — current cost table (built-in defaults, user overrides highlighted)
   - `sw costs set <model> <input_cost> <output_cost>` — custom cost per model
   - `sw costs reset <model>` — remove the override, back to built-in
3. **`src/specweaver/cli/__init__.py`** [MODIFY] — register `usage_commands` and `cost_commands` with
   the Typer app.

## Tests

| File | Test | Checks |
|---|---|---|
| `tests/unit/llm/test_telemetry.py` | `test_estimate_cost_known_model` | correct cost for a known model |
| | `test_estimate_cost_unknown_model` | returns 0.0 |
| | `test_estimate_cost_with_override` | overrides dict beats the default |
| | `test_create_usage_record` | all fields populated |
| | `test_task_type_enum` | all task types are valid StrEnum members |
| `tests/unit/llm/test_collector.py` | `test_collector_captures_generate` | one record per generate() call |
| | `test_collector_captures_generate_with_tools` | one record, cumulative usage |
| | `test_collector_captures_generate_stream` | one record, estimated tokens |
| | `test_collector_task_type_from_config` | record uses config.task_type, not the constructor |
| | `test_collector_multiple_calls_multiple_records` | 3 calls → 3 separate records |
| | `test_collector_flush` | records persisted, list cleared |
| | `test_collector_flush_error_handling` | DB error logged, not raised |
| | `test_collector_proxies_all_methods` | available(), count_tokens(), etc. delegate |
| | `test_collector_timing` | duration_ms > 0 |
| `tests/unit/config/test_database.py` | `test_schema_v9_migration` | both tables + indices created |
| | `test_log_usage` | insert and query back |
| | `test_get_usage_summary` | aggregation by project |
| | `test_get_usage_by_task_type` | grouping |
| | `test_cost_overrides_crud` | set, get, delete |
| `tests/integration/flow/` | `test_pipeline_flushes_telemetry` | pipeline with FakeLLM → one record per step in DB |
| | `test_direct_cli_flushes_telemetry` | direct `sw review` → records in DB |
| `tests/unit/cli/test_usage.py` | `test_sw_usage_default` | current project summary |
| | `test_sw_usage_all` | all projects |
| | `test_sw_usage_empty` | graceful output with no records |
| | `test_sw_costs_show` | merged cost table |
| | `test_sw_costs_set` | override persists |
| | `test_sw_costs_reset` | override removed |

Manual:

- `sw draft greet_service` → `sw usage` → token count matches
- `sw review code greet.py` → `sw usage --by-model` → model name appears
- `sw costs set gemini-2.5-pro 0.001 0.002` → `sw costs` → override shown

## Backlog (deferred at audit)

- **API-only timing** — measure only the LLM round-trip, excluding tool execution. Needs adapter
  loop instrumentation. Phase 4 enhancement.
- **Streaming prompt_tokens** — `0` today. Needs adapters to return `usage_metadata` from the final
  streaming chunk.
- **Cost table auto-updater** — agent or web scraper that updates model pricing monthly. Track in
  the roadmap as a future capability.
