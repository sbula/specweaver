# Implementation Plan: The Cost Ledger Prices Cached Input at the Full Price [SF-02: The cached counts]
- **Feature ID**: TECH-074
- **Sub-Feature**: SF-02 — The cached counts
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-074/TECH-074_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-074/TECH-074_sf02_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-18

**FRs owned**: FR-3, FR-4, FR-6, FR-10, FR-11 · **Depends on**: SF-01 (committed `46638028`)

## Shape

| Piece | Where | Tag |
|---|---|---|
| `TokenUsage` gains `cached_read_tokens` and `cache_write_tokens`, `None` = unknown (NFR-1); `prompt_tokens` stays the whole prompt, cached included; a sum is unknown when either side is | `infrastructure/llm/models.py` | MODIFY |
| Anthropic: `cache_read_input_tokens`, `cache_creation_input_tokens`, both added to `prompt_tokens` (Anthropic leaves them out of `input_tokens`) | `adapters/anthropic.py` (`_accumulate_usage`, `generate`) | MODIFY |
| OpenAI, Qwen, vLLM (`openai-compatible`): `prompt_tokens_details.cached_tokens`; writes 0, as these bill no write; absent details → unknown | `adapters/openai.py` | MODIFY |
| llama.cpp: `timings.cache_n`, outside `usage` (the SDK keeps it as an extra field) | `adapters/openai.py` | MODIFY |
| Mistral: `prompt_tokens_details.cached_tokens`, read defensively like its other fields | `adapters/mistral.py` | MODIFY |
| Gemini: `cached_content_token_count`, inside `prompt_token_count`; writes 0 | `adapters/gemini.py` (`_extract_usage`) | MODIFY |
| a stream's usage stays estimated from text: its cached counts are unknown | `collector.py` | — |
| `estimate_cost`: uncached input × input, cached reads × their price, writes × theirs, output × output; a cached kind with no price → the input price, which can only overstate | `telemetry.py` | MODIFY |
| which price of a kind applies: the one whose rule fits the call (the prompt-length tier; the lifetime the request asked for — none yet, so the shortest) | `prices.py` (`PriceBook.price_for`) | NEW |
| `llm_usage_log` gains `cached_read_tokens`, `cache_write_tokens` (NULL = unknown) and `local` (NULL on older rows), added at start-up; a new table `llm_usage_price` (usage id, token kind, USD per 1M, source) holds one line per kind that priced the call — the invoice line of Q1 | `store.py`, `db_bootstrap.py` | MODIFY |
| `sw usage` shows a *Cached* column, unknown never shown as 0 (`get_usage_summary` sums the known and counts the unknown); `sw costs` says when a cached kind falls back to the input price | `interfaces/cli.py`, `store.py` | MODIFY |
| a local call with no price you set costs *not applicable*, never *unknown*: its row has `local` set and no cost, and `sw usage` shows `n/a` | `telemetry.py`, `interfaces/cli.py` | MODIFY |
| a cached count that breaks its rule warns once per model: cached tokens under the minimum prefix, or cached without the breakpoint or key the rule requires (SpecWeaver sends neither yet); the lifetime check is `C-FLOW-14`'s | `collector.py` | NEW |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | `TokenUsage` and the five adapters' cached counts | FR-3 | every adapter drops the cached field; Anthropic's prompt total misses its cached part |
| CB-2 | the ledger columns, each kind priced, the price record, local calls | FR-4, FR-10 | a call with 9,000 of 10,000 prompt tokens cached is billed as 10,000 at the input price |
| CB-3 | the *Cached* column, the fallback note in `sw costs`, the rule warning | FR-6, FR-11 | `sw usage` has no cached column; a cache below the minimum prefix is silent |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit + integration | each adapter over `tests/fake_http.py` with a recorded reply carrying the cached field: counts read; field absent → unknown; Anthropic total = input + read + write; a tool loop sums its rounds |
| CB-2 | integration | a call through `build_router` to a faked hosted server: the ledger row holds the cached counts and the cost at each kind's price; an older database gains the columns at start-up and keeps its rows; unknown cached count → priced as uncached input |
| CB-3 | e2e + integration | `sw usage` over a real database shows the *Cached* column and *unknown*; a reply caching 200 tokens of a 300-token prompt against a 512-token minimum warns once |

## Mutants (into `TECH-074_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | each adapter's cached read → 0; Anthropic's prompt total without the cached part; unknown → 0 | CB-1 tests |
| CB-2 | cached reads at the input price; the fallback → 0; the column add skipped | CB-2 integration |
| CB-3 | the column dropped; the minimum-prefix comparison inverted; warn every call, not once | CB-3 tests |

## Research Notes

- Usage mapping today: Anthropic `anthropic.py:35-46`, `:119-123`; OpenAI `openai.py:36-42`, `:157-161`;
  Mistral `mistral.py:33-41`; Gemini `gemini.py:237-245`. Qwen and `openai-compatible` servers use the
  OpenAI adapter (`QwenAdapter(OpenAIAdapter)`, `adapters/registry.py`).
- A failed tool loop keeps its usage on the exception (`errors.py:89`, `attach_usage`); cached counts
  ride along.
- A stream is counted from its text (`collector.py:202-222`), so its cached counts are unknown.
- `sw usage`: `interfaces/cli.py:288-360`, summed by `LlmRepository.get_usage_summary` (`store.py:264`).
- Columns are added at start-up, never by Alembic (`db_bootstrap.py`, `_add_call_status`).

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | How a ledger row records the prices that priced it, when a settings price has no row (NFR-3) | the row keeps the four prices it used and each one's source, as an invoice line `[agreed 2026-10-18]` |
| Q2 | The cost of a local call when you set a price for its model | that price; with none, *not applicable* `[agreed 2026-10-18]` |
| Q3 | Where the lifetime part of FR-11 is checked | `C-FLOW-14`, which tracks prompt prefixes; SF-02 checks the minimum prefix and the requirement `[agreed 2026-10-18]` |

## Dev notes

- CB-1: OpenAI also reports `cache_write_tokens` in `prompt_tokens_details`; it is read. Mistral's SDK
  keeps `prompt_tokens_details` as an extra field. Gemini without `cached_content_token_count` is
  unknown, not 0 (NFR-1).
- CB-1: nothing proved that the Anthropic, Gemini and Mistral tool loops add up every round; each has a
  test now, and a Mistral assertion that could not fail (`total_tokens >= 0`) is exact.
- CB-2: the four new record fields are grouped as `UsageRecord.billed`, to keep the class under the
  15-attribute limit.
- CB-3: the `sw usage` headers are shorter (`Task`, `Prompt`, `Output`, `Total`, `Secs`) so the extra
  column fits 80 characters. Two older journey parsers read cells by count and were fixed to read by
  position. The *Cached* text and the `n/a` cost are checked by cell tests, as a table cell is
  width-bound.

## Backlog

none
