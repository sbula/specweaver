# Design: The Cost Ledger Prices Cached Input at the Full Price

- **Feature ID**: TECH-074
- **Epic**: Topic 07 (Technical Debt)
- **Kind**: bugfix, with the price model it needs
- **Status**: APPROVED by the user 2026-10-18
- **Origin**: 2026-10-17, the user's question on cached input tokens; measurements in
  [prompt_caching_2026-10-17.md](../../../../analysis/prompt_caching_2026-10-17.md). A defect in delivered
  work (`C-FLOW-01` ✅ the cost ledger, `C-FLOW-13` ✅ the prices), so it is not an edit to either.

| | |
|---|---|
| Fixes | `C-FLOW-01` (the ledger) · `C-FLOW-13` (the prices) |
| Enables | `C-FLOW-14` — the cache rules this ticket stores are what it shapes prompts by |
| Not touched | shaping prompts to hit a cache (`C-FLOW-14`) · choosing models (`A-FLOW-01`) |

## What is wrong

Every provider bills reused (cached) input at about a tenth of the input price. SpecWeaver reads, stores
and prices none of it:

- `TokenUsage` has only prompt, completion and total tokens (`infrastructure/llm/models.py:102-115`);
  `llm_usage_log` has no cached column; no adapter reads a cache field.
- `estimate_cost` prices every prompt token at the input price (`telemetry.py:52-64`). OpenAI and Gemini
  already cache on their own, so `sw usage` and `sw costs` overstate spend.
- The catalogue keeps one input price, "the highest tier", so Anthropic's input is its cache-**write**
  price, 25% above base input (`catalogue_data/models.toml:5`).
- Prices change at the provider whether SpecWeaver knows or not; the hand-kept list follows only with a
  release.

## The price model `[agreed 2026-10-18]`

A price belongs to **a model at a host** (`model@server`): the same open-weight model costs differently at
different hosts, and nothing on a private server costs money. A price row is the **default** for its token
kind, or a **special** price that applies only when its **rule** holds; a token that does not meet the rule
is billed at the default.

```
offering (id, model, host, context, max_output, tool_calls, …)              one row per model@host
price    (id, offering_id, token_kind, usd_per_million,
          valid_from, source, rule_id NULL)                                  NULL rule = the default
rule     (id, min_prefix_tokens NULL, max_age_seconds NULL,
          min_prompt_tokens NULL, requires)                                  requires: nothing | breakpoint | cache_key
```

`token_kind` is a fixed list in code — `input`, `output`, `cached_read`, `cache_write` — not a table.

Opus 5.5 at Anthropic, as rows: input 4.00 (default) · output 20.00 · cache_write 5.00 (default, 5 min) ·
cache_write 8.00 (rule: max_age 3600 s) · cached_read 0.20 (rule: min_prefix 512, max_age 300 s, requires
breakpoint). A long-prompt tier is a special price whose rule sets `min_prompt_tokens`.

**The exactly-one check**, on every insert or update and for every point in time: a **hosted** offering
has exactly one default price per token kind; a special price must carry a rule; two special prices with the same rule are refused. A
**local** offering (a `private` server) has no price rows — its cost is *not applicable*, which is not
*unknown* `[agreed 2026-10-18]`.

