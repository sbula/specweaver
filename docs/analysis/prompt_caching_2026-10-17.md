# Cached input tokens — what the providers offer and what SpecWeaver does (2026-10-17)

Asked by the user 2026-10-17: model APIs bill three kinds of tokens — input, output and **cached
input** (a prefix sent before and reused, billed far cheaper). How should SpecWeaver measure, price
and above all *hit* the cache? Provider facts were fetched from the official docs on 2026-10-17; the
SpecWeaver facts cite the code as it stood at `da84d184`.

## The providers

| Provider | How it caches | Smallest prefix | How long it lives | Where the response reports it | Price of a cached read |
|---|---|---|---|---|---|
| Anthropic | opt-in: `cache_control`, one top-level breakpoint that moves with the history, or up to 4 on blocks | 512–4,096 tokens by model | 5 min, renewed free on each hit; or 1 h | `cache_read_input_tokens`, `cache_creation_input_tokens`; **`input_tokens` then counts only what follows the last breakpoint** | 0.05–0.1× input; a write costs 1.25× (5 min) or 2× (1 h) |
| OpenAI | automatic; newer models also take explicit breakpoints; `prompt_cache_key` keeps requests on one cache | 1,024 tokens | about 30 min | `prompt_tokens_details.cached_tokens`, inside the prompt total | 0.1× |
| Gemini | implicit, on by default; explicit caches carry a storage fee | 4,096 tokens | not stated | `cached_content_token_count`, inside `prompt_token_count` | 0.1× |
| Mistral | opt-in with `prompt_cache_key`; a hit is not guaranteed | 64-token blocks | not documented | `prompt_tokens_details.cached_tokens` | 0.1× |
| vLLM (GB10) | prefix caching on by default | one block | until evicted | only with `--enable-prompt-tokens-details`, off by default | local: saves time, not money |
| llama.cpp | `cache_prompt` on by default, same slot only | — | server lifetime | `timings.cache_n`, outside `usage` | local |

Sources: Anthropic `platform.claude.com/docs/en/build-with-claude/prompt-caching` and pricing; OpenAI
`developers.openai.com/api/docs/guides/prompt-caching`; Gemini `ai.google.dev/gemini-api/docs/caching`
(updated 2026-10-13); Mistral `docs.mistral.ai/studio/conversations/advanced/prompt-caching`; vLLM
`docs.vllm.ai` config and issues #44377, #44961; llama.cpp `tools/server/README.md`.

## SpecWeaver today

- `TokenUsage` holds only prompt, completion and total tokens (`infrastructure/llm/models.py:102-115`);
  the ledger has no cache column (`store.py:30-34`). No adapter reads a cache field, and the Anthropic
  adapter never sends `cache_control`.
- `estimate_cost` prices every prompt token at the full input price (`telemetry.py:52-64`). The shipped
  catalogue kept the **highest** tier, so Anthropic's "input" price is the 5-minute *write* price — 25%
  above base input (`catalogue_data/models.toml:5`).
- The brake's worst case is the prompt × 1.25 plus the whole output cap, at that price, reserved again
  every tool round (`collector.py:40-50`, `106-111`, `170-176`).
- The prompt is one user message: instructions, overrides, project metadata, constitution, standards,
  plan, topology, files, context (`prompt/render.py:124-138`). The project metadata carries a
  microsecond timestamp (`run_context.py:218`), right after the instructions: the prefix is stable
  inside a run but changes between runs ahead of the constitution and standards. Instructions differ
  by step type, so a review and a generation share no prefix.
- Tool loops resend the whole growing message list every round (`anthropic.py:234-250`,
  `openai.py:248-272`, `gemini.py:298-331`); mentioned files are appended at the end.

## The gaps, by money

1. Anthropic never caches — a tool loop's resent history is paid in full every round.
2. Turning it on without reading `cache_read` / `cache_creation` would *under*-count tokens and cost,
   because `input_tokens` shrinks to the part after the breakpoint.
3. OpenAI and Gemini already cache automatically, but the ledger prices the cached part at full price
   and overstates spend.
4. Anthropic's uncached input is priced 25% high (the write price).
5. The timestamp early in the prompt makes every new run miss the cache on the constitution and
   standards.
6. Mistral never caches without `prompt_cache_key`.
7. On the GB10, vLLM's cached tokens are invisible without `--enable-prompt-tokens-details` (time, not
   money).

## Decisions this leaves to the user

Anthropic breakpoints (one automatic, or explicit after the stable prefix); a 5-minute or 1-hour cache;
separate cache-read and cache-write prices in the catalogue, or one highest price; whether cached tokens
count fully toward the token limit; where the timestamp goes; whether stable parts move ahead of the
instructions so step types share a prefix; whether and how to send `prompt_cache_key`.
