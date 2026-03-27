# Feature 3.12 Implementation Plan: Token & Cost Telemetry

> **Analysis**: [LLM Routing & Cost Optimization](../../analysis/llm_routing_and_cost_analysis.md)
> **Audit**: Completed 2026-03-27 — all questions resolved across 2 audit passes

The goal of this feature is to log token usage and estimated cost for **every** LLM call (pipeline, CLI, API), persist the data in the project database, and expose it via CLI. This is the foundation for all downstream cost optimization features (3.12a multi-provider, 3.12b static routing, 4.5a cost analytics).

## Key Design Decision: TelemetryCollector (Decorator Pattern)

All telemetry is captured at the adapter level via a **decorator** that wraps any `LLMAdapter`. This guarantees a single collection point for ALL LLM calls regardless of caller (pipeline, direct CLI, REST API). The collector is **not** a subclass of `LLMAdapter` — it uses the decorator pattern and delegates all calls to the wrapped adapter. This works because `RunContext.llm` is typed `Any` (duck typing).

Each call to `generate()`, `generate_with_tools()`, or `generate_stream()` produces one `UsageRecord` — stored as an individual row in the DB. A pipeline that runs draft → review → implement produces 3 separate records, each with the correct `task_type` read from `config.task_type`.

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

## Proposed Changes

---

### 1. `llm/` — Models, Telemetry, and Collector

#### [MODIFY] [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/models.py)

Add `TaskType` enum and a `task_type` field to `GenerationConfig`:

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

Purely metadata — does not affect generation. Each handler's config helper function sets the correct task type (see Section 1a).

#### [NEW] [telemetry.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/telemetry.py)

Pure-logic module (no I/O, no DB access) providing:

- `CostEntry` — `NamedTuple(input_cost_per_1k: float, output_cost_per_1k: float)`
- `DEFAULT_COST_TABLE: dict[str, CostEntry]` — built-in fallback prices, shipped with sensible defaults.
- `estimate_cost(model: str, usage: TokenUsage, overrides: dict[str, CostEntry] | None = None) -> float` — looks up model in `overrides` first, then `DEFAULT_COST_TABLE`. Returns `0.0` for unknown models. The `overrides` parameter is loaded from DB by the caller, keeping this module pure.
- `UsageRecord` Pydantic model: `timestamp`, `project_name`, `task_type`, `model`, `provider`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `estimated_cost_usd`, `duration_ms`
- `create_usage_record(config: GenerationConfig, response: LLMResponse, provider: str, project: str, duration_ms: int, cost_overrides: dict | None = None) -> UsageRecord`

#### [MODIFY] [context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/llm/context.yaml)

Add `TelemetryCollector`, `UsageRecord`, and `TaskType` to `exposes` list — they are consumed by `flow/` and `cli/`.

#### [NEW] [collector.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/collector.py)

**TelemetryCollector** — decorator (not a subclass) that wraps any `LLMAdapter`:

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

> [!NOTE]
> **task_type**: Read from `config.task_type` per call, not from the constructor. Each handler sets `config.task_type` when creating its `GenerationConfig`, so multi-step pipelines produce correctly labeled records.

> [!NOTE]
> **Streaming telemetry**: `generate_stream` captures timing and estimates output tokens from concatenated text. Exact token counts require adapter-level support (deferred to backlog). `prompt_tokens` is `0` for streaming — this is a known gap.

> [!NOTE]
> **Duration**: Measures wall-clock time (includes tool execution for `generate_with_tools`). Adapter-level API-only timing is deferred — see backlog.

---

### 1a. `flow/` — Config Helpers: Set `task_type`

Existing config helper functions build `GenerationConfig` without `task_type`. Each must add it:

#### [MODIFY] [_review.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/_review.py)

`_review_config_from_context()` → add `task_type=TaskType.REVIEW`

```python
def _review_config_from_context(context: RunContext) -> GenerationConfig:
    from specweaver.llm.models import GenerationConfig, TaskType
    ...
    return GenerationConfig(
        model=..., temperature=0.3, max_output_tokens=...,
        task_type=TaskType.REVIEW,  # ← NEW
    )
```

#### [MODIFY] [_generation.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/_generation.py)

- `_gen_config_from_context()` → accepts `task_type` param, defaults to `TaskType.IMPLEMENT`
- `GenerateCodeHandler` passes `task_type=TaskType.IMPLEMENT`
- `GenerateTestsHandler` passes `task_type=TaskType.IMPLEMENT`
- `PlanSpecHandler._build_config()` → add `task_type=TaskType.PLAN`

#### [MODIFY] [_draft.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/_draft.py)

If a config helper exists here, add `task_type=TaskType.DRAFT`.

#### [MODIFY] [standards.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/standards.py) (line 91)

Direct `GenerationConfig()` creation → add `task_type=TaskType.CHECK`.

> [!IMPORTANT]
> These are one-liner additions to existing config factory functions. No telemetry logic in handlers — the collector captures everything transparently.

---

### 2. `config/` — DB Schema & Persistence

#### [MODIFY] [_schema.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/_schema.py)

Add `SCHEMA_V9` — new `llm_usage_log` table + `llm_cost_overrides` table:

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

No foreign key to `projects` — usage records survive project deletion for historical analysis.

#### [MODIFY] [database.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/database.py)

- Import `SCHEMA_V9` and add v9 migration in `_ensure_schema()`.
- New methods:
  - `log_usage(record: dict)` — insert one row into `llm_usage_log`
  - `get_usage_summary(project: str | None, since: str | None) -> list[dict]` — aggregation
  - `get_usage_by_task_type(project: str) -> list[dict]` — grouping
  - `get_cost_overrides() -> dict[str, CostEntry]` — load all overrides
  - `set_cost_override(model_pattern, input_cost, output_cost)` — upsert
  - `delete_cost_override(model_pattern)` — remove one override

