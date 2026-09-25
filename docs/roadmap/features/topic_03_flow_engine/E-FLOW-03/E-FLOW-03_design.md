# E-FLOW-03 — Multi-Provider Adapter Registry

**Status**: APPROVED · **COMPLETE** — SF-01 committed · **DAL**: E (Prototyping)

| | |
|---|---|
| Touches | `infrastructure/llm/adapters/`, `infrastructure/llm/factory.py`, `core/config/settings_loader.py`, `core/config/profiles.py` |
| Deferred | automatic fallback → D-FLOW-03 Static Routing |
| Not touched | flow engine, validation, sandbox, workspace layers |

## What it does

Replaces the single hardcoded Gemini provider with a **multi-provider adapter registry**: Gemini,
OpenAI, Anthropic, Mistral and Qwen, selected by DB-stored configuration. All LLM calls go through
the `LLMAdapter` ABC, which ends provider lock-in.

Adding a provider = one adapter file with `provider_name`, `api_key_env_var` and `default_costs` as
class attributes. Zero manual registration.

Constraints: SDKs are optional (only Gemini is required); existing Gemini-only users are unaffected;
costs layer adapter code defaults → DB overrides, never overwriting user data.

## Architecture

| Component | File | Size | Tests |
|:---|:---|:---|:---|
| `LLMAdapter` ABC with metadata | `infrastructure/llm/adapters/base.py` | 4.8KB | `test_adapters.py` |
| Auto-discovery registry | `infrastructure/llm/adapters/registry.py` | 2.9KB | `test_registry.py` |
| `GeminiAdapter` | `infrastructure/llm/adapters/gemini.py` | 15.8KB | `test_llm.py` |
| `OpenAIAdapter` (full tool-use) | `infrastructure/llm/adapters/openai.py` | 8.7KB | `test_openai.py` |
| `AnthropicAdapter` (full tool-use) | `infrastructure/llm/adapters/anthropic.py` | 9.9KB | `test_anthropic.py` |
| `MistralAdapter` (full tool-use) | `infrastructure/llm/adapters/mistral.py` | 9.2KB | `test_mistral.py` |
| `QwenAdapter` (extends OpenAI) | `infrastructure/llm/adapters/qwen.py` | 1.3KB | `test_qwen.py` |
| Registry-based factory | `infrastructure/llm/factory.py` | 4.1KB | `test_factory.py` |
| Rate limiter wrapper | `infrastructure/llm/adapters/_rate_limit.py` | 4.3KB | `test_rate_limit.py` |
| Config `provider` field | `core/config/settings.py` + `settings_loader.py` | — | `test_settings.py` |
| DB `provider` column | `infrastructure/llm/store.py` (SQLAlchemy `LlmProfile.provider`) | — | — |
| Context.yaml boundaries | `infrastructure/llm/adapters/context.yaml` | — | `tach check` |
| Integration tests | `tests/integration/sandbox/test_multi_provider_integration.py` | 6.1KB | 4 tests (OpenAI, Anthropic, Mistral, Qwen + ToolDispatcher) |

Sizes and files as of the codebase audit, 2026-05-03.

Capabilities per adapter:

- `generate()` ✅ all 5
- `generate_stream()` ✅ all 5 (Qwen inherits from OpenAI)
- `generate_with_tools()` ✅ OpenAI, Anthropic, Mistral (Qwen inherits OpenAI); base fallback for
  others
- `_handle_error()`, `available()`, `count_tokens()` ✅ all 5

Patterns (checked against 2024-2026 industry practice): ABC provider contracts · auto-discovery
registry (no manual registration) · self-describing adapters with cost metadata · DB-stored
provider selection · cost layering (code defaults → DB overrides) · telemetry proxy
(`TelemetryCollector`) · per-provider rate limiting (`AsyncRateLimiterAdapter`). Not done: automatic
fallback (deferred to D-FLOW-03 Static Routing).

## Decisions

