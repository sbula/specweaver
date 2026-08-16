# Design: US-16 Base Integration Contract — AI Operations & Cost Routing

- **Feature ID**: INT-US-16
- **Phase**: Integration (Topic 08)
- **Status**: APPROVED (2026-08-16 — FR-2 kept in this contract per AD-4)
- **Design Doc**: docs/roadmap/features/topic_08_integration/INT-US-16/INT-US-16_design.md

## Feature Overview

`INT-US-16` proves the US-16 journey end to end: a real `sw implement` run records its LLM token
usage and cost, and `sw usage` then shows that run's spend for the active project. It solves the
gap that every US-16 MVS capability is delivered — `C-FLOW-01` (Telemetry DB), `D-FLOW-03` (Static
Routing), token tracking, the Config DB — while **nothing joins them**: today's proof is cut in two
and the halves meet at a hand-written `sqlite3` INSERT. It interacts with the implement CLI's
adapter construction, `TelemetryCollector`, `PipelineRunner._flush_telemetry`,
`LlmRepository.get_usage_summary` and the `sw usage` renderer, and does **not** touch the unbuilt
US-16 add-ons (dynamic routing, friction analytics, OpenTelemetry tracing, REST telemetry API).
Key constraints: no live API calls in the proof, warn-and-continue when no active project is set,
and one surface proven end to end rather than six proven shallowly.

## Research Findings

### Codebase Patterns

**The machinery is complete and correctly wired.** This was checked rather than assumed, and it is
the opposite of what the `INT-US-25` precedent predicted:

- `TelemetryCollector` wraps the adapter when a project is given — `factory.py:84-92`, and again in
  `router.py:120` for the routed path.
- `PipelineRunner._flush_telemetry` drains it in a `finally`, so a failed run still records what it
  spent — `runner.py:300-314` → `core/flow/engine/telemetry.py:20-35`.
- All six LLM-calling surfaces pass `telemetry_project`: `sw run` and `sw resume`
  (`core/flow/interfaces/cli.py:96,289`), `sw implement`
  (`workflows/implementation/interfaces/cli.py:219`), `sw review` ×2
  (`workflows/review/interfaces/cli.py:195,293`), drift (`cli_drift.py:97`), plus both REST routes.
- `sw usage` and `sw costs` render real aggregates — `infrastructure/llm/interfaces/cli.py:127`.

**What is missing is the join.** No test runs a SpecWeaver command and then asserts that command's
cost is visible. The existing proof splits cleanly in two:

| Existing test | Enters at | Ends at |
|---|---|---|
| `tests/integration/test_telemetry_roundtrip.py`, `tests/e2e/capabilities/infrastructure/test_telemetry_e2e.py` | the **factory**, called directly | DB rows |
| `tests/integration/test_telemetry_integration.py::test_flush_data_queryable_via_get_usage_summary` | the **collector** | `get_usage_summary` |
| `tests/e2e/test_cli_decentralized_e2e.py::test_usage_e2e_happy_path` | a **hand-written `sqlite3` INSERT** naming ten columns as literals | `sw usage` output |

The read half is proven against a row the test typed itself. If the writer's column set drifted,
both halves would stay green — the `INT-US-25` failure mode one step less severe: not a dead
capability, but a seam that meets at a fixture instead of at a run.

**The defect this exposes — corrected 2026-08-16, after running it.** This section originally
claimed that a run without an active project *proceeds and records nothing silently*, reasoned from
`cli.py:216-219` (`telemetry_project=None` skips the collector wrap) and the `# type:
ignore[arg-type]` beside it. **The command refuses instead.** `load_settings(db, None)` raises
before `create_llm_adapter` is reached, and the user sees `Error: LLM configuration failed: Project
'None' not found` — a database lookup that failed on the string `None`, rather than "you have not
run `sw use`". So the defect is real but smaller and different: a message, not lost money. The
`# type: ignore[arg-type]` silences the type checker; the runtime does raise.

**What the correction cost is worth recording**: two documents and two reports stated the wrong
version as fact before anyone ran it, which is the same reading-instead-of-measuring failure this
contract exists to catch, committed by its own design.

