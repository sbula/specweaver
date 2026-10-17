# Design: The Cost Ledger Prices Cached Input at the Full Price

- **Feature ID**: TECH-074
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: 2026-10-17, the user's question on cached input tokens; measurements in
  [prompt_caching_2026-10-17.md](../../../../analysis/prompt_caching_2026-10-17.md). A defect in delivered
  work (`C-FLOW-01` ✅ the cost ledger, `C-FLOW-13` ✅ the prices), so it is not an edit to either.

## Problem Statement

Every provider bills reused (cached) input at about a tenth of the input price; SpecWeaver records and
prices none of it:

- `TokenUsage` has only prompt, completion and total tokens (`infrastructure/llm/models.py:102-115`);
  `llm_usage_log` has no cached column. No adapter reads a cache field — OpenAI's
  `prompt_tokens_details.cached_tokens`, Gemini's `cached_content_token_count`, Anthropic's
  `cache_read_input_tokens` / `cache_creation_input_tokens`, Mistral's cached tokens.
- `estimate_cost` prices every prompt token at the full input price (`telemetry.py:52-64`). OpenAI and
  Gemini already cache automatically, so `sw usage` and `sw costs` show more spend than was billed.
- The catalogue's Anthropic input price is the 5-minute cache-**write** price, 25% above base input
  (`catalogue_data/models.toml:5` keeps "the highest tier").

## Candidate Approaches (not yet designed)

- `TokenUsage` gains cached-read and cache-write counts; each adapter maps its provider's fields; the
  ledger stores them; `estimate_cost` prices each kind at its own rate.
- The catalogue carries base input, cached-read and cache-write prices per model.

## Non-Goals (proposed, pending design)

- Making prompts hit a cache — that is `C-FLOW-14`, sequenced after this ticket.

## Next Step

Run `specweaver-design TECH-074`. It must land before `C-FLOW-14` turns on Anthropic caching: with
caching on and this unread, Anthropic's `input_tokens` shrinks to the part after the breakpoint and the
ledger *under*-counts tokens and money.
