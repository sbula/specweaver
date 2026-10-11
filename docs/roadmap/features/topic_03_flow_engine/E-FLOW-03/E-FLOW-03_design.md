# E-FLOW-03 — Provider Adapters

**Status**: APPROVED. Built; `🔧` until the user signs off. Scope reduced 2026-10-11 to what lives:
prices, the factory and the database `provider` field moved to `C-FLOW-13` (FR-3, FR-4, FR-5 removed). ·
**DAL**: E (Prototyping)

## What it does

One adapter per provider — Gemini, OpenAI, Anthropic, Mistral, Qwen, and any OpenAI-compatible
server — behind the `LLMAdapter` base. A server's `kind` in `settings.toml` (`C-FLOW-13`) names its
adapter; the registry finds it. Adding a provider is one adapter file. Only the Gemini SDK is
required; the others install as extras.

## Decisions

| # | Decision | Why |
|---|----------|-----|
| AD-1 | Auto-discovery via `pkgutil` + subclass scan | no manual registration, no entry points for in-tree adapters |
| AD-2 | `QwenAdapter` extends `OpenAIAdapter` | Qwen speaks the OpenAI API; only the address and metadata differ |
| AD-3 | Adapters hold no prices, telemetry or limits | those are `C-FLOW-13` (prices), `C-FLOW-01` (telemetry), `B-FLOW-05` (limits) |

## Functional Requirements

| # | FR | Outcome |
|---|-----|---------|
| FR-1 | Self-describing adapter | Each adapter declares its `provider_name`, which a server's `kind` names |
| FR-2 | Auto-discovery registry | A new provider is one file in `adapters/`; the registry finds it at first use |
| FR-6 | Optional SDKs | Only `google-genai` is required; `openai`, `anthropic`, `mistralai` are `pyproject.toml` extras |
| FR-7 | Error mapping | Each adapter maps the provider's errors to `AuthenticationError`, `RateLimitError`, `ModelNotFoundError`, else `GenerationError` — by status code or SDK error type, never by words in the message |

## Non-Functional Requirements

| # | NFR | Threshold |
|---|-----|-----------|
| NFR-2 | Graceful SDK absence | A missing SDK skips its adapter with a debug log; no crash |
| NFR-3 | Zero registration | No central list of adapters to maintain |

## Live demo

`sw review <spec>` with a `[servers.gemini]` server: the registry finds `GeminiAdapter` and the
review comes back. A wrong key gives "authentication failed", a busy model "generation failed — 503".
The nightly live run (`B-FLOW-05` NFR-4) goes through this path.

## Sub-features

| SF | Does | FRs | Plan | Committed |
|----|------|-----|------|-----------|
| SF-01 | Optional SDK extras, accurate `context.yaml` | FR-6 | [sf01](E-FLOW-03_sf01_implementation_plan.md) | ✅ |