**Modules touched**: `workflows/implementation/interfaces/cli.py` (delivery layer — the warning),
plus new tests. No new module, no schema change, no new dependency. `infrastructure/llm`'s
`context.yaml` (`consumes: specweaver/config`, `forbids: specweaver/sandbox/*`) is not approached.

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| typer | >=0.21 | `CliRunner.invoke(app, args)` | `pyproject.toml:13` |
| sqlalchemy[asyncio] | >=2.0.0 | `select(...).group_by(...)` behind `LlmRepository` | `pyproject.toml:18` |
| aiosqlite | >=0.20.0 | async SQLite driver under the Config DB | `pyproject.toml:19` |

No new external dependency is introduced. This contract composes surfaces that already exist, so
Track B found no API to validate beyond confirming that the three above are the versions these
paths already run on.

### Blueprint References

`docs/ORIGINS.md:64` — token budget awareness ("Step 9a"), the origin of the token-tracking half of
this story. It is a prose label, not a capability ID, which is why the roadmap's
`✅ Step 9a: Token Tracking` line is the one US-16 MVS entry no gate can resolve.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | The journey, in tokens | `sw implement` → `sw usage` | A real `sw implement` run with an active project set, driven by a doubled provider adapter, SHALL persist its LLM usage; a subsequent `sw usage` SHALL display that run's token counts, attributed to that project and to no other | The larger half of *"see exactly how much each agent is spending"*, proven by one test crossing the whole seam rather than two meeting at a hand-seeded row |
| FR-4 | The journey, in money | `sw costs set` → `sw implement` → `sw usage` | The USD figure `sw usage` displays SHALL be priced from a rate the user set with `sw costs set`. **Split out of FR-1 on 2026-08-16**: no command passes `cost_overrides` into `create_llm_adapter`, so a configured rate is echoed back by `sw costs` and then ignored | The money half is a separate claim because it is separately broken. Keeping it inside FR-1 would have held a working journey hostage to a pricing bug |
| FR-2 | The refusal names its own cause | `sw implement` | When no active project is set, SHALL fail with a message naming the condition and the remedy (`sw use <name>`) instead of `LLM configuration failed: Project 'None' not found`. Exit code stays 1 | A user who forgot `sw use` is told so, rather than being shown a database lookup that failed on the string `None`. **Amended 2026-08-16 — see AD-5** |
| FR-3 | The collector actually reaches the runner | `sw implement` | With an active project set, the adapter that **the `implement` command itself constructs** SHALL be a `TelemetryCollector` on `RunContext.model.llm`, so `PipelineRunner._flush_telemetry` drains it rather than returning early. The test SHALL drive that construction, never build a `RunContext` by hand | The `isinstance` guard in `flush_telemetry` is satisfied by construction, and the silent-no-op path has a test that fails when it regresses |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1, FR-4 | per-call token/cost rows, grouped for display | `C-FLOW-01` · `LlmRepository.get_usage_summary(project: str \| None = None, since: datetime \| None = None) -> list[dict[str, Any]]` | read `infrastructure/llm/store.py:215-219` |
| FR-1, FR-4 | the flush that writes them at run end | flow engine · `flush_telemetry(context: RunContext, logger: Logger) -> None`, called from `PipelineRunner._flush_telemetry` in a `finally` | read `core/flow/engine/telemetry.py:20-35`, `core/flow/engine/runner.py:300-314` |
| FR-1, FR-4 | a doubled provider that leaves the real factory intact | `infrastructure/llm` · `factory._get_adapter_class` | read `tests/e2e/capabilities/infrastructure/test_telemetry_e2e.py:172` |
| FR-2 | whether an active project exists | config repo · `get_active_project()` via `_core.run_repo_op` | read `workflows/implementation/interfaces/cli.py:216` |
| FR-3 | the condition under which the collector is installed | `infrastructure/llm` · `create_llm_adapter(settings, *, telemetry_project: str \| None = None, cost_overrides=None)`, which wraps only `if telemetry_project:` | read `infrastructure/llm/factory.py:39-44,84-92` |

