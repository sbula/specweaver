# Implementation Plan: Spend Brake [SF-01: Accounting and limits]
- **Feature ID**: B-FLOW-05
- **Sub-Feature**: SF-01 — Accounting and limits
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-05/B-FLOW-05_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-05/B-FLOW-05_sf01_implementation_plan.md
- **Status**: APPROVED `[agreed 2026-10-06]`

## Goal

Every call of a run is counted and checked against every limit **before** it is sent: the run's
money total (hosted servers), its token total (private servers), the model's and the role's limits.
A hosted model with no price or an unknown thinking cap is refused at the start. FR-1, FR-2, FR-4,
FR-5, FR-9.

SF-01 stops the run when a limit would be crossed, as today's brake does. SF-02 turns that stop into
a question or a park; SF-01 raises `SpendLimitReached` so SF-02 has one signal to catch.

## Where it plugs in (measured 2026-10-06)

| Need | Surface | Read |
|---|---|---|
| The budget | `SpendBudget(limit_usd, token_limit=None, currency=None)`, `record(cost_usd, tokens=0)`, `check()` | `infrastructure/llm/budget.py:47-127` |
| Built once per command | `build_router(files, *, project, roles, run_model=None)` | `infrastructure/llm/router.py:49` |
| One collector per server | `RoleResolver._adapter(server_name) -> TelemetryCollector` | `infrastructure/llm/resolve.py:116` |
| Check and record | `TelemetryCollector.generate`, `generate_with_tools`, `generate_stream`, `_capture` | `infrastructure/llm/collector.py:79-166` |
| A hook before each tool round | `on_tool_round(round_num, messages)`, called before each request | `adapters/openai.py:206-253` (and the other three) |
| Which role a call is for | `GenerationConfig.task_type`; `ModelRouter.get_for_task(task_type)` | `models.py:79`, `router.py:39` |
| The role entry behind a role | `RoleResolver._setting(role) -> ResolvedRole` (falls back to `default`) | `resolve.py:83` |
| Model facts per call | `Catalogue.facts(kind, model, overrides)`: prices, `max_output`, `thinking_in_output_cap`, `spend_per_run`, `tokens_per_run` | `catalogue.py:62`, `core/config/llm_settings.py:119-133` |
| Prompt size | `estimate_tokens(text)` (`len // 4`) | `adapters/base.py:144` |

## Decisions (audit)

| # | Question | Options | Proposal |
|---|----------|---------|----------|
| Q-1 | A tool loop fails partway (a provider error in round 3): its earlier rounds cost money, and the adapter loses their usage | (a) the adapters attach the usage so far to the error; an error without it counts its reserved worst case; (b) count the reserved worst case always; (c) count nothing | **(a)** `[agreed 2026-10-06]` — exact where we can, fail closed where we cannot |
| Q-2 | A role left unset runs on `default`. Does `default`'s role limit apply per role or once? | (a) once: every role that runs on `default` shares its limit; (b) per role: each gets its own counter at that value | **(a)** `[agreed 2026-10-06]` — a limit is one number on one entry. Roles the user sets each keep their own limit, also on the same model; the model's own limit covers all its roles, and the lower always wins |
| Q-3 | A role sets the other unit for its server (`spend_per_run` on a GB10 role) | (a) refused when the command starts, naming the key; (b) ignored | **(a)** `[agreed 2026-10-06]` — a limit that silently does nothing misleads |
| Q-4 | Fact correction: Q12 says "Gemini counts exactly", but Gemini's exact count is a network request, which Q12 rules out | every adapter uses the local estimate (`len // 4`) + 25% | **record corrected** `[agreed 2026-10-06]`; the decision ("no extra request") stands |

## Changes

**CB-1 — the limits and the per-call check** · FR-1, FR-2, FR-4, FR-5

1. `infrastructure/llm/budget.py`: the budget holds **limits**, each with a key (`brake.hosted_spend_per_run`,
   `models."<id>".tokens_per_run`, `roles.review.spend_per_run`, …), a unit (USD or tokens), a value
   and its spent total. Per call the caller passes the call's **scope**: server private or not, model
   facts, role entry. Methods:
   - `before_call(scope, worst_usd, worst_tokens)` — for every limit that applies to the scope:
     if spent + reserved + worst > value → raise `SpendLimitReached(limit, spent)`.
   - `record(scope, cost_usd | None, tokens)` — adds to every limit that applies; warns once at 80%
     of each limit.
   - Which limits apply: hosted server → the money ones (run, model, role); private server → the
     token ones. Pseudocode only; no class body here.
2. `SpendLimitReached(BudgetExceededError)` carries the limit key, value, spent, and the unit; its
   message names the key and shows money with `format_money`.
3. `infrastructure/llm/router.py::build_router` builds the limits from `brake_limits(files)`,
   `files.machine.currency` and the machine roles; `to_usd` converts every money value once.