| # | Decision | Rationale | Arch Switch? |
|---|----------|-----------|:---:|
| AD-1 | Auto-discovery via `pkgutil` + subclass scan | Simpler than entry points for in-tree adapters. No third-party loader needed. | No |
| AD-2 | `QwenAdapter` extends `OpenAIAdapter` | Qwen uses OpenAI-compatible API. Only `base_url` + metadata differ. Zero code duplication. | No |
| AD-3 | Telemetry wrapping in factory, not adapter | Adapters stay pure. `TelemetryCollector` is applied by `factory.py`. | No |
| AD-4 | Cost defaults as class attributes | Each adapter owns its cost data. No central cost table. `get_merged_default_costs()` aggregates at runtime. | No |

## Functional Requirements

| # | FR | Outcome |
|---|-----|---------|
| FR-1 | Self-describing adapter metadata | Each adapter declares `provider_name`, `api_key_env_var`, `default_costs` as class attributes. ✅ Done. |
| FR-2 | Auto-discovery registry | Adding a new provider = 1 file in `adapters/`. Registry scans at first access. ✅ Done. |
| FR-3 | Registry-based factory instantiation | `factory.py` resolves adapter class via `get_adapter_class(provider)`. ✅ Done. |
| FR-4 | Cost layering (code → DB) | `get_merged_default_costs()` provides fallback for `estimate_cost()`. ✅ Done. |
| FR-5 | Config `provider` field | `LLMSettings.provider` stored in DB, resolved per-profile. ✅ Done. |
| FR-6 | Optional SDK dependencies | `pyproject.toml` declares `openai`, `anthropic`, `mistralai` as extras. ❌ Pending. |
| FR-7 | Comprehensive error mapping | Each adapter maps provider-specific errors → `LLMError` hierarchy. ✅ Done. |

FR-6's "❌ Pending" predates SF-01; `pyproject.toml` declares the extras today (checked 2026-09-25).

## Non-Functional Requirements

| # | NFR | Threshold |
|---|-----|-----------|
| NFR-1 | Backward Compatibility | Existing Gemini-only users must not be affected. Default `provider: "gemini"`. ✅ Verified. |
| NFR-2 | Graceful SDK absence | If `openai` not installed, registry skips it with debug log. No crash. ✅ Verified. |
| NFR-3 | Zero-registration pattern | No central map/array to maintain. Auto-discovery + class attributes only. ✅ Verified. |

## Sub-features

| SF | Does | FRs | Depends on | Plan |
|----|------|-----|-----------|------|
| SF-01 | Polish & Close — the gaps the 2026-05-03 audit found (below) | FR-6 | — | [sf01](E-FLOW-03_sf01_implementation_plan.md) |

Gaps SF-01 closed (single commit boundary):

| Item | State at audit | Evidence |
|:---|:---|:---|
| Optional deps in `pyproject.toml` | ❌ Missing | No `[project.optional-dependencies]` section for `openai`, `anthropic`, `mistralai` |
| `llm/context.yaml` description | ❌ Stale | Says "currently Google Gemini" — multi-provider is live |
| `llm/context.yaml` exposes | ❌ Incomplete | Only lists `GeminiAdapter` — should list all adapters |
| `llm/context.yaml` `async_ready` | ❌ Wrong | Says `false` but all adapter methods are `async` |
| `llm/adapters/context.yaml` `async_ready` | ❌ Wrong | Says `false` |
| E2E user journey test | ❌ Missing | No test exercises `provider=openai → sw draft → telemetry shows openai` |
| Documentation updates | ❌ Pending | README, quickstart, architecture_reference not yet updated |

## Definition of Done

| # | Criterion | Verification Method |
|---|-----------|:---|
| 1 | All 5 adapters importable + `available()` returns True with API key | `test_adapters.py` |
| 2 | Auto-discovery finds all adapters | `test_registry.py` |
| 3 | `factory.py` creates correct adapter per provider | `test_factory.py` |
| 4 | Optional deps declared in `pyproject.toml` | File inspection |
| 5 | `context.yaml` metadata accurate (description, exposes, async_ready) | Manual review |
| 6 | E2E test proves full stack (config → factory → adapter → telemetry) | New E2E test |
| 7 | `tach check` clean | `tach check` command |
| 8 | README + quickstart updated | File inspection |

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Polish & Close | — | ✅ | ✅ | ✅ | ✅ | ✅ |
