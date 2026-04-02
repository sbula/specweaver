# Feature 3.12a Implementation Plan: Multi-Provider Adapter Registry

> **Analysis**: [LLM Routing & Cost Optimization](../../analysis/llm_routing_and_cost_analysis.md)
> **Depends on**: Feature 3.12 (Token & Cost Telemetry) — ✅ complete
> **Enables**: Feature 3.12b (Static Model Routing)

The goal of this feature is to extend SpecWeaver's LLM layer from a single hardcoded Gemini provider to a **multi-provider adapter registry** supporting OpenAI, Anthropic, Mistral, and Qwen — all selectable via configuration. Adding a new provider = implementing one adapter file. Zero other changes.

## Key Design Decision: Self-Describing Adapters + Auto-Discovery

Each adapter carries **all its own metadata** as class attributes. The registry is built automatically by scanning `llm/adapters/` for `LLMAdapter` subclasses at import time. No manual registration, no scattered maps, no central cost tables to maintain.

### Self-describing adapter metadata

```python
class OpenAIAdapter(LLMAdapter):
    provider_name = "openai"                    # Registry key
    api_key_env_var = "OPENAI_API_KEY"           # Env var for API key resolution
    default_costs = {                            # Built-in cost defaults (code)
        "gpt-4o": CostEntry(0.00250, 0.01000),
        "gpt-4o-mini": CostEntry(0.00015, 0.00060),
    }
```

### Auto-discovery at import

```
llm/adapters/__init__.py
  → scans all .py files in llm/adapters/
  → imports each, finds LLMAdapter subclasses
  → builds ADAPTER_REGISTRY from provider_name
  → builds merged DEFAULT_COST_TABLE from all default_costs
  → builds API_KEY_ENV_MAP from all api_key_env_var
  → skips adapters whose SDK is not installed (ImportError)
```

### Cost layering (never overwrites user data)

```
                   Lookup order
                       │
                       ▼
┌──────────────────────────────────────┐
│  llm_cost_overrides (DB)             │ ← User-controlled via `sw costs set`
│  Written by user, never by system    │   Survives upgrades, never overwritten
└──────────────────────┬───────────────┘
                       │ miss
                       ▼
┌──────────────────────────────────────┐
│  adapter.default_costs (code)        │ ← Shipped with SpecWeaver
│  Updated when SpecWeaver is upgraded │   Always fresh, read-only at runtime
└──────────────────────────────────────┘
```

`estimate_cost()` (from 3.12) already checks DB overrides first → falls back to code defaults. No DB seeding, no "first-scan" detection, no overwrite risk.

### Why not a plugin system

- All adapters ship with SpecWeaver — no third-party adapter loading needed.
- Auto-discovery within a known package is simpler than entry points / `importlib.metadata`.
- 3.12b (static routing) will use the same registry to resolve per-task-type providers.

## User Review Required

> [!IMPORTANT]
> **New SDK dependencies**: `openai`, `anthropic`, `mistralai` as **optional** deps. Not required for Gemini-only default. Qwen uses `openai` SDK with a different base URL (no extra dep).

> [!IMPORTANT]
> **API key env vars**: Each adapter declares its own env var. The factory resolves the correct one from the adapter's `api_key_env_var` class attribute. No central map to maintain.

> [!IMPORTANT]
> **Breaking change to `LLMSettings`**: Adds `provider` field (default `"gemini"`). `load_settings()` resolves API key from the provider-appropriate env var. Existing Gemini-only users are unaffected.

## Proposed Changes

---

### 1. `llm/adapters/base.py` — Adapter ABC: Add Metadata Attributes ✅ DONE

#### [MODIFY] [base.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/adapters/base.py)

Add class-level metadata attributes that subclasses must define:

```python
class LLMAdapter(ABC):
    """Abstract base class for LLM provider adapters."""

    # --- Metadata (subclasses MUST override) ---
    provider_name: str = ""             # e.g. "gemini", "openai"
    api_key_env_var: str = ""           # e.g. "GEMINI_API_KEY"
    default_costs: dict[str, CostEntry] = {}  # Model → CostEntry

    # --- Existing abstract methods unchanged ---
    ...
```