4. `ResolvedRole` gains the role entry's `spend_per_run` / `tokens_per_run` (the run model has none).
5. `RoleResolver` gives each collector a `scope_of(config) -> CallScope`: the server's `private`, the
   model's facts, the role entry that serves `config.task_type` (via `_setting`).
6. `TelemetryCollector`: before `generate` / `generate_stream`, estimate the worst case
   (`estimate_tokens` of every message's text and the tool schemas, × 1.25, plus
   `config.max_output_tokens`; money at the facts' prices) and call `before_call`, which **reserves**
   it until the call is recorded — so calls running in parallel cannot each pass on the same
   headroom. After the call, `record` replaces the reservation. A streamed call records its estimated
   input tokens.

**CB-2 — tool rounds, failed loops, roles everywhere, refusals** · FR-1, FR-2, FR-5, FR-9

7. `generate_with_tools` wraps `on_tool_round`: before each round it reserves that round's worst case
   and calls `before_call`; after the loop it replaces the reservations with the real usage.
8. The four adapters attach the usage so far to an exception raised inside the loop (Q-1);
   `ToolRoundsExceededError` carries it too. The collector records it, or the reservation if absent.
9. `ModelRouter.get_for_task` stamps `config.task_type`, so REST and direct calls carry their role.
10. `RoleResolver.require` (before the first call) refuses, naming the key to set:
    a hosted model with no input or output price (`models."<id>".usd_per_million_input`), one whose
    `thinking_in_output_cap` is not `true`, and a role limit in the wrong unit for its server (Q-3).
11. Docs: `adding_llm_adapters.md` (attach usage to an error in the tool loop),
    installation guide (model and role limits are now applied).

Code comments stay short and say only what the code does; no dates or history `[agreed 2026-10-06]`.

## Tests

| Tier | Bucket | Test | FR | CB |
|---|---|---|---|---|
| Unit | Happy | a hosted call is counted against the run, model and role money limits; a private call against the token ones | FR-1, FR-5 | 1 |
| Unit | Boundary | a call whose worst case lands exactly on the limit is allowed; one token over is refused before the call | FR-2 | 1 |
| Unit | Boundary | the 80% warning fires once per limit, not once per budget | FR-4 | 1 |
| Unit | Hostile | a role limit higher than the model's never raises it: the lower one stops the run | FR-5 | 1 |
| Integration | Seam | settings file → `build_router` → collector → budget: CHF limits converted once, a GB10 call never counts money | FR-5 | 1 |
| Unit | Degradation | a streamed call records its estimated input tokens | FR-1 | 1 |
| Unit | Degradation | a tool loop that fails in round 3 records the usage of rounds 1–2; an error without usage counts the reservation | FR-1 | 2 |
| Unit | Boundary | round 4's worst case would cross → refused before round 4's request; rounds 1–3 ran | FR-2 | 2 |
| Integration | Seam | `POST /implement`'s calls carry `task_type`, so a role limit applies over REST | FR-5 | 2 |
| E2E (US-04 S3) | Hostile | `sw run` with a hosted model without a price, or with `thinking_in_output_cap` unset → refused before any request, naming the key | FR-9 | 2 |
| E2E (US-04 S4, S5) | Journey | a GB10 model's `tokens_per_run`, and a tool round that would cross a limit → no crossing request is sent; the run stops naming the limit (SF-02 turns the stop into a pause) | FR-2, FR-5 | 2 |

Mutants to record: the worst case not added before a call; a private call counted in money; the role
limit able to raise the model's; the 80% warning once per budget; a failed loop's usage dropped;
the unpriced and the uncappable refusals skipped.

## Research Notes

- The collector already has the facts per call through its `prices` lookup (`resolve.py:123`); the
  scope reuses it.
- `on_tool_round` is called before every request in all four adapters, so it is the per-round
  check point without a new adapter parameter.
- `RoleResolver._setting` returns the `default` entry for an unset role, so its `ResolvedRole.role`
  is `"default"` — the key Q-2 (a) shares.
- Only the money limit warns today (`budget.py:96`); FR-4 makes every limit warn.
- New roles later (the user names "simple implementation", "complex implementation"): limits are
  keyed by the role's name, so the brake needs no change; a new role is added to `RoleName`,
  `TaskType` and `ROLE_OF_STEP`.

## Red/Blue review (2026-10-06, 2 cycles)

| # | Finding | Severity | Resolution |
|---|---|---|---|
| R-1 | Parallel calls could each pass on the same headroom | HIGH | worst case reserved until the call is recorded (item 6) |
| R-2 | "the prompt" was undefined for a message list with tools | MEDIUM | every message's text plus the tool schemas (item 6) |
| R-3 | `SpendBudget`'s constructor changes; the built version's tests construct it directly | MEDIUM | those tests move to the new shape in CB-1; their `Proves:` ids (FR-1, FR-2, FR-4, FR-5) keep their meaning |
| R-4 | The run token total stops counting hosted tokens | LOW | agreed (Q6); the installation guide says so in CB-2 |

Cycle 2 re-checked the bindings and the commit boundaries; nothing above LOW.

