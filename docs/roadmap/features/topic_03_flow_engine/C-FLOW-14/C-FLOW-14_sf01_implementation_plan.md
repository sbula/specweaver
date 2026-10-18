# Implementation Plan: Cached Input Tokens [SF-01: Prompts that hit the cache]
- **Feature ID**: C-FLOW-14
- **Sub-Feature**: SF-01 — Prompts that hit the cache
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-14/C-FLOW-14_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-14/C-FLOW-14_sf01_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-18

**FRs owned**: FR-1, FR-2, FR-3 · **NFRs**: NFR-1, NFR-2, NFR-3 · **Depends on**: none

## Shape

| Piece | Where | Tag |
|---|---|---|
| a new last prompt slot, `run_clock`, holding only the run's timestamp; `project_metadata` renders without `date_iso`; `FULL`, `MINIMAL` and `INTERACTIVE` (the profiles with metadata) end with it; `ARBITER` has neither | `prompt/profiles.py` (`PromptSlot`), `prompt/render.py` (`_DEFAULT_TAG_ORDER`), `core/flow/handlers/_profiles.py`, `prompt/adapter.py`, `prompt/adders.py` | MODIFY |
| `date_iso` stays on `ProjectMetadata`; decomposition keeps reading it | `models.py`, `handlers/decompose.py` | — |
| Anthropic: `cache_control = {"type": "ephemeral"}` (automatic caching, 5 minutes) in the request of `generate` and of every tool round | `adapters/anthropic.py` | MODIFY |
| `GenerationConfig.cache_key: str = ""`; the collector fills it per call: `sw-` + the first 32 hex of SHA-256 over project and `task_type` (the step type) | `models.py`, `collector.py` | MODIFY |
| a class flag `sends_cache_key`: true on `OpenAIAdapter` and `MistralAdapter`, false on `OpenAICompatibleAdapter` and `QwenAdapter` (NFR-3); a set key goes out as `prompt_cache_key` | `adapters/openai.py`, `adapters/qwen.py`, `adapters/mistral.py` | MODIFY |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the `run_clock` slot | FR-3, NFR-1 | two runs' prompts differ before the constitution, at the metadata's timestamp |
| CB-2 | Anthropic's automatic caching | FR-1 | the request has no `cache_control` |
| CB-3 | the cache key | FR-2, NFR-2, NFR-3 | no request carries `prompt_cache_key` |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit + integration | the rendered prompt of a real review handler ends with the timestamp, and two runs a moment apart are equal up to it; the metadata holds no date; decomposition still gets `date_iso` |
| CB-2 | integration | through `build_router` and `fake_httpx2`: `generate` and each round of a tool loop send `cache_control`, and the prompt text sent is unchanged |
| CB-3 | integration + e2e | first-party OpenAI and Mistral send the same key for two calls of one step type, a different one for another step type or project; the key contains neither name; `openai-compatible` and Qwen send none. e2e: `sw review` twice on one spec sends one key and the same prompt start both times |

## Mutants (into `C-FLOW-14_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | the timestamp left in the metadata; the clock slot left out of a profile's order | CB-1 tests |
| CB-2 | `cache_control` dropped from the tool rounds only; from `generate` only | CB-2 tests |
| CB-3 | the key from the project only; the names in clear; `sends_cache_key` true on `openai-compatible` | CB-3 tests |

## Research Notes

- Slot order: `_DEFAULT_TAG_ORDER` (`prompt/render.py:124-138`) for the default profile; each named
  profile's `order` (`handlers/_profiles.py:53-107`) is the only source of its order, and
  `RenderProfile.__post_init__` refuses an active slot missing from `order` (`prompt/profiles.py:66`).
- The metadata is rendered by `ProjectMetadataPromptAdapter` (`prompt/adapter.py:111-124`) as JSON of
  the whole model; `date_iso` is set once per `RunContext` (`handlers/run_context.py:218`).
- `task_type` is set per call by each handler (`collector.py`, `_capture` docstring); the collector
  holds the project (`TelemetryCollector._project`).
- Adapters: Anthropic builds `kwargs` at `anthropic.py:117` and `:238`; OpenAI at `openai.py:150-170`
  and the tool loop; Mistral's one request is `_request` (`mistral.py:74-86`). `OpenAICompatibleAdapter`
  (`openai.py:307`) and `QwenAdapter` (`qwen.py:14`) subclass `OpenAIAdapter`.
- SDKs (checked 2026-10-18): `anthropic` 1.8.0 `cache_control`, `openai` 3.19.2 `prompt_cache_key`,
  `mistralai` `prompt_cache_key`.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| — | "Step type" in the agreed key (design FR-2) | `task_type`, the step's kind; a step's name differs per pipeline |

## Backlog

none