---

### 3. Integration Points — Where the Collector is Created

No changes to `RunContext`. No telemetry-related changes to handlers (the only handler-side change is setting `task_type` on `GenerationConfig` — see Section 1a). The collector wraps the adapter where it's created:

#### [MODIFY] [factory.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/factory.py)

Change return type annotation from `GeminiAdapter` to `Any` (since `TelemetryCollector` is a decorator, not a subclass). Add telemetry wrapping:

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

All existing callers (CLI commands, pipeline runner, API endpoints) pass `telemetry_project` to opt in. Callers that don't pass it get the raw adapter — zero behavioral change.

#### [MODIFY] [runner.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/runner.py)

After pipeline completes (success or failure), flush telemetry:

```python
if isinstance(context.llm, TelemetryCollector):
    context.llm.flush(db)
```

#### [MODIFY] [_helpers.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/_helpers.py)

The CLI helper `get_llm_adapter()` wraps `create_llm_adapter()` — it must pass the active project name as `telemetry_project` so all CLI-created adapters are automatically wrapped in a collector.

```python
def get_llm_adapter(db, *, llm_role="draft"):
    project = db.get_active_project()  # already available
    return create_llm_adapter(db, llm_role=llm_role, telemetry_project=project)
```

#### [MODIFY] CLI command files (`review_commands.py`, `draft_commands.py`, etc.)

After direct (non-pipeline) LLM operations complete, flush telemetry. Each command receives the adapter from `_helpers.py` and calls `flush()` in a `finally` block:

```python
try:
    result = await reviewer.review_spec(...)
finally:
    if isinstance(adapter, TelemetryCollector):
        adapter.flush(db)
```

---

### 4. `cli/` — Usage Reporting

#### [NEW] [usage_commands.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/usage_commands.py)

- `sw usage` — show usage summary for current project (total tokens, cost, by task type)
- `sw usage --all` — show usage across all projects
- `sw usage --since 7d` — filter by time window
- `sw usage --by-model` — group by model instead of task type

Output: Rich table with columns: Task Type | Model | Calls | Tokens (In/Out) | Est. Cost

#### [NEW] [cost_commands.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/cost_commands.py)

- `sw costs` — show current cost table (built-in defaults + user overrides highlighted)
- `sw costs set <model> <input_cost> <output_cost>` — set custom cost per model
- `sw costs reset <model>` — remove override, revert to built-in

#### [MODIFY] [__init__.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli/__init__.py)

Register `usage_commands` and `cost_commands` with the Typer app.

---

## Backlog

> [!NOTE]
> Items identified during audit, deferred from this feature.

- **Adapter-level API-only timing** — measure only LLM round-trip time, excluding tool execution. Requires adapter loop instrumentation. Phase 4 enhancement.
- **Streaming prompt_tokens** — currently `0` for streaming calls. Requires adapter-level support to return `usage_metadata` from the final streaming chunk.
- **Cost table auto-updater** — agent or web scraper to update model pricing monthly. Track in roadmap as future capability.

---

## Verification Plan

### Automated Tests

**Unit tests** (`tests/unit/llm/test_telemetry.py`):
- `test_estimate_cost_known_model` — returns correct cost for known model
- `test_estimate_cost_unknown_model` — returns 0.0
- `test_estimate_cost_with_override` — overrides dict takes precedence over default
- `test_create_usage_record` — all fields populated correctly
- `test_task_type_enum` — all task types are valid StrEnum members

**Unit tests** (`tests/unit/llm/test_collector.py`):
- `test_collector_captures_generate` — one record created per generate() call
- `test_collector_captures_generate_with_tools` — one record, cumulative usage
- `test_collector_captures_generate_stream` — one record, estimated tokens
- `test_collector_task_type_from_config` — record uses config.task_type, not constructor
- `test_collector_multiple_calls_multiple_records` — 3 calls → 3 separate records
- `test_collector_flush` — records persisted and list cleared
- `test_collector_flush_error_handling` — DB error logged, not raised
- `test_collector_proxies_all_methods` — available(), count_tokens(), etc. delegate correctly
- `test_collector_timing` — duration_ms > 0

**Unit tests** (`tests/unit/config/test_database.py`):
- `test_schema_v9_migration` — both tables + indices created
- `test_log_usage` — insert and query back
- `test_get_usage_summary` — aggregation by project
- `test_get_usage_by_task_type` — grouping
- `test_cost_overrides_crud` — set, get, delete

**Integration tests** (`tests/integration/flow/`):
- `test_pipeline_flushes_telemetry` — run pipeline with FakeLLM, verify individual records per step in DB
- `test_direct_cli_flushes_telemetry` — invoke `sw review` directly, verify records in DB

**Unit tests** (`tests/unit/cli/test_usage.py`):
- `test_sw_usage_default` — shows current project summary
- `test_sw_usage_all` — shows all projects
- `test_sw_usage_empty` — graceful output when no records
- `test_sw_costs_show` — displays merged cost table
- `test_sw_costs_set` — override persists
- `test_sw_costs_reset` — override removed

### Manual Verification

- Run `sw draft greet_service` → `sw usage` → verify token count matches
- Run `sw review code greet.py` → `sw usage --by-model` → verify model name appears
- Run `sw costs set gemini-2.5-pro 0.001 0.002` → `sw costs` → verify override shown
