# Implementation Plan: Model Catalogue [SF-05: Run override, brake values]
- **Feature ID**: C-FLOW-13
- **Sub-Feature**: SF-05 — `--model` for one run; brake values handed to `B-FLOW-05`
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-13/C-FLOW-13_design.md
- **Design Section**: §Sub-features → SF-05
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-13/C-FLOW-13_sf05_implementation_plan.md
- **Status**: APPROVED `[agreed 2026-10-04]`

## Goal

FR-16: `sw implement` and `sw run` take `--model <model@server>` for this run only.
FR-17: every limit lives in the machine `settings.toml` — stored, strictly read, shown with its
origin, handed to the brake — and today's brake reads its numbers from there. SF-05 brings no
numbers and no new brake rules (Q-13).

## Where it plugs in (measured 2026-10-02)

| Need | Surface | Read |
|---|---|---|
| Layer for one run | `resolve_roles(files, run_overrides: dict[str, RoleEntry] \| None)`; origin `RUN_OVERRIDE = "run --model"` | `core/config/llm_settings.py:300` — exists since SF-01, unused since SF-03 CB-3 |
| Resolver | `RoleResolver(files, *, telemetry_project, budget, catalogue=None)` calls `resolve_roles(files)` | `infrastructure/llm/resolve.py:42-51` |
| Router | `build_router(files, *, project, roles, spend_limit_usd, token_limit)` | `infrastructure/llm/router.py:51` |
| CLI | `command_router(project, settings, roles)` passes `settings.llm.max_spend_usd`, `max_tokens_per_run` | `infrastructure/llm/interfaces/command.py:22` |
| REST | `api_router(...)` passes the same two | `interfaces/api/v1/_llm.py:33` |
| `sw run` | `run_pipeline` → `_execute_run` → `_build_run_context` → `_wire_models` | `core/flow/interfaces/cli.py:129-280` |
| `sw implement` | `implement(spec, project, selector)` → `command_router` | `workflows/implementation/interfaces/cli.py:170` |
| Brake values today | `BrakeValues(hosted_spend_per_run=20, local_gpu_hours_per_run=2, agent_turns=10)` — read by `sw config show` only | `llm_settings.py:127` |
| Spend ceilings today | `LLMSettings.max_spend_usd = 25.0`, `max_tokens_per_run = 20_000_000` — in code, not in any file | `core/config/settings.py:45-64` |

Two spend numbers exist for one thing: 25 USD in code (used) and 20 in the file (unused).

## Decisions (audit)

| # | Question | Options | Proposal |
|---|----------|---------|----------|
| Q-13 | Scope of SF-05 | (a) infrastructure only, as the design's FR-17 says; (b) plus new brake rules | **(a): SF-05 provides the place for every limit — stored, strictly read, shown with its origin, handed to the brake through one interface — and the existing brake reads its numbers from there. No numbers, no new brake rules** `[agreed 2026-10-03]` |
| Q-1 | Where limits live | — | **No limit and no default value in code; every limit is in the settings files; a needed value that is unset stops the command, naming it** `[agreed 2026-10-03]` |
| Q-4 | Per-model limit fields | — | **In the model's `[models."<id>"]` entry, beside its price: `spend_per_run` (configured currency) and `tokens_per_run`** `[agreed 2026-10-03]` |
| Q-11 | A money total per run | — | **Yes: `[brake] hosted_spend_per_run`, in the configured currency; today's brake reads it, converted to USD** `[agreed 2026-10-03]` |
| Q-15 | Today's run-wide token total | — | **`[brake] tokens_per_run`, read by today's brake until `B-FLOW-05` applies the per-model limits; `local_gpu_hours_per_run` goes** `[agreed 2026-10-03]` |
| Q-12 | Limits per kind of task | — | **The role entry carries limit fields, stored and read now; applying them is `B-FLOW-05`'s** `[agreed 2026-10-03]` |
| Q-6 | Round limit | — | **`[brake] agent_turns` replaces `GenerationConfig.max_tool_rounds = 5` in code; today's tool loop reads the file value** `[agreed 2026-10-03]` |
| Q-14 | The fake answer "Max tool rounds exceeded." | — | **Fixed in SF-05: reaching the round limit raises a clear error** `[agreed 2026-10-03]` |
| Q-7 | What `--model` replaces | — | **Every role of this run** `[agreed 2026-10-03]` |
| Q-8 | Which commands take `--model` | — | **`sw implement`, `sw run`, `sw resume`** `[agreed 2026-10-03]` |
| Q-16 | How a role limit is written | — | **As an amount, with the model's field names: `spend_per_run`, `tokens_per_run`** `[agreed 2026-10-03]` |
| Q-17 | How limits are set | — | **By hand in the file; `sw config show` reads each back with its file and line** `[agreed 2026-10-03]` |
| Q-18 | Role limits in a project file | — | **No: limits live in the machine file only; a project role entry with a limit field is refused** `[agreed 2026-10-03]` |
| — | Moved to `B-FLOW-05` by Q-13, with the user's notes | — | a cloud model with no price is refused; a private server's models use the token limit, others the money limit; a model with no own limit falls under the run total; a role limit only lowers the model's; close-to-limit stays 80% warning + refusal until pause-and-ask; the loop detector (loops can span several steps; weigh effort against result) and the repeat check, which if built must be removed once the detector exists |