> [!NOTE]
> `provider_name` is currently an `@property` on `GeminiAdapter`. It becomes a plain class attribute on the ABC, and existing adapters switch from `@property` to class attribute assignment. Both are duck-typing compatible.

> [!CAUTION]
> **Migration check**: `TelemetryCollector` accesses `self._adapter.provider_name` (instance access — safe). Search codebase for all `provider_name` references and verify no code relies on `type(adapter).provider_name` behaving as a property.

---

### 2. `llm/adapters/` — New Adapter Implementations

Each adapter follows the `GeminiAdapter` pattern: lazy client init, `_handle_error()` for provider-specific error mapping, `_parse_response()` for response conversion. Each adapter handles its own error mapping internally (~15 lines per adapter) — acceptable duplication at this scale.

**Tool-use scope**: OpenAI and Anthropic get full `generate_with_tools()`. Mistral and Qwen use the base class fallback (logs warning, calls `generate()`) — tool-use for these can be added later. This means research tools (3.10) won't work with Mistral/Qwen; acceptable for initial release.

#### [MODIFY] [gemini.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/adapters/gemini.py)

Migrate `provider_name` from `@property` to class attribute. Add `api_key_env_var` and `default_costs`:

```python
class GeminiAdapter(LLMAdapter):
    provider_name = "gemini"
    api_key_env_var = "GEMINI_API_KEY"
    default_costs = {
        "gemini-3-flash-preview": CostEntry(0.00010, 0.00040),
        "gemini-2.5-flash-preview-04-17": CostEntry(0.00015, 0.00060),
        "gemini-2.5-pro-preview-03-25": CostEntry(0.00125, 0.01000),
        "gemini-2.0-flash": CostEntry(0.00010, 0.00040),
        "gemini-2.0-flash-lite": CostEntry(0.00005, 0.00020),
    }
```

#### [NEW] [openai.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/adapters/openai.py)

`OpenAIAdapter` — wraps the `openai` SDK (AsyncOpenAI client). Includes full `generate_with_tools()`.

```python
class OpenAIAdapter(LLMAdapter):
    provider_name = "openai"
    api_key_env_var = "OPENAI_API_KEY"
    default_costs = {
        "gpt-4o": CostEntry(0.00250, 0.01000),
        "gpt-4o-mini": CostEntry(0.00015, 0.00060),
        "gpt-4.1": CostEntry(0.00200, 0.00800),
        "gpt-4.1-mini": CostEntry(0.00040, 0.00160),
        "gpt-4.1-nano": CostEntry(0.00010, 0.00040),
    }

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get(self.api_key_env_var, "")
        self._client = None
```

**Key mappings**:
- `Message(role=SYSTEM)` → `{"role": "system", "content": ...}`
- `GenerationConfig.tools` → `[{"type": "function", "function": {...}}]` via `ToolDefinition.to_json_schema()`
- `response.usage` → `TokenUsage(prompt_tokens, completion_tokens, total_tokens)`
- `response.choices[0].finish_reason` → `LLMResponse.finish_reason`

#### [NEW] [anthropic.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/adapters/anthropic.py)

`AnthropicAdapter` — wraps the `anthropic` SDK (AsyncAnthropic client). Includes full `generate_with_tools()`.

```python
class AnthropicAdapter(LLMAdapter):
    provider_name = "anthropic"
    api_key_env_var = "ANTHROPIC_API_KEY"
    default_costs = {
        "claude-sonnet-4-20250514": CostEntry(0.00300, 0.01500),
        "claude-3-5-haiku-20241022": CostEntry(0.00080, 0.00400),
    }
```

**Key differences from OpenAI**:
- System instruction is a separate `system` parameter, not a message
- Tool use returns `tool_use` content blocks (not `function_call`)
- Token usage: `input_tokens` / `output_tokens` (no `total_tokens` — compute it)
- `stop_reason` instead of `finish_reason`

#### [NEW] [mistral.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/adapters/mistral.py)