Where it lives `[agreed 2026-10-18]`: provider facts are machine-written and change outside the user's
control, so they live in the **database**; the user's settings stay in the **settings files** and win
(a correction there is a price with source *your settings*). The shipped catalogue remains the offline
starting point. This supersedes `C-FLOW-13` AD-7 (*never fetched at runtime*) for provider facts only: a
provider applies a new price whether SpecWeaver has it or not, so waiting for a release keeps the ledger
and the brake wrong.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Prices per model at a host | Price store | SHALL hold offerings, prices and rules as above, with the exactly-one check refusing any insert or update that breaks it `[agreed 2026-10-18]` | every call meets exactly one price per token kind |
| FR-2 | Your settings win | Price store | SHALL apply a price from the machine or project settings file over a downloaded or shipped one `[agreed 2026-10-18]` | a deliberate correction is never overwritten |
| FR-3 | Cached tokens are read | Each adapter | SHALL fill `cached_read` and `cache_write` from its provider's fields — Anthropic `cache_read_input_tokens` / `cache_creation_input_tokens` (and add them to the prompt total, which Anthropic leaves out), OpenAI and Mistral `prompt_tokens_details.cached_tokens`, Gemini `cached_content_token_count`, vLLM likewise when reported, llama.cpp `timings.cache_n`; a server that does not report it records *unknown*, never 0 | the ledger knows what was billed as cached |
| FR-4 | Each kind at its own price | Ledger | SHALL price uncached input, cached reads, cache writes and output each at its own price; a cached kind with no price of its own is priced at the input price, which can only overstate, and `sw costs` says so; each ledger row records the price rows that priced it `[agreed 2026-10-18]` | `sw usage` and `sw costs` show what was really billed, and an old row stays explainable after a price change |
| FR-5 | The brake reserves the most | Spend brake | SHALL reserve a call's worst case at the highest price among its prompt token kinds; a token limit counts every token, cached included `[agreed 2026-10-18]` | turning a cache on never lets the brake reserve too little |
| FR-6 | Cached tokens are shown | `sw usage` | SHALL show a *Cached* column beside the prompt tokens `[agreed 2026-10-18]` | the user sees whether the cache works |
| FR-7 | Prices follow the providers | Price refresh | SHALL refresh the prices of the offerings the roles use from models.dev when they are older than 24 hours, at the start of a command that calls a model, and on `sw costs refresh`; a change is reported, never held for approval `[agreed 2026-10-18]` | the ledger and the brake use the price the provider bills |
| FR-8 | A bad download changes nothing | Price refresh | SHALL refuse a downloaded price that is missing, zero, negative or breaks the exactly-one check, keep the last good price, and warn; offline, the last prices stay, with a warning | a broken source never corrupts the money figures |
| FR-9 | Cache rules are kept | Price store | SHALL hold each offering's cache rule — minimum prefix, lifetime, what the request must send — from the shipped catalogue, which models.dev does not carry | `C-FLOW-14` can tell before a call whether a token will count as cached |
| FR-10 | Local models are covered | Ledger, store | SHALL record cached tokens for local calls and their cost as *not applicable*; a hosted offering without a default price is refused, a local one needs none | the GB10's cache is visible; local calls never read as unpriced |
| FR-11 | A changed rule is noticed | Ledger | SHALL warn when a response's cached count disagrees with the offering's rule — cached tokens below its minimum prefix, or after its lifetime `[agreed 2026-10-18]` | a rule a provider changed is found from the calls, without a release |

## Non-Functional Requirements

| # | NFR | Rule |
|---|---|---|
| NFR-1 | Unknown stays unknown | An unreported cached count is unknown, never 0; an unpriced hosted model is unknown, never free (`C-FLOW-13` FR-12) |
| NFR-2 | Telemetry never breaks a run | A refresh or a price lookup that fails falls back to the last good price and is logged |
| NFR-3 | One writer of prices | Only the refresh and the start-up seed write provider rows; settings are read, never copied into the database |

## Requirement–Surface Bindings

| FR | Binds to | Verified how |
|---|---|---|
| FR-3 | `TokenUsage` and each adapter's usage mapping | read `infrastructure/llm/models.py:102`, `adapters/anthropic.py:119`, `openai.py:36`, `mistral.py:33`, `gemini.py:237` |
| FR-4 | `estimate_cost(usage, facts)` and its callers | read `telemetry.py:52-64`, `collector.py` (`_row`) |
| FR-5 | `TelemetryCollector._worst_of` | read `collector.py:109` |
| FR-2 | `ModelFacts` prices, `sw costs set` / `reset` | read `core/config/llm_settings.py:128`, `bootstrap/llm_settings_writer.py:36` |
| FR-7 | models.dev `api.json` → provider → models → `cost` (`input`, `output`, `cache_read`, `cache_write`, nested tiers) | read the removed `scripts/update_model_catalogue.py` (`e39ebd7e^`) |
| FR-1 | tables added at start-up like the other columns, never Alembic | read `core/config/bootstrap/db_bootstrap.py` |

## Sub-Feature Breakdown

| SF | Does | FRs | Depends on |
|---|---|---|---|
| SF-01 | The price model: offerings, prices, rules, the check, seeded from the shipped catalogue; settings win; the brake's highest price | FR-1, FR-2, FR-5, FR-9 | — |
| SF-02 | The cached counts: adapters, `TokenUsage`, the ledger, each kind priced, the *Cached* column, local calls | FR-3, FR-4, FR-6, FR-10, FR-11 | SF-01 |
| SF-03 | The refresh: models.dev for the offerings in use, 24 hours, reported, refused when bad, offline | FR-7, FR-8 | SF-01 |

## Non-Goals

- Shaping prompts to hit a cache, and per-model cache lifetimes beyond the shipped rules — `C-FLOW-14`.
- Reconciling against the provider's invoice.
- Downloading models nobody's roles use.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | The price model | — | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-02 | The cached counts | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-03 | The refresh | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Now**: SF-01 plan approved 2026-10-18.
**Next**: SF-01 dev, CB-1.