Every row converges: the surface provides what the FR needs, so no provider requires a new FR and
the A.1d cross-story gate does not fire. All three FRs cross a module boundary, so **none of them
is a unit-tier claim** — FR-1 is e2e, FR-2 and FR-3 are integration.

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Telemetry never breaks the run | A flush failure SHALL be logged and swallowed, never propagated. Carried from the surface: `TelemetryCollector.flush` documents *"Never raises — telemetry failures are logged, not propagated"* (`collector.py:159-167`) |
| NFR-2 | The proof makes no live API call | The e2e SHALL double the provider at `factory._get_adapter_class`, **not** at `create_llm_adapter`, so the real telemetry branch under test still executes. **[proof: meta — rule about tests, docs or the diff]** |
| NFR-3 | Backward compatible | No schema change, no new CLI flag, no change to `sw implement`'s exit codes — a run with no active project still exits 1, with a better message. Every existing invocation is unaffected |
| NFR-4 | The warning is legible on a wrapped terminal | The FR-2 assertion SHALL go through `tests/rendering.py::shows()`, since Rich soft-wraps at `COLUMNS` and a raw `in` check passes or fails on terminal width (`TECH-017`, twice, in cited proofs) |
| NFR-5 | FR-1/FR-4 cannot pass on an empty table | `sw usage` prints *"No usage data recorded"* and **exits 0**, so asserting the exit code proves nothing. The e2e SHALL assert the scripted model name, a token count matching the scripted payload, and a non-zero USD figure, against an isolated `tmp_path` DB so no other test's rows can satisfy it |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| typer | 0.21 | `CliRunner.invoke` | Yes | already used by every CLI test in the repo |
| sqlalchemy[asyncio] | 2.0.0 | async session + `select` | Yes | unchanged; no new query is written |
| aiosqlite | 0.20.0 | async SQLite driver | Yes | unchanged |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Warn and continue when no active project, rather than refusing to run | Refusing would break every current no-project invocation, and `sw implement --project <path>` works today without `sw use`. Deriving a fallback key from the path would silently create a second telemetry identity for one project. Chosen by the user, 2026-08-16 | No |
| AD-2 | The FR-1 e2e doubles the provider at `factory._get_adapter_class`, never at `create_llm_adapter` | **`tests/scripted_llm.py::scripted_world` cannot be used here.** It patches `create_llm_adapter` to return a bare `ScriptedLLM` (`scripted_llm.py:80-97`), so `context.model.llm` would not be a `TelemetryCollector`, `flush_telemetry` would return early, and the test would pass while proving nothing. Patching the factory would also skip the exact `if telemetry_project:` branch FR-3 is about | No |
| AD-3 | One surface end to end, not six | Five of the six CLI surfaces exercise the identical collector → flush → `get_usage_summary` path; repeating the journey on each re-proves one seam and buys coverage of no new code. Chosen by the user, 2026-08-16 | No |
| AD-4 | The contract carries the FR-2 fix rather than deferring it to a separate ticket | `ADR-003` sequencing: the journey test is written first and must be able to go green inside its own boundary. Splitting the fix into another ticket would leave a planned red at commit, which is the shape `check_proof_tier.py` exists to catch. **Confirmed by the user 2026-08-16**, against the alternative of a separate TECH ticket | No |
| AD-5 | **Amended 2026-08-16: FR-2 is a message fix, not a silent-spend fix.** The original read *"a run without an active project proceeds and records nothing, silently"* | That was reasoned from `cli.py:216-219` (`telemetry_project=None` skips the collector wrap) and from the `# type: ignore[arg-type]` beside it — never run. Run, the command **refuses**: `load_settings(db, None)` raises first (`settings_loader.py:179`), so `create_llm_adapter` is never reached, no adapter is built, and `PipelineRunner` is never constructed. There is no untracked spend from this command — only a cryptic message. Pinned by `TestImplementInstallsTelemetryCollector::test_no_active_project_stops_the_command_before_any_adapter_is_built`. It remains true that **no telemetry opt-out setting exists anywhere** in `src/`, which is why the message should name the remedy rather than imply a toggle | No |
| AD-6 | FR-1 prices the run via `sw costs set` inside the test | `estimated_cost` for an unknown model is `0.0`, so a "cost > 0" assertion would fail for the wrong reason. Setting a rate first makes the figure deterministic **and** pulls `sw costs` into the journey — which is the other half of the US-16 benefit, *"how much money"*. `test_costs_e2e_happy_path` already proves `sw costs set` persists | No |