`MistralAdapter` — wraps the `mistralai` SDK. No `generate_with_tools()` (uses base class fallback).

```python
class MistralAdapter(LLMAdapter):
    provider_name = "mistral"
    api_key_env_var = "MISTRAL_API_KEY"
    default_costs = {
        "mistral-large-latest": CostEntry(0.00200, 0.00600),
        "mistral-small-latest": CostEntry(0.00010, 0.00030),
        "codestral-latest": CostEntry(0.00030, 0.00090),
    }
```

#### [NEW] [qwen.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/adapters/qwen.py)

`QwenAdapter` — thin subclass of `OpenAIAdapter` with overridden `base_url`. Uses OpenAI-compatible endpoint, no `dashscope` SDK dependency.

```python
class QwenAdapter(OpenAIAdapter):
    provider_name = "qwen"
    api_key_env_var = "DASHSCOPE_API_KEY"
    default_costs = {
        "qwen-max": CostEntry(0.00160, 0.00640),
        "qwen-plus": CostEntry(0.00040, 0.00120),
        "qwen-turbo": CostEntry(0.00020, 0.00060),
    }

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        return self._client
```

> [!NOTE]
> `QwenAdapter` inherits from `OpenAIAdapter`, not `LLMAdapter`. It reuses all generate/stream/error logic. Only `_get_client()`, `provider_name`, `api_key_env_var`, and `default_costs` differ.

---

### 3. `llm/adapters/__init__.py` — Auto-Discovery Registry ✅ DONE

#### [MODIFY] [__init__.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/adapters/__init__.py)

Replace the static 5-line file with auto-discovery:

```python
"""LLM adapter implementations with auto-discovery registry.

At import time, scans this package for LLMAdapter subclasses and builds:
- ADAPTER_REGISTRY: provider_name → adapter class
- KNOWN_PROVIDERS: all provider names (including unavailable SDKs)

Adding a new provider = drop in a new .py file. Zero other changes.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.llm.adapters.base import LLMAdapter
    from specweaver.llm.telemetry import CostEntry

logger = logging.getLogger(__name__)

# Populated by _discover_adapters() at module load
ADAPTER_REGISTRY: dict[str, type[LLMAdapter]] = {}
KNOWN_PROVIDERS: set[str] = set()


def _discover_adapters() -> None:
    """Scan this package for LLMAdapter subclasses.

    For each .py module in llm/adapters/:
    - Try to import it
    - Find all LLMAdapter subclasses
    - Register by provider_name
    - If ImportError (SDK missing), record as known but unavailable
    """
    from specweaver.llm.adapters.base import LLMAdapter as BaseClass

    package = importlib.import_module(__name__)
    for _importer, modname, _ispkg in pkgutil.iter_modules(package.__path__):
        if modname.startswith("_") or modname == "base":
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{modname}")
        except ImportError:
            # SDK not installed — record the module name as a known provider
            KNOWN_PROVIDERS.add(modname)
            logger.debug("Adapter '%s' skipped — SDK not installed", modname)
            continue

        for _name, cls in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(cls, BaseClass)
                and cls is not BaseClass
                and cls.__module__ == mod.__name__  # Only classes DEFINED in this module
                and cls.provider_name
                and cls.provider_name not in ADAPTER_REGISTRY
            ):
                ADAPTER_REGISTRY[cls.provider_name] = cls
                KNOWN_PROVIDERS.add(cls.provider_name)


_discover_adapters()


def get_adapter_class(provider: str) -> type[LLMAdapter]:
    """Look up an adapter class by provider name.

    Raises:
        ValueError: With actionable message distinguishing
            "unknown provider" from "SDK not installed".
    """
    cls = ADAPTER_REGISTRY.get(provider)
    if cls is not None:
        return cls

    if provider in KNOWN_PROVIDERS:
        msg = (
            f"Provider '{provider}' requires its SDK. "
            f"Install with: pip install specweaver[{provider}]"
        )
    else:
        available = ", ".join(sorted(ADAPTER_REGISTRY.keys()))
        msg = f"Unknown LLM provider '{provider}'. Available: {available}"
    raise ValueError(msg)


def get_merged_default_costs() -> dict[str, CostEntry]:
    """Merge default_costs from all registered adapters.

    Returns a single dict: model_name → CostEntry.
    If two adapters declare the same model, first-registered wins.
    """
    merged: dict[str, CostEntry] = {}
    for adapter_cls in ADAPTER_REGISTRY.values():
        for model, entry in adapter_cls.default_costs.items():
            if model not in merged:
                merged[model] = entry
    return merged
```

