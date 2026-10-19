# Implementation Plan: Cached Input Tokens [SF-02: The cache warnings]
- **Feature ID**: C-FLOW-14
- **Sub-Feature**: SF-02 — The cache warnings
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-14/C-FLOW-14_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-14/C-FLOW-14_sf02_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-19

**FRs owned**: FR-4, FR-5 · **Depends on**: SF-01 (committed `1df7aef6`)

## Shape

| Piece | Where | Tag |
|---|---|---|
| a request's **start**: a hash of its system text and of its first message up to the run clock — what a cache can hold from run to run | `collector.py` | NEW |
| when each start was last sent: a table `llm_prompt_start` (server, model, start hash, last sent), written by the collector, never holding prompt text (Q2); a row goes 7 days after its start was last sent (Q3) | `store.py`, `collector.py` | NEW |
| a reply with cached tokens whose start was last sent more than twice the cached-read rule's `max_age_seconds` ago (Q1) warns once per model: the provider may keep caches longer than the shipped rule says | `collector.py` (`_check_cache_rule`), `prices.py` (`rule_break`) | MODIFY |
| a reply from a local server with no cached count warns once per server: "if this is vLLM, start it with `--enable-prompt-tokens-details`" | `collector.py` (`_capture`) | MODIFY |
| the user guide says the same | `docs/user_guides/1_installation_and_setup.md` | MODIFY |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the vLLM hint | FR-5 | a GB10 reply without a cached count says nothing |
| CB-2 | the start, its last-sent time, the lifetime warning | FR-4 | a cache hit long after the start was last sent says nothing |

| CB | Tier | Test |
|---|---|---|
| CB-1 | integration | through `build_router` and `fake_httpx2`: a GB10 reply without `prompt_tokens_details` warns once over three calls; one with it, or llama.cpp's `timings`, does not; a hosted server never gets the hint |
| CB-2 | integration | over a real database: a cached reply within twice the lifetime says nothing; one after it warns once per model, also when the earlier call was in another process; another start does not count as the same; the table holds no word of the prompt |

## Mutants (into `C-FLOW-14_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | the hint on every call; on a hosted server; never | CB-1 tests |
| CB-2 | the lifetime comparison inverted; the run clock left in the start; the last-sent time never updated | CB-2 tests |

## Research Notes

- `_check_cache_rule` (`collector.py:289-305`) already warns once per model on a broken prefix or
  requirement through `prices.rule_break`; FR-4 adds the lifetime to the same check.
- Lifetimes in the shipped list: Anthropic cached read 300 s (renewed free on every hit), OpenAI
  1,800 s ("about 30 minutes"), Gemini and Mistral none (`catalogue_data/models.toml`).
- The run clock is the prompt's last slot (`SF-01`), so the text before `<run_clock>` is the part a
  cache can hold across runs.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | How far past the rule's lifetime a hit must come to warn | more than twice the lifetime `[agreed 2026-10-19]` |
| Q2 | Where the last-sent times are kept (design AD-2 said: in the process) | in the database, one row per server, model and start: a process forgets between runs, and runs are what the warning is for `[agreed 2026-10-19]` |
| Q3 | How long a start's row is kept | 7 days after it was last sent, then deleted `[agreed 2026-10-19]` |

## Dev notes

- CB-2: SF-01 made TECH-074's rule check wrong: Anthropic now sends a breakpoint and Mistral a cache
  key, but the check assumed nothing is sent, so every such cache hit would have warned. Each adapter
  now says what it sent (`cache_sent`), and the check uses it; the TECH-074 test that expected the
  warning now expects none.
- CB-1: the hint skips streams, whose usage is estimated; a stream test with too short a text had an
  estimate of zero and could not fail, and was lengthened.

## Backlog

none
