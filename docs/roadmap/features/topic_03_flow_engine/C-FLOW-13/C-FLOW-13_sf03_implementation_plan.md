# C-FLOW-13 SF-03 — Consumers Switched Over

**Status**: APPROVED — approved by Steve Bula `[agreed 2026-09-27]` ·
names `code`, `per_usd`, `hosted_spend_per_run` `[agreed 2026-09-27]` · **FRs owned**: FR-10, FR-11, FR-12, FR-13, FR-15 · **Depends on**: SF-02 (committed) ·
Design: [C-FLOW-13_design.md](C-FLOW-13_design.md) §Sub-features → SF-03

## Goal

Every LLM call — every command, the REST API and every pipeline step — gets its adapter, model,
sampling and price through one resolver that reads the settings files. The 11 hard-coded fallback
models, the per-adapter price tables and the router's separate adapter path go. Money shows in one
configured currency.

**One fallback, one place** `[agreed 2026-09-27]`: the `default` role in the settings file is the only
fallback model. No model name remains in code.

## Where it plugs in (measured 2026-09-27)

| Fact | Where |
|---|---|
| 8 entry points build adapters: `sw draft` `review/interfaces/cli.py:201`, `sw review` `:304` (forces temperature 0.3 at `:312`), `sw implement` `implementation/interfaces/cli.py:226` (forces 0.2 at `:235`), `sw run`/`resume` `flow/interfaces/cli.py:95` and router `:282`, `sw drift check --analyze` `cli_drift.py:97`, REST `api/v1/review.py:45`, `api/v1/implement.py:46` (forces 0.2), `sw standards scan` `standards/interfaces/cli.py:155` (always `GeminiAdapter`, no limiter, no telemetry) | inventory |
| Router: builds adapters itself (`router.py:101-120`); its collectors get **no budget** (`collector.py:60`), **no rate limiter**, and are **never flushed** (`engine/telemetry.py:21-31` flushes only `context.model.llm`); `cost_overrides` never supplied (`flow/interfaces/cli.py:282`) | `router.py`, `collector.py`, `runner.py:299-312` |
| Handlers asking the router: generation (IMPLEMENT) `generation.py:46`, plan `:314`, review `review.py:33`, lint-fix (CHECK) `lint_fix.py:313`. Handlers using `context.model.llm` directly: draft `draft.py:169`, feature draft `:362`, decompose `decompose.py:48`, arbiter `arbiter.py:230`, standards enrich `standards.py:110`, drift `drift.py:178` | handlers |
| The 11 fallbacks, all `"gemini-3-flash-preview"`: `generation.py:69,339`, `review.py:55`, `lint_fix.py:304`, `drift.py:176`, `drafting/_base.py:77`, `generator.py:69`, `reviewer.py:96`, `decomposer.py:60`, `planner.py:77`, `enricher.py:38`. Also DB seeds `db_bootstrap.py:50,59,68` and `store.py:27` | inventory |
| Prices: `CostEntry` is USD per **1K** (`telemetry.py:26`); `default_costs` on 6 adapter classes; `estimate_cost` prices an unknown model at `0.0` (`telemetry.py:61-90`); `LlmUsageLog.estimated_cost` is `nullable=False, default=0.0` (`store.py:55`) | telemetry, store |
| `sw costs` prints the USD/1K table and edits DB overrides; it shows **no** month-to-date spend. Spend is in `sw usage` (USD, `interfaces/cli.py:166-235`) | `infrastructure/llm/interfaces/cli.py` |
| `TaskType` values = `RoleName` minus `default`, plus `unknown` | `models.py:29`, `llm_settings.py:32` |
| `GenerationConfig.temperature: float = 0.7`, `max_output_tokens: int = 4096` | `models.py:65-66` |
| `tests/scripted_llm.py` patches `factory.create_llm_adapter` and `ModelRouter.get_for_task` — both change here | `scripted_llm.py:80-104` |

## Changes

**CB-1 — one resolver** · FR-10, FR-11