#### [MODIFY] [context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/llm/adapters/context.yaml)

Update description and exposes:

```yaml
description: |
  Concrete LLM provider adapters with auto-discovery registry.
  Each adapter is self-describing (provider_name, api_key_env_var, default_costs).
  Adding a new provider = one file, zero other changes.

exposes:
  - LLMAdapter
  - GeminiAdapter
  - OpenAIAdapter
  - AnthropicAdapter
  - MistralAdapter
  - QwenAdapter
  - ADAPTER_REGISTRY
  - get_adapter_class
  - get_merged_default_costs
```

---

### 4. `llm/telemetry.py` — Remove Hardcoded Cost Table ✅ DONE

#### [MODIFY] [telemetry.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/telemetry.py)

Remove `DEFAULT_COST_TABLE` dict. Replace with a cached function that loads from the registry:

```python
_cached_default_costs: dict[str, CostEntry] | None = None

def get_default_cost_table() -> dict[str, CostEntry]:
    """Get the merged default cost table from all registered adapters.

    Cached after first call — adapter registration is complete at import time.
    """
    global _cached_default_costs
    if _cached_default_costs is None:
        from specweaver.llm.adapters import get_merged_default_costs
        _cached_default_costs = get_merged_default_costs()
    return _cached_default_costs
```

> [!CAUTION]
> **Import chain constraint**: New adapters import `CostEntry` from `telemetry.py` at module level (needed for `default_costs` dict values). `adapters/__init__.py` imports those adapter modules at module level (via `_discover_adapters()`). Therefore, the `from specweaver.llm.adapters import get_merged_default_costs` in `telemetry.py` **must stay lazy** (inside the function body) to avoid a circular import: `adapters/__init__.py → openai.py → telemetry.py → adapters/__init__.py`.

Update `estimate_cost()` to call `get_default_cost_table()` as fallback:

```python
def estimate_cost(model, usage, overrides=None) -> float:
    entry = None
    if overrides:
        entry = overrides.get(model)
    if entry is None:
        entry = get_default_cost_table().get(model)
    if entry is None:
        return 0.0
    ...
```

---

### 5. `config/` — Provider Configuration ✅ DONE

#### [MODIFY] [settings.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/settings.py)

Add `provider` field to `LLMSettings`:

```python
class LLMSettings(BaseModel):
    provider: str = "gemini"        # ← NEW
    model: str
    temperature: float = 0.7
    max_output_tokens: int = 4096
    response_format: Literal["text", "json"] = "text"
    api_key: str = ""
```

Update `load_settings()` to read `provider` from DB profile and resolve API key from the adapter's env var:

```python
def load_settings(db, project_name, *, llm_role="review"):
    ...
    provider = str(profile.get("provider", "gemini"))

    # Resolve API key from adapter metadata
    from specweaver.llm.adapters import ADAPTER_REGISTRY
    adapter_cls = ADAPTER_REGISTRY.get(provider)
    env_var = adapter_cls.api_key_env_var if adapter_cls else "GEMINI_API_KEY"

    llm = LLMSettings(
        provider=provider,
        model=str(profile["model"]),
        ...
        api_key=os.environ.get(env_var, ""),
    )
```

> [!NOTE]
> No `_PROVIDER_API_KEY_ENV` dict needed — the env var comes from the adapter class itself. One less thing to maintain.

#### [MODIFY] [_schema.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/_schema.py)

Add `SCHEMA_V10` migration:

