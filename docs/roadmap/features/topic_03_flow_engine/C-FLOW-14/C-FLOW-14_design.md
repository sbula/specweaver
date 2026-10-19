# Design: Cached Input Tokens

- **Feature ID**: C-FLOW-14
- **Epic**: Topic 03 (Flow Engine) · US-16 add-on "Centralized Model Table"
- **Status**: APPROVED by the user 2026-10-18
- **Origin**: 2026-10-17, the user's question on cached input tokens —
  [research](../../../../analysis/prompt_caching_2026-10-17.md). Precondition `TECH-074` (closed
  `968e51f9`): cached counts are read, each kind is priced, the cache rules are stored.

## Feature Overview

C-FLOW-14 makes SpecWeaver's prompts hit the providers' caches, where a reused token costs about a
tenth. Today Anthropic never caches, so every tool round pays again for the whole history it
resends; and a microsecond timestamp near the start of every prompt makes each new run miss the cache
on everything after it. It touches the adapters' requests and the prompt's slot order for the
timestamp only; it does not reorder the prompt otherwise, and makes no claim about answer quality.

| Path | Who walks it | Span |
|---|---|---|
| a tool loop on Anthropic reuses its earlier rounds from the cache | any agent step | this feature |
| a second run of the same step type on OpenAI or Mistral starts from the cache | every LLM step | this feature, seam with the prompt builder |
| `sw usage` shows the cached tokens these calls report | the user | `TECH-074` ✅ — already proven |
| a cache hit that outlived its rule warns | the user, via the log | this feature, seam with `TECH-074` FR-11 |

## Research Findings

### Codebase Patterns

- One user message carries the prompt, in the slot order of `prompt/render.py:124-138`;
  `RenderProfile.order` (`prompt/profiles.py:43`) is the only source of the order per profile.
- `project_metadata` is the third slot and carries `date_iso`, a microsecond timestamp
  (`core/flow/handlers/run_context.py:218`); every other metadata field is stable across runs.
  `date_iso` is also read by decomposition (`handlers/decompose.py:83`, `decomposition_artifacts.py:236`).
- Tool loops resend the whole message list each round (`adapters/anthropic.py:234-250`,
  `openai.py:248-272`); the Anthropic adapter sends no `cache_control`, none sends a cache key.
- The cache rules and the warning on a broken rule exist (`TECH-074` FR-9, FR-11:
  `prices.rule_break`, `TelemetryCollector._check_cache_rule`); the lifetime part was left to here.

### External Tools

The installed SDKs accept every field this needs (checked 2026-10-18): `anthropic` 1.8.0
`messages.create(cache_control=...)`, `openai` 3.19.2 `chat.completions.create(prompt_cache_key=...)`,
`mistralai` `prompt_cache_key`. Provider behaviour is in the research note above.

### Blueprint References

Anthropic's automatic caching places one breakpoint at the last cacheable block and moves it as the
conversation grows; each provider advises static content first (not adopted here, see Non-Goals).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Anthropic caches | Anthropic adapter | SHALL send automatic caching (`cache_control`, one breakpoint that moves with the conversation) on every request, tool rounds included `[agreed 2026-10-18]`, with the 5-minute lifetime `[agreed 2026-10-18]` | a tool loop pays the full price for each round's new part only |
| FR-2 | A cache key for runs that start alike | OpenAI and Mistral adapters | SHALL send `prompt_cache_key` derived from the project and the step type `[agreed 2026-10-18]`, to first-party OpenAI and Mistral servers only | runs of one step type share a cache; Mistral caches at all |
| FR-3 | The timestamp at the end | Prompt builder | SHALL render the run's timestamp at the end of the prompt, not in the metadata at its start `[agreed 2026-10-18]`; `date_iso` stays for decomposition | everything before it is the same from run to run |
| FR-4 | An outlived cache warns | Collector | SHALL warn, once per model, when a reply reports cached tokens although the same start was last sent more than twice the rule's lifetime ago `[agreed 2026-10-19]` | a provider's changed lifetime is noticed from the calls (`TECH-074` FR-11) |
| FR-5 | vLLM's missing count is explained | Collector | SHALL warn once per local server whose reply carries no cached count, naming `--enable-prompt-tokens-details` `[agreed 2026-10-18]`; the user guide says the same | the GB10's cache is visible without reading the guide |