1. `infrastructure/llm/resolve.py`: `llm_for_role(role, files, *, telemetry_project, budget) ->
   (adapter, GenerationConfig)`. Steps: layer roles (`resolve_roles`, SF-01) → the role, else
   `default`, else refuse (`SettingsFileError` naming the role and the file to set it in) → its server
   → `adapter_for_server` (SF-02) → facts from the catalogue → sampling: role, else catalogue, else
   none sent → output limit (Q-4) → wrap in one `TelemetryCollector` with the run's shared budget.
2. `GenerationConfig.temperature` becomes optional: `None` is not sent.
3. The run keeps one resolver per command, caching adapters per server, and flushes every collector
   it built. A command resolves every role its steps use **before the first call**, so an unset role
   refuses at the start, not halfway through a paid run.

**CB-2 — one price source, one currency** · FR-12, FR-13

4. The collector prices from catalogue facts (USD per 1M). `CostEntry`, `default_costs`,
   `get_merged_default_costs` and the per-1K table go. Unknown price → `estimated_cost = NULL`
   (Alembic: column nullable), reported as unknown, never 0 (Q-5).
5. One currency everywhere (Q-6): `[currency] code = "CHF"`, `per_usd = 0.80`, `rate_date`. Prices and
   the database stay in USD (AD-8); every amount shown or set is converted once, at the edge. No
   `[currency]` → USD. `Currency(usd_to_chf, rate_date)` becomes `Currency(code, per_usd, rate_date)`;
   the brake's `hosted_chf_per_run` becomes `hosted_spend_per_run`, in that currency.
6. `sw costs`: each model in use with its price per 1M tokens and month-to-date spend; `sw usage` the
   same currency.

**CB-3 — every consumer on the resolver** · FR-10, FR-11

7. The 8 entry points call the resolver with their role (Q-2); forced temperatures go (Q-3);
   `sw standards scan` stops building `GeminiAdapter`.
8. `ModelRouter` becomes the resolver's per-task face: same return type, adapters from the resolver,
   so routed calls get the limiter, the shared budget and the flush.
9. Handlers that bypass the router ask it for their role; the 11 fallbacks and the DB seed models go.
10. `scripted_world` patches the resolver instead of the two old targets.

| File | Change | FR |
|------|--------|-----|
| `src/specweaver/infrastructure/llm/resolve.py` | new | FR-10, FR-11 |
| `src/specweaver/infrastructure/llm/{router,factory,collector,telemetry,models}.py` | one path; prices per 1M | FR-10, FR-12 |
| `src/specweaver/infrastructure/llm/adapters/*.py` | `default_costs` removed | FR-12 |
| `alembic/versions/<new>.py` | `estimated_cost` nullable | FR-12 |
| `src/specweaver/infrastructure/llm/interfaces/cli.py` | `sw costs`, `sw usage` in CHF | FR-13 |
| 8 entry points, 10 handlers/workflow classes | resolver, no fallbacks | FR-10, FR-11 |

## Tests

| Tier | Bucket | Case | FR |
|---|---|---|---|
| Unit | Happy | role set → its model, server, sampling; `default` covers an unset role | FR-11 |
| Unit | Degradation | neither role nor `default` → refused, naming role and file; no call made | FR-11 |
| Unit | Boundary | sampling from catalogue when the role sets none; nothing known → temperature not sent | FR-10 |
| Unit | Happy | price from catalogue per 1M; machine override wins | FR-12 |
| Unit | Hostile | unknown model → cost unknown, never 0 | FR-12 |
| Integration | Happy | settings files → resolver → fake HTTP: one budget shared by two roles; both collectors flushed | FR-10 |
| Integration | Boundary | migration: `estimated_cost` NULL stored and summed as unknown | FR-12 |
| E2E P1, P2, P3 | Journey | `sw draft` on the GB10 role → request at the GB10; private-only → refused before any request (the SF-02 xfails turn green) | FR-7, FR-9, FR-10 |
| E2E P6 | Journey | `sw costs` and `sw usage` show the configured currency with the rate date; no `[currency]` → USD | FR-13 |
| Unit | Degradation | `sw run` with an unset role → refused before the first call | FR-11 |
| E2E | Journey | `sw run` pipeline: a routed step's usage is recorded (was never flushed) | FR-10 |
| E2E | Journey | `sw config set-role draft m@gb10` then `sw config show` → the value, its file and line; a comment above it survives | FR-15 |
| Unit | Hostile | `set-role` naming an unknown server → refused, file unchanged | FR-15 |
| Integration | Happy | Alembic upgrade drops the three tables; downgrade restores them | FR-15 |