```python
SCHEMA_V10 = """\
ALTER TABLE llm_profiles ADD COLUMN provider TEXT NOT NULL DEFAULT 'gemini';
"""
```

Update `DEFAULT_PROFILES` to include `provider` as 8th element:

```python
DEFAULT_PROFILES = [
    ("system-default", 1, "gemini-3-flash-preview", 0.7, 4096, "text", 128_000, "gemini"),
    ("review",         1, "gemini-3-flash-preview", 0.3, 4096, "text", 128_000, "gemini"),
    ("draft",          1, "gemini-3-flash-preview", 0.7, 4096, "text", 128_000, "gemini"),
    ("search",         1, "gemini-3-flash-preview", 0.1, 4096, "text", 128_000, "gemini"),
]
```

> [!CAUTION]
> **INSERT SQL sync**: The INSERT in [database.py line 144](file:///c:/development/pitbula/specweaver/src/specweaver/config/database.py#L144) explicitly lists column names. Both the column list AND the tuple must be updated in sync. Test with fresh DB creation.

#### [MODIFY] [_db_llm_mixin.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/_db_llm_mixin.py)

Add `provider` param to `create_llm_profile()` and update the INSERT SQL on [lines 49-51](file:///c:/development/pitbula/specweaver/src/specweaver/config/_db_llm_mixin.py#L49-L51) to include `provider` in both the column list and VALUES placeholder:

```python
def create_llm_profile(self, name, *, model, is_global=True,
                       temperature=0.7, max_output_tokens=4096,
                       response_format="text", provider="gemini"):
    with self.connect() as conn:
        cursor = conn.execute(
            "INSERT INTO llm_profiles "
            "(name, is_global, model, temperature, max_output_tokens, response_format, provider) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, int(is_global), model, temperature, max_output_tokens, response_format, provider),
        )
```

#### [MODIFY] [database.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/database.py)

- Import `SCHEMA_V10` and add v10 migration in `_ensure_schema()`.
- Update default profile seed INSERT to include `provider` column.

---

### 6. `llm/factory.py` — Registry-Based Instantiation

#### [MODIFY] [factory.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/factory.py)

Replace hardcoded `GeminiAdapter` with registry lookup:

```python
def create_llm_adapter(db, *, llm_role="draft", telemetry_project=None):
    from specweaver.llm.adapters import get_adapter_class
    ...
    settings = load_settings_for_active(db, llm_role=llm_role)

    adapter_cls = get_adapter_class(settings.llm.provider)
    adapter: Any = adapter_cls(api_key=settings.llm.api_key or None)

    if not adapter.available():
        msg = (
            f"No API key configured for {settings.llm.provider}. "
            f"Set {adapter_cls.api_key_env_var} environment variable."
        )
        raise LLMAdapterError(msg)
    ...
```

Update the fallback path similarly (no active project → still use registry).

---

### 7. `cli/` — Provider Management Commands

#### [MODIFY] CLI config commands (in `cli/config_commands.py`)

- `sw config show` — display `Provider:` line
- `sw config set-provider <provider>` — update active profile's provider in DB. Validates against `ADAPTER_REGISTRY` keys.

#### [MODIFY] `sw costs` (existing from 3.12)

- `sw costs` — show merged table: adapter defaults + DB overrides (overrides highlighted)

> [!NOTE]
> No model-provider mismatch validation (e.g., `provider: openai` + `model: gemini-3-flash`). The API will reject it with a clear error. Structured validation deferred to 3.12b when task routing makes this more manageable.

---

### 8. Optional Dependencies (pyproject.toml)

#### [MODIFY] [pyproject.toml](file:///c:/development/pitbula/specweaver/pyproject.toml)

```toml
[project.optional-dependencies]
openai = ["openai>=1.5"]
anthropic = ["anthropic>=0.25"]
mistral = ["mistralai>=1.0"]
all-llm = ["openai>=1.5", "anthropic>=0.25", "mistralai>=1.0"]
```

> [!NOTE]
> No `dashscope` dependency — `QwenAdapter` reuses the `openai` SDK with a different base URL. Users who want Qwen install `specweaver[openai]`.

> [!WARNING]
> **Version bounds**: Verify that async client support exists at these minimums (`openai>=1.5` for `AsyncOpenAI`, `anthropic>=0.25` for `AsyncAnthropic`). Pin tighter if needed during implementation.

---

## Backlog

> [!NOTE]
> Items identified during planning, deferred from this feature.

- **Ollama / vLLM adapters** — local model support (no API key, different deployment model)
- **`generate_with_tools()` for Mistral/Qwen** — uses base class fallback for now
- **Tiktoken for OpenAI token counting** — `count_tokens()` uses base class estimate for now
- **Streaming telemetry per provider** — provider-specific streaming enhancements
- **`sw providers` CLI command** — list all registered/available providers

### Documentation updates

After implementation, update:
- `README.md` — "Multi-Provider Support" section
- `docs/quickstart.md` — how to configure a non-Gemini provider
- `docs/architecture/architecture_reference.md` — update Feature Map, LLM adapter section
- `docs/proposals/specweaver_roadmap.md` — mark 3.12a complete
- `docs/proposals/roadmap/phase_3_feature_expansion.md` — mark 3.12a complete

---

## Verification Plan

### Automated Tests

**Unit tests — adapter metadata** (`tests/unit/llm/test_adapters.py` — extend):

Each adapter:
- `test_{provider}_adapter_provider_name` — correct string
- `test_{provider}_adapter_api_key_env_var` — correct env var
- `test_{provider}_adapter_default_costs_non_empty` — has cost entries
- `test_{provider}_adapter_available_with_key` — True when key set
- `test_{provider}_adapter_available_without_key` — False when no key
- `test_{provider}_adapter_generate_mock` — mock SDK, verify LLMResponse
- `test_{provider}_adapter_error_auth` — 401 → AuthenticationError
- `test_{provider}_adapter_error_rate_limit` — 429 → RateLimitError

**Unit tests — auto-discovery** (`tests/unit/llm/test_registry.py`):

- `test_registry_discovers_gemini` — always present
- `test_registry_all_have_provider_name` — no empty provider_name
- `test_registry_all_have_api_key_env_var` — no empty env var
- `test_registry_all_have_default_costs` — non-empty cost dict
- `test_get_adapter_class_known` — returns correct class
- `test_get_adapter_class_unknown` — ValueError with available list
- `test_get_adapter_class_sdk_missing` — ValueError with install hint
- `test_get_merged_default_costs` — all adapter costs merged
- `test_merged_costs_no_duplicates` — first-registered wins

**Unit tests — settings** (`tests/unit/config/test_settings.py` — extend):

- `test_llm_settings_provider_default` — defaults to `"gemini"`
- `test_load_settings_resolves_api_key_from_adapter` — correct env var

**Unit tests — factory** (`tests/unit/llm/test_factory.py` — extend):

- `test_factory_creates_gemini_by_default` — backward compatible
- `test_factory_creates_openai_adapter` — provider="openai" → OpenAIAdapter
- `test_factory_unknown_provider_raises` — ValueError
- `test_factory_missing_api_key_raises` — LLMAdapterError with env var hint

**Unit tests — DB migration** (`tests/unit/config/test_database.py` — extend):

- `test_schema_v10_migration` — provider column added
- `test_create_profile_with_provider` — stores correctly
- `test_default_profiles_include_provider` — seed data includes provider

**Integration tests** (`tests/integration/llm/`):

- `test_factory_telemetry_wrapping_multi_provider` — TelemetryCollector wraps any adapter

### Manual Verification

- Set `OPENAI_API_KEY` → `sw config set-provider openai` → `sw config set-model gpt-4o` → `sw draft greet_service` → `sw usage` shows provider=openai
- Missing SDK → `sw config set-provider anthropic` → friendly "install specweaver[anthropic]" error
- `sw costs` → shows merged table (Gemini + OpenAI defaults + any user overrides)

### Commands

```bash
python -m pytest tests/unit/llm/ tests/unit/config/ -v
python -m pytest tests/integration/llm/ -v
python -m pytest --tb=short
```
