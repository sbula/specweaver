# Design: Multi-Provider Adapter Registry

- **Feature ID**: E-FLOW-03
- **DAL**: E (Prototyping)
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_03_flow_engine/E-FLOW-03/E-FLOW-03_design.md

## Feature Overview

Feature E-FLOW-03 extends SpecWeaver's LLM layer from a single hardcoded Gemini provider to a **multi-provider adapter registry** supporting OpenAI, Anthropic, Mistral, and Qwen — all selectable via DB-stored configuration. Adding a new provider = implementing one adapter file with `provider_name`, `api_key_env_var`, and `default_costs` as class attributes. Zero manual registration needed.

It solves provider lock-in by abstracting all LLM interactions behind the `LLMAdapter` ABC. It interacts with `infrastructure/llm/adapters/`, `infrastructure/llm/factory.py`, `core/config/settings_loader.py`, and `core/config/profiles.py`. It does NOT touch the flow engine, validation, sandbox, or workspace layers.

Key constraints: Optional SDKs (only Gemini is required), backward compatibility (existing Gemini-only users unaffected), and cost layering (adapter code defaults → DB overrides — never overwrites user data).

## Research Findings

### Codebase Audit (2026-05-03)

The feature is **architecturally complete**. The following components are fully implemented and tested:

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

**Verified capabilities per adapter:**
- `generate()` ✅ all 5
- `generate_stream()` ✅ all 5 (Qwen inherits from OpenAI)
- `generate_with_tools()` ✅ OpenAI, Anthropic, Mistral (Qwen inherits OpenAI); base fallback for others
- `_handle_error()` ✅ all 5
- `available()` ✅ all 5
- `count_tokens()` ✅ all 5

### What Remains (Polish Items)

| Item | Status | Evidence |
|:---|:---|:---|
| Optional deps in `pyproject.toml` | ❌ Missing | No `[project.optional-dependencies]` section for `openai`, `anthropic`, `mistralai` |
| `llm/context.yaml` description | ❌ Stale | Says "currently Google Gemini" — multi-provider is live |
| `llm/context.yaml` exposes | ❌ Incomplete | Only lists `GeminiAdapter` — should list all adapters |
| `llm/context.yaml` `async_ready` | ❌ Wrong | Says `false` but all adapter methods are `async` |
| `llm/adapters/context.yaml` `async_ready` | ❌ Wrong | Says `false` |
| E2E user journey test | ❌ Missing | No test exercises `provider=openai → sw draft → telemetry shows openai` |
| Documentation updates | ❌ Pending | README, quickstart, architecture_reference not yet updated |

### Industry Patterns Verification

SpecWeaver's implementation aligns with 2024-2026 industry best practices:
- ✅ Abstract Base Class provider contracts
- ✅ Auto-discovery registry (no manual registration)
- ✅ Self-describing adapters with cost metadata
- ✅ Configuration-driven provider selection (DB-stored)
- ✅ Cost layering (code defaults → DB overrides)
- ✅ Telemetry proxy pattern (`TelemetryCollector`)
- ✅ Per-provider rate limiting (`AsyncRateLimiterAdapter`)
- ❌ Automatic fallback (deferred to D-FLOW-03 Static Routing)

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

## Non-Functional Requirements

| # | NFR | Threshold |
|---|-----|-----------|
| NFR-1 | Backward Compatibility | Existing Gemini-only users must not be affected. Default `provider: "gemini"`. ✅ Verified. |
| NFR-2 | Graceful SDK absence | If `openai` not installed, registry skips it with debug log. No crash. ✅ Verified. |
| NFR-3 | Zero-registration pattern | No central map/array to maintain. Auto-discovery + class attributes only. ✅ Verified. |

## Architectural Decisions

| # | Decision | Rationale | Arch Switch? |
|---|----------|-----------|:---:|
| AD-1 | Auto-discovery via `pkgutil` + subclass scan | Simpler than entry points for in-tree adapters. No third-party loader needed. | No |
| AD-2 | `QwenAdapter` extends `OpenAIAdapter` | Qwen uses OpenAI-compatible API. Only `base_url` + metadata differ. Zero code duplication. | No |
| AD-3 | Telemetry wrapping in factory, not adapter | Adapters stay pure. `TelemetryCollector` is applied transparently by `factory.py`. | No |
| AD-4 | Cost defaults as class attributes | Each adapter owns its cost data. No central cost table. `get_merged_default_costs()` aggregates at runtime. | No |

## Sub-Feature Breakdown

### SF-1: Polish & Close
- **Scope**: Complete the remaining polish items to make E-FLOW-03 shippable.
- **FRs**: FR-6 (optional deps)
- **Work**:
  1. Add `[project.optional-dependencies]` to `pyproject.toml`
  2. Fix `infrastructure/llm/context.yaml` (description, exposes, async_ready)
  3. Fix `infrastructure/llm/adapters/context.yaml` (async_ready)
  4. Add E2E test (mocked HTTP layer, not mocked adapter layer)
  5. Update documentation (README, quickstart, architecture_reference)
- **Depends on**: Nothing.
- **Impl Plan**: `docs/roadmap/features/topic_03_flow_engine/E-FLOW-03/E-FLOW-03_sf1_implementation_plan.md`

## Definition of Done

E-FLOW-03 is complete when ALL of the following are true:

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

## Execution Order

1. SF-1 (Polish & Close) — single commit boundary.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Polish & Close | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design APPROVED. Core implementation complete (all adapters, registry, factory, config, tests). Polish items remain.
**Next step**: Create SF-1 implementation plan, then `/dev`.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ and resume.