Mutants to record: fall back to a hard-coded model; router bypassing the shared budget; unknown price
recorded as 0; CHF shown without conversion; routed collector not flushed.

**CB-4 — commands write the files; the old DB settings go** · FR-15

11. `core/config/bootstrap/llm_settings_writer.py` (the only writer, NFR-4): set a role, set or remove
    a model's prices, with `tomlkit`, keeping comments and key order (NFR-6); validate the result with
    the SF-01 parser before writing, so a command never leaves a broken file.
12. `sw config set-role <role> <model@server> [--project]` replaces `set-provider` and
    `routing set/show/clear`. `sw costs set <model> <input> <output>` takes the price per 1M tokens
    in the configured currency and stores USD; `sw costs reset <model>` removes it.
13. Alembic drops `llm_profiles`, `llm_project_links`, `llm_cost_overrides`; the profile reading in
    `settings_loader`, the DB seeds and the repository methods go. Servers, currency and brake values
    are edited in the file by hand (Q-9).

Commit boundaries: CB-1 (items 1–3), CB-2 (4–6), CB-3 (7–10, with the e2e), CB-4 (11–13).

## Decisions (audit)

| # | Question | Options | Proposal |
|---|----------|---------|----------|
| Q-1 | After SF-03 the DB profiles, routing entries and price overrides are ignored, and `sw config set-provider`, `routing set`, `sw costs set` write to a DB nothing reads. SF-04 (migration, commands write files) depends only on SF-01 | (a) build SF-04 first, then SF-03; (b) SF-03 first; the DB commands refuse until SF-04 | ~~(a) SF-04 first~~ — superseded by Q-7/Q-8 the same day: no migration, and the old commands go in SF-03's last commit |
| Q-2 | Role per consumer: `sw draft`, draft handlers → `draft`; `sw review`, review handlers, arbiter, drift, REST review → `review`; `sw implement`, generation handlers, REST implement → `implement`; plan, decompose → `plan`; lint-fix → `check`; standards scan and enrich → `check` | (a) as listed; (b) change some | **(a)** `[agreed 2026-09-27]` — `default` is the one fallback, set in one place |
| Q-3 | `sw review` forces temperature 0.3, `sw implement` and REST implement 0.2 | (a) remove: role, then catalogue, else not sent; (b) keep as defaults | **(a)** `[agreed 2026-09-27]` |
| Q-4 | Output limit when the role sets none | (a) the model's own maximum from the catalogue; unknown → refused, naming `max_output_tokens`; (b) a fixed default | **(a)** `[agreed 2026-09-27]` |
| Q-5 | A call with an unknown price | (a) stored as unknown; the spend brake counts its tokens, and says once that its money is unknown; (b) refuse models without a price | **(a)** `[agreed 2026-09-27]` |
| Q-6 | `sw usage` shows spend in USD | one currency everywhere, and it is configurable | **`[currency] code`, `per_usd`, `rate_date`; unset → USD** `[agreed 2026-09-27]` |
| Q-7 | Migrate the DB's LLM settings (FR-14)? | measured: 3 seeded profiles (Gemini 2.5), 0 links, 0 overrides | **dropped** `[agreed 2026-09-27]` (design AD-9) |
| Q-8 | Where FR-15 lives | (a) SF-03's last commit, with the old commands and tables removed in the same step; (b) SF-04 | **(a)** `[agreed 2026-09-27]` — no commit with a command that does nothing; SF-04 retired |
| Q-9 | Which commands | (a) `set-role`, `costs set`, `costs reset` only; (b) also `set-server`, `set-currency` | **(a)** `[agreed 2026-09-27]` |
| Q-10 | The old tables | (a) dropped by Alembic; (b) left unused | **(a)** `[agreed 2026-09-27]` |
