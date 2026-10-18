# Implementation Plan: The Cost Ledger Prices Cached Input at the Full Price [SF-01: The price model]
- **Feature ID**: TECH-074
- **Sub-Feature**: SF-01 — The price model
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-074/TECH-074_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-074/TECH-074_sf01_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-18

**FRs owned**: FR-1, FR-2, FR-5, FR-9 · **Depends on**: none

## Shape

| Piece | Where | Tag |
|---|---|---|
| tables `llm_offering`, `llm_price`, `llm_price_rule`, created with the other LLM tables | `infrastructure/llm/store.py` | NEW |
| `TokenKind` (input, output, cached_read, cache_write) | `infrastructure/llm/models.py` | NEW |
| `check_prices(rows)`: per hosted offering and point in time, exactly one default input and output, at most one default cached read and cache write (FR-4 lets a cached kind fall back to input); a special has a rule; no two specials share a rule; a local offering has no rows — pure, run by the one writer before it commits (NFR-3) | `infrastructure/llm/prices.py` | NEW |
| the shipped catalogue gains four prices and a cache rule per hosted model (schema 2): base input, output, cached read, cache write, and specials (Anthropic's 1-hour write) | `catalogue_data/models.toml`, `catalogue.py` | MODIFY |
| the start-up seeds the catalogue's rows (source `catalogue`, valid from its `checked` date), idempotent, through `check_prices` | `core/config/bootstrap/db_bootstrap.py` | MODIFY |
| `PriceBook`: the offering's rows, then the settings file's prices over them; `default(kind)`, `price_for(kind, situation)`, `highest_prompt_price()` | `infrastructure/llm/prices.py` | NEW |
| an offering is a model at a host: the provider kind for a first-party API, the server's name for an `openai-compatible` host | `PriceBook` lookup | NEW |
| the collector's one price seam, `prices=lambda model: …` (`resolve.py:214`), returns the `PriceBook`; the brake's worst case at `highest_prompt_price()`; the ledger keeps input and output at their defaults until SF-02 splits the kinds | `resolve.py` (`_adapter`, `_scope`), `collector.py` (`_worst_of`, `_row`), `telemetry.py` | MODIFY |
| `sw costs` shows the `PriceBook`'s defaults and their source (catalogue or your settings), so the screen and the ledger read one source | `interfaces/cli.py:65` (`_price_source`) | MODIFY |
| a hosted model still needs a default input and output price to run | `resolve.py` (`_check_bounded`) | MODIFY |
| the settings file accepts `usd_per_million_cached_read` and `usd_per_million_cache_write` beside the old two `[agreed 2026-10-18]` | `core/config/llm_settings.py` (`ModelFacts`) | MODIFY |

A price holds from its `valid_from` until a later row of the same offering, kind and rule replaces it,
so "every point in time" means: no two rows share offering, kind, rule and `valid_from`, and a cached
kind never starts before its input does. The `PriceBook` is read once per resolver from the LLM
database, the one the ledger already writes; a lookup that fails falls back to the catalogue and logs
it (NFR-2).

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the tables, `TokenKind`, `check_prices` | FR-1 | an overlap, a gap, a special without a rule each pass today — there is no check |
| CB-2 | the catalogue's four prices and rules, the seed, `PriceBook` with settings winning | FR-2, FR-9 | Anthropic's input reads 5, the write price; no cached price exists |
| CB-3 | the brake and the run check read `PriceBook` | FR-5 | the worst case uses the input price, below a cache write once caching is on |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit | `check_prices` on rows: overlap, gap, special without rule, two specials with one rule, a local offering with no rows, two defaults in different periods |
| CB-2 | integration | a real database seeded at start-up; `PriceBook` reads Opus at 4 / 20 / 0.20 / 5 and its 1-hour write at 8; a machine-file price wins and is never written to the database; a second start changes nothing; a catalogue that breaks the check is refused and the start-up warns; `sw costs` shows 4, not 5 |
| CB-3 | integration | a collector over the real `PriceBook` reserves at the cache-write price; a hosted model with no default price is refused at the run check |

## Mutants (into `TECH-074_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | the two-defaults refusal; the special-without-rule refusal; the same-rule refusal; the local-has-no-rows rule | CB-1 unit |
| CB-2 | settings over the database (swap the order); the seed's idempotence (insert again); the cached-read rule's `min_prefix` | CB-2 integration |
| CB-3 | `highest_prompt_price` → the default input; the hosted-needs-a-default check | CB-3 integration |

## What changes for the user

- Anthropic input drops 25% on the screen and in the ledger (5 → 4 for Opus), the correction FR-4 is for.
- The brake reserves Opus prompts at 8, its 1-hour write, not 5 (FR-5, agreed): a run near its money
  limit stops a little earlier than today.

## Research Notes

- The catalogue is keyed `"<kind>/<model>"`, the machine file by `"<model>"` or `"<kind>/<model>"`
  (`catalogue.py:53-67`); `ModelFacts` carries the two prices (`llm_settings.py:128-129`).
- Prices are read at `telemetry.py:60` (`estimate_cost`), `resolve.py:141` (the run check), the `sw costs`
  lines (`interfaces/cli.py:66`, `219`); `sw costs set` writes the two to the machine file
  (`llm_settings_writer.py:36`).
- The collector gets its prices through one function, `prices=lambda model: catalogue.facts(...)`
  (`resolve.py:214`); `_scope` reads facts again (`resolve.py:226`). The brake's worst case: `collector.py:109-111` (`_worst_of` → `estimate_cost(worst, scope.facts)`).
- Prices to ship, from the providers' pages fetched 2026-10-17 (`prompt_caching_2026-10-17.md`): Opus 5.5
  4 / 20, cached read 0.20, write 5 (5 min) and 8 (1 h); Sonnet 5 2 / 10, 0.20, 2.5 and 4; Haiku 4.5 1 / 5,
  0.10, 1.25 and 2; OpenAI, Gemini and Mistral cached reads at 0.1× input. Rules: Anthropic min prefix
  512 / 1,024 / 4,096 by model, 300 s, requires a breakpoint; OpenAI 1,024, 1,800 s; Gemini 4,096;
  Mistral requires a cache key.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | The names of the two new prices in the settings file | `usd_per_million_cached_read`, `usd_per_million_cache_write` — the token kinds' names `[agreed 2026-10-18]` |
| Q2 | How a changed cache rule is found | from the calls: a cached count that breaks the rule warns — design FR-11, built in SF-02 `[agreed 2026-10-18]` |

## Dev notes

- CB-2: `schema_version` stays 1. `specials` is an addition, and the list ships with the code that
  reads it.
- CB-2: a list with no `checked` date gives prices valid from always. Refusing it broke every test list.
- CB-2: a price you set for a model on a local server still applies (`sw costs set`, `C-FLOW-13`
  FR-12). The database stores no prices for local models. Whether a local call shows a cost or
  *not applicable* (FR-10) is a question for the SF-02 plan.
- CB-2: five `C-FLOW-13` mutants aimed at `scripts/update_model_catalogue.py`, deleted in `e39ebd7e`,
  were removed. Three were re-anchored to the code that replaced theirs.

## Backlog

none