## Requirement–Surface Bindings

| FR | Binds to | Verified how |
|---|---|---|
| FR-1 | `AnthropicAdapter.generate`, `.generate_with_tools` request kwargs | read `adapters/anthropic.py:117`, `:238`; SDK signature checked |
| FR-2 | `OpenAIAdapter` and `MistralAdapter` request kwargs, `GenerationConfig` (step type, project) | read `adapters/openai.py`, `mistral.py`; `models.py` `GenerationConfig` |
| FR-3 | `_DEFAULT_TAG_ORDER`, the profiles' `order`, the metadata renderer | read `prompt/render.py:124`, `prompt/profiles.py:43` |
| FR-4 | `TelemetryCollector._check_cache_rule`, the rule's `max_age_seconds` | read `collector.py`, `prices.py` (`TECH-074`) |
| FR-5 | `TelemetryCollector._capture`, the server's `private` flag | read `collector.py` |

## Non-Functional Requirements

| # | NFR | Rule |
|---|---|---|
| NFR-1 | The ask is unchanged | Apart from where the timestamp stands, the model gets the same text as before |
| NFR-2 | A cache key names nothing | The key is a hash; neither the project nor the step type is sent in clear |
| NFR-3 | Only where it is understood | No cache field goes to a server that may not know it: `openai-compatible` servers get none |

## External Dependencies

None new.

## Architectural Decisions

| # | Decision | Why |
|---|---|---|
| AD-1 | The prompt order stays instructions first `[agreed 2026-10-18]`; moving stable parts first is left to the quality score `A-FLOW-01` lists as open | its effect on answers cannot be judged until quality can be measured |
| AD-2 | The lifetime check keeps, in the database, when each prompt start was last sent: a hash of the start, never its text, kept 7 days after it was last sent `[agreed 2026-10-19]` | runs are separate processes, and a hit after a run is what reveals a changed lifetime |

## ROI Analysis

### Investment Cost

Two small sub-features in the adapters, the prompt builder and the collector.

### Returns

A tool loop of *n* rounds over a history *H* pays about *n × H* input today; with caching about
1.25 *H* once and 0.1 *H* per later round. Repeated runs of one step type on OpenAI, Gemini and
Mistral reuse their stable start.

### Risk Assessment

| Risk | Mitigation |
|---|---|
| Caching under-counts tokens | prevented by `TECH-074`: Anthropic's cached part joins the prompt total |
| A cache write costs 1.25× and is never read | the 5-minute lifetime; FR-4 and `sw usage`'s *Cached* column show whether hits happen |

### Refactoring Opportunities

None needed.

## Developer Guides Required

None; the user guide gains the vLLM flag (FR-5).

## Non-Goals

- Reordering the prompt for caches shared across step types (AD-1).
- The 1-hour cache, fixed breakpoints, Gemini's explicit caches (they carry a storage fee).

## Sub-Feature Breakdown

### SF-01: Prompts that hit the cache

FR-1, FR-2, FR-3. Inputs: the request, the step type, the project. Output: requests with the cache
fields and a stable start.

### SF-02: The cache warnings

FR-4, FR-5. Inputs: each reply's cached count, the rules, the server. Output: one warning each.

## Execution Order

SF-01, then SF-02 (FR-4 needs the caches SF-01 creates to be testable end to end).

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Prompts that hit the cache | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | The cache warnings | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Now**: design approved 2026-10-18.
**Next**: the user's sign-off. SF-01 and SF-02 committed; every FR and NFR is cited by a test.