## ROI Analysis

### Investment Cost

| Item | Effort | Risk |
|------|--------|------|
| FR-2 warning + guard in the implement CLI | ~10 lines, one module | Low — additive, no behaviour removed |
| FR-1 journey e2e (real command → real DB → `sw usage`) | One test, using an established patch point | Medium — the run must reach an LLM call with a doubled provider and a real DB |
| FR-3 integration test on the collector reaching `RunContext` | One test | Low |

### Returns

| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| US-16 as an epic | Its base contract stops being `[Pending definition...]`, and the story can close | High — it is one of three reserve epic-closers in the routing queue |
| Anyone running `sw implement` without `sw use` | Told what to do, instead of being shown a lookup that failed on the string `None` | Medium — downgraded 2026-08-16 with `AD-5`; the untracked-spend scenario it was rated for does not exist |
| The four unbuilt US-16 add-ons | Inherit a proven seam to build on rather than a presumed one | Medium |
| `sw run` / `sw review` / drift | Not covered by FR-1, but the defect class is now named and testable for them | Low |

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| The e2e turns out to need a live API key | Low | High | AD-2's patch point is already proven by `test_telemetry_e2e.py:172`; the e2e is written first, so this surfaces at the red, not at the end |
| The journey needs more of the implement loop than can run in a test (spec file, project init, DB) | Medium | Medium | `test_cli_decentralized_e2e.py` already does `init` → `use` → command in one `CliRunner` session; reuse that shape |
| FR-2's warning becomes noise for users who never want telemetry | Low | Low | It fires only when no active project is set, which is already the unusual case |

### Refactoring Opportunities

| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `test_usage_e2e_happy_path` | Hand-writes a `llm_usage_log` row with ten literal column names, so schema drift cannot fail it | Once FR-1 exists, this test's seeded INSERT is no longer the only join between writer and reader; it can stay as a pure read-path test or be narrowed | Low |
| `sw run`, `sw resume`, `sw review`, drift | Same `get_active_project()` → `telemetry_project` shape, same silent no-op | FR-2's guard is a candidate to lift into one shared helper once a second surface needs it. **Not done here** — one caller is not a pattern | Low, later |
| Roadmap `✅ Step 9a: Token Tracking` | A legacy prose label with no capability ID, so no gate can resolve or verify it | Out of scope for this contract; recorded here so it is not lost | — |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| — | This contract introduces no new sub-system, paradigm or extension layer. It proves an existing seam and adds one warning | N/A |

## Sub-Feature Breakdown

**Single feature — no decomposition.** Phase 4 assessed: 3 FRs (≤ 5), one source module touched
(≤ 3), no external integration, one capability area. None of the decomposition triggers fires.

## Execution Order

Single feature — no decomposition. Two commit boundaries inside one implementation plan, ordered so
the journey test is written before the code that makes it pass (`ADR-003`):

1. **CB-1** — FR-1's e2e and FR-3's integration test, written red. FR-1 fails because a
   no-active-project run records nothing; FR-3 fails on the `isinstance` guard.
2. **CB-2** — FR-2's warning and guard, turning both green.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| — | Single feature | — | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design APPROVED 2026-08-16. The one open question (AD-4 — whether FR-2's
warning belongs here or in its own TECH ticket) was decided by the user: **it stays here**.
**Next step**: `specweaver-dev` on CB-1 of
`INT-US-16_implementation_plan.md` (APPROVED 2026-08-16). Its Execution Order **supersedes**
this document's — the journey e2e is falsified by mutant, not by a red.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ and resume from
there with the matching skill.
