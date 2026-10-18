# Implementation Plan: The Cost Ledger Prices Cached Input at the Full Price [SF-03: The refresh]
- **Feature ID**: TECH-074
- **Sub-Feature**: SF-03 — The refresh
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-074/TECH-074_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-074/TECH-074_sf03_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-18

**FRs owned**: FR-7, FR-8 · **Depends on**: SF-01 (committed `46638028`)

## Shape

| Piece | Where | Tag |
|---|---|---|
| download `api.json` with `If-None-Match` on the last ETag; an unchanged file costs one empty reply (Q1) | `infrastructure/llm/price_refresh.py` (`httpx2`, so the test guard `block_real_httpx2` catches a stray request) | NEW |
| which offerings: the models the roles use, at a first-party kind (models.dev ids `anthropic`, `openai`, `google`, `mistral`, `alibaba-cn`) or at a hosted `openai-compatible` server with `models_dev = "<provider id>"` in its entry (Q2); local servers never | `price_refresh.py` | NEW |
| models.dev `cost` → rows: `input`, `output`, `cache_read` → cached read, `cache_write` → cache write; a tier table (`context_over_200k`) → a special price with `min_prompt_tokens`; a cached price keeps the shipped list's rule for that kind (FR-9) | `price_refresh.py` | NEW |
| refused, with a warning, and the last good price kept: missing, zero, negative, not a number, or a set that breaks the exactly-one check (FR-8) | `price_refresh.py`, `price_store.py` (`_seed_one`, the one writer) | MODIFY |
| when: at the start of a command that calls a model, if the last refresh is older than 24 hours; and `sw costs refresh` always; a 5-second timeout (Q3) or no network → the last prices, with a warning; a failed attempt counts as the day's, so an offline machine waits once a day, and `sw costs refresh` retries at once | `router.py` (`build_router`), `interfaces/cli.py` | MODIFY |
| the last refresh's time and ETag: a one-row table `llm_price_refresh`, added at start-up | `store.py` | NEW |
| two commands refreshing at once never store a price twice: a unique index on offering, kind, rule (NULL as 0) and start date, and the write in one transaction; a lost race is a no-op | `store.py`, `db_bootstrap.py` | MODIFY |
| `models_dev` joins `ServerEntry` | `core/config/llm_settings.py` | MODIFY |
| the test suite never reaches models.dev: the start-up refresh is off in `tests/conftest.py` unless a test asks for it | `tests/conftest.py` | MODIFY |
| a change is reported, never held for approval: one line per changed price, old → new, at warning level so the console shows it | `price_refresh.py` | NEW |
| `sw costs` names the real source of a price: `catalogue`, `models.dev`, or `your settings file` | `interfaces/cli.py` (`_price_source`) | MODIFY |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | converting `api.json` to rows, the refusals, storing through the one writer | FR-8, FR-7 (rows) | a zero or negative downloaded price, or one breaking the check, would be stored |
| CB-2 | the download, the 24-hour rule, the ETag, `sw costs refresh`, the report, the source shown | FR-7 | prices never change after a release |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit + integration | a recorded `api.json` excerpt → rows; each refusal keeps the stored price; a tier → `min_prompt_tokens` |
| CB-2 | integration + e2e | `respx` serves `api.json`: a stale store refreshes and reports; a fresh one does not ask; `304` writes nothing; a timeout and a 500 keep the last prices and warn; `sw costs refresh` over a real database shows the new price and `models.dev` |

## Mutants (into `TECH-074_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | the zero refusal; the check before storing; the tier's `min_prompt_tokens`; the shipped rule on a cached price | CB-1 tests |
| CB-2 | the 24-hour comparison; the ETag header; the timeout fallback; the change report | CB-2 tests |

## Research Notes

- models.dev documents `api.json` (the full catalogue), `models.json` and `catalog.json`; no endpoint per
  provider or per model (its README, read 2026-10-18). `api.json` → provider → `models` → `cost`
  (`input`, `output`, `reasoning`, `cache_read`, `cache_write`, nested tiers) and `limit`.
- The deleted script (`e39ebd7e^:scripts/update_model_catalogue.py`) mapped provider ids
  `google`→`gemini`, `alibaba-cn`→`qwen`, read the ETag, and skipped `status = "deprecated"`.
- The one price writer is `price_store._seed_one`, through `check_prices` (NFR-3).
- Network in tests: `fake_httpx2` answers `httpx2`, and `block_real_httpx2` refuses any request no fake answers (`tests/fake_http.py`).

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | The whole `api.json` is the only download, against the non-goal "no models nobody's roles use" | download it at most once a day with its ETag; store only the offerings the roles use `[agreed 2026-10-18]` |
| Q2 | How a hosted `openai-compatible` server names its models.dev provider | an optional `models_dev = "<provider id>"` in its server entry; without it, no refresh `[agreed 2026-10-18]` |
| Q3 | How long a refresh at command start may wait | 5 seconds, then the last prices with a warning `[agreed 2026-10-18]` |

## Backlog

none