## Changes

**CB-1 — `--model` for one run** · FR-16

1. `RoleResolver(..., run_model: RoleEntry | None = None)` and `build_router(..., run_model=None)`.
   When set, the resolver calls `resolve_roles(files, run_overrides={role: run_model for every
   role the files name, plus every role the run requires})` (Q-7). Server check, privacy rule and
   key check apply unchanged; the origin reads `run --model`.
2. `command_router(project, settings, roles, *, run_model=None)` passes it on.
3. `--model <model@server>` on `sw implement`, `sw run`, `sw resume` (Q-8). The value parses
   through `RoleEntry` (the `model@server` validator), so a malformed value refuses before any
   call, naming the form. `sw run` hands it through `_execute_run` → `_build_run_context` →
   `_wire_models`; `sw resume` the same way.

**CB-2 — every limit from the machine file** · FR-17

4. `BrakeValues`: `hosted_spend_per_run: float | None`, `tokens_per_run: int | None`,
   `agent_turns: int | None`, all `gt 0`, **no default** (Q-1, Q-11, Q-15, Q-6);
   `local_gpu_hours_per_run` goes. A file without them still parses (FR-4: commands that call no
   model are unaffected).
5. `ModelFacts` gains `spend_per_run` (configured currency) and `tokens_per_run` (Q-4); `RoleEntry`
   gains the same two (Q-16). A project role entry carrying either is refused, naming the machine
   file (Q-18). These are stored and shown only; applying them is `B-FLOW-05`'s (Q-13).
6. `build_router` takes the machine file's brake and currency instead of `spend_limit_usd` /
   `token_limit`: before building anything it refuses, naming `brake.<key>`, if any of the three is
   unset; then `SpendBudget(limit_usd=to_usd(hosted_spend_per_run, currency),
   token_limit=tokens_per_run)`. `command_router` and `api_router` stop reading `settings.llm`.
7. `LLMSettings` and `SpecWeaverSettings.llm` go — nothing is left on them.
8. `BudgetExceededError(setting=...)` names `brake.hosted_spend_per_run` / `brake.tokens_per_run`;
   the message shows money in the configured currency (`format_money`).
9. Round limit: `GenerationConfig.max_tool_rounds: int | None = None`; the resolver sets it from
   `brake.agent_turns`. A tool loop given `None` refuses; reaching the limit raises
   `ToolRoundsExceededError` (an `LLMAdapterError`) naming `brake.agent_turns` — never the text
   "Max tool rounds exceeded." (openai, anthropic, mistral) nor the last partial response
   (gemini) (Q-14).
10. `sw config show`: the brake rows show `unset` instead of a built-in value; model and role
    limit fields appear with their file and line, marked `applied by B-FLOW-05` (R-4).
11. Docs: installation guide §3a (`[brake]` is required, the model and role fields), the GB10 guide
    Step 6 (`[brake]` in the example), `B-FLOW-05` design (its FR-5 home is now `[brake]`; the rules
    moved to it by Q-13, listed in §Decisions here).

| File | Change | FR |
|------|--------|-----|
| `src/specweaver/core/config/llm_settings.py` | brake, model and role limit fields; project refusal; report rows | FR-17 |
| `src/specweaver/core/config/settings.py` | `LLMSettings` removed | FR-17 |
| `src/specweaver/infrastructure/llm/{resolve,router,budget,models}.py` | run model; budget from the file; round limit | FR-16, FR-17 |
| `src/specweaver/infrastructure/llm/adapters/{openai,anthropic,mistral,gemini}.py` | round limit raises | FR-17 |
| `src/specweaver/infrastructure/llm/interfaces/command.py`, `interfaces/api/v1/_llm.py` | no `settings.llm` | FR-17 |
| `src/specweaver/workflows/implementation/interfaces/cli.py`, `core/flow/interfaces/cli.py` | `--model` | FR-16 |

## Tests

| Tier | Bucket | Test | FR | Boundary |
|---|---|---|---|---|
| E2E (US-16 P8) | Journey | `sw implement --model qwen3-coder-next@gb10 spec.md` with `default` on another server → every request reaches the GB10; the file is unchanged | FR-16 | CB-1, written red first |
| Unit | Hostile | `--model gpt-6` (no `@server`) → refused, exit 1, no call | FR-16 | CB-1 |
| Unit | Hostile | `--model m@hosted` in a `private_only` project → refused, naming the rule | FR-16 | CB-1 |
| Unit | Edge | `--model m@nosuch` → refused, naming the server | FR-16 | CB-1 |
| Integration | Seam | `sw run` and `sw resume` with `--model` → the router resolves every role to it | FR-16 | CB-1 |
| Integration | Seam | `hosted_spend_per_run = 16`, `[currency] per_usd = 0.8` → the run's budget refuses after USD 20 | FR-17 | CB-2 |
| Integration | Degradation | no `[brake]` → an LLM command refuses naming `brake.hosted_spend_per_run`; `sw check` still runs | FR-17, FR-4 | CB-2 |
| Unit | Hostile | `local_gpu_hours_per_run` in the file → refused as unknown; `agent_turns = 0` → refused | FR-17 | CB-2 |
| Unit | Hostile | a project `[llm.roles]` entry with `spend_per_run` → refused, naming the machine file | FR-17 | CB-2 |
| Unit | Degradation | each adapter at `agent_turns` rounds → `ToolRoundsExceededError` naming `brake.agent_turns` | FR-17 | CB-2 |
| Unit | Happy | `sw config show` lists model and role limit fields with file and line; unset brake values show `unset` | FR-17 | CB-2 |
| Integration | Seam, `xfail(strict=True)` blocked on `B-FLOW-05` | a model's `spend_per_run` and a role's `spend_per_run` stop the run at the lower of the two | FR-17 | CB-2 |

Mutants: run model ignored; run model skips the privacy check; brake value not converted from
the currency; brake value unset passes silently; round limit reached returns text again; a project
role limit accepted.

## Research Notes

- `resolve_roles` already layers `run_overrides` with the origin `run --model` and checks the
  server and the privacy rule on it (`llm_settings.py:300-330`). SF-05 only feeds it.
- `sw resume` rebuilds the context through `_build_run_context`, the same path as `sw run`.
- `B-FLOW-05` FR-5 cites `llm.max_spend_usd` / `llm.max_tokens_per_run`; its design text must name
  the new home after CB-2.
- No `~/.specweaver/settings.toml` exists on the user's machine (checked 2026-10-03), so dropping
  `local_gpu_hours_per_run` and requiring `[brake]` breaks no file. `schema_version` stays 1: a
  file with the old key gets the strict "unknown key" error with its line (FR-4), and old versions
  are not supported `[agreed 2026-09-27]`.
- `GenerationConfig.max_tool_rounds = 5` is the only round limit (`infrastructure/llm/models.py:74`).
  At the limit, openai/anthropic/mistral return the text "Max tool rounds exceeded." with
  `finish_reason="max_tokens"`; gemini returns its last partial response. All four change (Q-14).
- `Reviewer._execute_review` re-raises `BudgetExceededError` only (`B-FLOW-05` FR-3); a
  `ToolRoundsExceededError` there becomes `ReviewVerdict.ERROR` with the error's message — a visible
  failure, not an answer. Planner and ScenarioGenerator call outside their retry `try`, so it
  propagates.

## Red/Blue review (2026-10-03, 2 cycles)

| # | Finding | Severity | Resolution |
|---|---|---|---|
| R-1 | Requiring three `[brake]` values makes every LLM command stop on a file without them | MEDIUM | Intended (Q-1); the refusal names the key; installation guide and GB10 guide show `[brake]` |
| R-2 | `max_tool_rounds = None` on configs that never use tools could trip a tool loop in tests | LOW | Only the tool loop reads it; it refuses `None` with the key's name; `tests/scripted_llm.py` `TEST_CONFIG` sets a value |
| R-3 | `--model` on `sw resume` could resume under a model the run did not start with | LOW | Intended (Q-8): the user chose it for this resume; without `--model` the files decide |
| R-4 | Model and role limit fields stored but not applied could read as active | MEDIUM | `sw config show` marks them `applied by B-FLOW-05`; the strict xfail test turns green when it is |
| R-5 | `[brake] tokens_per_run` also counts cloud tokens until `B-FLOW-05` | LOW | Today's behaviour, kept on purpose (Q-15) |
| R-6 | `api_router` with no `[brake]` | LOW | Same `SettingsFileError` → HTTP 500 `LLM_SETTINGS`, as for any settings error |

Cycle 2 re-checked R-1..R-6 and the bindings; no new finding above LOW.
